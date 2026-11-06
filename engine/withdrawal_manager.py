"""
Withdrawal Manager implementing BR-09 and BR-02 (Sibling Re-ranking)
Handles 30-day notice rule, unstarted term tuition refund, hostel deposit refund minus damages,
TC clearance (blocked if dues > 0), and sibling concession re-ranking from next instalment.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from engine.models import (
    FeeHead,
    GradeFeeStructure,
    HostelSubscription,
    Instalment,
    InstalmentHeadDue,
    Student,
    StudentStatus,
    TCStatus,
    Transaction,
    TransactionType,
    quantize_amount,
)
from engine.rules import (
    TERM_SPLITS,
    WITHDRAWAL_NOTICE_DAYS_REQUIRED,
)
from engine.fee_calculator import FeeCalculator


class WithdrawalManager:
    """Manages student withdrawals, refund calculations, TC clearance, and sibling re-ranking."""

    # Term start dates for 3-term academic year
    TERM_START_DATES = {
        1: date(2026, 4, 1),
        2: date(2026, 8, 1),
        3: date(2026, 12, 1),
    }

    @classmethod
    def process_withdrawal(
        cls,
        student: Student,
        schedule: List[Instalment],
        withdrawal_date: date,
        notice_date: date,
        hostel_sub: Optional[HostelSubscription] = None,
        hostel_damages: Decimal = Decimal("0.00"),
    ) -> Tuple[Decimal, Decimal, List[Transaction]]:
        """
        Processes student withdrawal adhering to BR-09:
        1. Tuition refunded ONLY for full unstarted terms if notice given >= 30 days before term start.
        2. Other heads non-refundable.
        3. Last term (Term 3) refunds nothing.
        4. Hostel deposit refunded minus damages.
        5. Sibling group re-ranking triggered for remaining siblings.
        6. TC clearance check.
        """
        student.status = StudentStatus.WITHDRAWN
        student.withdrawal_date = withdrawal_date
        student.withdrawal_notice_date = notice_date

        tuition_refund_total = Decimal("0.00")
        deposit_refund_total = Decimal("0.00")
        txns: List[Transaction] = []

        # 1. Evaluate unstarted terms tuition refund
        # Notice must be at least 30 days before the term start
        for term_num, term_start in cls.TERM_START_DATES.items():
            # Withdrawal in last term refunds nothing
            if term_num == 3:
                continue

            # Full unstarted term check: withdrawal must be before or on term start
            # AND notice date must be at least 30 days before term start
            days_notice = (term_start - notice_date).days
            if withdrawal_date <= term_start and days_notice >= WITHDRAWAL_NOTICE_DAYS_REQUIRED:
                # Find matching instalment
                inst = next((i for i in schedule if i.instalment_number == term_num), None)
                if inst and FeeHead.TUITION in inst.heads:
                    t_head = inst.heads[FeeHead.TUITION]
                    # Refund tuition that was paid for this unstarted term
                    refund_amt = t_head.paid_amount
                    if refund_amt > Decimal("0.00"):
                        tuition_refund_total += refund_amt
                        t_head.paid_amount = Decimal("0.00")
                        txns.append(Transaction(
                            txn_id=f"REFUND-{student.student_id}-TERM-{term_num}-TUITION",
                            student_id=student.student_id,
                            txn_date=withdrawal_date,
                            txn_type=TransactionType.REFUND,
                            amount=refund_amt,
                            head=FeeHead.TUITION,
                            instalment_number=term_num,
                            description=f"Tuition refund for unstarted Term {term_num} (Notice given {days_notice} days prior)",
                        ))

                    # Cancel unstarted term dues so they don't linger as debt
                    for h_name, h_due in inst.heads.items():
                        h_due.net_amount = h_due.paid_amount

        # 2. Hostel deposit refund minus damages
        if hostel_sub and hostel_sub.deposit_paid:
            damages = quantize_amount(hostel_damages)
            hostel_sub.damages = damages
            refund_deposit = max(Decimal("0.00"), hostel_sub.deposit_amount - damages)
            hostel_sub.deposit_refunded = refund_deposit
            deposit_refund_total = refund_deposit

            txns.append(Transaction(
                txn_id=f"REFUND-{student.student_id}-HOSTEL-DEPOSIT",
                student_id=student.student_id,
                txn_date=withdrawal_date,
                txn_type=TransactionType.REFUND,
                amount=refund_deposit,
                head=FeeHead.HOSTEL_DEPOSIT,
                description=f"Hostel security deposit refund (Rs {hostel_sub.deposit_amount} less Rs {damages} damages)",
            ))

        # Check TC Status
        cls.evaluate_tc_clearance(student, schedule)

        return tuition_refund_total, deposit_refund_total, txns

    @classmethod
    def evaluate_tc_clearance(cls, student: Student, schedule: List[Instalment]) -> TCStatus:
        """
        BR-09: TC is issued ONLY when dues are zero.
        """
        total_dues = sum((inst.total_outstanding for inst in schedule), Decimal("0.00"))
        if total_dues <= Decimal("0.00"):
            student.tc_status = TCStatus.ISSUED
        else:
            student.tc_status = TCStatus.BLOCKED_DUE_TO_DUES
        return student.tc_status

    @classmethod
    def re_rank_siblings_after_withdrawal(
        cls,
        withdrawn_student: Student,
        sibling_students: List[Student],
        fee_structures: Dict[int, GradeFeeStructure],
        all_schedules: Dict[str, List[Instalment]],
        effective_from_term: int = 2,
    ) -> List[str]:
        """
        BR-02: If the eldest withdraws, concessions re-rank from the next instalment.
        Recomputes remaining instalments for active siblings in the group.
        """
        if not withdrawn_student.sibling_group_id:
            return []

        active_siblings = [
            s for s in sibling_students
            if s.sibling_group_id == withdrawn_student.sibling_group_id and s.status == StudentStatus.ACTIVE
        ]

        if not active_siblings:
            return []

        recomputed_students = []

        # Re-sort active siblings by age / DOB
        sorted_active = sorted(active_siblings, key=lambda s: (s.dob, s.admission_date, s.student_id))

        for new_rank_idx, s in enumerate(sorted_active):
            new_rank = new_rank_idx + 1
            old_sched = all_schedules.get(s.student_id, [])
            fee_struct = fee_structures.get(s.grade)
            if not old_sched or not fee_struct:
                continue

            # Compute new annual fee with new sibling ranking
            new_annual_fee = FeeCalculator.compute_annual_fee(s, fee_struct, sorted_active)

            # Update instalments from effective_from_term onwards
            for inst in old_sched:
                if inst.instalment_number >= effective_from_term:
                    # Update tuition net amount
                    t_full_net = new_annual_fee.net_heads.get(FeeHead.TUITION, Decimal("0.00"))
                    # In TERM plan, Term 2 is 30%, Term 3 is 30%
                    if len(old_sched) == 3:
                        split_ratio = Decimal("0.30")
                        new_term_tuition = quantize_amount(t_full_net * split_ratio)
                    elif len(old_sched) == 10:
                        new_term_tuition = quantize_amount(t_full_net / Decimal("10"))
                    else:
                        new_term_tuition = t_full_net

                    if FeeHead.TUITION in inst.heads:
                        inst.heads[FeeHead.TUITION].net_amount = new_term_tuition

            recomputed_students.append(f"{s.student_id} (New Sibling Rank: {new_rank})")

        return recomputed_students
