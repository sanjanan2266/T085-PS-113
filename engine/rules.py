"""
Business Rules Registry and Configuration for PS-113
All rules registered as BR-01 through BR-12 as specified in requirements.
"""
from datetime import date
from decimal import Decimal
from typing import Dict, List, Tuple


# BR-01: Instalment Plans
# Academic Year: 2026-2027 (standard 10-month academic calendar Apr-Jan)
ACADEMIC_YEAR_START = date(2026, 4, 1)
ACADEMIC_YEAR_END = date(2027, 3, 31)
TOTAL_ACADEMIC_MONTHS = 10  # April to January

ANNUAL_TUITION_DISCOUNT_PERCENT = Decimal("0.03")  # 3% discount on tuition

# TERM plan: 3 instalments 40/30/30 on 10 Apr, 10 Aug, 10 Dec
TERM_SPLITS: List[Tuple[str, date, Decimal, List[int]]] = [
    ("Term 1", date(2026, 4, 10), Decimal("0.40"), [4, 5, 6, 7]),        # Apr-Jul (4 months)
    ("Term 2", date(2026, 8, 10), Decimal("0.30"), [8, 9, 10]),          # Aug-Oct (3 months)
    ("Term 3", date(2026, 12, 10), Decimal("0.30"), [11, 12, 1]),        # Nov-Jan (3 months)
]

# MONTHLY plan: 10 instalments on 10th of Apr through Jan
MONTHLY_DUE_DAY = 10
MONTHLY_MONTHS = [
    (4, 2026, "April"),
    (5, 2026, "May"),
    (6, 2026, "June"),
    (7, 2026, "July"),
    (8, 2026, "August"),
    (9, 2026, "September"),
    (10, 2026, "October"),
    (11, 2026, "November"),
    (12, 2026, "December"),
    (1, 2027, "January"),
]

# BR-02: Sibling Concession
SIBLING_CONCESSION_ELDEST = Decimal("0.00")      # 0%
SIBLING_CONCESSION_SECOND = Decimal("0.10")      # 10%
SIBLING_CONCESSION_THIRD_PLUS = Decimal("0.20")  # 20%

# BR-03: Category Concessions & Combined Cap
CATEGORY_CONCESSIONS: Dict[str, Dict[str, Decimal]] = {
    "STAFF_WARD": {"tuition": Decimal("0.50"), "other": Decimal("0.00")},
    "MERIT": {"tuition": Decimal("0.25"), "other": Decimal("0.00")},
    "EWS": {"tuition": Decimal("1.00"), "other": Decimal("0.50")},
    "NONE": {"tuition": Decimal("0.00"), "other": Decimal("0.00")},
}
COMBINED_TUITION_CAP = Decimal("0.60")  # 60% cap on tuition concession when stacking

# BR-04: Transport Add-on
TRANSPORT_MID_MONTH_CUTOFF_DAY = 15
DEFAULT_TRANSPORT_RATES = {
    "Zone A": Decimal("1800.00"),
    "Zone B": Decimal("2400.00"),
    "Zone C": Decimal("3000.00"),
}

# BR-05: Hostel Add-on
DEFAULT_HOSTEL_RATES = {
    "shared": Decimal("9000.00"),
    "single": Decimal("12000.00"),
}

# BR-06: Late Fee
LATE_FEE_PER_DAY = Decimal("50.00")
LATE_FEE_MAX_CAP = Decimal("1500.00")
APRIL_GRACE_DAYS = 7
DEFAULTER_DAYS_THRESHOLD = 60

# BR-08: Mid-Year Admission
FLAT_ADMISSION_FEE = Decimal("10000.00")
MID_YEAR_MONTH_CUTOFF_DAY = 15

# BR-09: Withdrawal
WITHDRAWAL_NOTICE_DAYS_REQUIRED = 30

# BR-10: Cheque Bounce
CHEQUE_BOUNCE_CHARGE = Decimal("500.00")

# BR-11: Fee Revision
MID_YEAR_REVISION_MAX_PERCENT = Decimal("0.10")  # 10%
