"""
Report Generation for PS-113:
- Fee Demand Notice
- Instalment Schedule Table
- Student Account Ledger
- Defaulter List (as-of date with WITHHELD hall tickets)
- Payment Receipts with campus sequential numbering
"""
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from engine.models import (
    FeeHead,
    Instalment,
    PaymentRecord,
    Student,
    Transaction,
    quantize_amount,
)
from engine.late_fee import DefaulterRecord


class ReportGenerator:
    """Generates formatted text reports and ledgers for school administration."""

    @staticmethod
    def print_fee_demand(
        student: Student,
        schedule: List[Instalment],
        as_of_date: date,
    ) -> str:
        """Prints a comprehensive Fee Demand Notice."""
        lines = []
        lines.append("=" * 76)
        lines.append(f"{'DELHI PUBLIC ACADEMY - FEE DEMAND NOTICE':^76}")
        lines.append(f"{'Academic Year 2026-2027':^76}")
        lines.append("=" * 76)
        lines.append(f"Student ID   : {student.student_id:<20} Date       : {as_of_date.isoformat()}")
        lines.append(f"Student Name : {student.name:<20} Grade/Sec  : {student.grade}-{student.section}")
        lines.append(f"Plan         : {student.plan.value:<20} Category   : {student.concession_category.value}")
        lines.append(f"Campus       : {student.campus:<20} Status     : {student.status.value}")
        if student.sibling_group_id:
            lines.append(f"Sibling Grp  : {student.sibling_group_id}")
        lines.append("-" * 76)
        lines.append(f"{'Inst #':<8}{'Name':<22}{'Due Date':<14}{'Fee (Rs)':>12}{'Late Fee':>10}{'Total (Rs)':>10}")
        lines.append("-" * 76)

        grand_fee = Decimal("0.00")
        grand_late = Decimal("0.00")
        grand_total = Decimal("0.00")

        for inst in schedule:
            fee_due = inst.remaining_fee_due
            late_due = inst.remaining_late_fee
            tot = inst.total_outstanding

            grand_fee += fee_due
            grand_late += late_due
            grand_total += tot

            lines.append(
                f"{inst.instalment_number:<8}{inst.name:<22}{inst.due_date.isoformat():<14}"
                f"{fee_due:>12.2f}{late_due:>10.2f}{tot:>10.2f}"
            )

        lines.append("-" * 76)
        lines.append(f"{'TOTAL DUE':<44}{grand_fee:>12.2f}{grand_late:>10.2f}{grand_total:>10.2f}")
        if student.advance_credit > Decimal("0.00"):
            lines.append(f"Advance Credit Available: Rs {student.advance_credit:>10.2f}")
            net_payable = max(Decimal("0.00"), grand_total - student.advance_credit)
            lines.append(f"Net Amount Payable      : Rs {net_payable:>10.2f}")
        lines.append("=" * 76)
        return "\n".join(lines)

    @staticmethod
    def print_instalment_schedule(
        student: Student,
        schedule: List[Instalment],
    ) -> str:
        """Prints the full breakdown of each instalment by fee head."""
        lines = []
        lines.append("=" * 88)
        lines.append(f"{'INSTALMENT SCHEDULE & BREAKDOWN':^88}")
        lines.append(f"Student: {student.name} ({student.student_id}) | Grade: {student.grade}-{student.section} | Plan: {student.plan.value}")
        lines.append("=" * 88)
        lines.append(
            f"{'Inst':<6}{'Due Date':<12}{'Tuition':>10}{'Dev':>9}{'Lab':>8}"
            f"{'Activity':>9}{'Exam':>8}{'Add-ons':>10}{'Total':>12}{'Paid':>10}"
        )
        lines.append("-" * 88)

        total_net = Decimal("0.00")
        total_paid = Decimal("0.00")

        for inst in schedule:
            t = inst.heads.get(FeeHead.TUITION).net_amount if FeeHead.TUITION in inst.heads else Decimal("0.00")
            d = inst.heads.get(FeeHead.DEVELOPMENT).net_amount if FeeHead.DEVELOPMENT in inst.heads else Decimal("0.00")
            l = inst.heads.get(FeeHead.LAB).net_amount if FeeHead.LAB in inst.heads else Decimal("0.00")
            a = inst.heads.get(FeeHead.ACTIVITY).net_amount if FeeHead.ACTIVITY in inst.heads else Decimal("0.00")
            e = inst.heads.get(FeeHead.EXAM).net_amount if FeeHead.EXAM in inst.heads else Decimal("0.00")

            addon = sum(
                (inst.heads[h].net_amount for h in [FeeHead.TRANSPORT, FeeHead.HOSTEL, FeeHead.HOSTEL_DEPOSIT] if h in inst.heads),
                Decimal("0.00"),
            )
            tot = inst.total_net_fee
            pd = inst.total_fee_paid
            total_net += tot
            total_paid += pd

            lines.append(
                f"{inst.instalment_number:<6}{inst.due_date.isoformat():<12}"
                f"{t:>10.2f}{d:>9.2f}{l:>8.2f}{a:>9.2f}{e:>8.2f}{addon:>10.2f}"
                f"{tot:>12.2f}{pd:>10.2f}"
            )

        lines.append("-" * 88)
        lines.append(f"{'TOTALS':<18}{'':>44}{total_net:>12.2f}{total_paid:>10.2f}")
        lines.append(f"Balance Outstanding: Rs {total_net - total_paid:>10.2f}")
        lines.append("=" * 88)
        return "\n".join(lines)

    @staticmethod
    def print_student_ledger(
        student: Student,
        transactions: List[Transaction],
        as_of_date: Optional[date] = None,
    ) -> str:
        """Prints a running statement of account / student ledger."""
        lines = []
        lines.append("=" * 88)
        lines.append(f"{'STUDENT ACCOUNT STATEMENT / LEDGER':^88}")
        lines.append(f"Student: {student.name} ({student.student_id}) | Grade: {student.grade}-{student.section}")
        lines.append(f"Campus: {student.campus} | Hall Ticket: {student.hall_ticket_status.value} | TC Status: {student.tc_status.value}")
        lines.append("=" * 88)
        lines.append(f"{'Date':<12}{'Txn ID':<18}{'Description':<32}{'Debit (Rs)':>12}{'Credit (Rs)':>12}")
        lines.append("-" * 88)

        running_balance = Decimal("0.00")
        total_debits = Decimal("0.00")
        total_credits = Decimal("0.00")

        # Sort transactions chronologically
        sorted_txns = sorted(transactions, key=lambda tx: (tx.txn_date, tx.txn_id))

        for tx in sorted_txns:
            if as_of_date and tx.txn_date > as_of_date:
                continue

            debit_amt = Decimal("0.00")
            credit_amt = Decimal("0.00")

            if tx.txn_type.value in ["CHARGE_FEE", "CHARGE_LATE_FEE", "CHARGE_BOUNCE", "REVERSAL_BOUNCE"]:
                debit_amt = tx.amount
                running_balance += debit_amt
                total_debits += debit_amt
            elif tx.txn_type.value in ["PAYMENT", "REFUND", "ADJUSTMENT"]:
                credit_amt = tx.amount
                running_balance -= credit_amt
                total_credits += credit_amt

            desc = (tx.description[:30] + "..") if len(tx.description) > 32 else tx.description
            lines.append(
                f"{tx.txn_date.isoformat():<12}{tx.txn_id:<18}{desc:<32}"
                f"{debit_amt:>12.2f}{credit_amt:>12.2f}"
            )

        lines.append("-" * 88)
        lines.append(f"{'TOTALS':<62}{total_debits:>12.2f}{total_credits:>12.2f}")
        lines.append(f"Current Closing Balance : Rs {running_balance:>12.2f}")
        if student.advance_credit > Decimal("0.00"):
            lines.append(f"Unadjusted Advance Credit: Rs {student.advance_credit:>12.2f}")
        lines.append("=" * 88)
        return "\n".join(lines)

    @staticmethod
    def print_defaulters_list(
        defaulters: List[DefaulterRecord],
        as_of_date: date,
    ) -> str:
        """Prints the Defaulter List as of a specified date."""
        lines = []
        lines.append("=" * 88)
        lines.append(f"{'DEFAULTER LIST (OVERDUE > 60 DAYS)':^88}")
        lines.append(f"As of Date: {as_of_date.isoformat()} | Hall Tickets: WITHHELD")
        lines.append("=" * 88)
        lines.append(
            f"{'Student ID':<12}{'Name':<20}{'Grade/Sec':<10}{'Inst':<6}"
            f"{'Due Date':<12}{'Days Over':>10}{'Overdue (Rs)':>14}"
        )
        lines.append("-" * 88)

        total_overdue = Decimal("0.00")

        if not defaulters:
            lines.append(f"{'No defaulters found as of this date.':^88}")
        else:
            for d in defaulters:
                total_overdue += d.total_due
                lines.append(
                    f"{d.student_id:<12}{d.student_name:<20}{d.grade}-{d.section:<8}{d.overdue_instalment:<6}"
                    f"{d.due_date.isoformat():<12}{d.days_overdue:>10}{d.total_due:>14.2f}"
                )

        lines.append("-" * 88)
        lines.append(f"{'TOTAL DEFAULTER AMOUNT':<60}{total_overdue:>24.2f}")
        lines.append(f"Total Defaulter Students: {len(defaulters)}")
        lines.append("=" * 88)
        return "\n".join(lines)

    @staticmethod
    def generate_receipt(
        payment: PaymentRecord,
        student: Student,
    ) -> str:
        """Generates an official payment receipt with sequential number."""
        lines = []
        lines.append("=" * 64)
        lines.append(f"{'DELHI PUBLIC ACADEMY - PAYMENT RECEIPT':^64}")
        lines.append(f"{'Receipt No: ' + payment.receipt_number:^64}")
        lines.append("=" * 64)
        lines.append(f"Date         : {payment.payment_date.isoformat():<20} Campus : {student.campus}")
        lines.append(f"Student ID   : {student.student_id:<20} Grade  : {student.grade}-{student.section}")
        lines.append(f"Student Name : {student.name}")
        lines.append(f"Payment Mode : {payment.payment_mode.value:<20} Ref    : {payment.reference or 'N/A'}")
        lines.append("-" * 64)
        lines.append(f"{'Inst #':<8}{'Fee Head':<24}{'Amount Paid (Rs)':>28}")
        lines.append("-" * 64)

        for alloc in payment.allocations:
            lines.append(f"{alloc.instalment_number:<8}{alloc.head.value.title():<24}{alloc.amount:>28.2f}")

        if payment.advance_credit_generated > Decimal("0.00"):
            lines.append(f"{'-':<8}{'Advance Credit':<24}{payment.advance_credit_generated:>28.2f}")

        lines.append("-" * 64)
        lines.append(f"{'TOTAL RECEIVED':<32}{payment.amount:>28.2f}")
        lines.append("=" * 64)
        return "\n".join(lines)
