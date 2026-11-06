"""
Late Fee and Defaulter Management implementing BR-06
Handles Rs 50/day late fee, Rs 1500 cap per instalment, April 7-day grace period,
and flagging of defaulters with withheld hall tickets (> 60 days overdue).
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional
from engine.models import (
    HallTicketStatus,
    Instalment,
    Student,
    quantize_amount,
)
from engine.rules import (
    DEFAULTER_DAYS_THRESHOLD,
    LATE_FEE_MAX_CAP,
    LATE_FEE_PER_DAY,
)


@dataclass
class DefaulterRecord:
    student_id: str
    student_name: str
    grade: int
    section: str
    overdue_instalment: int
    due_date: date
    days_overdue: int
    overdue_amount: Decimal
    late_fee_amount: Decimal
    total_due: Decimal
    hall_ticket_status: HallTicketStatus


class LateFeeCalculator:
    """Computes late fees per instalment and identifies defaulters."""

    @classmethod
    def compute_late_fee(
        cls,
        instalment: Instalment,
        as_of_date: date,
        late_fee_from_due_date_after_grace: bool = True,
    ) -> Decimal:
        """
        BR-06:
        - Rs 50/day from day after due date capped at Rs 1,500 per instalment.
        - Grace of 7 days applies to April instalment only.
        - If paid/assessed on or before due_date + grace_days: Rs 0.
        - If assessed after grace period:
          Late fee applies per day overdue, capped at Rs 1,500.
        """
        # If instalment has no remaining fee dues, no new late fees accumulate
        if instalment.remaining_fee_due <= Decimal("0.00"):
            return Decimal("0.00")

        due_date = instalment.due_date
        grace_days = instalment.grace_days
        grace_end_date = due_date + timedelta(days=grace_days)

        if as_of_date <= grace_end_date:
            return Decimal("0.00")

        # Past grace period
        if late_fee_from_due_date_after_grace:
            # Overdue days counted from due date once grace is breached
            overdue_days = (as_of_date - due_date).days
        else:
            # Overdue days counted from grace end date
            overdue_days = (as_of_date - grace_end_date).days

        if overdue_days <= 0:
            return Decimal("0.00")

        calculated = quantize_amount(Decimal(str(overdue_days)) * LATE_FEE_PER_DAY)
        return min(calculated, LATE_FEE_MAX_CAP)

    @classmethod
    def update_instalment_late_fee(
        cls,
        instalment: Instalment,
        as_of_date: date,
        late_fee_from_due_date_after_grace: bool = True,
    ) -> Decimal:
        """Updates the instalment's late_fee_assessed property as of a given date."""
        late_fee = cls.compute_late_fee(instalment, as_of_date, late_fee_from_due_date_after_grace)
        instalment.late_fee_assessed = late_fee
        return late_fee

    @classmethod
    def check_defaulter_status(
        cls,
        student: Student,
        schedule: List[Instalment],
        as_of_date: date,
    ) -> Optional[DefaulterRecord]:
        """
        BR-06: Students with dues beyond 60 days are listed as DEFAULTERS
        and exam hall tickets are flagged WITHHELD.
        """
        worst_overdue_days = 0
        worst_inst: Optional[Instalment] = None
        total_overdue_fee = Decimal("0.00")
        total_late_fee = Decimal("0.00")

        for inst in schedule:
            # Check overdue
            if as_of_date > inst.due_date:
                cls.update_instalment_late_fee(inst, as_of_date)
                if inst.remaining_fee_due > Decimal("0.00"):
                    days_overdue = (as_of_date - inst.due_date).days
                    total_overdue_fee += inst.remaining_fee_due
                    total_late_fee += inst.remaining_late_fee
                    if days_overdue > worst_overdue_days:
                        worst_overdue_days = days_overdue
                        worst_inst = inst

        if worst_overdue_days > DEFAULTER_DAYS_THRESHOLD and worst_inst:
            student.hall_ticket_status = HallTicketStatus.WITHHELD
            return DefaulterRecord(
                student_id=student.student_id,
                student_name=student.name,
                grade=student.grade,
                section=student.section,
                overdue_instalment=worst_inst.instalment_number,
                due_date=worst_inst.due_date,
                days_overdue=worst_overdue_days,
                overdue_amount=total_overdue_fee,
                late_fee_amount=total_late_fee,
                total_due=quantize_amount(total_overdue_fee + total_late_fee),
                hall_ticket_status=HallTicketStatus.WITHHELD,
            )
        else:
            student.hall_ticket_status = HallTicketStatus.CLEARED
            return None
