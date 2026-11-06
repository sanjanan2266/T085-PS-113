"""
Unit Tests for Cheque Bounce Rules (BR-10)
Verifies:
- Rs 500 charge debited
- Reversal of payment allocations
- Retroactive late fee recomputation as if payment was never made
- Explicit edge case: Bounced cheque for an instalment already past the late-fee cap
"""
import unittest
from datetime import date
from decimal import Decimal
from engine.models import (
    FeeHead,
    Instalment,
    InstalmentHeadDue,
    PaymentMode,
    Student,
)
from engine.payment_waterfall import PaymentWaterfallProcessor


class TestChequeBounce(unittest.TestCase):

    def setUp(self):
        self.student = Student(
            student_id="STU_BOUNCE", name="BounceStudent", grade=5, section="A",
            dob=date(2013, 1, 1), admission_date=date(2026, 4, 1),
        )
        self.inst1 = Instalment(
            instalment_id="INST-1",
            student_id=self.student.student_id,
            instalment_number=1,
            name="Term 1",
            due_date=date(2026, 4, 10),
            grace_days=7,
            heads={
                FeeHead.TUITION: InstalmentHeadDue(head=FeeHead.TUITION, net_amount=Decimal("20000.00")),
            },
        )
        self.schedule = [self.inst1]

    def test_cheque_bounce_applies_500_fee_and_reverses_allocation(self):
        """Cheque bounce charges Rs 500, reverses payment, and recomputes late fees."""
        # Record payment of 20,000 on 2026-04-15
        rec, _ = PaymentWaterfallProcessor.apply_payment(
            student=self.student,
            schedule=self.schedule,
            payment_id="PMT_BOUNCE_1",
            payment_date=date(2026, 4, 15),
            amount=Decimal("20000.00"),
            payment_mode=PaymentMode.CHEQUE,
            reference="CHQ-1001",
        )
        self.assertEqual(self.inst1.heads[FeeHead.TUITION].paid_amount, Decimal("20000.00"))

        # Bounce happens on 2026-05-15 (35 days after 2026-04-10)
        bounce_txns = PaymentWaterfallProcessor.process_cheque_bounce(
            student=self.student,
            schedule=self.schedule,
            payment_record=rec,
            bounce_date=date(2026, 5, 15),
            all_payments_for_student=[rec],
        )

        self.assertTrue(rec.is_bounced)
        # Tuition paid reversed back to 0
        self.assertEqual(self.inst1.heads[FeeHead.TUITION].paid_amount, Decimal("0.00"))

        # Cheque bounce fee txn exists for Rs 500
        bounce_chg_txn = next(t for t in bounce_txns if t.head == FeeHead.CHEQUE_BOUNCE)
        self.assertEqual(bounce_chg_txn.amount, Decimal("500.00"))

        # Retroactive late fee recomputed: on 2026-05-15 (past April grace)
        self.assertGreater(self.inst1.late_fee_assessed, Decimal("0.00"))

    def test_edge_case_bounced_cheque_for_instalment_already_past_late_fee_cap(self):
        """
        Explicit Edge Case from problem statement:
        'Bounced cheque for an instalment already past the late-fee cap'
        Instalment due date was 2026-04-10.
        Cheque paid on 2026-04-15.
        Cheque bounces on 2026-08-01 (113 days after due date, way past 30 days needed for cap).
        Late fee recomputed MUST hit the max cap of Rs 1,500.00!
        Plus Rs 500 bounce charge debited.
        """
        rec, _ = PaymentWaterfallProcessor.apply_payment(
            student=self.student,
            schedule=self.schedule,
            payment_id="PMT_BOUNCE_CAP",
            payment_date=date(2026, 4, 15),
            amount=Decimal("20000.00"),
            payment_mode=PaymentMode.CHEQUE,
            reference="CHQ-9999",
        )
        self.inst1.heads[FeeHead.TUITION].paid_amount = Decimal("20000.00")

        # Cheque bounces on 2026-08-01
        bounce_txns = PaymentWaterfallProcessor.process_cheque_bounce(
            student=self.student,
            schedule=self.schedule,
            payment_record=rec,
            bounce_date=date(2026, 8, 1),
            all_payments_for_student=[rec],
        )

        # 1. Late fee recomputed at max cap: Rs 1,500
        self.assertEqual(self.inst1.late_fee_assessed, Decimal("1500.00"))

        # 2. Rs 500 bounce penalty charged
        bounce_fee_txn = next(t for t in bounce_txns if t.head == FeeHead.CHEQUE_BOUNCE)
        self.assertEqual(bounce_fee_txn.amount, Decimal("500.00"))


if __name__ == "__main__":
    unittest.main()
