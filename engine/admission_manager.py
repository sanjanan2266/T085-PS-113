"""
Mid-Year Admission Manager implementing BR-08
Handles pro-rating (15th cutoff), non-pro-rated development fee, flat Rs 10,000 admission fee,
and remaining instalment generation.
"""
from datetime import date
from decimal import Decimal
from typing import Dict, List, Tuple
from engine.models import (
    FeeHead,
    GradeFeeStructure,
    Instalment,
    InstalmentHeadDue,
    InstalmentPlanType,
    Student,
    quantize_amount,
)
from engine.rules import (
    FLAT_ADMISSION_FEE,
    MID_YEAR_MONTH_CUTOFF_DAY,
    MONTHLY_MONTHS,
    TOTAL_ACADEMIC_MONTHS,
)
from engine.fee_calculator import FeeCalculator, ComputedAnnualFee
from engine.instalment_scheduler import InstalmentScheduler


class AdmissionManager:
    """Processes regular and mid-year admissions adhering strictly to BR-08."""

    @classmethod
    def calculate_remaining_months_count(cls, admission_date: date) -> int:
        """
        BR-08: A month counts if admitted on or before the 15th, else does not.
        Academic months: April (month 4, 2026) through January (month 1, 2027) = 10 months.
        """
        # Academic year check: if admitted before April 2026, counts all 10 months
        if admission_date <= date(2026, 4, 15):
            return TOTAL_ACADEMIC_MONTHS

        # Map academic months in chronological sequence
        academic_sequence = [
            (4, 2026), (5, 2026), (6, 2026), (7, 2026), (8, 2026),
            (9, 2026), (10, 2026), (11, 2026), (12, 2026), (1, 2027),
        ]

        count = 0
        for m, y in academic_sequence:
            if (y, m) < (admission_date.year, admission_date.month):
                continue
            elif (y, m) == (admission_date.year, admission_date.month):
                if admission_date.day <= MID_YEAR_MONTH_CUTOFF_DAY:
                    count += 1
            else:
                count += 1

        return count

    @classmethod
    def enrol_student(
        cls,
        student: Student,
        fee_structure: GradeFeeStructure,
        sibling_group_students: List[Student],
    ) -> Tuple[ComputedAnnualFee, List[Instalment]]:
        """
        Enrols a student. If mid-year admission (after April 15), applies BR-08 pro-rating:
        - Tuition and other heads (lab, activity, exam) pro-rated by remaining months / 10.
        - Development fee is NEVER pro-rated (100%).
        - Flat Rs 10,000 admission fee added.
        - Concessions then applied with precedence (BR-12).
        - Schedule generated.
        """
        is_mid_year = student.admission_date > date(2026, 4, 15)

        if not is_mid_year:
            # Regular admission
            annual_fee = FeeCalculator.compute_annual_fee(student, fee_structure, sibling_group_students)
            schedule = InstalmentScheduler.generate_schedule(student, annual_fee)
            return annual_fee, schedule

        # Mid-year admission
        remaining_months = cls.calculate_remaining_months_count(student.admission_date)
        pro_rate_ratio = Decimal(str(remaining_months)) / Decimal(str(TOTAL_ACADEMIC_MONTHS))

        # Build pro-rated base fee structure
        pro_rated_heads: Dict[FeeHead, Decimal] = {}
        for head in [FeeHead.TUITION, FeeHead.DEVELOPMENT, FeeHead.LAB, FeeHead.ACTIVITY, FeeHead.EXAM]:
            full_amt = fee_structure.get_head(head)
            if head == FeeHead.DEVELOPMENT:
                # BR-08: Development fee is NEVER pro-rated!
                pro_rated_heads[head] = full_amt
            else:
                pro_rated_heads[head] = quantize_amount(full_amt * pro_rate_ratio)

        # Create temporary fee structure
        temp_structure = GradeFeeStructure(grade=student.grade, heads=pro_rated_heads)

        # Compute concessions on pro-rated amounts
        annual_fee = FeeCalculator.compute_annual_fee(student, temp_structure, sibling_group_students)

        # Add flat Rs 10,000 admission fee
        annual_fee.base_heads[FeeHead.ADMISSION] = FLAT_ADMISSION_FEE
        annual_fee.concession_discounts[FeeHead.ADMISSION] = Decimal("0.00")
        annual_fee.plan_discounts[FeeHead.ADMISSION] = Decimal("0.00")
        annual_fee.net_heads[FeeHead.ADMISSION] = FLAT_ADMISSION_FEE

        # Generate schedule for remaining instalments
        schedule = cls._generate_mid_year_schedule(student, annual_fee, remaining_months)
        return annual_fee, schedule

    @classmethod
    def _generate_mid_year_schedule(
        cls,
        student: Student,
        annual_fee: ComputedAnnualFee,
        remaining_months: int,
    ) -> List[Instalment]:
        """Generates future instalments for a mid-year admission."""
        if student.plan == InstalmentPlanType.ANNUAL:
            # Single instalment due immediately on admission date (or 10th of next month)
            due_date = student.admission_date
            inst = Instalment(
                instalment_id=f"{student.student_id}-INST-1",
                student_id=student.student_id,
                instalment_number=1,
                name="Mid-Year Annual Fee",
                due_date=due_date,
                grace_days=0,
                heads={
                    head: InstalmentHeadDue(
                        head=head,
                        base_amount=annual_fee.base_heads.get(head, Decimal("0.00")),
                        concession_discount=annual_fee.concession_discounts.get(head, Decimal("0.00")),
                        plan_discount=annual_fee.plan_discounts.get(head, Decimal("0.00")),
                        net_amount=net_amt,
                    )
                    for head, net_amt in annual_fee.net_heads.items()
                },
            )
            return [inst]

        elif student.plan == InstalmentPlanType.TERM:
            # Check which terms are still open
            # Term 1: 10 Apr, Term 2: 10 Aug, Term 3: 10 Dec
            term_dates = [
                ("Term 1", date(2026, 4, 10)),
                ("Term 2", date(2026, 8, 10)),
                ("Term 3", date(2026, 12, 10)),
            ]
            open_terms = [(name, d, idx + 1) for idx, (name, d) in enumerate(term_dates) if d >= student.admission_date]
            if not open_terms:
                # If admitted after Dec 10, bill immediately
                open_terms = [("Final Term", student.admission_date, 3)]

            num_open = len(open_terms)
            divisor = Decimal(str(num_open))
            schedule: List[Instalment] = []

            for idx, (t_name, d_date, t_num) in enumerate(open_terms):
                is_last = (idx == num_open - 1)
                t_heads: Dict[FeeHead, InstalmentHeadDue] = {}
                for head, net_amt in annual_fee.net_heads.items():
                    if not is_last:
                        h_net = quantize_amount(net_amt / divisor)
                    else:
                        prev_sum = quantize_amount(net_amt / divisor) * (num_open - 1)
                        h_net = net_amt - prev_sum

                    # Attach flat admission fee to the first instalment
                    base_h = annual_fee.base_heads.get(head, Decimal("0.00"))
                    t_heads[head] = InstalmentHeadDue(
                        head=head,
                        base_amount=quantize_amount(base_h / divisor) if not is_last else base_h - quantize_amount(base_h / divisor)*(num_open - 1),
                        concession_discount=annual_fee.concession_discounts.get(head, Decimal("0.00")),
                        plan_discount=Decimal("0.00"),
                        net_amount=h_net,
                    )

                schedule.append(Instalment(
                    instalment_id=f"{student.student_id}-INST-{t_num}",
                    student_id=student.student_id,
                    instalment_number=t_num,
                    name=t_name,
                    due_date=d_date,
                    grace_days=0,
                    heads=t_heads,
                ))
            return schedule

        elif student.plan == InstalmentPlanType.MONTHLY:
            # Remaining monthly instalments
            open_months = [
                (m, y, name, idx + 1)
                for idx, (m, y, name) in enumerate(MONTHLY_MONTHS)
                if date(y, m, 10) >= student.admission_date or (student.admission_date.year == y and student.admission_date.month == m)
            ]
            num_open = len(open_months)
            divisor = Decimal(str(max(1, num_open)))
            schedule = []

            for idx, (m, y, name, inst_num) in enumerate(open_months):
                is_last = (idx == num_open - 1)
                m_heads = {}
                due_d = date(y, m, 10) if date(y, m, 10) >= student.admission_date else student.admission_date
                for head, net_amt in annual_fee.net_heads.items():
                    if not is_last:
                        h_net = quantize_amount(net_amt / divisor)
                    else:
                        prev_sum = quantize_amount(net_amt / divisor) * (num_open - 1)
                        h_net = net_amt - prev_sum
                    m_heads[head] = InstalmentHeadDue(
                        head=head,
                        base_amount=quantize_amount(annual_fee.base_heads.get(head, Decimal("0.00")) / divisor),
                        net_amount=h_net,
                    )
                schedule.append(Instalment(
                    instalment_id=f"{student.student_id}-INST-{inst_num}",
                    student_id=student.student_id,
                    instalment_number=inst_num,
                    name=f"{name} Instalment",
                    due_date=due_d,
                    grace_days=0,
                    heads=m_heads,
                ))
            return schedule
        else:
            return []
