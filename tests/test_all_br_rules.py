"""
Comprehensive Test Suite for Every Business Rule (BR-01 through BR-12)
Week 3 Requirement: "Every business rule implemented; every edge case handled; tests for every BR-ID"
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
    TCStatus,
    TransportSubscription,
)
from engine.fee_calculator import FeeCalculator
from engine.instalment_scheduler import InstalmentScheduler
from engine.addon_manager import AddOnManager
from engine.late_fee import LateFeeCalculator
from engine.payment_waterfall import PaymentWaterfallProcessor
from engine.admission_manager import AdmissionManager
from engine.withdrawal_manager import WithdrawalManager
from engine.fee_revision import FeeRevisionManager


class TestAllBusinessRules(unittest.TestCase):

    def setUp(self):
        # Standard fee card for Grade 5:
        # Tuition: 40,000, Dev: 12,000, Lab: 3,000, Activity: 2,500, Exam: 2,000 (Total: 59,500)
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

    # -------------------------------------------------------------
    # BR-01: Instalment Plans
    # -------------------------------------------------------------
    def test_BR_01_annual_plan_tuition_discount(self):
        """BR-01: ANNUAL plan grants exactly 3% discount on net tuition."""
        st = Student("S1", "A", 5, "A", admission_date=date(2026, 4, 1), dob=date(2013, 1, 1), plan=InstalmentPlanType.ANNUAL)
        annual = FeeCalculator.compute_annual_fee(st, self.fee_structure)
        sched = InstalmentScheduler.generate_schedule(st, annual)
        self.assertEqual(len(sched), 1)
        self.assertEqual(sched[0].due_date, date(2026, 4, 10))
        # 3% of 40,000 = 1,200. Net tuition = 38,800
        self.assertEqual(annual.plan_discounts[FeeHead.TUITION], Decimal("1200.00"))
        self.assertEqual(sched[0].heads[FeeHead.TUITION].net_amount, Decimal("38800.00"))

    def test_BR_01_term_plan_40_30_30_split(self):
        """BR-01: TERM plan splits into 3 instalments: 40% on 10 Apr, 30% on 10 Aug, 30% on 10 Dec."""
        st = Student("S2", "B", 5, "A", admission_date=date(2026, 4, 1), dob=date(2013, 1, 1), plan=InstalmentPlanType.TERM)
        annual = FeeCalculator.compute_annual_fee(st, self.fee_structure)
        sched = InstalmentScheduler.generate_schedule(st, annual)
        self.assertEqual(len(sched), 3)
        self.assertEqual(sched[0].due_date, date(2026, 4, 10))
        self.assertEqual(sched[1].due_date, date(2026, 8, 10))
        self.assertEqual(sched[2].due_date, date(2026, 12, 10))
        # Tuition 40,000 -> 16,000 (40%), 12,000 (30%), 12,000 (30%)
        self.assertEqual(sched[0].heads[FeeHead.TUITION].net_amount, Decimal("16000.00"))
        self.assertEqual(sched[1].heads[FeeHead.TUITION].net_amount, Decimal("12000.00"))
        self.assertEqual(sched[2].heads[FeeHead.TUITION].net_amount, Decimal("12000.00"))

    def test_BR_01_monthly_plan_rounding_absorbed_in_january(self):
        """BR-01: MONTHLY plan has 10 equal instalments; January absorbs rounding residue."""
        odd_fee = GradeFeeStructure(5, {FeeHead.TUITION: Decimal("40001.33"), FeeHead.DEVELOPMENT: Decimal("12000.00")})
        st = Student("S3", "C", 5, "A", admission_date=date(2026, 4, 1), dob=date(2013, 1, 1), plan=InstalmentPlanType.MONTHLY)
        annual = FeeCalculator.compute_annual_fee(st, odd_fee)
        sched = InstalmentScheduler.generate_schedule(st, annual)
        self.assertEqual(len(sched), 10)
        # 1-9 instalments get 4000.13, 10th gets 4000.16
        self.assertEqual(sched[8].heads[FeeHead.TUITION].net_amount, Decimal("4000.13"))
        self.assertEqual(sched[9].heads[FeeHead.TUITION].net_amount, Decimal("4000.16"))
        self.assertEqual(sum(i.heads[FeeHead.TUITION].net_amount for i in sched), Decimal("40001.33"))

    def test_BR_01_plan_change_restricted_after_first_due_date(self):
        """BR-01: Plan can change only before the first due date (10 April)."""
        st = Student("S4", "D", 5, "A", admission_date=date(2026, 4, 1), dob=date(2013, 1, 1), plan=InstalmentPlanType.TERM)
        sched = InstalmentScheduler.generate_schedule(st, FeeCalculator.compute_annual_fee(st, self.fee_structure))
        self.assertTrue(InstalmentScheduler.can_change_plan(st, sched, date(2026, 4, 9)))
        self.assertFalse(InstalmentScheduler.can_change_plan(st, sched, date(2026, 4, 10)))
        self.assertFalse(InstalmentScheduler.can_change_plan(st, sched, date(2026, 4, 11)))

    # -------------------------------------------------------------
    # BR-02: Sibling Concession & Dynamic Re-ranking
    # -------------------------------------------------------------
    def test_BR_02_sibling_concession_ranking(self):
        """BR-02: Eldest 0%, 2nd 10%, 3rd+ 20% on tuition."""
        s1 = Student("S1", "Eldest", 5, "A", admission_date=date(2026, 4, 1), dob=date(2010, 1, 1), sibling_group_id="FAM1")
        s2 = Student("S2", "Second", 5, "A", admission_date=date(2026, 4, 1), dob=date(2012, 1, 1), sibling_group_id="FAM1")
        s3 = Student("S3", "Third", 5, "A", admission_date=date(2026, 4, 1), dob=date(2014, 1, 1), sibling_group_id="FAM1")
        fam = [s1, s2, s3]
        ann1 = FeeCalculator.compute_annual_fee(s1, self.fee_structure, fam)
        ann2 = FeeCalculator.compute_annual_fee(s2, self.fee_structure, fam)
        ann3 = FeeCalculator.compute_annual_fee(s3, self.fee_structure, fam)
        self.assertEqual(ann1.concession_breakdown.sibling_tuition_pct, Decimal("0.00"))
        self.assertEqual(ann2.concession_breakdown.sibling_tuition_pct, Decimal("0.10"))
        self.assertEqual(ann3.concession_breakdown.sibling_tuition_pct, Decimal("0.20"))

    def test_BR_02_dynamic_reranking_when_eldest_withdraws(self):
        """BR-02: If eldest withdraws, concessions re-rank from next instalment."""
        s1 = Student("S1", "Eldest", 5, "A", admission_date=date(2026, 4, 1), dob=date(2010, 1, 1), sibling_group_id="FAM2")
        s2 = Student("S2", "Second", 5, "A", admission_date=date(2026, 4, 1), dob=date(2012, 1, 1), sibling_group_id="FAM2")
        fam = [s1, s2]
        schedules = {s.student_id: InstalmentScheduler.generate_schedule(s, FeeCalculator.compute_annual_fee(s, self.fee_structure, fam)) for s in fam}
        # S2 Term 2 tuition was 10% off: 40,000 * 0.90 * 0.30 = 10,800
        self.assertEqual(schedules["S2"][1].heads[FeeHead.TUITION].net_amount, Decimal("10800.00"))
        s1.status = StudentStatus.WITHDRAWN
        WithdrawalManager.re_rank_siblings_after_withdrawal(s1, fam, {5: self.fee_structure}, schedules, effective_from_term=2)
        # S2 now eldest: pays full 40,000 * 0.30 = 12,000
        self.assertEqual(schedules["S2"][1].heads[FeeHead.TUITION].net_amount, Decimal("12000.00"))

    # -------------------------------------------------------------
    # BR-03: Category Concessions & Combined 60% Cap
    # -------------------------------------------------------------
    def test_BR_03_category_rates_and_stacking_cap(self):
        """BR-03: Staff ward (50%) + 3rd sibling (20%) capped at 60% tuition concession."""
        s1 = Student("S1", "Eldest", 5, "A", admission_date=date(2026, 4, 1), dob=date(2010, 1, 1), sibling_group_id="FAM3")
        s2 = Student("S2", "Second", 5, "A", admission_date=date(2026, 4, 1), dob=date(2012, 1, 1), sibling_group_id="FAM3")
        s3 = Student("S3", "StaffThird", 5, "A", admission_date=date(2026, 4, 1), dob=date(2014, 1, 1), concession_category=ConcessionCategory.STAFF_WARD, sibling_group_id="FAM3")
        annual = FeeCalculator.compute_annual_fee(s3, self.fee_structure, [s1, s2, s3])
        self.assertEqual(annual.concession_breakdown.combined_tuition_pct_raw, Decimal("0.70"))
        self.assertEqual(annual.concession_breakdown.combined_tuition_pct_effective, Decimal("0.60"))
        self.assertTrue(annual.concession_breakdown.tuition_cap_applied)
        self.assertEqual(annual.net_heads[FeeHead.TUITION], Decimal("16000.00"))

    def test_BR_03_ews_concession(self):
        """BR-03: EWS gives 100% tuition and 50% on all other heads."""
        st = Student("S_EWS", "EWS", 5, "A", admission_date=date(2026, 4, 1), dob=date(2013, 1, 1), concession_category=ConcessionCategory.EWS)
        ann = FeeCalculator.compute_annual_fee(st, self.fee_structure)
        self.assertEqual(ann.net_heads[FeeHead.TUITION], Decimal("0.00"))
        self.assertEqual(ann.net_heads[FeeHead.DEVELOPMENT], Decimal("6000.00"))
        self.assertEqual(ann.net_heads[FeeHead.LAB], Decimal("1500.00"))
        self.assertEqual(ann.net_heads[FeeHead.ACTIVITY], Decimal("1250.00"))
        self.assertEqual(ann.net_heads[FeeHead.EXAM], Decimal("1000.00"))

    # -------------------------------------------------------------
    # BR-04: Transport Add-on
    # -------------------------------------------------------------
    def test_BR_04_transport_cutoff_15th_vs_16th(self):
        """BR-04: Joined on/before 15th bills full month; on/after 16th bills half month."""
        sub15 = TransportSubscription("S1", "Zone A", date(2026, 4, 15))
        sub16 = TransportSubscription("S2", "Zone A", date(2026, 4, 16))
        self.assertEqual(AddOnManager.calculate_transport_fee_for_months(sub15, self.rate_card, [(4, 2026)]), Decimal("1800.00"))
        self.assertEqual(AddOnManager.calculate_transport_fee_for_months(sub16, self.rate_card, [(4, 2026)]), Decimal("900.00"))

    # -------------------------------------------------------------
    # BR-05: Hostel Add-on
    # -------------------------------------------------------------
    def test_BR_05_hostel_deposit_and_non_discountable(self):
        """BR-05: 1-month deposit collected; never discounted by concessions."""
        st = Student("S_H", "H", 5, "A", date(2013, 1, 1), date(2026, 4, 1), concession_category=ConcessionCategory.EWS)
        sched = InstalmentScheduler.generate_schedule(st, FeeCalculator.compute_annual_fee(st, self.fee_structure))
        h_sub = HostelSubscription("S_H", "single", date(2026, 4, 1))
        AddOnManager.apply_addons_to_schedule(sched, st.plan, self.rate_card, hostel_sub=h_sub)
        self.assertEqual(sched[0].heads[FeeHead.HOSTEL_DEPOSIT].net_amount, Decimal("12000.00"))
        self.assertEqual(sched[0].heads[FeeHead.HOSTEL].net_amount, Decimal("48000.00"))
        self.assertEqual(sched[0].heads[FeeHead.HOSTEL].concession_discount, Decimal("0.00"))

    # -------------------------------------------------------------
    # BR-06: Late Fees & Defaulters
    # -------------------------------------------------------------
    def test_BR_06_late_fee_grace_and_cap(self):
        """BR-06: Rs 50/day, April 7-day grace, capped at Rs 1,500."""
        inst = Instalment("I1", "S", 1, "Term 1", date(2026, 4, 10), grace_days=7,
                          heads={FeeHead.TUITION: InstalmentHeadDue(head=FeeHead.TUITION, net_amount=Decimal("10000.00"))})
        # Grace day 7 (17 Apr): 0
        self.assertEqual(LateFeeCalculator.compute_late_fee(inst, date(2026, 4, 17)), Decimal("0.00"))
        # Day 8 (18 Apr): 50 * 8 = 400
        self.assertEqual(LateFeeCalculator.compute_late_fee(inst, date(2026, 4, 18)), Decimal("400.00"))
        # 60 days overdue: capped at 1,500
        self.assertEqual(LateFeeCalculator.compute_late_fee(inst, date(2026, 6, 15)), Decimal("1500.00"))

    def test_BR_06_defaulter_beyond_60_days_withheld_ticket(self):
        """BR-06: Overdue > 60 days flags DEFAULTER and WITHHELD hall ticket."""
        st = Student("S_DEF", "D", 5, "A", date(2013, 1, 1), date(2026, 4, 1))
        inst = Instalment("I1", "S_DEF", 1, "Term 1", date(2026, 4, 10),
                          heads={FeeHead.TUITION: InstalmentHeadDue(head=FeeHead.TUITION, net_amount=Decimal("10000.00"))})
        # Day 60 (9 June): Not defaulter
        self.assertIsNone(LateFeeCalculator.check_defaulter_status(st, [inst], date(2026, 6, 9)))
        # Day 61 (10 June): Defaulter
        rec = LateFeeCalculator.check_defaulter_status(st, [inst], date(2026, 6, 10))
        self.assertIsNotNone(rec)
        self.assertEqual(st.hall_ticket_status.value, "WITHHELD")

    # -------------------------------------------------------------
    # BR-07: Payment Application Waterfall
    # -------------------------------------------------------------
    def test_BR_07_waterfall_allocation_order(self):
        """BR-07: Late fee -> Tuition -> Other heads -> Add-ons -> Next instalment -> Advance credit."""
        st = Student("S_WF", "W", 5, "A", date(2013, 1, 1), date(2026, 4, 1))
        inst = Instalment("I1", "S_WF", 1, "Term 1", date(2026, 4, 10), grace_days=7,
                          heads={
                              FeeHead.TUITION: InstalmentHeadDue(FeeHead.TUITION, net_amount=Decimal("5000.00")),
                              FeeHead.DEVELOPMENT: InstalmentHeadDue(FeeHead.DEVELOPMENT, net_amount=Decimal("2000.00")),
                              FeeHead.TRANSPORT: InstalmentHeadDue(FeeHead.TRANSPORT, net_amount=Decimal("1000.00")),
                          })
        # Payment on 2026-04-20 (late fee is 500)
        rec, _ = PaymentWaterfallProcessor.apply_payment(st, [inst], "P1", date(2026, 4, 20), Decimal("10000.00"), PaymentMode.UPI)
        self.assertEqual(inst.late_fee_paid, Decimal("500.00"))
        self.assertEqual(inst.heads[FeeHead.TUITION].paid_amount, Decimal("5000.00"))
        self.assertEqual(inst.heads[FeeHead.DEVELOPMENT].paid_amount, Decimal("2000.00"))
        self.assertEqual(inst.heads[FeeHead.TRANSPORT].paid_amount, Decimal("1000.00"))
        # Overpayment 10000 - (500 + 5000 + 2000 + 1000 = 8500) = 1500 advance credit
        self.assertEqual(st.advance_credit, Decimal("1500.00"))

    # -------------------------------------------------------------
    # BR-08: Mid-Year Admission
    # -------------------------------------------------------------
    def test_BR_08_midyear_admission_prorating_and_rules(self):
        """BR-08: Admitted on 16 Aug excludes Aug; dev fee never pro-rated; Rs 10,000 admission fee."""
        st = Student(
            student_id="S_MY",
            name="MY",
            grade=5,
            section="A",
            admission_date=date(2026, 8, 16),
            dob=date(2013, 1, 1),
            plan=InstalmentPlanType.TERM,
        )
        ann, sched = AdmissionManager.enrol_student(st, self.fee_structure, [st])
        # 5 months remaining out of 10 -> 50% pro-rating
        self.assertEqual(ann.net_heads[FeeHead.TUITION], Decimal("20000.00"))
        self.assertEqual(ann.net_heads[FeeHead.DEVELOPMENT], Decimal("12000.00"))  # NEVER pro-rated
        self.assertEqual(ann.net_heads[FeeHead.ADMISSION], Decimal("10000.00"))

    # -------------------------------------------------------------
    # BR-09: Withdrawal Rules & TC Clearance
    # -------------------------------------------------------------
    def test_BR_09_withdrawal_notice_and_tc_clearance(self):
        """BR-09: Unstarted term refund with 30-day notice; TC blocked until dues are 0."""
        st = Student("S_W", "W", 5, "A", date(2013, 1, 1), date(2026, 4, 1), plan=InstalmentPlanType.TERM)
        sched = InstalmentScheduler.generate_schedule(st, FeeCalculator.compute_annual_fee(st, self.fee_structure))
        sched[1].heads[FeeHead.TUITION].paid_amount = Decimal("12000.00")

        # Notice on 2 July (30 days before 1 Aug) -> Refund granted
        t_ref, _, _ = WithdrawalManager.process_withdrawal(st, sched, date(2026, 7, 10), date(2026, 7, 2))
        self.assertEqual(t_ref, Decimal("12000.00"))

        # TC clearance check
        st2 = Student("S_TC", "TC", 5, "A", date(2013, 1, 1), date(2026, 4, 1))
        inst = Instalment("I1", "S_TC", 1, "Term 1", date(2026, 4, 10),
                          heads={FeeHead.TUITION: InstalmentHeadDue(FeeHead.TUITION, net_amount=Decimal("100.00"))})
        self.assertEqual(WithdrawalManager.evaluate_tc_clearance(st2, [inst]), TCStatus.BLOCKED_DUE_TO_DUES)
        inst.heads[FeeHead.TUITION].paid_amount = Decimal("100.00")
        self.assertEqual(WithdrawalManager.evaluate_tc_clearance(st2, [inst]), TCStatus.ISSUED)

    # -------------------------------------------------------------
    # BR-10: Cheque Bounce
    # -------------------------------------------------------------
    def test_BR_10_cheque_bounce_penalty_and_reversal(self):
        """BR-10: Rs 500 charge debited, payment reversed, late fee retroactively recomputed."""
        st = Student("S_B", "B", 5, "A", date(2013, 1, 1), date(2026, 4, 1))
        inst = Instalment("I1", "S_B", 1, "Term 1", date(2026, 4, 10), grace_days=7,
                          heads={FeeHead.TUITION: InstalmentHeadDue(FeeHead.TUITION, net_amount=Decimal("10000.00"))})
        rec, _ = PaymentWaterfallProcessor.apply_payment(st, [inst], "P1", date(2026, 4, 15), Decimal("10000.00"), PaymentMode.CHEQUE)
        # Bounces on 2026-08-01 (past cap)
        txns = PaymentWaterfallProcessor.process_cheque_bounce(st, [inst], rec, date(2026, 8, 1), [rec])
        self.assertTrue(rec.is_bounced)
        self.assertEqual(inst.heads[FeeHead.TUITION].paid_amount, Decimal("0.00"))
        self.assertEqual(inst.late_fee_assessed, Decimal("1500.00"))
        self.assertEqual(next(t.amount for t in txns if t.head == FeeHead.CHEQUE_BOUNCE), Decimal("500.00"))

    # -------------------------------------------------------------
    # BR-11: Fee Revision
    # -------------------------------------------------------------
    def test_BR_11_fee_revision_thresholds(self):
        """BR-11: <=10% applies to future instalments; >10% requires board approval for next year."""
        st = Student("S_R", "R", 5, "A", date(2013, 1, 1), date(2026, 4, 1))
        i1 = Instalment("I1", "S_R", 1, "T1", date(2026, 4, 10), heads={FeeHead.TUITION: InstalmentHeadDue(FeeHead.TUITION, net_amount=Decimal("10000.00"))})
        i2 = Instalment("I2", "S_R", 2, "T2", date(2026, 8, 10), heads={FeeHead.TUITION: InstalmentHeadDue(FeeHead.TUITION, net_amount=Decimal("10000.00"))})
        schedules = {"S_R": [i1, i2]}
        grades = {"S_R": 5}

        # 5% revision on 2026-07-01 -> Only T2 updated
        succ, _, cnt = FeeRevisionManager.apply_fee_revision(5, FeeHead.TUITION, Decimal("0.05"), date(2026, 7, 1), False, self.fee_structure, schedules, grades)
        self.assertTrue(succ)
        self.assertEqual(cnt, 1)
        self.assertEqual(i1.heads[FeeHead.TUITION].net_amount, Decimal("10000.00"))
        self.assertEqual(i2.heads[FeeHead.TUITION].net_amount, Decimal("10500.00"))

        # 15% without board approval -> REJECTED
        succ_reject, msg, _ = FeeRevisionManager.apply_fee_revision(5, FeeHead.TUITION, Decimal("0.15"), date(2026, 7, 1), False, self.fee_structure, schedules, grades)
        self.assertFalse(succ_reject)
        self.assertIn("REJECTED", msg)

    # -------------------------------------------------------------
    # BR-12: Full Precedence Pipeline
    # -------------------------------------------------------------
    def test_BR_12_full_precedence_pipeline(self):
        """
        BR-12: Category concession -> Sibling stacking -> 60% cap -> Plan discount -> Split -> Addons -> Late fees.
        """
        s1 = Student("S1", "Eldest", 5, "A", date(2010, 1, 1), date(2026, 4, 1), sibling_group_id="FAM_P")
        s2 = Student("S2", "Second", 5, "A", date(2012, 1, 1), date(2026, 4, 1), sibling_group_id="FAM_P")
        s3 = Student("S3", "ThirdStaffAnnual", 5, "A", date(2014, 1, 1), date(2026, 4, 1),
                     plan=InstalmentPlanType.ANNUAL, concession_category=ConcessionCategory.STAFF_WARD, sibling_group_id="FAM_P")
        annual = FeeCalculator.compute_annual_fee(s3, self.fee_structure, [s1, s2, s3])

        # Base tuition: 40,000
        # Category (50%) + Sibling (20%) = 70% -> Capped at 60%
        # Tuition after 60% concession = 16,000
        # 3% Annual plan discount on 16,000 = 480
        # Final Net Tuition = 16,000 - 480 = 15,520
        self.assertEqual(annual.concession_discounts[FeeHead.TUITION], Decimal("24000.00"))
        self.assertEqual(annual.plan_discounts[FeeHead.TUITION], Decimal("480.00"))
        self.assertEqual(annual.net_heads[FeeHead.TUITION], Decimal("15520.00"))


if __name__ == "__main__":
    unittest.main()
