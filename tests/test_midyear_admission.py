"""
Unit Tests for Mid-Year Admission Rules (BR-08)
Verifies:
- Pro-rating of tuition and other heads by remaining months
- Cutoff on the 15th: Admitted on or before 15th counts that month
- Explicit edge case: Mid-year admission on the 16th (month does not count)
- Development fee is NEVER pro-rated
- Flat Rs 10,000 admission fee charged
"""
import unittest
from datetime import date
from decimal import Decimal
from engine.models import (
    FeeHead,
    GradeFeeStructure,
    InstalmentPlanType,
    Student,
)
from engine.admission_manager import AdmissionManager


class TestMidYearAdmission(unittest.TestCase):

    def setUp(self):
        # Grade 7:
        # Tuition: 48,000, Development: 15,000, Lab: 5,100, Activity: 4,200, Exam: 3,200 (Total: 75,500)
        self.fee_structure = GradeFeeStructure(
            grade=7,
            heads={
                FeeHead.TUITION: Decimal("48000.00"),
                FeeHead.DEVELOPMENT: Decimal("15000.00"),
                FeeHead.LAB: Decimal("5100.00"),
                FeeHead.ACTIVITY: Decimal("4200.00"),
                FeeHead.EXAM: Decimal("3200.00"),
            },
        )

    def test_admission_on_15th_counts_current_month(self):
        """
        Admitted on 15 August 2026:
        August counts!
        Remaining months: Aug, Sep, Oct, Nov, Dec, Jan = 6 months.
        Pro-rate ratio: 6 / 10 = 0.60 (60%).
        """
        months_count = AdmissionManager.calculate_remaining_months_count(date(2026, 8, 15))
        self.assertEqual(months_count, 6)

        student = Student(
            student_id="STU_ADM_15", name="Midyear15", grade=7, section="A",
            dob=date(2013, 3, 1), admission_date=date(2026, 8, 15),
            plan=InstalmentPlanType.TERM,
        )
        annual, schedule = AdmissionManager.enrol_student(student, self.fee_structure, [student])

        # Tuition pro-rated to 60%: 48,000 * 0.60 = 28,800
        self.assertEqual(annual.net_heads[FeeHead.TUITION], Decimal("28800.00"))

        # BR-08: Development fee is NEVER pro-rated!
        self.assertEqual(annual.net_heads[FeeHead.DEVELOPMENT], Decimal("15000.00"))

        # Flat admission fee: 10,000
        self.assertEqual(annual.net_heads[FeeHead.ADMISSION], Decimal("10000.00"))

    def test_edge_case_admission_on_16th_does_not_count_month(self):
        """
        Explicit Edge Case from problem statement:
        'Mid-year admission on the 16th'
        Admitted on 16 August 2026:
        August does NOT count!
        Remaining months: Sep, Oct, Nov, Dec, Jan = 5 months.
        Pro-rate ratio: 5 / 10 = 0.50 (50%).
        """
        months_count = AdmissionManager.calculate_remaining_months_count(date(2026, 8, 16))
        self.assertEqual(months_count, 5)

        student = Student(
            student_id="STU_ADM_16", name="Midyear16", grade=7, section="A",
            dob=date(2013, 3, 1), admission_date=date(2026, 8, 16),
            plan=InstalmentPlanType.TERM,
        )
        annual, schedule = AdmissionManager.enrol_student(student, self.fee_structure, [student])

        # Tuition pro-rated to 50%: 48,000 * 0.50 = 24,000
        self.assertEqual(annual.net_heads[FeeHead.TUITION], Decimal("24000.00"))

        # Development fee is NEVER pro-rated: 15,000 full
        self.assertEqual(annual.net_heads[FeeHead.DEVELOPMENT], Decimal("15000.00"))

        # Lab pro-rated to 50%: 5,100 * 0.50 = 2,550
        self.assertEqual(annual.net_heads[FeeHead.LAB], Decimal("2550.00"))

        # Flat admission fee: 10,000
        self.assertEqual(annual.net_heads[FeeHead.ADMISSION], Decimal("10000.00"))


if __name__ == "__main__":
    unittest.main()
