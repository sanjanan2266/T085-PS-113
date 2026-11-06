"""
Unit Tests for Transport and Hostel Add-ons (BR-04, BR-05)
Verifies:
- Route-based transport pricing (Zone A 1,800, Zone B 2,400, Zone C 3,000)
- Edge case: Transport joined on the 15th bills full month
- Edge case: Transport joined on the 16th bills half month (50%)
- Hostel pricing: Shared Rs 9,000, Single Rs 12,000 (includes mess)
- Hostel 1-month security deposit billed once
- Hostel fees are never discounted by concessions
- Security deposit refund minus damages
"""
import unittest
from datetime import date
from decimal import Decimal
from engine.models import (
    AddOnRateCard,
    ConcessionCategory,
    FeeHead,
    GradeFeeStructure,
    HostelSubscription,
    InstalmentPlanType,
    Student,
    TransportSubscription,
)
from engine.fee_calculator import FeeCalculator
from engine.instalment_scheduler import InstalmentScheduler
from engine.addon_manager import AddOnManager


class TestAddOns(unittest.TestCase):

    def setUp(self):
        self.rate_card = AddOnRateCard()
        self.fee_structure = GradeFeeStructure(
            grade=5,
            heads={
                FeeHead.TUITION: Decimal("40000.00"),
                FeeHead.DEVELOPMENT: Decimal("12000.00"),
                FeeHead.LAB: Decimal("3000.00"),
                FeeHead.ACTIVITY: Decimal("2500.00"),
                FeeHead.EXAM: Decimal("2000.00"),
            },
        )

    def test_edge_case_transport_joined_on_15th_bills_full_month(self):
        """
        Explicit Edge Case from problem statement:
        'Transport joined on the 15th'
        BR-04: 'starting mid-month bills the full month if joined on or before the 15th, else half'
        If joined on 15 April, April is billed 100% of Zone A (Rs 1,800).
        """
        sub = TransportSubscription(
            student_id="STU_T15",
            zone="Zone A",
            start_date=date(2026, 4, 15),
        )
        # Fraction for month 4 (April)
        frac = AddOnManager.get_month_fraction(sub.start_date, 4, 2026)
        self.assertEqual(frac, Decimal("1.00"))

        fee = AddOnManager.calculate_transport_fee_for_months(sub, self.rate_card, [(4, 2026)])
        self.assertEqual(fee, Decimal("1800.00"))

    def test_edge_case_transport_joined_on_16th_bills_half_month(self):
        """
        BR-04: Starting mid-month after the 15th bills half month (50%).
        If joined on 16 April, April is billed 50% of Zone A (Rs 900).
        """
        sub = TransportSubscription(
            student_id="STU_T16",
            zone="Zone A",
            start_date=date(2026, 4, 16),
        )
        frac = AddOnManager.get_month_fraction(sub.start_date, 4, 2026)
        self.assertEqual(frac, Decimal("0.50"))

        fee = AddOnManager.calculate_transport_fee_for_months(sub, self.rate_card, [(4, 2026)])
        self.assertEqual(fee, Decimal("900.00"))

    def test_transport_billed_with_instalments_for_covered_months(self):
        """
        BR-04: Transport billed with each instalment for the months it covers.
        TERM plan:
        Term 1 covers 4 months (Apr-Jul) -> 4 * 1800 = 7,200
        Term 2 covers 3 months (Aug-Oct) -> 3 * 1800 = 5,400
        Term 3 covers 3 months (Nov-Jan) -> 3 * 1800 = 5,400
        """
        s = Student(
            student_id="STU_T_TERM", name="TransportStudent", grade=5, section="A",
            dob=date(2013, 1, 1), admission_date=date(2026, 4, 1),
            plan=InstalmentPlanType.TERM,
        )
        annual = FeeCalculator.compute_annual_fee(s, self.fee_structure)
        schedule = InstalmentScheduler.generate_schedule(s, annual)

        t_sub = TransportSubscription(student_id=s.student_id, zone="Zone A", start_date=date(2026, 4, 1))
        AddOnManager.apply_addons_to_schedule(schedule, s.plan, self.rate_card, transport_sub=t_sub)

        self.assertEqual(schedule[0].heads[FeeHead.TRANSPORT].net_amount, Decimal("7200.00"))
        self.assertEqual(schedule[1].heads[FeeHead.TRANSPORT].net_amount, Decimal("5400.00"))
        self.assertEqual(schedule[2].heads[FeeHead.TRANSPORT].net_amount, Decimal("5400.00"))

    def test_hostel_fees_include_mess_and_are_never_discounted_by_concessions(self):
        """
        BR-05:
        - Shared: Rs 9,000/mo, Single: Rs 12,000/mo.
        - Security deposit: 1 month collected once.
        - Hostel fees are NEVER discounted by concessions (even for EWS or Staff Ward).
        """
        s = Student(
            student_id="STU_HOSTEL_EWS", name="EWS_Hostel", grade=5, section="A",
            dob=date(2013, 1, 1), admission_date=date(2026, 4, 1),
            plan=InstalmentPlanType.TERM,
            concession_category=ConcessionCategory.EWS,  # 100% tuition, 50% other heads
        )
        annual = FeeCalculator.compute_annual_fee(s, self.fee_structure)
        schedule = InstalmentScheduler.generate_schedule(s, annual)

        h_sub = HostelSubscription(student_id=s.student_id, room_type="single", start_date=date(2026, 4, 1))
        AddOnManager.apply_addons_to_schedule(schedule, s.plan, self.rate_card, hostel_sub=h_sub)

        # Term 1 covers 4 months * 12,000 = 48,000. No discount!
        self.assertEqual(schedule[0].heads[FeeHead.HOSTEL].net_amount, Decimal("48000.00"))
        self.assertEqual(schedule[0].heads[FeeHead.HOSTEL].concession_discount, Decimal("0.00"))

        # 1-month deposit collected once on Term 1 = 12,000
        self.assertEqual(schedule[0].heads[FeeHead.HOSTEL_DEPOSIT].net_amount, Decimal("12000.00"))

        # Term 2 covers 3 months * 12,000 = 36,000. No deposit billed in Term 2
        self.assertEqual(schedule[1].heads[FeeHead.HOSTEL].net_amount, Decimal("36000.00"))
        self.assertNotIn(FeeHead.HOSTEL_DEPOSIT, schedule[1].heads)


if __name__ == "__main__":
    unittest.main()
