"""
Payment Application Waterfall implementing BR-07 and BR-10
Strict Order:
Late fees -> Oldest instalment tuition -> Other heads -> Add-ons -> Next instalment.
Overpayment becomes advance credit.
Cheque bounce: Rs 500 charge, reversal of allocations, and retroactive late fee recomputation.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from engine.models import (
    FeeHead,
    Instalment,
    PaymentAllocation,
    PaymentMode,
    PaymentRecord,
    Student,
    Transaction,
    TransactionType,
    quantize_amount,
)
from engine.rules import (
    CHEQUE_BOUNCE_CHARGE,
)
from engine.late_fee import LateFeeCalculator


# Other heads order
OTHER_HEADS_ORDER = [
    FeeHead.DEVELOPMENT,
    FeeHead.LAB,
    FeeHead.ACTIVITY,
    FeeHead.EXAM,
    FeeHead.ADMISSION,
]

# Add-on heads order
ADDON_HEADS_ORDER = [
    FeeHead.TRANSPORT,
    FeeHead.HOSTEL,
    FeeHead.HOSTEL_DEPOSIT,
]


class PaymentWaterfallProcessor:
    """Processes payments, executes waterfall allocation, and manages bounces."""

    @classmethod
    def apply_payment(
        cls,
        student: Student,
        schedule: List[Instalment],
        payment_id: str,
        payment_date: date,
        amount: Decimal,
        payment_mode: PaymentMode,
        reference: str = "",
        receipt_number: str = "",
    ) -> Tuple[PaymentRecord, List[Transaction]]:
        """
        Applies a payment according to BR-07:
        1. Assess late fees on instalments as of payment_date.
        2. In chronological order of instalments:
           a. Late fees of instalment
           b. Tuition of instalment
           c. Other heads of instalment
           d. Add-ons of instalment
        3. Advance credit for any leftover amount.
        """
        amount = quantize_amount(amount)
        remaining = amount
        allocations: List[PaymentAllocation] = []
        transactions: List[Transaction] = []

        # Sort instalments chronologically
        sorted_schedule = sorted(schedule, key=lambda inst: (inst.due_date, inst.instalment_number))

        # First update late fees up to payment_date
        for inst in sorted_schedule:
            if payment_date > inst.due_date:
                LateFeeCalculator.update_instalment_late_fee(inst, payment_date)

        txn_counter = 1

        for inst in sorted_schedule:
            if remaining <= Decimal("0.00"):
                break

            # 1. Late fee of this instalment
            late_fee_due = inst.remaining_late_fee
            if late_fee_due > Decimal("0.00") and remaining > Decimal("0.00"):
                applied = min(remaining, late_fee_due)
                inst.late_fee_paid += applied
                remaining -= applied
                allocations.append(PaymentAllocation(
                    instalment_number=inst.instalment_number,
                    head=FeeHead.LATE_FEE,
                    amount=applied,
                ))
                transactions.append(Transaction(
                    txn_id=f"{payment_id}-TXN-{txn_counter}",
                    student_id=student.student_id,
                    txn_date=payment_date,
                    txn_type=TransactionType.PAYMENT,
                    amount=applied,
                    head=FeeHead.LATE_FEE,
                    instalment_number=inst.instalment_number,
                    payment_mode=payment_mode,
                    reference=reference,
                    description=f"Payment for Late Fee (Instalment {inst.instalment_number})",
                ))
                txn_counter += 1

            # 2. Tuition head of this instalment
            if FeeHead.TUITION in inst.heads and remaining > Decimal("0.00"):
                t_due = inst.heads[FeeHead.TUITION].remaining_due
                if t_due > Decimal("0.00"):
                    applied = min(remaining, t_due)
                    inst.heads[FeeHead.TUITION].paid_amount += applied
                    remaining -= applied
                    allocations.append(PaymentAllocation(
                        instalment_number=inst.instalment_number,
                        head=FeeHead.TUITION,
                        amount=applied,
                    ))
                    transactions.append(Transaction(
                        txn_id=f"{payment_id}-TXN-{txn_counter}",
                        student_id=student.student_id,
                        txn_date=payment_date,
                        txn_type=TransactionType.PAYMENT,
                        amount=applied,
                        head=FeeHead.TUITION,
                        instalment_number=inst.instalment_number,
                        payment_mode=payment_mode,
                        reference=reference,
                        description=f"Payment for Tuition (Instalment {inst.instalment_number})",
                    ))
                    txn_counter += 1

            # 3. Other heads of this instalment
            for head in OTHER_HEADS_ORDER:
                if remaining <= Decimal("0.00"):
                    break
                if head in inst.heads:
                    h_due = inst.heads[head].remaining_due
                    if h_due > Decimal("0.00"):
                        applied = min(remaining, h_due)
                        inst.heads[head].paid_amount += applied
                        remaining -= applied
                        allocations.append(PaymentAllocation(
                            instalment_number=inst.instalment_number,
                            head=head,
                            amount=applied,
                        ))
                        transactions.append(Transaction(
                            txn_id=f"{payment_id}-TXN-{txn_counter}",
                            student_id=student.student_id,
                            txn_date=payment_date,
                            txn_type=TransactionType.PAYMENT,
                            amount=applied,
                            head=head,
                            instalment_number=inst.instalment_number,
                            payment_mode=payment_mode,
                            reference=reference,
                            description=f"Payment for {head.value.title()} (Instalment {inst.instalment_number})",
                        ))
                        txn_counter += 1

            # 4. Add-on heads of this instalment
            for head in ADDON_HEADS_ORDER:
                if remaining <= Decimal("0.00"):
                    break
                if head in inst.heads:
                    h_due = inst.heads[head].remaining_due
                    if h_due > Decimal("0.00"):
                        applied = min(remaining, h_due)
                        inst.heads[head].paid_amount += applied
                        remaining -= applied
                        allocations.append(PaymentAllocation(
                            instalment_number=inst.instalment_number,
                            head=head,
                            amount=applied,
                        ))
                        transactions.append(Transaction(
                            txn_id=f"{payment_id}-TXN-{txn_counter}",
                            student_id=student.student_id,
                            txn_date=payment_date,
                            txn_type=TransactionType.PAYMENT,
                            amount=applied,
                            head=head,
                            instalment_number=inst.instalment_number,
                            payment_mode=payment_mode,
                            reference=reference,
                            description=f"Payment for Add-on {head.value.title()} (Instalment {inst.instalment_number})",
                        ))
                        txn_counter += 1

        # Advance credit if remaining > 0
        advance_credit = Decimal("0.00")
        if remaining > Decimal("0.00"):
            advance_credit = quantize_amount(remaining)
            student.advance_credit += advance_credit
            transactions.append(Transaction(
                txn_id=f"{payment_id}-TXN-{txn_counter}",
                student_id=student.student_id,
                txn_date=payment_date,
                txn_type=TransactionType.ADJUSTMENT,
                amount=advance_credit,
                payment_mode=payment_mode,
                reference=reference,
                description=f"Overpayment credited as advance credit (Rs {advance_credit})",
            ))

        payment_record = PaymentRecord(
            payment_id=payment_id,
            student_id=student.student_id,
            payment_date=payment_date,
            amount=amount,
            payment_mode=payment_mode,
            reference=reference,
            receipt_number=receipt_number,
            allocations=allocations,
            advance_credit_generated=advance_credit,
        )

        return payment_record, transactions

    @classmethod
    def apply_advance_credit(
        cls,
        student: Student,
        schedule: List[Instalment],
        as_of_date: date,
    ) -> List[Transaction]:
        """Draws down existing advance credit against any currently due instalments."""
        if student.advance_credit <= Decimal("0.00"):
            return []

        credit_avail = student.advance_credit

        dummy_record, txns = cls.apply_payment(
            student=student,
            schedule=schedule,
            payment_id=f"ADV-DRAW-{as_of_date.strftime('%Y%m%d')}",
            payment_date=as_of_date,
            amount=credit_avail,
            payment_mode=PaymentMode.BANK_TRANSFER,
            reference="ADVANCE_CREDIT_SETTLEMENT",
        )

        # Keep only the unused portion of the original advance credit.
        student.advance_credit = dummy_record.advance_credit_generated

        return txns

    @classmethod
    def process_cheque_bounce(
        cls,
        student: Student,
        schedule: List[Instalment],
        payment_record: PaymentRecord,
        bounce_date: date,
        all_payments_for_student: List[PaymentRecord],
    ) -> List[Transaction]:
        """
        BR-10:
        1. Rs 500 charge debited.
        2. Payment reversed as of original date.
        3. Late fees recomputed as if payment was never made.
        """
        if payment_record.is_bounced:
            raise ValueError(f"Payment {payment_record.payment_id} has already been marked as bounced.")

        payment_record.is_bounced = True
        payment_record.bounce_date = bounce_date

        txns: List[Transaction] = []

        # 1. Reverse the payment allocations
        for alloc in payment_record.allocations:
            inst = next((i for i in schedule if i.instalment_number == alloc.instalment_number), None)
            if not inst:
                continue

            if alloc.head == FeeHead.LATE_FEE:
                inst.late_fee_paid = max(Decimal("0.00"), inst.late_fee_paid - alloc.amount)
            elif alloc.head in inst.heads:
                inst.heads[alloc.head].paid_amount = max(Decimal("0.00"), inst.heads[alloc.head].paid_amount - alloc.amount)

            txns.append(Transaction(
                txn_id=f"REV-{payment_record.payment_id}-{alloc.instalment_number}-{alloc.head.value}",
                student_id=student.student_id,
                txn_date=bounce_date,
                txn_type=TransactionType.REVERSAL_BOUNCE,
                amount=alloc.amount,
                head=alloc.head,
                instalment_number=alloc.instalment_number,
                payment_mode=payment_record.payment_mode,
                reference=f"Reversal of {payment_record.payment_id}",
                description=f"Reversal of payment on {alloc.head.value} due to cheque bounce",
            ))

        # Reverse advance credit if any was generated
        if payment_record.advance_credit_generated > Decimal("0.00"):
            student.advance_credit = max(Decimal("0.00"), student.advance_credit - payment_record.advance_credit_generated)

        # 2. Charge Rs 500 cheque bounce fee
        txns.append(Transaction(
            txn_id=f"BOUNCE-CHG-{payment_record.payment_id}",
            student_id=student.student_id,
            txn_date=bounce_date,
            txn_type=TransactionType.CHARGE_BOUNCE,
            amount=CHEQUE_BOUNCE_CHARGE,
            head=FeeHead.CHEQUE_BOUNCE,
            reference=f"Cheque bounce: {payment_record.reference}",
            description=f"Cheque bounce penalty of Rs {CHEQUE_BOUNCE_CHARGE}",
        ))

        # 3. Retroactively recompute late fees as of bounce_date
        for inst in schedule:
            if bounce_date > inst.due_date:
                LateFeeCalculator.update_instalment_late_fee(inst, bounce_date)

        return txns
