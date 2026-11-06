"""
Command Processor for PS-113 Command-File Driven Engine
Executes commands, loads CSV datasets, updates engine state, and produces reports.
"""
import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from engine.models import (
    AddOnRateCard,
    ConcessionCategory,
    FeeHead,
    GradeFeeStructure,
    HostelSubscription,
    Instalment,
    InstalmentPlanType,
    PaymentMode,
    PaymentRecord,
    Student,
    Transaction,
    TransactionType,
    TransportSubscription,
    quantize_amount,
)
from engine.fee_calculator import FeeCalculator, ComputedAnnualFee
from engine.instalment_scheduler import InstalmentScheduler
from engine.addon_manager import AddOnManager
from engine.late_fee import LateFeeCalculator, DefaulterRecord
from engine.payment_waterfall import PaymentWaterfallProcessor
from engine.admission_manager import AdmissionManager
from engine.withdrawal_manager import WithdrawalManager
from engine.fee_revision import FeeRevisionManager
from engine.scholarship_manager import ScholarshipManager
from engine.reports import ReportGenerator


def parse_date(date_str: str) -> date:
    """Parses date string in YYYY-MM-DD format."""
    return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()


class SchoolFeeEngine:
    """Core School Fee Management Engine state and orchestrator."""

    def __init__(self):
        self.fee_structures: Dict[int, GradeFeeStructure] = {}
        self.rate_card: AddOnRateCard = AddOnRateCard()
        self.students: Dict[str, Student] = {}
        self.computed_annual_fees: Dict[str, ComputedAnnualFee] = {}
        self.schedules: Dict[str, List[Instalment]] = {}
        self.transport_subs: Dict[str, TransportSubscription] = {}
        self.hostel_subs: Dict[str, HostelSubscription] = {}
        self.payments: Dict[str, PaymentRecord] = {}
        self.transactions: Dict[str, List[Transaction]] = {}
        self.campus_receipt_counters: Dict[str, int] = {}
        self.scholarship_manager: Optional[ScholarshipManager] = None

    def _next_receipt_number(self, campus: str) -> str:
        count = self.campus_receipt_counters.get(campus, 0) + 1
        self.campus_receipt_counters[campus] = count
        return f"RCP-{campus}-{count:05d}"

    def load_fee_structure(
        self,
        grade: int,
        tuition: Decimal,
        development: Decimal,
        lab: Decimal,
        activity: Decimal,
        exam: Decimal,
    ) -> GradeFeeStructure:
        heads = {
            FeeHead.TUITION: quantize_amount(tuition),
            FeeHead.DEVELOPMENT: quantize_amount(development),
            FeeHead.LAB: quantize_amount(lab),
            FeeHead.ACTIVITY: quantize_amount(activity),
            FeeHead.EXAM: quantize_amount(exam),
        }
        struct = GradeFeeStructure(grade=grade, heads=heads)
        self.fee_structures[grade] = struct
        return struct

    def enrol_student(
        self,
        student_id: str,
        name: str,
        grade: int,
        section: str,
        dob: date,
        admission_date: date,
        plan: InstalmentPlanType = InstalmentPlanType.TERM,
        category: ConcessionCategory = ConcessionCategory.NONE,
        previous_year_percentage: float = 0.0,
        sibling_group_id: Optional[str] = None,
        campus: str = "CAMPUS-1",
    ) -> Tuple[ComputedAnnualFee, List[Instalment]]:
        student = Student(
            student_id=student_id,
            name=name,
            grade=grade,
            section=section,
            dob=dob,
            admission_date=admission_date,
            plan=plan,
            concession_category=category,
            previous_year_percentage=previous_year_percentage,
            sibling_group_id=sibling_group_id if sibling_group_id else None,
            campus=campus,
        )
        self.students[student_id] = student
        self.transactions[student_id] = []

        fee_structure = self.fee_structures.get(grade)
        if not fee_structure:
            raise ValueError(f"Fee structure for grade {grade} not loaded.")

        all_students = list(self.students.values())
        annual_fee, schedule = AdmissionManager.enrol_student(student, fee_structure, all_students)

        self.computed_annual_fees[student_id] = annual_fee
        self.schedules[student_id] = schedule

        # Record debit transactions for initial fee heads
        for inst in schedule:
            for head, h_due in inst.heads.items():
                if h_due.net_amount > Decimal("0.00"):
                    self.transactions[student_id].append(Transaction(
                        txn_id=f"INIT-{student_id}-INST{inst.instalment_number}-{head.value}",
                        student_id=student_id,
                        txn_date=inst.due_date,
                        txn_type=TransactionType.CHARGE_FEE,
                        amount=h_due.net_amount,
                        head=head,
                        instalment_number=inst.instalment_number,
                        description=f"Fee charge: {head.value.title()} (Instalment {inst.instalment_number})",
                    ))

        return annual_fee, schedule

    def change_plan(self, student_id: str, new_plan: InstalmentPlanType, request_date: date) -> bool:
        student = self.students.get(student_id)
        if not student:
            raise ValueError(f"Student {student_id} not found.")

        schedule = self.schedules.get(student_id, [])
        if not InstalmentScheduler.can_change_plan(student, schedule, request_date):
            raise ValueError(
                f"REJECTED: Instalment plan for student {student_id} cannot be changed after first due date (Request: {request_date})."
            )

        student.plan = new_plan
        fee_structure = self.fee_structures[student.grade]
        all_students = list(self.students.values())
        annual_fee = FeeCalculator.compute_annual_fee(student, fee_structure, all_students)
        new_schedule = InstalmentScheduler.generate_schedule(student, annual_fee)

        # Re-apply add-ons if any
        AddOnManager.apply_addons_to_schedule(
            schedule=new_schedule,
            plan=student.plan,
            rate_card=self.rate_card,
            transport_sub=self.transport_subs.get(student_id),
            hostel_sub=self.hostel_subs.get(student_id),
        )

        self.computed_annual_fees[student_id] = annual_fee
        self.schedules[student_id] = new_schedule
        return True

    def add_transport(self, student_id: str, zone: str, start_date: date) -> TransportSubscription:
        student = self.students.get(student_id)
        if not student:
            raise ValueError(f"Student {student_id} not found.")

        sub = TransportSubscription(student_id=student_id, zone=zone, start_date=start_date, active=True)
        self.transport_subs[student_id] = sub

        # Update schedule with transport charges
        schedule = self.schedules.get(student_id, [])
        AddOnManager.apply_addons_to_schedule(
            schedule=schedule,
            plan=student.plan,
            rate_card=self.rate_card,
            transport_sub=sub,
            hostel_sub=self.hostel_subs.get(student_id),
        )
        return sub

    def remove_transport(self, student_id: str, end_date: date) -> Optional[TransportSubscription]:
        sub = self.transport_subs.get(student_id)
        if not sub:
            return None

        sub.end_date = end_date
        sub.active = False

        student = self.students[student_id]
        schedule = self.schedules.get(student_id, [])
        AddOnManager.apply_addons_to_schedule(
            schedule=schedule,
            plan=student.plan,
            rate_card=self.rate_card,
            transport_sub=sub,
            hostel_sub=self.hostel_subs.get(student_id),
        )
        return sub

    def add_hostel(self, student_id: str, room_type: str, start_date: date) -> HostelSubscription:
        student = self.students.get(student_id)
        if not student:
            raise ValueError(f"Student {student_id} not found.")

        sub = HostelSubscription(student_id=student_id, room_type=room_type, start_date=start_date, active=True)
        self.hostel_subs[student_id] = sub

        schedule = self.schedules.get(student_id, [])
        AddOnManager.apply_addons_to_schedule(
            schedule=schedule,
            plan=student.plan,
            rate_card=self.rate_card,
            transport_sub=self.transport_subs.get(student_id),
            hostel_sub=sub,
        )
        return sub

    def record_payment(
        self,
        payment_id: str,
        student_id: str,
        amount: Decimal,
        payment_date: date,
        payment_mode: PaymentMode,
        reference: str = "",
    ) -> PaymentRecord:
        student = self.students.get(student_id)
        if not student:
            raise ValueError(f"Student {student_id} not found.")

        schedule = self.schedules.get(student_id, [])
        receipt_num = self._next_receipt_number(student.campus)

        record, txns = PaymentWaterfallProcessor.apply_payment(
            student=student,
            schedule=schedule,
            payment_id=payment_id,
            payment_date=payment_date,
            amount=amount,
            payment_mode=payment_mode,
            reference=reference,
            receipt_number=receipt_num,
        )

        self.payments[payment_id] = record
        if student_id not in self.transactions:
            self.transactions[student_id] = []
        self.transactions[student_id].extend(txns)

        # Check if hostel deposit was paid
        hostel_sub = self.hostel_subs.get(student_id)
        if hostel_sub:
            deposit_alloc = any(a.head == FeeHead.HOSTEL_DEPOSIT for a in record.allocations)
            if deposit_alloc:
                hostel_sub.deposit_paid = True

        return record

    def bounce_payment(self, payment_id: str, bounce_date: date) -> List[Transaction]:
        record = self.payments.get(payment_id)
        if not record:
            raise ValueError(f"Payment {payment_id} not found.")

        student = self.students[record.student_id]
        schedule = self.schedules.get(record.student_id, [])
        all_payments = [p for p in self.payments.values() if p.student_id == student.student_id]

        txns = PaymentWaterfallProcessor.process_cheque_bounce(
            student=student,
            schedule=schedule,
            payment_record=record,
            bounce_date=bounce_date,
            all_payments_for_student=all_payments,
        )

        self.transactions[student.student_id].extend(txns)
        return txns

    def withdraw_student(
        self,
        student_id: str,
        withdrawal_date: date,
        notice_date: date,
        hostel_damages: Decimal = Decimal("0.00"),
    ) -> Tuple[Decimal, Decimal, List[str]]:
        student = self.students.get(student_id)
        if not student:
            raise ValueError(f"Student {student_id} not found.")

        schedule = self.schedules.get(student_id, [])
        hostel_sub = self.hostel_subs.get(student_id)

        t_refund, d_refund, txns = WithdrawalManager.process_withdrawal(
            student=student,
            schedule=schedule,
            withdrawal_date=withdrawal_date,
            notice_date=notice_date,
            hostel_sub=hostel_sub,
            hostel_damages=hostel_damages,
        )

        self.transactions[student_id].extend(txns)

        # Trigger sibling re-ranking from next instalment
        recomputed = WithdrawalManager.re_rank_siblings_after_withdrawal(
            withdrawn_student=student,
            sibling_students=list(self.students.values()),
            fee_structures=self.fee_structures,
            all_schedules=self.schedules,
            effective_from_term=2,
        )

        return t_refund, d_refund, recomputed

    def revise_fee(
        self,
        grade: int,
        head: FeeHead,
        revision_percent: Decimal,
        effective_date: date,
        board_approved: bool = False,
    ) -> Tuple[bool, str]:
        fee_struct = self.fee_structures.get(grade)
        if not fee_struct:
            raise ValueError(f"Grade {grade} fee structure not found.")

        student_grades = {s.student_id: s.grade for s in self.students.values()}

        success, msg, _ = FeeRevisionManager.apply_fee_revision(
            grade=grade,
            head=head,
            revision_percent=revision_percent,
            effective_date=effective_date,
            board_approved=board_approved,
            fee_structure=fee_struct,
            all_student_schedules=self.schedules,
            student_grades=student_grades,
        )
        return success, msg

    def allocate_scholarship_fund(self, total_fund: Decimal) -> int:
        self.scholarship_manager = ScholarshipManager(total_fund)
        awards = self.scholarship_manager.allocate_scholarships(
            students=list(self.students.values()),
            all_schedules=self.schedules,
        )
        return len(awards)

    def get_defaulters(self, as_of_date: date) -> List[DefaulterRecord]:
        defaulters: List[DefaulterRecord] = []
        for s in self.students.values():
            if s.status.value != "ACTIVE":
                continue
            schedule = self.schedules.get(s.student_id, [])
            record = LateFeeCalculator.check_defaulter_status(s, schedule, as_of_date)
            if record:
                defaulters.append(record)
        return defaulters


class CommandProcessor:
    """Executes commands line by line or from command files."""

    def __init__(self, engine: Optional[SchoolFeeEngine] = None):
        self.engine = engine or SchoolFeeEngine()

    def process_file(self, filepath: str | Path) -> List[str]:
        output_logs: List[str] = []
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Command file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    res = self.process_command(line)
                    if res:
                        output_logs.append(res)
                except Exception as e:
                    err = f"[Line {line_no} ERROR] {line} -> {str(e)}"
                    output_logs.append(err)

        return output_logs

    def process_command(self, cmd_line: str) -> Optional[str]:
        parts = cmd_line.strip().split()
        if not parts:
            return None

        verb = parts[0].upper()

        if verb == "LOAD_FEE_STRUCTURE":
            # LOAD_FEE_STRUCTURE <grade> <tuition> <dev> <lab> <activity> <exam>
            grade = int(parts[1])
            tuition = Decimal(parts[2])
            dev = Decimal(parts[3])
            lab = Decimal(parts[4])
            act = Decimal(parts[5])
            exam = Decimal(parts[6])
            self.engine.load_fee_structure(grade, tuition, dev, lab, act, exam)
            return f"LOADED: Fee structure for Grade {grade}"

        elif verb == "LOAD_FEE_FILE":
            # LOAD_FEE_FILE <path_to_csv>
            csv_path = Path(parts[1])
            count = 0
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.engine.load_fee_structure(
                        grade=int(row["grade"]),
                        tuition=Decimal(row["tuition"]),
                        development=Decimal(row["development"]),
                        lab=Decimal(row["lab"]),
                        activity=Decimal(row["activity"]),
                        exam=Decimal(row["exam"]),
                    )
                    count += 1
            return f"LOADED: {count} grade fee structures from {csv_path.name}"

        elif verb == "ENROL_STUDENT":
            # ENROL_STUDENT <id> <name> <grade> <sec> <dob> <adm_date> <plan> [category] [prev_pct] [sibling_grp] [campus]
            s_id = parts[1]
            s_name = parts[2]
            grade = int(parts[3])
            section = parts[4]
            dob = parse_date(parts[5])
            adm_date = parse_date(parts[6])
            plan = InstalmentPlanType(parts[7].upper())
            cat = ConcessionCategory(parts[8].upper()) if len(parts) > 8 else ConcessionCategory.NONE
            prev_pct = float(parts[9]) if len(parts) > 9 else 0.0
            sibling_grp = parts[10] if len(parts) > 10 and parts[10] != "-" else None
            campus = parts[11] if len(parts) > 11 else "CAMPUS-1"

            self.engine.enrol_student(
                student_id=s_id,
                name=s_name,
                grade=grade,
                section=section,
                dob=dob,
                admission_date=adm_date,
                plan=plan,
                category=cat,
                previous_year_percentage=prev_pct,
                sibling_group_id=sibling_grp,
                campus=campus,
            )
            return f"ENROLLED: Student {s_name} ({s_id}) in Grade {grade}-{section} Plan: {plan.value}"

        elif verb == "LOAD_STUDENTS_FILE":
            csv_path = Path(parts[1])
            count = 0
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cat = ConcessionCategory(row.get("category", "NONE").upper())
                    sibling_grp = row.get("sibling_group_id")
                    if sibling_grp in ["", "-", "None"]:
                        sibling_grp = None

                    self.engine.enrol_student(
                        student_id=row["student_id"],
                        name=row["name"],
                        grade=int(row["grade"]),
                        section=row.get("section", "A"),
                        dob=parse_date(row["dob"]),
                        admission_date=parse_date(row["admission_date"]),
                        plan=InstalmentPlanType(row.get("plan", "TERM").upper()),
                        category=cat,
                        previous_year_percentage=float(row.get("previous_year_percentage", 0.0) or 0.0),
                        sibling_group_id=sibling_grp,
                        campus=row.get("campus", "CAMPUS-1"),
                    )
                    count += 1
            return f"LOADED: {count} students from {csv_path.name}"

        elif verb == "CHANGE_PLAN":
            # CHANGE_PLAN <student_id> <new_plan> <request_date>
            s_id = parts[1]
            new_p = InstalmentPlanType(parts[2].upper())
            req_d = parse_date(parts[3])
            self.engine.change_plan(s_id, new_p, req_d)
            return f"PLAN CHANGED: Student {s_id} changed to {new_p.value} on {req_d}"

        elif verb == "ADD_TRANSPORT":
            # ADD_TRANSPORT <student_id> <zone> <start_date>
            # Handle zone with space like "Zone A"
            s_id = parts[1]
            if parts[2] == "Zone" and len(parts) >= 5:
                zone = f"{parts[2]} {parts[3]}"
                s_date = parse_date(parts[4])
            else:
                zone = parts[2]
                s_date = parse_date(parts[3])
            self.engine.add_transport(s_id, zone, s_date)
            return f"TRANSPORT ADDED: Student {s_id} enrolled in {zone} from {s_date}"

        elif verb == "REMOVE_TRANSPORT":
            s_id = parts[1]
            e_date = parse_date(parts[2])
            self.engine.remove_transport(s_id, e_date)
            return f"TRANSPORT REMOVED: Student {s_id} stopped transport effective {e_date}"

        elif verb == "ADD_HOSTEL":
            # ADD_HOSTEL <student_id> <room_type> <start_date>
            s_id = parts[1]
            room = parts[2].lower()
            s_date = parse_date(parts[3])
            self.engine.add_hostel(s_id, room, s_date)
            return f"HOSTEL ADDED: Student {s_id} allocated {room} room from {s_date}"

        elif verb == "RECORD_PAYMENT":
            # RECORD_PAYMENT <payment_id> <student_id> <amount> <payment_date> <mode> [ref]
            p_id = parts[1]
            s_id = parts[2]
            amt = Decimal(parts[3])
            p_date = parse_date(parts[4])
            mode = PaymentMode(parts[5].upper())
            ref = parts[6] if len(parts) > 6 else ""
            rec = self.engine.record_payment(p_id, s_id, amt, p_date, mode, ref)
            return f"PAYMENT RECORDED: {p_id} for Rs {amt} on {p_date} (Receipt: {rec.receipt_number})"

        elif verb == "LOAD_PAYMENTS_FILE":
            csv_path = Path(parts[1])
            count = 0
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.engine.record_payment(
                        payment_id=row["payment_id"],
                        student_id=row["student_id"],
                        amount=Decimal(row["amount"]),
                        payment_date=parse_date(row["payment_date"]),
                        payment_mode=PaymentMode(row.get("payment_mode", "UPI").upper()),
                        reference=row.get("reference", ""),
                    )
                    count += 1
            return f"LOADED: {count} payments from {csv_path.name}"

        elif verb == "BOUNCE_PAYMENT":
            # BOUNCE_PAYMENT <payment_id> <bounce_date>
            p_id = parts[1]
            b_date = parse_date(parts[2])
            self.engine.bounce_payment(p_id, b_date)
            return f"PAYMENT BOUNCED: {p_id} bounced on {b_date}. Rs 500 charge applied & reversed."

        elif verb == "WITHDRAW_STUDENT":
            # WITHDRAW_STUDENT <student_id> <withdrawal_date> <notice_date> [damages]
            s_id = parts[1]
            w_date = parse_date(parts[2])
            n_date = parse_date(parts[3])
            damages = Decimal(parts[4]) if len(parts) > 4 else Decimal("0.00")
            t_ref, d_ref, recomputed = self.engine.withdraw_student(s_id, w_date, n_date, damages)
            msg = f"WITHDRAWN: Student {s_id} on {w_date}. Tuition refunded: Rs {t_ref}, Deposit refunded: Rs {d_ref}."
            if recomputed:
                msg += f" Sibling re-rank: {', '.join(recomputed)}"
            return msg

        elif verb == "REVISE_FEE":
            # REVISE_FEE <grade> <head> <percent> <effective_date> [board_approved]
            grade = int(parts[1])
            head = FeeHead(parts[2].lower())
            pct = Decimal(parts[3])
            eff_date = parse_date(parts[4])
            board = (parts[5].upper() == "TRUE") if len(parts) > 5 else False
            _, msg = self.engine.revise_fee(grade, head, pct, eff_date, board)
            return msg

        elif verb == "ALLOCATE_SCHOLARSHIP":
            fund = Decimal(parts[1])
            cnt = self.engine.allocate_scholarship_fund(fund)
            return f"SCHOLARSHIP: Allocated fund Rs {fund} across {cnt} merit students."

        elif verb == "PRINT_DEMAND":
            s_id = parts[1]
            as_of = parse_date(parts[2]) if len(parts) > 2 else date(2026, 4, 10)
            st = self.engine.students.get(s_id)
            sched = self.engine.schedules.get(s_id, [])
            if not st:
                return f"Student {s_id} not found."
            return ReportGenerator.print_fee_demand(st, sched, as_of)

        elif verb == "PRINT_SCHEDULE":
            s_id = parts[1]
            st = self.engine.students.get(s_id)
            sched = self.engine.schedules.get(s_id, [])
            if not st:
                return f"Student {s_id} not found."
            return ReportGenerator.print_instalment_schedule(st, sched)

        elif verb == "PRINT_LEDGER":
            s_id = parts[1]
            as_of = parse_date(parts[2]) if len(parts) > 2 else None
            st = self.engine.students.get(s_id)
            txns = self.engine.transactions.get(s_id, [])
            if not st:
                return f"Student {s_id} not found."
            return ReportGenerator.print_student_ledger(st, txns, as_of)

        elif verb == "PRINT_DEFAULTERS":
            as_of = parse_date(parts[1])
            defaulters = self.engine.get_defaulters(as_of)
            return ReportGenerator.print_defaulters_list(defaulters, as_of)

        else:
            return f"UNKNOWN COMMAND: {verb}"
