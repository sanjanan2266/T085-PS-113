"""
Unit Tests for Concession Rules (BR-02, BR-03, BR-12)
Verifies:
- Sibling concession ranking (0%, 10%, 20%)
- Category concession (Staff ward 50%, Merit 25%, EWS 100% tuition + 50% others)
- Highest single category concession precedence
- Additive stacking with sibling concession
- Combined cap of 60% on tuition
- Staff ward + 3rd sibling edge case (50% + 20% capped at 60%)
- Annual plan 3% discount applied on net tuition
"""
import unittest
from datetime import date
from decimal import Decimal
from engine.models import (
    ConcessionCategory,
    FeeHead,
    GradeFeeStructure,
    InstalmentPlanType,
    Student,
)
from engine.fee_calculator import FeeCalculator


class TestConcessions(unittest.TestCase):

    def setUp(self):
        # Grade 5 Fee Structure:
        # Tuition: 42,000, Development: 14,000, Lab: 3,900, Activity: 3,800, Exam: 2,800 (Total: 66,500)
        self.fee_structure = GradeFeeStructure(
            grade=5,
            heads={
                FeeHead.TUITION: Decimal("42000.00"),
                FeeHead.DEVELOPMENT: Decimal("14000.00"),
                FeeHead.LAB: Decimal("3900.00"),
                FeeHead.ACTIVITY: Decimal("3800.00"),
                FeeHead.EXAM: Decimal("2800.00"),
            },
        )

    def test_eldest_sibling_pays_full(self):
        """Eldest child in sibling group gets 0% sibling concession."""
        s1 = Student(
            student_id="S1", name="Elder", grade=5, section="A",
            dob=date(2012, 1, 1), admission_date=date(2026, 4, 1),
            plan=InstalmentPlanType.TERM, concession_category=ConcessionCategory.NONE,
            sibling_group_id="GRP1",
        )
        s2 = Student(
            student_id="S2", name="Younger", grade=3, section="A",
            dob=date(2014, 1, 1), admission_date=date(2026, 4, 1),
            plan=InstalmentPlanType.TERM, concession_category=ConcessionCategory.NONE,
            sibling_group_id="GRP1",
        )
        siblings = [s1, s2]

        annual_s1 = FeeCalculator.compute_annual_fee(s1, self.fee_structure, siblings)
        self.assertEqual(annual_s1.concession_breakdown.sibling_rank, 1)
        self.assertEqual(annual_s1.concession_breakdown.sibling_tuition_pct, Decimal("0.00"))
        self.assertEqual(annual_s1.net_heads[FeeHead.TUITION], Decimal("42000.00"))

    def test_second_sibling_gets_10_percent_tuition(self):
        """2nd child gets 10% on tuition."""
        s1 = Student(
            student_id="S1", name="Elder", grade=5, section="A",
            dob=date(2012, 1, 1), admission_date=date(2026, 4, 1),
            plan=InstalmentPlanType.TERM, concession_category=ConcessionCategory.NONE,
            sibling_group_id="GRP1",
        )
        s2 = Student(
            student_id="S2", name="Second", grade=5, section="A",
            dob=date(2014, 1, 1), admission_date=date(2026, 4, 1),
            plan=InstalmentPlanType.TERM, concession_category=ConcessionCategory.NONE,
            sibling_group_id="GRP1",
        )
        siblings = [s1, s2]

        annual_s2 = FeeCalculator.compute_annual_fee(s2, self.fee_structure, siblings)
        self.assertEqual(annual_s2.concession_breakdown.sibling_rank, 2)
        self.assertEqual(annual_s2.concession_breakdown.sibling_tuition_pct, Decimal("0.10"))
        # 42,000 * 0.90 = 37,800
        self.assertEqual(annual_s2.net_heads[FeeHead.TUITION], Decimal("37800.00"))

    def test_third_sibling_gets_20_percent_tuition(self):
        """3rd child gets 20% on tuition."""
        s1 = Student(
            student_id="S1", name="Elder", grade=5, section="A",
            dob=date(2012, 1, 1), admission_date=date(2026, 4, 1),
            sibling_group_id="GRP1",
        )
        s2 = Student(
            student_id="S2", name="Second", grade=5, section="A",
            dob=date(2014, 1, 1), admission_date=date(2026, 4, 1),
            sibling_group_id="GRP1",
        )
        s3 = Student(
            student_id="S3", name="Third", grade=5, section="A",
            dob=date(2016, 1, 1), admission_date=date(2026, 4, 1),
            sibling_group_id="GRP1",
        )
        siblings = [s1, s2, s3]

        annual_s3 = FeeCalculator.compute_annual_fee(s3, self.fee_structure, siblings)
        self.assertEqual(annual_s3.concession_breakdown.sibling_rank, 3)
        self.assertEqual(annual_s3.concession_breakdown.sibling_tuition_pct, Decimal("0.20"))
        # 42,000 * 0.80 = 33,600
        self.assertEqual(annual_s3.net_heads[FeeHead.TUITION], Decimal("33600.00"))

    def test_staff_ward_alone_50_percent(self):
        """Staff ward alone gets 50% tuition discount."""
        s = Student(
            student_id="S_STAFF", name="StaffWard", grade=5, section="A",
            dob=date(2012, 1, 1), admission_date=date(2026, 4, 1),
            concession_category=ConcessionCategory.STAFF_WARD,
        )
        annual = FeeCalculator.compute_annual_fee(s, self.fee_structure)
        self.assertEqual(annual.concession_breakdown.category_tuition_pct, Decimal("0.50"))
        # 42,000 * 0.50 = 21,000
        self.assertEqual(annual.net_heads[FeeHead.TUITION], Decimal("21000.00"))

    def test_merit_alone_25_percent(self):
        """Merit (marks >= 90%) gets 25% tuition discount."""
        s = Student(
            student_id="S_MERIT", name="MeritStudent", grade=5, section="A",
            dob=date(2012, 1, 1), admission_date=date(2026, 4, 1),
            concession_category=ConcessionCategory.MERIT, previous_year_percentage=95.0,
        )
        annual = FeeCalculator.compute_annual_fee(s, self.fee_structure)
        self.assertEqual(annual.concession_breakdown.category_tuition_pct, Decimal("0.25"))
        # 42,000 * 0.75 = 31,500
        self.assertEqual(annual.net_heads[FeeHead.TUITION], Decimal("31500.00"))

    def test_edge_case_staff_ward_who_is_3rd_sibling_hits_60_percent_cap(self):
        """
        Explicit Edge Case from problem statement:
        'Staff ward who is also a 3rd sibling (combined cap)'
        Staff ward (50%) + 3rd sibling (20%) = 70% raw.
        Must be capped at 60% on tuition!
        """
        s1 = Student(student_id="S1", name="Eldest", grade=5, section="A", dob=date(2010, 1, 1), admission_date=date(2026, 4, 1), sibling_group_id="GRP_EDGE")
        s2 = Student(student_id="S2", name="Second", grade=5, section="A", dob=date(2012, 1, 1), admission_date=date(2026, 4, 1), sibling_group_id="GRP_EDGE")
        s3 = Student(
            student_id="S3", name="ThirdStaff", grade=5, section="A",
            dob=date(2014, 1, 1), admission_date=date(2026, 4, 1),
            concession_category=ConcessionCategory.STAFF_WARD,
            sibling_group_id="GRP_EDGE",
        )
        siblings = [s1, s2, s3]

        annual = FeeCalculator.compute_annual_fee(s3, self.fee_structure, siblings)
        breakdown = annual.concession_breakdown

        self.assertEqual(breakdown.sibling_rank, 3)
        self.assertEqual(breakdown.category_tuition_pct, Decimal("0.50"))
        self.assertEqual(breakdown.sibling_tuition_pct, Decimal("0.20"))
        self.assertEqual(breakdown.combined_tuition_pct_raw, Decimal("0.70"))
        self.assertEqual(breakdown.combined_tuition_pct_effective, Decimal("0.60"))
        self.assertTrue(breakdown.tuition_cap_applied)

        # Base tuition: 42,000. 60% concession = 25,200. Net tuition = 16,800
        self.assertEqual(annual.concession_discounts[FeeHead.TUITION], Decimal("25200.00"))
        self.assertEqual(annual.net_heads[FeeHead.TUITION], Decimal("16800.00"))

    def test_ews_concession_100_percent_tuition_and_50_percent_other_heads(self):
        """EWS gets 100% tuition concession and 50% other heads."""
        s = Student(
            student_id="S_EWS", name="EWS_Student", grade=5, section="A",
            dob=date(2012, 1, 1), admission_date=date(2026, 4, 1),
            concession_category=ConcessionCategory.EWS,
        )
        annual = FeeCalculator.compute_annual_fee(s, self.fee_structure)

        # Tuition net = 0
        self.assertEqual(annual.net_heads[FeeHead.TUITION], Decimal("0.00"))
        # Development: 14000 * 0.50 = 7000
        self.assertEqual(annual.net_heads[FeeHead.DEVELOPMENT], Decimal("7000.00"))
        # Lab: 3900 * 0.50 = 1950
        self.assertEqual(annual.net_heads[FeeHead.LAB], Decimal("1950.00"))
        # Activity: 3800 * 0.50 = 1900
        self.assertEqual(annual.net_heads[FeeHead.ACTIVITY], Decimal("1900.00"))
        # Exam: 2800 * 0.50 = 1400
        self.assertEqual(annual.net_heads[FeeHead.EXAM], Decimal("1400.00"))

    def test_annual_plan_3_percent_discount_on_post_concession_tuition(self):
        """Annual plan gives 3% discount on post-concession tuition."""
        # Student with 2nd sibling (10% concession) on ANNUAL plan
        s1 = Student(student_id="S1", name="Eldest", grade=5, section="A", dob=date(2010, 1, 1), admission_date=date(2026, 4, 1), sibling_group_id="GRP_A")
        s2 = Student(
            student_id="S2", name="SecondAnnual", grade=5, section="A",
            dob=date(2012, 1, 1), admission_date=date(2026, 4, 1),
            plan=InstalmentPlanType.ANNUAL, sibling_group_id="GRP_A",
        )
        annual = FeeCalculator.compute_annual_fee(s2, self.fee_structure, [s1, s2])

        # Base tuition: 42,000. Concession 10% = 4,200. Tuition after concession = 37,800.
        # Plan discount 3% of 37,800 = 1,134.00.
        # Net tuition = 37,800 - 1,134 = 36,666.00.
        self.assertEqual(annual.plan_discounts[FeeHead.TUITION], Decimal("1134.00"))
        self.assertEqual(annual.net_heads[FeeHead.TUITION], Decimal("36666.00"))


if __name__ == "__main__":
    unittest.main()
