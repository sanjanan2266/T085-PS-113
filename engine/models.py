"""
School Fee Management Engine - Core Domain Models
PS-113: School Fee Management Engine with Instalments, Sibling Concessions, Late Fees and Add-ons
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Dict, List, Optional, Set


def quantize_amount(val: Decimal | float | int | str) -> Decimal:
    """Consistently round currency to 2 decimal places using ROUND_HALF_UP."""
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class FeeHead(str, Enum):
    TUITION = "tuition"
    DEVELOPMENT = "development"
    LAB = "lab"
    ACTIVITY = "activity"
    EXAM = "exam"
    ADMISSION = "admission"
    TRANSPORT = "transport"
    HOSTEL = "hostel"
    HOSTEL_DEPOSIT = "hostel_deposit"
    LATE_FEE = "late_fee"
    CHEQUE_BOUNCE = "cheque_bounce"


class InstalmentPlanType(str, Enum):
    ANNUAL = "ANNUAL"
    TERM = "TERM"
    MONTHLY = "MONTHLY"


class ConcessionCategory(str, Enum):
    NONE = "NONE"
    STAFF_WARD = "STAFF_WARD"
    MERIT = "MERIT"
    EWS = "EWS"


class StudentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    WITHDRAWN = "WITHDRAWN"


class HallTicketStatus(str, Enum):
    CLEARED = "CLEARED"
    WITHHELD = "WITHHELD"


class TCStatus(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    ISSUED = "ISSUED"
    BLOCKED_DUE_TO_DUES = "BLOCKED_DUE_TO_DUES"


class PaymentMode(str, Enum):
    CASH = "CASH"
    CHEQUE = "CHEQUE"
    UPI = "UPI"
    BANK_TRANSFER = "BANK_TRANSFER"


class TransactionType(str, Enum):
    CHARGE_FEE = "CHARGE_FEE"
    CHARGE_LATE_FEE = "CHARGE_LATE_FEE"
    CHARGE_BOUNCE = "CHARGE_BOUNCE"
    PAYMENT = "PAYMENT"
    REVERSAL_BOUNCE = "REVERSAL_BOUNCE"
    REFUND = "REFUND"
    ADJUSTMENT = "ADJUSTMENT"


@dataclass
class GradeFeeStructure:
    grade: int
    heads: Dict[FeeHead, Decimal] = field(default_factory=dict)

    def get_head(self, head: FeeHead) -> Decimal:
        return self.heads.get(head, Decimal("0.00"))

    def total(self) -> Decimal:
        return sum((quantize_amount(v) for v in self.heads.values()), Decimal("0.00"))


@dataclass
class AddOnRateCard:
    # Transport zone -> monthly rate
    transport_rates: Dict[str, Decimal] = field(default_factory=lambda: {
        "Zone A": Decimal("1800.00"),
        "Zone B": Decimal("2400.00"),
        "Zone C": Decimal("3000.00"),
    })
    # Hostel type -> monthly rate
    hostel_rates: Dict[str, Decimal] = field(default_factory=lambda: {
        "shared": Decimal("9000.00"),
        "single": Decimal("12000.00"),
    })
    # Hostel security deposit (1 month)
    hostel_deposit_months: int = 1


@dataclass
class TransportSubscription:
    student_id: str
    zone: str
    start_date: date
    end_date: Optional[date] = None
    active: bool = True


@dataclass
class HostelSubscription:
    student_id: str
    room_type: str  # "shared" or "single"
    start_date: date
    end_date: Optional[date] = None
    deposit_amount: Decimal = Decimal("0.00")
    deposit_paid: bool = False
    damages: Decimal = Decimal("0.00")
    deposit_refunded: Decimal = Decimal("0.00")
    active: bool = True


@dataclass
class Student:
    student_id: str
    name: str
    grade: int
    section: str
    admission_date: date
    dob: date
    plan: InstalmentPlanType = InstalmentPlanType.TERM
    concession_category: ConcessionCategory = ConcessionCategory.NONE
    previous_year_percentage: float = 0.0
    sibling_group_id: Optional[str] = None
    campus: str = "CAMPUS-1"
    status: StudentStatus = StudentStatus.ACTIVE
    withdrawal_date: Optional[date] = None
    withdrawal_notice_date: Optional[date] = None
    tc_status: TCStatus = TCStatus.NOT_REQUESTED
    hall_ticket_status: HallTicketStatus = HallTicketStatus.CLEARED
    advance_credit: Decimal = Decimal("0.00")


@dataclass
class InstalmentHeadDue:
    head: FeeHead
    base_amount: Decimal = Decimal("0.00")
    concession_discount: Decimal = Decimal("0.00")
    plan_discount: Decimal = Decimal("0.00")
    revision_adjustment: Decimal = Decimal("0.00")
    net_amount: Decimal = Decimal("0.00")
    paid_amount: Decimal = Decimal("0.00")

    @property
    def remaining_due(self) -> Decimal:
        due = self.net_amount - self.paid_amount
        return max(Decimal("0.00"), quantize_amount(due))


@dataclass
class Instalment:
    instalment_id: str
    student_id: str
    instalment_number: int
    name: str
    due_date: date
    grace_days: int = 0
    # Breakdown of dues per fee head
    heads: Dict[FeeHead, InstalmentHeadDue] = field(default_factory=dict)
    # Late fee tracking
    late_fee_assessed: Decimal = Decimal("0.00")
    late_fee_paid: Decimal = Decimal("0.00")

    @property
    def total_net_fee(self) -> Decimal:
        return sum((h.net_amount for h in self.heads.values()), Decimal("0.00"))

    @property
    def total_fee_paid(self) -> Decimal:
        return sum((h.paid_amount for h in self.heads.values()), Decimal("0.00"))

    @property
    def remaining_fee_due(self) -> Decimal:
        return sum((h.remaining_due for h in self.heads.values()), Decimal("0.00"))

    @property
    def remaining_late_fee(self) -> Decimal:
        return max(Decimal("0.00"), self.late_fee_assessed - self.late_fee_paid)

    @property
    def total_outstanding(self) -> Decimal:
        return quantize_amount(self.remaining_fee_due + self.remaining_late_fee)

    @property
    def is_fully_paid(self) -> bool:
        return self.total_outstanding <= Decimal("0.00")


@dataclass
class Transaction:
    txn_id: str
    student_id: str
    txn_date: date
    txn_type: TransactionType
    amount: Decimal
    head: Optional[FeeHead] = None
    instalment_number: Optional[int] = None
    payment_mode: Optional[PaymentMode] = None
    reference: Optional[str] = None
    description: str = ""
    running_balance: Decimal = Decimal("0.00")


@dataclass
class PaymentAllocation:
    instalment_number: int
    head: FeeHead
    amount: Decimal


@dataclass
class PaymentRecord:
    payment_id: str
    student_id: str
    payment_date: date
    amount: Decimal
    payment_mode: PaymentMode
    reference: str = ""  # cheque number, txn reference, etc.
    receipt_number: str = ""
    is_bounced: bool = False
    bounce_date: Optional[date] = None
    allocations: List[PaymentAllocation] = field(default_factory=list)
    advance_credit_generated: Decimal = Decimal("0.00")
