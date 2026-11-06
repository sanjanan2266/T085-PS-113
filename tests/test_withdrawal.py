"""
Unit Tests for Withdrawal Rules, TC Clearance, and Sibling Re-ranking (BR-09, BR-02)
Verifies:
- 30-day notice rule for tuition refund on unstarted terms
- Explicit edge case: Notice given exactly 30 days before term start qualifies for refund
- Other heads are non-refundable
- Withdrawal in last term refunds nothing
- TC is issued ONLY when dues are zero
- Sibling re-ranking: Eldest sibling withdrawing mid-term re-ranks remaining siblings from next instalment
"""
import unittest
from datetime import date
from decimal import Decimal
from engine.models import (
    FeeHead,
    GradeFeeStructure,
    Instalment,
    InstalmentHeadDue,
    InstalmentPlanType,
    Student,
    StudentStatus,
    TCStatus,
)
from engine.withdrawal_manager import WithdrawalManager
from engine.fee_calculator import FeeCalculator
from engine.instalment_scheduler import InstalmentScheduler


class TestWithdrawal(unittest.TestCase):

    def setUp(self):
        # Grade 8: Tuition: 51,000 (Term 1: 20,400, Term 2: 15,300, Term 3: 15,300)
        self.fee_structure = GradeFeeStructure(
            grade=8,
            heads={
                FeeHead.TUITION: Decimal("51000.00"),
                FeeHead.DEVELOPMENT: Decimal("15500.00"),
                FeeHead.LAB: Decimal("5700.00"),
                FeeHead.ACTIVITY: Decimal("4400.00"),
                FeeHead.EXAM: Decimal("3400.00"),
            },
        )

    def test_edge_case_withdrawal_notice_given_exactly_30_days_before_term_start(self):
        """
        Explicit Edge Case from problem statement:
        'Withdrawal notice given exactly 30 days before the term start'
        Term 2 starts on 2026-08-01.
        Notice given on 2026-07-02 -> (2026-08-01 - 2026-07-02).days == 30 days.
        Tuition for unstarted Term 2 paid earlier MUST be refunded!
        """
        student = Student(
            student_id="STU_W30", name="Withdraw30", grade=8, section="A",
            dob=date(2012, 1, 1), admission_date=date(2026, 4, 1),
            plan=InstalmentPlanType.TERM,
        )
        annual = FeeCalculator.compute_annual_fee(student, self.fee_structure)
        schedule = InstalmentScheduler.generate_schedule(student, annual)

        # Suppose student had prepaid Term 2 tuition (15,300)
        schedule[1].heads[FeeHead.TUITION].paid_amount = Decimal("15300.00")

        # Withdraw on 2026-07-15 with notice on 2026-07-02 (exactly 30 days before 2026-08-01)
        t_refund, d_refund, txns = WithdrawalManager.process_withdrawal(
            student=student,
            schedule=schedule,
            withdrawal_date=date(2026, 7, 15),
            notice_date=date(2026, 7, 2),
        )

        self.assertEqual(t_refund, Decimal("15300.00"))
        self.assertEqual(student.status, StudentStatus.WITHDRAWN)

    def test_withdrawal_with_insufficient_notice_refunds_nothing(self):
        """Notice given 20 days before Term 2 start (< 30 days) yields Rs 0 refund."""
        student = Student(
            student_id="STU_W20", name="Withdraw20", grade=8, section="A",
            dob=date(2012, 1, 1), admission_date=date(2026, 4, 1),
            plan=InstalmentPlanType.TERM,
        )
        annual = FeeCalculator.compute_annual_fee(student, self.fee_structure)
        schedule = InstalmentScheduler.generate_schedule(student, annual)

        schedule[1].heads[FeeHead.TUITION].paid_amount = Decimal("15300.00")

        # Notice on 2026-07-12 (only 20 days before Aug 1)
        t_refund, _, _ = WithdrawalManager.process_withdrawal(
            student=student,
            schedule=schedule,
            withdrawal_date=date(2026, 7, 25),
            notice_date=date(2026, 7, 12),
        )
        self.assertEqual(t_refund, Decimal("0.00"))

    def test_withdrawal_in_last_term_refunds_nothing(self):
        """BR-09: A withdrawal in the last term (Term 3) refunds nothing."""
        student = Student(
            student_id="STU_W_LAST", name="WithdrawLast", grade=8, section="A",
            dob=date(2012, 1, 1), admission_date=date(2026, 4, 1),
            plan=InstalmentPlanType.TERM,
        )
        annual = FeeCalculator.compute_annual_fee(student, self.fee_structure)
        schedule = InstalmentScheduler.generate_schedule(student, annual)
        schedule[2].heads[FeeHead.TUITION].paid_amount = Decimal("15300.00")

        # Withdrawal in Term 3 (Dec 2026)
        t_refund, _, _ = WithdrawalManager.process_withdrawal(
            student=student,
            schedule=schedule,
            withdrawal_date=date(2026, 12, 15),
            notice_date=date(2026, 11, 1),
        )
        self.assertEqual(t_refund, Decimal("0.00"))

    def test_tc_clearance_blocked_until_dues_are_zero(self):
        """
        BR-09: TC is issued ONLY when dues are zero.
        """
        student = Student(
            student_id="STU_TC", name="TC_Student", grade=8, section="A",
            dob=date(2012, 1, 1), admission_date=date(2026, 4, 1),
        )
        inst = Instalment(
            instalment_id="INST-1",
            student_id=student.student_id,
            instalment_number=1,
            name="Term 1",
            due_date=date(2026, 4, 10),
            heads={FeeHead.TUITION: InstalmentHeadDue(head=FeeHead.TUITION, net_amount=Decimal("1000.00"))},
        )
        # Outstanding dues = 1,000 -> TC must be BLOCKED
        tc_stat = WithdrawalManager.evaluate_tc_clearance(student, [inst])
        self.assertEqual(tc_stat, TCStatus.BLOCKED_DUE_TO_DUES)

        # Clear dues to 0 -> TC becomes ISSUED
        inst.heads[FeeHead.TUITION].paid_amount = Decimal("1000.00")
        tc_stat2 = WithdrawalManager.evaluate_tc_clearance(student, [inst])
        self.assertEqual(tc_stat2, TCStatus.ISSUED)

    def test_edge_case_eldest_sibling_withdrawing_re_ranks_remaining_from_next_instalment(self):
        """
        Explicit Edge Case from problem statement:
        'Eldest sibling withdrawing mid-term with re-ranking'
        Family with 3 siblings:
        S1 (eldest, pays full), S2 (2nd child, 10% concession), S3 (3rd child, 20% concession).
        S1 withdraws during Term 1.
        From Term 2 onwards:
        S2 becomes eldest active child -> 0% sibling concession!
        S3 becomes 2nd active child -> 10% sibling concession!
        """
        s1 = Student(student_id="S1", name="Eldest", grade=8, section="A", dob=date(2010, 1, 1), admission_date=date(2026, 4, 1), sibling_group_id="FAM_RERANK")
        s2 = Student(student_id="S2", name="Second", grade=8, section="A", dob=date(2012, 1, 1), admission_date=date(2026, 4, 1), sibling_group_id="FAM_RERANK")
        s3 = Student(student_id="S3", name="Third", grade=8, section="A", dob=date(2014, 1, 1), admission_date=date(2026, 4, 1), sibling_group_id="FAM_RERANK")

        siblings = [s1, s2, s3]
        schedules = {}
        for s in siblings:
            ann = FeeCalculator.compute_annual_fee(s, self.fee_structure, siblings)
            schedules[s.student_id] = InstalmentScheduler.generate_schedule(s, ann)

        # Before withdrawal:
        # S2 Term 2 tuition had 10% concession: 51,000 * 0.90 * 0.30 = 13,770
        self.assertEqual(schedules["S2"][1].heads[FeeHead.TUITION].net_amount, Decimal("13770.00"))
        # S3 Term 2 tuition had 20% concession: 51,000 * 0.80 * 0.30 = 12,240
        self.assertEqual(schedules["S3"][1].heads[FeeHead.TUITION].net_amount, Decimal("12240.00"))

        # S1 withdraws
        s1.status = StudentStatus.WITHDRAWN
        WithdrawManager_res = WithdrawalManager.re_rank_siblings_after_withdrawal(
            withdrawn_student=s1,
            sibling_students=siblings,
            fee_structures={8: self.fee_structure},
            all_schedules=schedules,
            effective_from_term=2,
        )

        # S2 is now eldest -> 0% concession on Term 2 & 3: 51,000 * 1.0 * 0.30 = 15,300
        self.assertEqual(schedules["S2"][1].heads[FeeHead.TUITION].net_amount, Decimal("15300.00"))

        # S3 is now 2nd child -> 10% concession on Term 2 & 3: 51,000 * 0.90 * 0.30 = 13,770
        self.assertEqual(schedules["S3"][1].heads[FeeHead.TUITION].net_amount, Decimal("13770.00"))


if __name__ == "__main__":
    unittest.main()
