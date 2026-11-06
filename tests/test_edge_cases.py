"""
Consolidated Suite for All 8 Explicit Edge Cases Specified in PS-113:
1. Staff ward who is also a 3rd sibling (combined cap of 60%)
2. Transport joined on the 15th (bills full month)
3. Payment on the 7th day of grace for April (0 late fee)
4. Eldest sibling withdrawing mid-term with re-ranking
5. Bounced cheque for an instalment already past the late-fee cap (recomputed at 1500 cap + 500 charge)
6. Mid-year admission on the 16th (month does not count)
7. Withdrawal notice given exactly 30 days before the term start (qualifies for full unstarted term refund)
8. Monthly plan rounding residue on the January instalment (last instalment absorbs rounding)
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
    Instalment,
    InstalmentHeadDue,
    InstalmentPlanType,
    PaymentMode,
    Student,
    StudentStatus,
    TransportSubscription,
)
from engine.fee_calculator import FeeCalculator
from engine.instalment_scheduler import InstalmentScheduler
from engine.addon_manager import AddOnManager
from engine.late_fee import LateFeeCalculator
from engine.payment_waterfall import PaymentWaterfallProcessor
from engine.admission_manager import AdmissionManager
from engine.withdrawal_manager import WithdrawalManager


class TestExplicitEdgeCases(unittest.TestCase):

    def setUp(self):
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
        self.rate_card = AddOnRateCard()

    # Edge Case 1: Staff ward who is also a 3rd sibling (combined cap)
    def test_edge_case_1_staff_ward_third_sibling_combined_cap(self):
        s1 = Student(student_id="S1", name="Eldest", grade=5, section="A", dob=date(2010, 1, 1), admission_date=date(2026, 4, 1), sibling_group_id="G1")
        s2 = Student(student_id="S2", name="Second", grade=5, section="A", dob=date(2012, 1, 1), admission_date=date(2026, 4, 1), sibling_group_id="G1")
        s3 = Student(
            student_id="S3", name="ThirdStaff", grade=5, section="A",
            dob=date(2014, 1, 1), admission_date=date(2026, 4, 1),
            concession_category=ConcessionCategory.STAFF_WARD,
            sibling_group_id="G1",
        )
        annual = FeeCalculator.compute_annual_fee(s3, self.fee_structure, [s1, s2, s3])
        # Staff (50%) + 3rd (20%) = 70% raw -> capped at 60%
        self.assertEqual(annual.concession_breakdown.combined_tuition_pct_raw, Decimal("0.70"))
        self.assertEqual(annual.concession_breakdown.combined_tuition_pct_effective, Decimal("0.60"))
        self.assertTrue(annual.concession_breakdown.tuition_cap_applied)
        # Tuition: 40,000 * 0.40 = 16,000 net
        self.assertEqual(annual.net_heads[FeeHead.TUITION], Decimal("16000.00"))

    # Edge Case 2: Transport joined on the 15th
    def test_edge_case_2_transport_joined_on_15th_bills_full_month(self):
        sub = TransportSubscription(student_id="S_T15", zone="Zone A", start_date=date(2026, 4, 15))
        frac = AddOnManager.get_month_fraction(sub.start_date, 4, 2026)
        self.assertEqual(frac, Decimal("1.00"))
        amt = AddOnManager.calculate_transport_fee_for_months(sub, self.rate_card, [(4, 2026)])
        self.assertEqual(amt, Decimal("1800.00"))

    # Edge Case 3: Payment on the 7th day of grace for April
    def test_edge_case_3_payment_on_7th_day_of_grace_for_april(self):
        inst = Instalment(
            instalment_id="INST-1", student_id="STU", instalment_number=1,
            name="Term 1", due_date=date(2026, 4, 10), grace_days=7,
            heads={FeeHead.TUITION: InstalmentHeadDue(head=FeeHead.TUITION, net_amount=Decimal("15000.00"))},
        )
        late_fee = LateFeeCalculator.compute_late_fee(inst, as_of_date=date(2026, 4, 17))
        self.assertEqual(late_fee, Decimal("0.00"))

    # Edge Case 4: Eldest sibling withdrawing mid-term with re-ranking
    def test_edge_case_4_eldest_sibling_withdrawing_mid_term_re_ranking(self):
        s1 = Student(student_id="S1", name="Eldest", grade=5, section="A", dob=date(2010, 1, 1), admission_date=date(2026, 4, 1), sibling_group_id="G_RERANK")
        s2 = Student(student_id="S2", name="Second", grade=5, section="A", dob=date(2012, 1, 1), admission_date=date(2026, 4, 1), sibling_group_id="G_RERANK")
        s3 = Student(student_id="S3", name="Third", grade=5, section="A", dob=date(2014, 1, 1), admission_date=date(2026, 4, 1), sibling_group_id="G_RERANK")
        siblings = [s1, s2, s3]

        schedules = {
            s.student_id: InstalmentScheduler.generate_schedule(s, FeeCalculator.compute_annual_fee(s, self.fee_structure, siblings))
            for s in siblings
        }

        # Eldest withdraws
        s1.status = StudentStatus.WITHDRAWN
        WithdrawalManager.re_rank_siblings_after_withdrawal(
            withdrawn_student=s1,
            sibling_students=siblings,
            fee_structures={5: self.fee_structure},
            all_schedules=schedules,
            effective_from_term=2,
        )

        # S2 is now eldest -> 0% concession on Term 2 & 3: 40,000 * 0.30 = 12,000
        self.assertEqual(schedules["S2"][1].heads[FeeHead.TUITION].net_amount, Decimal("12000.00"))
        # S3 is now 2nd child -> 10% concession on Term 2 & 3: 40,000 * 0.90 * 0.30 = 10,800
        self.assertEqual(schedules["S3"][1].heads[FeeHead.TUITION].net_amount, Decimal("10800.00"))

    # Edge Case 5: Bounced cheque for an instalment already past the late-fee cap
    def test_edge_case_5_bounced_cheque_for_instalment_past_late_fee_cap(self):
        st = Student(student_id="STU", name="B", grade=5, section="A", dob=date(2013, 1, 1), admission_date=date(2026, 4, 1))
        inst = Instalment(
            instalment_id="INST-1", student_id="STU", instalment_number=1,
            name="Term 1", due_date=date(2026, 4, 10),
            heads={FeeHead.TUITION: InstalmentHeadDue(head=FeeHead.TUITION, net_amount=Decimal("15000.00"))},
        )
        rec, _ = PaymentWaterfallProcessor.apply_payment(
            student=st, schedule=[inst], payment_id="PMT_BOUNCE",
            payment_date=date(2026, 4, 12), amount=Decimal("15000.00"),
            payment_mode=PaymentMode.CHEQUE, reference="CHQ-777",
        )
        # Bounce on 2026-08-15 (127 days overdue, cap is reached at 30 days)
        txns = PaymentWaterfallProcessor.process_cheque_bounce(
            student=st, schedule=[inst], payment_record=rec,
            bounce_date=date(2026, 8, 15), all_payments_for_student=[rec],
        )
        # Late fee is capped at exactly 1,500
        self.assertEqual(inst.late_fee_assessed, Decimal("1500.00"))
        # Cheque bounce fee charged is 500
        bounce_fee = next(t.amount for t in txns if t.head == FeeHead.CHEQUE_BOUNCE)
        self.assertEqual(bounce_fee, Decimal("500.00"))

    # Edge Case 6: Mid-year admission on the 16th
    def test_edge_case_6_mid_year_admission_on_16th_does_not_count_month(self):
        count = AdmissionManager.calculate_remaining_months_count(date(2026, 8, 16))
        # August does not count -> only Sep, Oct, Nov, Dec, Jan = 5 months
        self.assertEqual(count, 5)
        st = Student(student_id="STU_ADM16", name="Mid16", grade=5, section="A", dob=date(2013, 1, 1), admission_date=date(2026, 8, 16), plan=InstalmentPlanType.TERM)
        ann, sched = AdmissionManager.enrol_student(st, self.fee_structure, [st])
        # Tuition pro-rated to 5/10 = 50%: 40,000 * 0.50 = 20,000
        self.assertEqual(ann.net_heads[FeeHead.TUITION], Decimal("20000.00"))
        # Development fee is NEVER pro-rated: 12,000 full
        self.assertEqual(ann.net_heads[FeeHead.DEVELOPMENT], Decimal("12000.00"))
        # Flat admission fee: 10,000
        self.assertEqual(ann.net_heads[FeeHead.ADMISSION], Decimal("10000.00"))

    # Edge Case 7: Withdrawal notice given exactly 30 days before the term start
    def test_edge_case_7_withdrawal_notice_given_exactly_30_days_before_term_start(self):
        st = Student(student_id="STU_W", name="W", grade=5, section="A", dob=date(2013, 1, 1), admission_date=date(2026, 4, 1), plan=InstalmentPlanType.TERM)
        ann = FeeCalculator.compute_annual_fee(st, self.fee_structure)
        sched = InstalmentScheduler.generate_schedule(st, ann)
        # Term 2 tuition paid in advance (12,000)
        sched[1].heads[FeeHead.TUITION].paid_amount = Decimal("12000.00")
        # Notice on 2026-07-02 (exactly 30 days before 2026-08-01 Term 2 start)
        t_ref, _, _ = WithdrawalManager.process_withdrawal(st, sched, date(2026, 7, 10), date(2026, 7, 2))
        self.assertEqual(t_ref, Decimal("12000.00"))

    # Edge Case 8: Monthly plan rounding residue on the January instalment
    def test_edge_case_8_monthly_plan_rounding_residue_absorbed_in_january(self):
        odd_fee_struct = GradeFeeStructure(
            grade=5,
            heads={FeeHead.TUITION: Decimal("40001.33"), FeeHead.DEVELOPMENT: Decimal("12000.00")},
        )
        st = Student(student_id="STU_M", name="M", grade=5, section="A", dob=date(2013, 1, 1), admission_date=date(2026, 4, 1), plan=InstalmentPlanType.MONTHLY)
        ann = FeeCalculator.compute_annual_fee(st, odd_fee_struct)
        sched = InstalmentScheduler.generate_schedule(st, ann)

        self.assertEqual(len(sched), 10)
        sum_tuition = sum(inst.heads[FeeHead.TUITION].net_amount for inst in sched)
        self.assertEqual(sum_tuition, Decimal("40001.33"))

        # First 9 instalments get quantize(40001.33 / 10) = 4000.13 each (total: 36001.17)
        # January (10th) instalment absorbs residue = 40001.33 - 36001.17 = 4000.16
        self.assertEqual(sched[8].heads[FeeHead.TUITION].net_amount, Decimal("4000.13"))
        self.assertEqual(sched[9].heads[FeeHead.TUITION].net_amount, Decimal("4000.16"))
        self.assertEqual(sched[9].name, "January Instalment")


if __name__ == "__main__":
    unittest.main()
