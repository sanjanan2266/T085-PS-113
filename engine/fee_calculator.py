"""
Fee Calculator implementing BR-02, BR-03, and BR-12
Precedence: Category Concession -> Sibling Stacking -> Combined Cap -> Plan Discount
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional
from engine.models import (
    ConcessionCategory,
    FeeHead,
    GradeFeeStructure,
    InstalmentPlanType,
    Student,
    quantize_amount,
)
from engine.rules import (
    ANNUAL_TUITION_DISCOUNT_PERCENT,
    CATEGORY_CONCESSIONS,
    COMBINED_TUITION_CAP,
    SIBLING_CONCESSION_ELDEST,
    SIBLING_CONCESSION_SECOND,
    SIBLING_CONCESSION_THIRD_PLUS,
)


@dataclass
class ConcessionBreakdown:
    category_applied: ConcessionCategory
    category_tuition_pct: Decimal
    category_other_pct: Decimal
    sibling_rank: int  # 1 = eldest, 2 = second, 3 = third+
    sibling_tuition_pct: Decimal
    combined_tuition_pct_raw: Decimal
    combined_tuition_pct_effective: Decimal
    tuition_cap_applied: bool
    plan_discount_pct: Decimal


@dataclass
class ComputedAnnualFee:
    student_id: str
    base_heads: Dict[FeeHead, Decimal]
    concession_breakdown: ConcessionBreakdown
    concession_discounts: Dict[FeeHead, Decimal]
    plan_discounts: Dict[FeeHead, Decimal]
    net_heads: Dict[FeeHead, Decimal]

    @property
    def total_base(self) -> Decimal:
        return sum((quantize_amount(v) for v in self.base_heads.values()), Decimal("0.00"))

    @property
    def total_concession(self) -> Decimal:
        return sum((quantize_amount(v) for v in self.concession_discounts.values()), Decimal("0.00"))

    @property
    def total_plan_discount(self) -> Decimal:
        return sum((quantize_amount(v) for v in self.plan_discounts.values()), Decimal("0.00"))

    @property
    def total_net(self) -> Decimal:
        return sum((quantize_amount(v) for v in self.net_heads.values()), Decimal("0.00"))


class FeeCalculator:
    """Calculates annual student fees adhering strictly to BR-02, BR-03, and BR-12."""

    @staticmethod
    def determine_sibling_rank(student: Student, sibling_group_students: List[Student]) -> int:
        """
        Determines the student's rank within their active sibling group.
        Eldest enrolled active student is rank 1 (pays full).
        Ranked strictly by DOB ascending (older birth date = older child).
        If DOB is identical, ranked by admission date or student_id.
        """
        if not student.sibling_group_id or not sibling_group_students:
            return 1

        active_siblings = [
            s for s in sibling_group_students
            if s.sibling_group_id == student.sibling_group_id and s.status.value == "ACTIVE"
        ]

        if not active_siblings:
            return 1

        # Sort active siblings by dob ascending, then admission_date ascending, then id
        sorted_siblings = sorted(active_siblings, key=lambda s: (s.dob, s.admission_date, s.student_id))

        for idx, s in enumerate(sorted_siblings):
            if s.student_id == student.student_id:
                return idx + 1
        return 1

    @classmethod
    def get_sibling_concession_pct(cls, rank: int) -> Decimal:
        """BR-02: 1st child 0%, 2nd child 10%, 3rd and beyond 20%."""
        if rank <= 1:
            return SIBLING_CONCESSION_ELDEST
        elif rank == 2:
            return SIBLING_CONCESSION_SECOND
        else:
            return SIBLING_CONCESSION_THIRD_PLUS

    @classmethod
    def compute_concession_breakdown(
        cls,
        student: Student,
        sibling_group_students: Optional[List[Student]] = None,
    ) -> ConcessionBreakdown:
        """
        Calculates concession percentages according to BR-03 and BR-12:
        1. Category concession (highest single)
        2. Sibling concession stacking
        3. Combined cap of 60% on tuition
        """
        category = student.concession_category or ConcessionCategory.NONE

        # Auto-detect merit if percentage >= 90% and no higher concession
        if student.previous_year_percentage >= 90.0 and category == ConcessionCategory.NONE:
            category = ConcessionCategory.MERIT

        # Category rates
        cat_conf = CATEGORY_CONCESSIONS.get(category.value, CATEGORY_CONCESSIONS["NONE"])
        cat_tuition_pct = cat_conf["tuition"]
        cat_other_pct = cat_conf["other"]

        # Sibling rank & rate
        rank = cls.determine_sibling_rank(student, sibling_group_students or [])
        sibling_tuition_pct = cls.get_sibling_concession_pct(rank)

        # Stacking & Cap
        if category == ConcessionCategory.EWS:
            # EWS standalone guarantees 100% tuition and 50% other heads
            combined_raw = Decimal("1.00") + sibling_tuition_pct
            combined_effective = Decimal("1.00")
            cap_applied = False
        else:
            combined_raw = cat_tuition_pct + sibling_tuition_pct
            if combined_raw > COMBINED_TUITION_CAP:
                combined_effective = COMBINED_TUITION_CAP
                cap_applied = True
            else:
                combined_effective = combined_raw
                cap_applied = False

        # Plan discount
        plan_discount_pct = (
            ANNUAL_TUITION_DISCOUNT_PERCENT
            if student.plan == InstalmentPlanType.ANNUAL
            else Decimal("0.00")
        )

        return ConcessionBreakdown(
            category_applied=category,
            category_tuition_pct=cat_tuition_pct,
            category_other_pct=cat_other_pct,
            sibling_rank=rank,
            sibling_tuition_pct=sibling_tuition_pct,
            combined_tuition_pct_raw=combined_raw,
            combined_tuition_pct_effective=combined_effective,
            tuition_cap_applied=cap_applied,
            plan_discount_pct=plan_discount_pct,
        )

    @classmethod
    def compute_annual_fee(
        cls,
        student: Student,
        fee_structure: GradeFeeStructure,
        sibling_group_students: Optional[List[Student]] = None,
    ) -> ComputedAnnualFee:
        """
        Computes the complete annual fee breakdown for a student.
        Order of operations:
        1. Base heads from fee structure.
        2. Apply category and sibling concessions (with 60% tuition cap).
        3. Apply 3% annual discount on net tuition (if ANNUAL plan).
        """
        breakdown = cls.compute_concession_breakdown(student, sibling_group_students)

        base_heads: Dict[FeeHead, Decimal] = {}
        concession_discounts: Dict[FeeHead, Decimal] = {}
        plan_discounts: Dict[FeeHead, Decimal] = {}
        net_heads: Dict[FeeHead, Decimal] = {}

        # Heads considered in standard fee structure
        standard_heads = [
            FeeHead.TUITION,
            FeeHead.DEVELOPMENT,
            FeeHead.LAB,
            FeeHead.ACTIVITY,
            FeeHead.EXAM,
        ]

        for head in standard_heads:
            base_amt = fee_structure.get_head(head)
            base_heads[head] = base_amt

            if head == FeeHead.TUITION:
                # Concession on tuition
                conc_amt = quantize_amount(base_amt * breakdown.combined_tuition_pct_effective)
                concession_discounts[head] = conc_amt
                tuition_after_conc = base_amt - conc_amt

                # Plan discount (3% on tuition after concession)
                plan_disc = quantize_amount(tuition_after_conc * breakdown.plan_discount_pct)
                plan_discounts[head] = plan_disc

                net_heads[head] = quantize_amount(tuition_after_conc - plan_disc)
            else:
                # Other heads: EWS gives 50% discount; others 0%
                conc_amt = quantize_amount(base_amt * breakdown.category_other_pct)
                concession_discounts[head] = conc_amt
                plan_discounts[head] = Decimal("0.00")
                net_heads[head] = quantize_amount(base_amt - conc_amt)

        return ComputedAnnualFee(
            student_id=student.student_id,
            base_heads=base_heads,
            concession_breakdown=breakdown,
            concession_discounts=concession_discounts,
            plan_discounts=plan_discounts,
            net_heads=net_heads,
        )
