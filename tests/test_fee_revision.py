"""
Unit Tests for Fee Revision Rules (BR-11)
Verifies:
- Mid-year fee revision up to 10% applies ONLY to instalments not yet due
- Fee revision above 10% requires BOARD_APPROVED flag and applies from next academic year
- Rejection of > 10% revision without board approval
"""
import unittest
from datetime import date
from decimal import Decimal
from engine.models import (
    FeeHead,
    GradeFeeStructure,
    Instalment,
    InstalmentHeadDue,
)
from engine.fee_revision import FeeRevisionManager


class TestFeeRevision(unittest.TestCase):

    def setUp(self):
        self.fee_structure = GradeFeeStructure(
            grade=5,
            heads={
                FeeHead.TUITION: Decimal("40000.00"),
                FeeHead.DEVELOPMENT: Decimal("12000.00"),
            },
        )
        # Term 1: due 2026-04-10 (past)
        self.inst1 = Instalment(
            instalment_id="INST-1",
            student_id="STU01",
            instalment_number=1,
            name="Term 1",
            due_date=date(2026, 4, 10),
            heads={FeeHead.TUITION: InstalmentHeadDue(head=FeeHead.TUITION, net_amount=Decimal("16000.00"))},
        )
        # Term 2: due 2026-08-10 (future relative to July)
        self.inst2 = Instalment(
            instalment_id="INST-2",
            student_id="STU01",
            instalment_number=2,
            name="Term 2",
            due_date=date(2026, 8, 10),
            heads={FeeHead.TUITION: InstalmentHeadDue(head=FeeHead.TUITION, net_amount=Decimal("12000.00"))},
        )
        self.schedule = [self.inst1, self.inst2]

    def test_mid_year_revision_up_to_10_percent_applies_only_to_future_instalments(self):
        """
        BR-11: A mid-year revision of up to 10% applies only to instalments not yet due.
        5% revision effective 2026-07-01:
        Term 1 (due 2026-04-10) is unchanged (remains 16,000).
        Term 2 (due 2026-08-10) receives 5% revision (+600 -> 12,600).
        """
        success, msg, count = FeeRevisionManager.apply_fee_revision(
            grade=5,
            head=FeeHead.TUITION,
            revision_percent=Decimal("0.05"),
            effective_date=date(2026, 7, 1),
            board_approved=False,
            fee_structure=self.fee_structure,
            all_student_schedules={"STU01": self.schedule},
            student_grades={"STU01": 5},
        )

        self.assertTrue(success)
        self.assertEqual(count, 1)  # Only Term 2 updated
        self.assertEqual(self.inst1.heads[FeeHead.TUITION].net_amount, Decimal("16000.00"))
        self.assertEqual(self.inst2.heads[FeeHead.TUITION].net_amount, Decimal("12600.00"))

    def test_revision_above_10_percent_rejected_without_board_approval(self):
        """
        BR-11: Revision above 10% requires BOARD_APPROVED flag.
        Without flag -> REJECTED.
        """
        success, msg, _ = FeeRevisionManager.apply_fee_revision(
            grade=5,
            head=FeeHead.TUITION,
            revision_percent=Decimal("0.15"),
            effective_date=date(2026, 7, 1),
            board_approved=False,
            fee_structure=self.fee_structure,
            all_student_schedules={"STU01": self.schedule},
            student_grades={"STU01": 5},
        )
        self.assertFalse(success)
        self.assertIn("REJECTED", msg)

    def test_revision_above_10_percent_approved_for_next_academic_year_only(self):
        """
        BR-11: Revision above 10% with BOARD_APPROVED applies from next academic year.
        Does NOT alter current year instalments.
        """
        success, msg, count = FeeRevisionManager.apply_fee_revision(
            grade=5,
            head=FeeHead.TUITION,
            revision_percent=Decimal("0.15"),
            effective_date=date(2026, 7, 1),
            board_approved=True,
            fee_structure=self.fee_structure,
            all_student_schedules={"STU01": self.schedule},
            student_grades={"STU01": 5},
        )
        self.assertTrue(success)
        self.assertIn("NEXT ACADEMIC YEAR", msg)
        self.assertEqual(count, 0)  # Current instalments untouched


if __name__ == "__main__":
    unittest.main()
