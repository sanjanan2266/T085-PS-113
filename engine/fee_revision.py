"""
Fee Revision Manager implementing BR-11
Handles mid-year fee revisions up to 10% on future instalments,
and enforces BOARD_APPROVED requirement for revisions above 10% (applicable only next academic year).
"""
from datetime import date
from decimal import Decimal
from typing import Dict, List, Tuple
from engine.models import (
    FeeHead,
    GradeFeeStructure,
    Instalment,
    quantize_amount,
)
from engine.rules import (
    MID_YEAR_REVISION_MAX_PERCENT,
)


class FeeRevisionManager:
    """Manages grade-level fee revisions according to BR-11."""

    @classmethod
    def apply_fee_revision(
        cls,
        grade: int,
        head: FeeHead,
        revision_percent: Decimal,
        effective_date: date,
        board_approved: bool,
        fee_structure: GradeFeeStructure,
        all_student_schedules: Dict[str, List[Instalment]],
        student_grades: Dict[str, int],
    ) -> Tuple[bool, str, int]:
        """
        BR-11:
        - Mid-year revision up to 10% applies only to instalments not yet due.
        - Revision above 10% requires BOARD_APPROVED flag and applies from next academic year.
        Returns: (success: bool, message: str, updated_instalment_count: int)
        """
        if revision_percent > MID_YEAR_REVISION_MAX_PERCENT:
            if not board_approved:
                return (
                    False,
                    f"REJECTED: Fee revision of {revision_percent * 100}% exceeds 10% threshold and lacks BOARD_APPROVED flag.",
                    0,
                )
            else:
                return (
                    True,
                    f"APPROVED FOR NEXT ACADEMIC YEAR: Revision of {revision_percent * 100}% has BOARD_APPROVED flag and will take effect in 2027-2028.",
                    0,
                )

        # Revision is <= 10%: applies mid-year to future instalments not yet due
        # 1. Update grade fee structure for future calculations
        current_base = fee_structure.get_head(head)
        adjustment = quantize_amount(current_base * revision_percent)
        fee_structure.heads[head] = current_base + adjustment

        # 2. Update existing schedules for enrolled students in this grade
        updated_count = 0
        for student_id, st_grade in student_grades.items():
            if st_grade != grade:
                continue

            schedule = all_student_schedules.get(student_id, [])
            for inst in schedule:
                # Applies only to instalments not yet due (due_date >= effective_date)
                if inst.due_date >= effective_date:
                    if head in inst.heads:
                        h_due = inst.heads[head]
                        head_adjustment = quantize_amount(h_due.net_amount * revision_percent)
                        h_due.revision_adjustment += head_adjustment
                        h_due.net_amount += head_adjustment
                        updated_count += 1

        return (
            True,
            f"SUCCESS: Mid-year revision of {revision_percent * 100}% applied to {updated_count} upcoming instalments for Grade {grade} on {head.value}.",
            updated_count,
        )
