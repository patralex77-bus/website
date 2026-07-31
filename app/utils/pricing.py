from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class PricingResult:
    km_cost: Decimal
    time_cost: Decimal
    waiting_cost: Decimal
    direct_cost: Decimal
    minimum_total: Decimal
    surcharge_total: Decimal
    net_total: Decimal
    vat_amount: Decimal
    gross_total: Decimal


def calculate_price(
    profile,
    *,
    total_km: float,
    operating_hours: float,
    waiting_hours: float = 0,
    days: int = 1,
    tolls=0,
    parking=0,
    driver_hotel_cost=0,
    is_international: bool = False,
    is_weekend: bool = False,
    is_holiday: bool = False,
    is_night: bool = False,
) -> PricingResult:
    days = max(1, int(days or 1))
    total_km_d = money(total_km)
    operating_hours_d = money(operating_hours)
    waiting_hours_d = money(waiting_hours)

    km_cost = money(total_km_d * money(profile.price_per_km))
    time_cost = money(operating_hours_d * money(profile.hourly_rate))
    waiting_cost = money(waiting_hours_d * money(profile.waiting_hourly_rate))

    direct_cost = money(
        km_cost
        + time_cost
        + waiting_cost
        + money(tolls)
        + money(parking)
        + money(driver_hotel_cost)
    )
    minimum_total = money(money(profile.minimum_day_rate) * days)
    subtotal = max(direct_cost, minimum_total)

    surcharge_pct = Decimal("0")
    if is_international:
        surcharge_pct += money(profile.international_surcharge_pct)
    if is_weekend:
        surcharge_pct += money(profile.weekend_surcharge_pct)
    if is_holiday:
        surcharge_pct += money(profile.holiday_surcharge_pct)
    if is_night:
        surcharge_pct += money(profile.night_surcharge_pct)

    surcharge_total = money(subtotal * surcharge_pct / Decimal("100"))
    net_total = money(subtotal + surcharge_total)
    vat_amount = money(net_total * money(profile.vat_percent) / Decimal("100"))
    gross_total = money(net_total + vat_amount)

    return PricingResult(
        km_cost=km_cost,
        time_cost=time_cost,
        waiting_cost=waiting_cost,
        direct_cost=direct_cost,
        minimum_total=minimum_total,
        surcharge_total=surcharge_total,
        net_total=net_total,
        vat_amount=vat_amount,
        gross_total=gross_total,
    )
