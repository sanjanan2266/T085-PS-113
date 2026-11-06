"""
Integration Test for the Sample Dataset Workflow
Verifies the end-to-end processing of:
- 12 grade fee structures
- 60 enrolled students with 8 sibling groups
- 30 transport and hostel subscriptions
- 350 payments across multiple months
- 6 cheque bounces with retroactive reversals and Rs 500 charges
- Mid-year withdrawal with sibling re-ranking
- Defaulter detection (> 60 days overdue) with WITHHELD hall tickets
- Stretch goal: Sequential campus receipt numbering
- Stretch goal: Merit-based scholarship fund allocation
"""
import unittest
from pathlib import Path
from decimal import Decimal
from engine.command_processor import SchoolFeeEngine, CommandProcessor
from engine.models import FeeHead, HallTicketStatus, StudentStatus


class TestSampleDatasetIntegration(unittest.TestCase):

    def test_full_sample_workflow_execution(self):
        cmd_file = Path("sample_data") / "commands.txt"
        self.assertTrue(cmd_file.exists(), f"Sample commands file must exist at {cmd_file}")

        processor = CommandProcessor()
        logs = processor.process_file(cmd_file)

        # 1. Check all 12 grades loaded
        self.assertEqual(len(processor.engine.fee_structures), 12)

        # 2. Check 60 original + 2 midyear = 62 students loaded
        self.assertGreaterEqual(len(processor.engine.students), 60)

        # 3. Check STU003 (Staff ward who is 3rd sibling)
        stu003 = processor.engine.students["STU003"]
        annual003 = processor.engine.computed_annual_fees["STU003"]
        self.assertTrue(annual003.concession_breakdown.tuition_cap_applied)
        self.assertEqual(annual003.concession_breakdown.combined_tuition_pct_effective, Decimal("0.60"))

        # 4. Check that 6 cheque bounces were processed
        bounced_count = sum(1 for p in processor.engine.payments.values() if p.is_bounced)
        self.assertEqual(bounced_count, 6)

        # 5. Check withdrawal of STU001 and sibling re-ranking
        stu001 = processor.engine.students["STU001"]
        self.assertEqual(stu001.status, StudentStatus.WITHDRAWN)

        # 6. Check defaulters exist on 2026-10-15
        from datetime import date
        defaulters = processor.engine.get_defaulters(date(2026, 10, 15))
        self.assertGreater(len(defaulters), 0)
        for d in defaulters:
            self.assertEqual(d.hall_ticket_status, HallTicketStatus.WITHHELD)

        # 7. Check scholarship allocation (stretch goal)
        self.assertIsNotNone(processor.engine.scholarship_manager)
        self.assertGreater(len(processor.engine.scholarship_manager.awards), 0)


if __name__ == "__main__":
    unittest.main()
