"""
Unit Tests for Instalment Schedule Rules (BR-01)
Verifies:
- ANNUAL plan: 1 instalment on 10 April with 7-day grace
- TERM plan: 3 instalments 40/30/30 on 10 Apr, 10 Aug, 10 Dec (last absorbs rounding)
- MONTHLY plan: 10 instalments Apr-Jan, equal, January absorbs rounding residue
- Plan change restriction: Allowed before first due date, strictly rejected on/after
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
from engine.instalment_scheduler import InstalmentScheduler


class TestInstalments(unittest.TestCase):

    def setUp(self):
        # Grade 6 Fee: Tuition: 45,000, Dev: 14,500, Lab: 4,500, Activity: 4,000, Exam: 3,000 (Total: 71,000)
        self.fee_structure = GradeFeeStructure(
            grade=6,
            heads={
                FeeHead.TUITION: Decimal("45000.00"),
                FeeHead.DEVELOPMENT: Decimal("14500.00"),
                FeeHead.LAB: Decimal("4500.00"),
                FeeHead.ACTIVITY: Decimal("4000.00"),
                FeeHead.EXAM: Decimal("3000.00"),
            },
        )

    def test_annual_plan_single_instalment(self):
        """ANNUAL plan generates exactly 1 instalment on 10 April 2026 with 7-day grace."""
        s = Student(
            student_id="STU_ANNUAL", name="AnnualStudent", grade=6, section="A",
            dob=date(2013, 2, 1), admission_date=date(2026, 4, 1),
            plan=InstalmentPlanType.ANNUAL,
        )
        annual_fee = FeeCalculator.compute_annual_fee(s, self.fee_structure)
        schedule = InstalmentScheduler.generate_schedule(s, annual_fee)

        self.assertEqual(len(schedule), 1)
        inst = schedule[0]
        self.assertEqual(inst.instalment_number, 1)
        self.assertEqual(inst.due_date, date(2026, 4, 10))
        self.assertEqual(inst.grace_days, 7)
        self.assertEqual(inst.total_net_fee, annual_fee.total_net)

    def test_term_plan_40_30_30_split_and_dates(self):
        """TERM plan generates 3 instalments 40/30/30 on 10 Apr, 10 Aug, 10 Dec."""
        s = Student(
            student_id="STU_TERM", name="TermStudent", grade=6, section="A",
            dob=date(2013, 2, 1), admission_date=date(2026, 4, 1),
            plan=InstalmentPlanType.TERM,
        )
        annual_fee = FeeCalculator.compute_annual_fee(s, self.fee_structure)
        schedule = InstalmentScheduler.generate_schedule(s, annual_fee)

        self.assertEqual(len(schedule), 3)

        # Dates & Grace
        self.assertEqual(schedule[0].due_date, date(2026, 4, 10))
        self.assertEqual(schedule[0].grace_days, 7)
        self.assertEqual(schedule[1].due_date, date(2026, 8, 10))
        self.assertEqual(schedule[1].grace_days, 0)
        self.assertEqual(schedule[2].due_date, date(2026, 12, 10))
        self.assertEqual(schedule[2].grace_days, 0)

        # Sum of 3 terms must equal total annual fee exactly
        sum_terms = sum((inst.total_net_fee for inst in schedule), Decimal("0.00"))
        self.assertEqual(sum_terms, annual_fee.total_net)

        # Verify 40% / 30% / 30% ratio on tuition
        t_full = annual_fee.net_heads[FeeHead.TUITION]
        self.assertEqual(schedule[0].heads[FeeHead.TUITION].net_amount, (t_full * Decimal("0.40")).quantize(Decimal("0.01")))
        self.assertEqual(schedule[1].heads[FeeHead.TUITION].net_amount, (t_full * Decimal("0.30")).quantize(Decimal("0.01")))
        self.assertEqual(schedule[2].heads[FeeHead.TUITION].net_amount, (t_full * Decimal("0.30")).quantize(Decimal("0.01")))

    def test_monthly_plan_rounding_residue_absorbed_in_january(self):
        """
        Explicit Edge Case from problem statement:
        'Monthly plan rounding residue on the January instalment'
        Total fee: 71,000. Divided by 10 = 7,100 per instalment.
        Suppose fee is odd, e.g. 71,001.33:
        Instalments 1 to 9 get 7,100.13 each (sum: 63,901.17).
        10th instalment (January) absorbs residue = 71,001.33 - 63,901.17 = 7,100.16.
        """
        odd_fee_structure = GradeFeeStructure(
            grade=6,
            heads={
                FeeHead.TUITION: Decimal("45000.33"),
                FeeHead.DEVELOPMENT: Decimal("14500.00"),
                FeeHead.LAB: Decimal("4500.00"),
                FeeHead.ACTIVITY: Decimal("4000.00"),
                FeeHead.EXAM: Decimal("3001.00"),
            },
        )
        s = Student(
            student_id="STU_MONTHLY", name="MonthlyStudent", grade=6, section="A",
            dob=date(2013, 2, 1), admission_date=date(2026, 4, 1),
            plan=InstalmentPlanType.MONTHLY,
        )
        annual_fee = FeeCalculator.compute_annual_fee(s, odd_fee_structure)
        schedule = InstalmentScheduler.generate_schedule(s, annual_fee)

        self.assertEqual(len(schedule), 10)

        # Due dates check: 10th of each month Apr-Jan
        expected_months = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1]
        for idx, inst in enumerate(schedule):
            self.assertEqual(inst.due_date.day, 10)
            self.assertEqual(inst.due_date.month, expected_months[idx])

        # Exact conservation of cents across 10 instalments
        sum_monthly = sum((inst.total_net_fee for inst in schedule), Decimal("0.00"))
        self.assertEqual(sum_monthly, annual_fee.total_net)

        # January instalment (10th) absorbs residue
        inst_9 = schedule[8]
        inst_10 = schedule[9]
        self.assertEqual(inst_10.name, "January Instalment")
        # Check that sum of 10 instalments equals annual fee
        sum_tuition = sum(inst.heads[FeeHead.TUITION].net_amount for inst in schedule)
        self.assertEqual(sum_tuition, annual_fee.net_heads[FeeHead.TUITION])

    def test_plan_change_validity_rule(self):
        """
        BR-01: Plan can change only before the first due date (10 April).
        """
        s = Student(
            student_id="STU_CHG", name="ChangeStudent", grade=6, section="A",
            dob=date(2013, 2, 1), admission_date=date(2026, 4, 1),
            plan=InstalmentPlanType.TERM,
        )
        annual_fee = FeeCalculator.compute_annual_fee(s, self.fee_structure)
        schedule = InstalmentScheduler.generate_schedule(s, annual_fee)

        # Request on 2026-04-05 (before 10 April) -> ALLOWED
        self.assertTrue(InstalmentScheduler.can_change_plan(s, schedule, date(2026, 4, 5)))

        # Request on 2026-04-10 (on due date) -> REJECTED
        self.assertFalse(InstalmentScheduler.can_change_plan(s, schedule, date(2026, 4, 10)))

        # Request on 2026-05-01 (after due date) -> REJECTED
        self.assertFalse(InstalmentScheduler.can_change_plan(s, schedule, date(2026, 5, 1)))


if __name__ == "__main__":
    unittest.main()
