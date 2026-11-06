"""
Instalment Scheduler implementing BR-01
Handles ANNUAL, TERM (40/30/30), and MONTHLY (10 instalments, Jan absorbs rounding residue).
Enforces plan change validity (only before the first due date).
"""
from datetime import date
from decimal import Decimal
from typing import Dict, List
from engine.models import (
    FeeHead,
    Instalment,
    InstalmentHeadDue,
    InstalmentPlanType,
    Student,
    quantize_amount,
)
from engine.rules import (
    APRIL_GRACE_DAYS,
    MONTHLY_DUE_DAY,
    MONTHLY_MONTHS,
    TERM_SPLITS,
)
from engine.fee_calculator import ComputedAnnualFee


class InstalmentScheduler:
    """Generates instalment schedules according to BR-01."""

    @classmethod
    def can_change_plan(cls, student: Student, current_schedule: List[Instalment], request_date: date) -> bool:
        """
        BR-01: Plan can change only before the first due date.
        """
        if not current_schedule:
            # No instalments yet, check against default first due date (10 Apr 2026)
            return request_date < date(2026, 4, 10)

        first_due_date = min(inst.due_date for inst in current_schedule)
        return request_date < first_due_date

    @classmethod
    def generate_schedule(
        cls,
        student: Student,
        annual_fee: ComputedAnnualFee,
    ) -> List[Instalment]:
        """
        Generates the instalment schedule based on student's plan.
        """
        if student.plan == InstalmentPlanType.ANNUAL:
            return cls._generate_annual_schedule(student, annual_fee)
        elif student.plan == InstalmentPlanType.TERM:
            return cls._generate_term_schedule(student, annual_fee)
        elif student.plan == InstalmentPlanType.MONTHLY:
            return cls._generate_monthly_schedule(student, annual_fee)
        else:
            raise ValueError(f"Unknown instalment plan: {student.plan}")

    @classmethod
    def _generate_annual_schedule(
        cls,
        student: Student,
        annual_fee: ComputedAnnualFee,
    ) -> List[Instalment]:
        """ANNUAL plan: 1 instalment on 10 April 2026 with 7-day grace."""
        due_date = date(2026, 4, 10)
        heads_map: Dict[FeeHead, InstalmentHeadDue] = {}

        for head, base_amt in annual_fee.base_heads.items():
            conc_disc = annual_fee.concession_discounts.get(head, Decimal("0.00"))
            plan_disc = annual_fee.plan_discounts.get(head, Decimal("0.00"))
            net_amt = annual_fee.net_heads.get(head, Decimal("0.00"))

            heads_map[head] = InstalmentHeadDue(
                head=head,
                base_amount=base_amt,
                concession_discount=conc_disc,
                plan_discount=plan_disc,
                net_amount=net_amt,
                paid_amount=Decimal("0.00"),
            )

        inst = Instalment(
            instalment_id=f"{student.student_id}-INST-1",
            student_id=student.student_id,
            instalment_number=1,
            name="Annual Fee",
            due_date=due_date,
            grace_days=APRIL_GRACE_DAYS,
            heads=heads_map,
        )
        return [inst]

    @classmethod
    def _generate_term_schedule(
        cls,
        student: Student,
        annual_fee: ComputedAnnualFee,
    ) -> List[Instalment]:
        """
        TERM plan: 3 instalments:
        Term 1 (40%): 10 Apr (7-day grace)
        Term 2 (30%): 10 Aug (0 grace)
        Term 3 (30%): 10 Dec (0 grace; absorbs rounding)
        """
        schedule: List[Instalment] = []
        heads_list = list(annual_fee.base_heads.keys())

        # Track accumulated amounts per head for Term 1 and Term 2
        accumulated_net: Dict[FeeHead, Decimal] = {h: Decimal("0.00") for h in heads_list}
        accumulated_base: Dict[FeeHead, Decimal] = {h: Decimal("0.00") for h in heads_list}
        accumulated_conc: Dict[FeeHead, Decimal] = {h: Decimal("0.00") for h in heads_list}

        for idx, (term_name, due_date, split_ratio, _) in enumerate(TERM_SPLITS):
            term_num = idx + 1
            grace = APRIL_GRACE_DAYS if due_date.month == 4 else 0
            term_heads: Dict[FeeHead, InstalmentHeadDue] = {}

            is_last = (term_num == len(TERM_SPLITS))

            for head in heads_list:
                full_base = annual_fee.base_heads.get(head, Decimal("0.00"))
                full_conc = annual_fee.concession_discounts.get(head, Decimal("0.00"))
                full_net = annual_fee.net_heads.get(head, Decimal("0.00"))

                if not is_last:
                    head_base = quantize_amount(full_base * split_ratio)
                    head_conc = quantize_amount(full_conc * split_ratio)
                    head_net = quantize_amount(full_net * split_ratio)

                    accumulated_base[head] += head_base
                    accumulated_conc[head] += head_conc
                    accumulated_net[head] += head_net
                else:
                    # Last term absorbs rounding residue
                    head_base = quantize_amount(full_base - accumulated_base[head])
                    head_conc = quantize_amount(full_conc - accumulated_conc[head])
                    head_net = quantize_amount(full_net - accumulated_net[head])

                term_heads[head] = InstalmentHeadDue(
                    head=head,
                    base_amount=head_base,
                    concession_discount=head_conc,
                    plan_discount=Decimal("0.00"),
                    net_amount=head_net,
                    paid_amount=Decimal("0.00"),
                )

            inst = Instalment(
                instalment_id=f"{student.student_id}-INST-{term_num}",
                student_id=student.student_id,
                instalment_number=term_num,
                name=term_name,
                due_date=due_date,
                grace_days=grace,
                heads=term_heads,
            )
            schedule.append(inst)

        return schedule

    @classmethod
    def _generate_monthly_schedule(
        cls,
        student: Student,
        annual_fee: ComputedAnnualFee,
    ) -> List[Instalment]:
        """
        MONTHLY plan: 10 instalments Apr-Jan, equal, last (Jan) absorbs rounding.
        Due on the 10th of each month.
        April has 7 days grace.
        """
        schedule: List[Instalment] = []
        heads_list = list(annual_fee.base_heads.keys())

        total_instalments = len(MONTHLY_MONTHS)  # 10
        divisor = Decimal(str(total_instalments))

        accumulated_net: Dict[FeeHead, Decimal] = {h: Decimal("0.00") for h in heads_list}
        accumulated_base: Dict[FeeHead, Decimal] = {h: Decimal("0.00") for h in heads_list}
        accumulated_conc: Dict[FeeHead, Decimal] = {h: Decimal("0.00") for h in heads_list}

        for idx, (month_num, year, month_name) in enumerate(MONTHLY_MONTHS):
            inst_num = idx + 1
            due_date = date(year, month_num, MONTHLY_DUE_DAY)
            grace = APRIL_GRACE_DAYS if month_num == 4 else 0
            is_last = (inst_num == total_instalments)

            m_heads: Dict[FeeHead, InstalmentHeadDue] = {}

            for head in heads_list:
                full_base = annual_fee.base_heads.get(head, Decimal("0.00"))
                full_conc = annual_fee.concession_discounts.get(head, Decimal("0.00"))
                full_net = annual_fee.net_heads.get(head, Decimal("0.00"))

                if not is_last:
                    # Equal instalments for 1-9
                    head_base = quantize_amount(full_base / divisor)
                    head_conc = quantize_amount(full_conc / divisor)
                    head_net = quantize_amount(full_net / divisor)

                    accumulated_base[head] += head_base
                    accumulated_conc[head] += head_conc
                    accumulated_net[head] += head_net
                else:
                    # January (10th) absorbs rounding residue
                    head_base = quantize_amount(full_base - accumulated_base[head])
                    head_conc = quantize_amount(full_conc - accumulated_conc[head])
                    head_net = quantize_amount(full_net - accumulated_net[head])

                m_heads[head] = InstalmentHeadDue(
                    head=head,
                    base_amount=head_base,
                    concession_discount=head_conc,
                    plan_discount=Decimal("0.00"),
                    net_amount=head_net,
                    paid_amount=Decimal("0.00"),
                )

            inst = Instalment(
                instalment_id=f"{student.student_id}-INST-{inst_num}",
                student_id=student.student_id,
                instalment_number=inst_num,
                name=f"{month_name} Instalment",
                due_date=due_date,
                grace_days=grace,
                heads=m_heads,
            )
            schedule.append(inst)

        return schedule
