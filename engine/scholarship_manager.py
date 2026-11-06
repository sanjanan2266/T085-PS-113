"""
Scholarship Fund Manager (Stretch Goal)
Allocates a limited scholarship pool to eligible students based on merit rank.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Tuple
from engine.models import (
    FeeHead,
    Instalment,
    Student,
    quantize_amount,
)


@dataclass
class ScholarshipAward:
    student_id: str
    merit_rank: int
    marks_percentage: float
    amount_awarded: Decimal


class ScholarshipManager:
    """Manages limited scholarship fund pool allocated by merit rank."""

    def __init__(self, total_fund: Decimal):
        self.total_fund = quantize_amount(total_fund)
        self.remaining_fund = self.total_fund
        self.awards: List[ScholarshipAward] = []

    def allocate_scholarships(
        self,
        students: List[Student],
        all_schedules: Dict[str, List[Instalment]],
        max_award_per_student: Decimal = Decimal("15000.00"),
    ) -> List[ScholarshipAward]:
        """
        Sorts students by previous_year_percentage descending (merit rank).
        Allocates up to max_award_per_student (or tuition due) until pool is exhausted.
        Applies award as a credit/discount on tuition dues.
        """
        # Filter eligible students (marks >= 85%)
        eligible = [s for s in students if s.previous_year_percentage >= 85.0]
        # Rank by marks descending
        sorted_eligible = sorted(eligible, key=lambda s: s.previous_year_percentage, reverse=True)

        for rank_idx, student in enumerate(sorted_eligible):
            if self.remaining_fund <= Decimal("0.00"):
                break

            merit_rank = rank_idx + 1
            schedule = all_schedules.get(student.student_id, [])

            # Check tuition due
            tuition_due = sum(
                inst.heads[FeeHead.TUITION].remaining_due
                for inst in schedule
                if FeeHead.TUITION in inst.heads
            )

            award_amount = min(self.remaining_fund, max_award_per_student, tuition_due)
            if award_amount > Decimal("0.00"):
                self.remaining_fund -= award_amount
                award = ScholarshipAward(
                    student_id=student.student_id,
                    merit_rank=merit_rank,
                    marks_percentage=student.previous_year_percentage,
                    amount_awarded=award_amount,
                )
                self.awards.append(award)

                # Deduct from first available tuition head
                rem_to_deduct = award_amount
                for inst in schedule:
                    if FeeHead.TUITION in inst.heads and rem_to_deduct > Decimal("0.00"):
                        t_due = inst.heads[FeeHead.TUITION]
                        deduct = min(rem_to_deduct, t_due.remaining_due)
                        t_due.net_amount -= deduct
                        rem_to_deduct -= deduct

        return self.awards
