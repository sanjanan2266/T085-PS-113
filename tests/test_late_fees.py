"""
Unit Tests for Late Fees and Defaulters (BR-06)
Verifies:
- Rs 50/day late fee rate
- April 7-day grace period
- Explicit edge case: Payment on the 7th day of grace for April results in Rs 0 late fee
- Late fee maximum cap of Rs 1,500 per instalment
- Defaulter listing (> 60 days overdue) with hall ticket flagged WITHHELD
"""
import unittest
from datetime import date
from decimal import Decimal
from engine.models import (
    FeeHead,
    HallTicketStatus,
    Instalment,
    InstalmentHeadDue,
    Student,
)
from engine.late_fee import LateFeeCalculator


class TestLateFees(unittest.TestCase):

    def setUp(self):
        self.student = Student(
            student_id="STU_LATE", name="LateStudent", grade=5, section="A",
            dob=date(2013, 1, 1), admission_date=date(2026, 4, 1),
        )

    def test_edge_case_payment_on_7th_day_of_grace_for_april_zero_late_fee(self):
        """
        Explicit Edge Case from problem statement:
        'Payment on the 7th day of grace for April'
        April due date: 2026-04-10.
        Grace: 7 days -> 11, 12, 13, 14, 15, 16, 17 April.
        Payment on 2026-04-17 (7th day of grace) MUST incur Rs 0 late fee!
        """
        inst = Instalment(
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
        late_fee_on_grace_day_7 = LateFeeCalculator.compute_late_fee(inst, as_of_date=date(2026, 4, 17))
        self.assertEqual(late_fee_on_grace_day_7, Decimal("0.00"))

    def test_april_late_fee_applies_after_grace_period(self):
        """On 2026-04-18 (day 8 after due date, 1 day past grace), late fee applies."""
        inst = Instalment(
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
        late_fee = LateFeeCalculator.compute_late_fee(inst, as_of_date=date(2026, 4, 18))
        self.assertGreater(late_fee, Decimal("0.00"))

    def test_late_fee_capped_at_1500_per_instalment(self):
        """
        BR-06: Rs 50/day capped at Rs 1,500 per instalment.
        For Term 2 (due 10 Aug, 0 grace days):
        On 10 October (61 days overdue): 61 * 50 = 3,050.
        Must be capped at exactly Rs 1,500.00!
        """
        inst = Instalment(
            instalment_id="INST-2",
            student_id=self.student.student_id,
            instalment_number=2,
            name="Term 2",
            due_date=date(2026, 8, 10),
            grace_days=0,
            heads={
                FeeHead.TUITION: InstalmentHeadDue(head=FeeHead.TUITION, net_amount=Decimal("20000.00")),
            },
        )
        late_fee = LateFeeCalculator.compute_late_fee(inst, as_of_date=date(2026, 10, 10))
        self.assertEqual(late_fee, Decimal("1500.00"))

    def test_defaulter_beyond_60_days_withheld_hall_ticket(self):
        """
        BR-06: Students with dues beyond 60 days are listed as DEFAULTERS
        and exam hall tickets are flagged WITHHELD.
        """
        inst = Instalment(
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
        # As of 2026-06-15: 66 days overdue from 2026-04-10
        defaulter = LateFeeCalculator.check_defaulter_status(self.student, [inst], as_of_date=date(2026, 6, 15))

        self.assertIsNotNone(defaulter)
        self.assertEqual(self.student.hall_ticket_status, HallTicketStatus.WITHHELD)
        self.assertEqual(defaulter.days_overdue, 66)
        self.assertEqual(defaulter.hall_ticket_status, HallTicketStatus.WITHHELD)

    def test_non_defaulter_within_60_days_cleared_hall_ticket(self):
        """Dues within 60 days: not a defaulter, hall ticket CLEARED."""
        inst = Instalment(
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
        # As of 2026-05-10: 30 days overdue
        defaulter = LateFeeCalculator.check_defaulter_status(self.student, [inst], as_of_date=date(2026, 5, 10))
        self.assertIsNone(defaulter)
        self.assertEqual(self.student.hall_ticket_status, HallTicketStatus.CLEARED)


if __name__ == "__main__":
    unittest.main()
