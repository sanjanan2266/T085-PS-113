"""
Add-on Manager implementing BR-04 (Transport) and BR-05 (Hostel)
Handles pro-rating (15th cutoff), security deposit, billing per instalment, and damages deduction.
"""
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from engine.models import (
    AddOnRateCard,
    FeeHead,
    HostelSubscription,
    Instalment,
    InstalmentHeadDue,
    InstalmentPlanType,
    TransportSubscription,
    quantize_amount,
)
from engine.rules import (
    MONTHLY_MONTHS,
    TERM_SPLITS,
    TRANSPORT_MID_MONTH_CUTOFF_DAY,
)


class AddOnManager:
    """Manages Transport and Hostel subscriptions and injects dues into instalments."""

    @staticmethod
    def get_month_fraction(start_date: date, month: int, year: int) -> Decimal:
        """
        BR-04: Starting mid-month bills the full month if joined on or before the 15th, else half.
        Returns fraction of the month billed: 1.0, 0.5, or 0.0.
        """
        # If start date is after this month
        if (year, month) < (start_date.year, start_date.month):
            return Decimal("0.00")
        # If joined in this specific month
        if year == start_date.year and month == start_date.month:
            if start_date.day <= TRANSPORT_MID_MONTH_CUTOFF_DAY:
                return Decimal("1.00")
            else:
                return Decimal("0.50")
        # If joined in an earlier month
        return Decimal("1.00")

    @classmethod
    def calculate_transport_fee_for_months(
        cls,
        subscription: TransportSubscription,
        rate_card: AddOnRateCard,
        months_covered: List[Tuple[int, int]],  # (month, year)
    ) -> Decimal:
        """Calculates total transport charge for a set of academic months."""
        if not subscription.active and subscription.end_date is None:
            return Decimal("0.00")

        monthly_rate = rate_card.transport_rates.get(subscription.zone, Decimal("0.00"))
        total = Decimal("0.00")

        for month, year in months_covered:
            # Check if subscription ended before or during this month
            if subscription.end_date and (year, month) > (subscription.end_date.year, subscription.end_date.month):
                continue

            fraction = cls.get_month_fraction(subscription.start_date, month, year)
            if subscription.end_date and year == subscription.end_date.year and month == subscription.end_date.month:
                # If removed mid-month: if removed on or before 15th, pays half, else full
                if subscription.end_date.day <= TRANSPORT_MID_MONTH_CUTOFF_DAY:
                    fraction = min(fraction, Decimal("0.50"))

            total += quantize_amount(monthly_rate * fraction)

        return quantize_amount(total)

    @classmethod
    def calculate_hostel_fee_for_months(
        cls,
        subscription: HostelSubscription,
        rate_card: AddOnRateCard,
        months_covered: List[Tuple[int, int]],
    ) -> Decimal:
        """
        BR-05: Calculates hostel fee for given months. Includes mess.
        Never discounted by concessions.
        """
        if not subscription.active and subscription.end_date is None:
            return Decimal("0.00")

        monthly_rate = rate_card.hostel_rates.get(subscription.room_type, Decimal("0.00"))
        total = Decimal("0.00")

        for month, year in months_covered:
            if (year, month) < (subscription.start_date.year, subscription.start_date.month):
                continue
            if subscription.end_date and (year, month) > (subscription.end_date.year, subscription.end_date.month):
                continue

            fraction = cls.get_month_fraction(subscription.start_date, month, year)
            total += quantize_amount(monthly_rate * fraction)

        return quantize_amount(total)

    @classmethod
    def apply_addons_to_schedule(
        cls,
        schedule: List[Instalment],
        plan: InstalmentPlanType,
        rate_card: AddOnRateCard,
        transport_sub: Optional[TransportSubscription] = None,
        hostel_sub: Optional[HostelSubscription] = None,
    ) -> None:
        """
        Bills transport and hostel onto each instalment for the months it covers.
        Also attaches 1-month hostel security deposit to the first relevant instalment.
        """
        # Map instalments to the months they cover
        instalment_months: Dict[int, List[Tuple[int, int]]] = {}

        if plan == InstalmentPlanType.ANNUAL:
            # 1 instalment covers all 10 months: (4, 2026) to (1, 2027)
            all_m = [(m, y) for (m, y, _) in MONTHLY_MONTHS]
            instalment_months[1] = all_m

        elif plan == InstalmentPlanType.TERM:
            # Term 1 covers months in TERM_SPLITS[0][3] = [4, 5, 6, 7]
            instalment_months[1] = [(4, 2026), (5, 2026), (6, 2026), (7, 2026)]
            # Term 2 covers [8, 9, 10]
            instalment_months[2] = [(8, 2026), (9, 2026), (10, 2026)]
            # Term 3 covers [11, 12, 1]
            instalment_months[3] = [(11, 2026), (12, 2026), (1, 2027)]

        elif plan == InstalmentPlanType.MONTHLY:
            # 10 instalments, each covers exactly 1 month
            for idx, (m, y, _) in enumerate(MONTHLY_MONTHS):
                instalment_months[idx + 1] = [(m, y)]

        hostel_deposit_billed = False

        for inst in schedule:
            months = instalment_months.get(inst.instalment_number, [])

            # Apply transport
            if transport_sub:
                t_amount = cls.calculate_transport_fee_for_months(transport_sub, rate_card, months)
                if t_amount > Decimal("0.00") or FeeHead.TRANSPORT in inst.heads:
                    inst.heads[FeeHead.TRANSPORT] = InstalmentHeadDue(
                        head=FeeHead.TRANSPORT,
                        base_amount=t_amount,
                        concession_discount=Decimal("0.00"),
                        plan_discount=Decimal("0.00"),
                        net_amount=t_amount,
                        paid_amount=inst.heads[FeeHead.TRANSPORT].paid_amount if FeeHead.TRANSPORT in inst.heads else Decimal("0.00"),
                    )

            # Apply hostel
            if hostel_sub:
                h_amount = cls.calculate_hostel_fee_for_months(hostel_sub, rate_card, months)
                if h_amount > Decimal("0.00") or FeeHead.HOSTEL in inst.heads:
                    inst.heads[FeeHead.HOSTEL] = InstalmentHeadDue(
                        head=FeeHead.HOSTEL,
                        base_amount=h_amount,
                        concession_discount=Decimal("0.00"),
                        plan_discount=Decimal("0.00"),
                        net_amount=h_amount,
                        paid_amount=inst.heads[FeeHead.HOSTEL].paid_amount if FeeHead.HOSTEL in inst.heads else Decimal("0.00"),
                    )

                # Hostel Security Deposit: 1 month fee collected once
                monthly_rate = rate_card.hostel_rates.get(hostel_sub.room_type, Decimal("0.00"))
                if not hostel_deposit_billed and monthly_rate > Decimal("0.00"):
                    # Check if this instalment is on or after hostel start date
                    if inst.due_date >= hostel_sub.start_date or inst.instalment_number == 1:
                        deposit_amt = quantize_amount(monthly_rate * rate_card.hostel_deposit_months)
                        hostel_sub.deposit_amount = deposit_amt
                        inst.heads[FeeHead.HOSTEL_DEPOSIT] = InstalmentHeadDue(
                            head=FeeHead.HOSTEL_DEPOSIT,
                            base_amount=deposit_amt,
                            concession_discount=Decimal("0.00"),
                            plan_discount=Decimal("0.00"),
                            net_amount=deposit_amt,
                            paid_amount=inst.heads[FeeHead.HOSTEL_DEPOSIT].paid_amount if FeeHead.HOSTEL_DEPOSIT in inst.heads else Decimal("0.00"),
                        )
                        hostel_deposit_billed = True
