"""
Unit Tests for Payment Application Waterfall (BR-07)
Verifies:
- Waterfall order: Late fees -> Oldest instalment tuition -> Other heads -> Add-ons -> Next instalment
- Partial payments applied strictly according to precedence
- Overpayment becomes advance credit
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


class TestPaymentWaterfall(unittest.TestCase):

    def setUp(self):
        self.student = Student(
            student_id="STU_WATERFALL", name="WaterfallStudent", grade=5, section="A",
            dob=date(2013, 1, 1), admission_date=date(2026, 4, 1),
        )

        # Term 1:
        # Tuition: 10,000, Development: 4,000, Transport: 2,000.
        # Due 2026-04-10 with 7 days grace.
        # On 2026-04-20 (10 days overdue), late fee is exactly 10 * 50 = 500.
        self.inst1 = Instalment(
            instalment_id="INST-1",
            student_id=self.student.student_id,
            instalment_number=1,
            name="Term 1",
            due_date=date(2026, 4, 10),
            grace_days=7,
            heads={
                FeeHead.TUITION: InstalmentHeadDue(head=FeeHead.TUITION, net_amount=Decimal("10000.00")),
                FeeHead.DEVELOPMENT: InstalmentHeadDue(head=FeeHead.DEVELOPMENT, net_amount=Decimal("4000.00")),
                FeeHead.TRANSPORT: InstalmentHeadDue(head=FeeHead.TRANSPORT, net_amount=Decimal("2000.00")),
            },
        )

        # Term 2:
        # Tuition: 10,000, Development: 4,000. Total = 14,000
        self.inst2 = Instalment(
            instalment_id="INST-2",
            student_id=self.student.student_id,
            instalment_number=2,
            name="Term 2",
            due_date=date(2026, 8, 10),
            grace_days=0,
            heads={
                FeeHead.TUITION: InstalmentHeadDue(head=FeeHead.TUITION, net_amount=Decimal("10000.00")),
                FeeHead.DEVELOPMENT: InstalmentHeadDue(head=FeeHead.DEVELOPMENT, net_amount=Decimal("4000.00")),
            },
        )
        self.schedule = [self.inst1, self.inst2]

    def test_waterfall_order_late_fee_first_then_tuition(self):
        """Payment of Rs 3,000 clears Rs 500 late fee first, then Rs 2,500 towards tuition."""
        record, _ = PaymentWaterfallProcessor.apply_payment(
            student=self.student,
            schedule=self.schedule,
            payment_id="PMT_01",
            payment_date=date(2026, 4, 20),
            amount=Decimal("3000.00"),
            payment_mode=PaymentMode.UPI,
        )
        self.assertEqual(self.inst1.late_fee_paid, Decimal("500.00"))
        self.assertEqual(self.inst1.heads[FeeHead.TUITION].paid_amount, Decimal("2500.00"))
        self.assertEqual(self.inst1.heads[FeeHead.DEVELOPMENT].paid_amount, Decimal("0.00"))
        self.assertEqual(self.inst1.heads[FeeHead.TRANSPORT].paid_amount, Decimal("0.00"))

    def test_waterfall_order_tuition_then_other_heads_then_addons(self):
        """
        Payment of Rs 15,000 on Term 1:
        1. Late fee: 500
        2. Tuition: 10,000
        3. Development (other head): 4,000
        4. Transport (add-on): remaining 500 out of 2,000
        """
        record, _ = PaymentWaterfallProcessor.apply_payment(
            student=self.student,
            schedule=self.schedule,
            payment_id="PMT_02",
            payment_date=date(2026, 4, 20),
            amount=Decimal("15000.00"),
            payment_mode=PaymentMode.BANK_TRANSFER,
        )
        self.assertEqual(self.inst1.late_fee_paid, Decimal("500.00"))
        self.assertEqual(self.inst1.heads[FeeHead.TUITION].paid_amount, Decimal("10000.00"))
        self.assertEqual(self.inst1.heads[FeeHead.DEVELOPMENT].paid_amount, Decimal("4000.00"))
        self.assertEqual(self.inst1.heads[FeeHead.TRANSPORT].paid_amount, Decimal("500.00"))

    def test_waterfall_flows_to_next_instalment(self):
        """
        Term 1 total is 16,500 (500 late + 10k tuition + 4k dev + 2k transport).
        Payment of Rs 20,000:
        Clears all 16,500 of Term 1, and remaining 3,500 applies to Term 2 tuition!
        """
        record, _ = PaymentWaterfallProcessor.apply_payment(
            student=self.student,
            schedule=self.schedule,
            payment_id="PMT_03",
            payment_date=date(2026, 4, 20),
            amount=Decimal("20000.00"),
            payment_mode=PaymentMode.CHEQUE,
        )
        self.assertTrue(self.inst1.is_fully_paid)
        self.assertEqual(self.inst2.heads[FeeHead.TUITION].paid_amount, Decimal("3500.00"))
        self.assertEqual(self.student.advance_credit, Decimal("0.00"))

    def test_overpayment_becomes_advance_credit(self):
        """
        Total dues across both instalments: 16,500 + 14,000 = 30,500.
        Payment of Rs 35,000:
        Clears both instalments fully, remaining Rs 4,500 becomes advance credit.
        """
        record, _ = PaymentWaterfallProcessor.apply_payment(
            student=self.student,
            schedule=self.schedule,
            payment_id="PMT_04",
            payment_date=date(2026, 4, 20),
            amount=Decimal("35000.00"),
            payment_mode=PaymentMode.CHEQUE,
        )
        self.assertTrue(self.inst1.is_fully_paid)
        self.assertTrue(self.inst2.is_fully_paid)
        self.assertEqual(record.advance_credit_generated, Decimal("4500.00"))
        self.assertEqual(self.student.advance_credit, Decimal("4500.00"))

    def test_apply_advance_credit_reduces_existing_balance_correctly(self):
        self.student.advance_credit = Decimal("1000.00")

        self.inst1.heads[FeeHead.TUITION].net_amount = Decimal("400.00")
        self.inst1.heads[FeeHead.DEVELOPMENT].net_amount = Decimal("0.00")
        self.inst1.heads[FeeHead.TRANSPORT].net_amount = Decimal("0.00")
        self.inst2.heads[FeeHead.TUITION].net_amount = Decimal("0.00")
        self.inst2.heads[FeeHead.DEVELOPMENT].net_amount = Decimal("0.00")

        PaymentWaterfallProcessor.apply_advance_credit(
            student=self.student,
            schedule=self.schedule,
           as_of_date=date(2026, 4, 17),
        )

        self.assertEqual(self.student.advance_credit, Decimal("600.00"))

    def test_apply_advance_credit_keeps_balance_when_no_dues(self):
        self.student.advance_credit = Decimal("1000.00")

        for instalment in self.schedule:
            for head in instalment.heads.values():
                head.net_amount = Decimal("0.00")

        PaymentWaterfallProcessor.apply_advance_credit(
            student=self.student,
            schedule=self.schedule,
            as_of_date=date(2026, 4, 20),
        )

        self.assertEqual(self.student.advance_credit, Decimal("1000.00"))
if __name__ == "__main__":
    unittest.main()
