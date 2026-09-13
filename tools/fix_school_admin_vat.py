# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import re
import shutil
import sys

ROOT = Path.cwd()
ADMIN_PY = ROOT / "app" / "routes" / "admin.py"
DETAIL_TEMPLATE = ROOT / "app" / "templates" / "admin" / "bus_request_detail.html"
OFFER_TEMPLATE = ROOT / "app" / "templates" / "admin" / "bus_request_offer.html"


def read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def backup(path: Path) -> None:
    backup_path = path.with_suffix(path.suffix + ".bak_school_vat")
    if not backup_path.exists():
        shutil.copy2(path, backup_path)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        print(f"WARN: could not find block for {label}; skipped")
        return text
    return text.replace(old, new, 1)


def patch_admin_py() -> None:
    text = read(ADMIN_PY)
    backup(ADMIN_PY)

    helper_block = """
SCHOOL_INCLUDED_VAT_MARKER = \"[Schulpreis: Endpreis inkl. USt.]\"


def is_school_request(item) -> bool:
    haystack = \" \".join([
        str(getattr(item, \"trip_type\", \"\") or \"\"),
        str(getattr(item, \"customer_type\", \"\") or \"\"),
        str(getattr(item, \"organisation\", \"\") or \"\"),
        str(getattr(item, \"route_description\", \"\") or \"\"),
    ]).lower()
    return \"schul\" in haystack


def money_decimal(value, fallback=\"0.00\") -> Decimal:
    try:
        return Decimal(str(value if value is not None else fallback)).quantize(Decimal(\"0.01\"))
    except Exception:
        return Decimal(str(fallback)).quantize(Decimal(\"0.01\"))


def included_vat_breakdown(gross_total, vat_percent):
    gross_total = money_decimal(gross_total)
    vat_percent = Decimal(str(vat_percent or 0))

    if vat_percent <= 0:
        return gross_total, Decimal(\"0.00\"), gross_total

    divisor = Decimal(\"1.00\") + (vat_percent / Decimal(\"100\"))
    net_total = (gross_total / divisor).quantize(Decimal(\"0.01\"))
    vat_amount = (gross_total - net_total).quantize(Decimal(\"0.01\"))
    return net_total, vat_amount, gross_total


def calculation_display_values(item, calculation):
    if not calculation:
        return None

    vat_percent = calculation.profile.vat_percent if calculation.profile else 10

    if is_school_request(item):
        # Legacy school calculations were saved as:
        # net_total = customer-facing final price, gross_total = net_total + VAT.
        # New calculations carry SCHOOL_INCLUDED_VAT_MARKER and are saved as:
        # gross_total = customer-facing final price, net_total/VAT extracted from gross.
        note = calculation.manual_note or \"\"
        if SCHOOL_INCLUDED_VAT_MARKER in note:
            gross_basis = calculation.gross_total
        else:
            gross_basis = calculation.manual_override_net or calculation.net_total or calculation.gross_total

        net_total, vat_amount, gross_total = included_vat_breakdown(gross_basis, vat_percent)
        return {
            \"gross_total\": gross_total,
            \"net_total\": net_total,
            \"vat_amount\": vat_amount,
            \"vat_percent\": vat_percent,
            \"is_school_price\": True,
        }

    return {
        \"gross_total\": money_decimal(calculation.gross_total),
        \"net_total\": money_decimal(calculation.net_total),
        \"vat_amount\": money_decimal(calculation.vat_amount),
        \"vat_percent\": vat_percent,
        \"is_school_price\": False,
    }


def attach_calculation_display_values(item):
    for calculation in list(getattr(item, \"calculations\", []) or []):
        values = calculation_display_values(item, calculation)
        if not values:
            continue
        calculation.display_gross_total = values[\"gross_total\"]
        calculation.display_net_total = values[\"net_total\"]
        calculation.display_vat_amount = values[\"vat_amount\"]
        calculation.display_vat_percent = values[\"vat_percent\"]
        calculation.display_is_school_price = values[\"is_school_price\"]

"""

    if "SCHOOL_INCLUDED_VAT_MARKER" not in text:
        marker = "def build_offer_context"
        if marker not in text:
            raise RuntimeError("Could not find build_offer_context in admin.py")
        text = text.replace(marker, helper_block + "\n" + marker, 1)

    old_detail_return = '    profiles = PricingProfile.query.filter_by(is_active=True).order_by(PricingProfile.name.asc()).all()\n    return render_template("admin/bus_request_detail.html", item=item, profiles=profiles)'
    new_detail_return = '    profiles = PricingProfile.query.filter_by(is_active=True).order_by(PricingProfile.name.asc()).all()\n    attach_calculation_display_values(item)\n    return render_template("admin/bus_request_detail.html", item=item, profiles=profiles, school_pricing_mode=is_school_request(item))'
    text = replace_once(text, old_detail_return, new_detail_return, "bus_request_detail render context")

    build_start = text.find("def build_offer_context")
    if build_start == -1:
        raise RuntimeError("build_offer_context not found after helper insertion")
    next_decorator = text.find("\n\n@admin_bp", build_start)
    if next_decorator == -1:
        raise RuntimeError("Could not find end of build_offer_context")

    new_build = '''def build_offer_context(item: BusRentalRequest, calculation: PricingCalculation | None):
    display_values = calculation_display_values(item, calculation) if calculation else None

    price_gross = display_values["gross_total"] if display_values else None
    price_net = display_values["net_total"] if display_values else None
    vat_amount = display_values["vat_amount"] if display_values else None
    vat_percent = display_values["vat_percent"] if display_values else (calculation.profile.vat_percent if calculation and calculation.profile else 10)
    is_school_price = bool(display_values and display_values.get("is_school_price"))

    subject = f"Angebot Austria Express – {item.departure_place} → {item.destination}"

    route_line = f"{item.departure_place} → {item.destination}"
    date_line = offer_date(item.date_start)
    if item.date_end:
        date_line = f"{date_line} – {item.date_end}"

    time_line = item.time_departure or "-"
    if item.time_return:
        time_line = f"{time_line} / Rückfahrt {item.time_return}"

    pax_line = f"{item.passengers} Personen" if item.passengers else "laut Anfrage"
    bus_line = item.bus_size or "passender Reisebus"

    if calculation and is_school_price:
        price_lines = (
            f"{offer_money(price_gross)} inkl. gesetzlicher USt.\n"
            f"Enthaltene USt. ({vat_percent}%): {offer_money(vat_amount)}; Nettoanteil: {offer_money(price_net)}."
        )
    elif calculation:
        price_lines = (
            f"{offer_money(price_gross)} brutto\n"
            f"Netto {offer_money(price_net)} zzgl. {vat_percent}% USt. ({offer_money(vat_amount)})"
        )
    else:
        price_lines = "Preis vorbehaltlich finaler Kalkulation."

    plain_text = f"""Sehr geehrte Damen und Herren,

vielen Dank für Ihre Anfrage. Gerne unterbreiten wir Ihnen folgendes Angebot:

Route:
{route_line}

Datum:
{date_line}

Zeit:
{time_line}

Gruppe:
{pax_line}

Fahrzeug:
{bus_line}

Leistung:
Bereitstellung eines passenden Reisebusses inkl. Fahrer für die angefragte Fahrt laut Programm und Angaben in Ihrer Anfrage.

Preis:
{price_lines}

Hinweise:
- Angebot freibleibend bis zur schriftlichen Bestätigung.
- Änderungen der Route, Zeiten, Gruppengröße oder Zusatzleistungen können zu einer Preisanpassung führen.
- Parkgebühren, Mauten, Einfahrtsgebühren oder Unterkunftskosten für Fahrer sind nur enthalten, wenn ausdrücklich angegeben.
- Stornobedingungen laut unseren AGB bzw. individueller Auftragsbestätigung.

Mit freundlichen Grüßen
Austria Express
AUSTRIAN INCENTIVE SERVICE GmbH
office@austria-express.eu
+43 676 849 113 200
"""

    mailto_body = quote(plain_text)
    mailto_subject = quote(subject)

    return {
        "subject": subject,
        "route_line": route_line,
        "date_line": date_line,
        "time_line": time_line,
        "pax_line": pax_line,
        "bus_line": bus_line,
        "price_gross": price_gross,
        "price_net": price_net,
        "vat_amount": vat_amount,
        "vat_percent": vat_percent,
        "is_school_price": is_school_price,
        "plain_text": plain_text,
        "mailto_subject": mailto_subject,
        "mailto_body": mailto_body,
    }
'''
    text = text[:build_start] + new_build + text[next_decorator:]

    old_price_block = '''    manual_override_net = (
        Decimal(str(to_float(request.form.get("manual_override_net"), 0)))
        if request.form.get("manual_override_net")
        else None
    )

    # The customer-facing offer amount should use the manual override when present.
    # The component calculation remains visible for control, but final net/vat/gross
    # reflect the override.
    final_net_total = manual_override_net if manual_override_net is not None else result.net_total
    final_vat_amount = Decimal(str(final_net_total * Decimal(str(profile.vat_percent or 0)) / Decimal("100"))).quantize(Decimal("0.01"))
    final_gross_total = Decimal(str(final_net_total + final_vat_amount)).quantize(Decimal("0.01"))
'''
    new_price_block = '''    manual_override_net = (
        Decimal(str(to_float(request.form.get("manual_override_net"), 0)))
        if request.form.get("manual_override_net")
        else None
    )

    manual_note = request.form.get("manual_note", "").strip() or None

    # For school inquiries the public frontend prices are already customer-facing
    # final prices incl. statutory VAT. Therefore the admin must not add VAT again.
    if is_school_request(item):
        final_customer_total = manual_override_net if manual_override_net is not None else result.net_total
        final_net_total, final_vat_amount, final_gross_total = included_vat_breakdown(final_customer_total, profile.vat_percent or 10)

        marker_note = SCHOOL_INCLUDED_VAT_MARKER + " Keine zusätzliche USt. auf Schulpreise aufschlagen."
        manual_note = (manual_note + "\n\n" + marker_note) if manual_note else marker_note
    else:
        # Standard bus rental calculations: profile rates are treated as net values,
        # VAT is added on top.
        final_net_total = manual_override_net if manual_override_net is not None else result.net_total
        final_vat_amount = Decimal(str(final_net_total * Decimal(str(profile.vat_percent or 0)) / Decimal("100"))).quantize(Decimal("0.01"))
        final_gross_total = Decimal(str(final_net_total + final_vat_amount)).quantize(Decimal("0.01"))
'''
    if old_price_block in text:
        text = text.replace(old_price_block, new_price_block, 1)
    elif "Keine zusätzliche USt. auf Schulpreise" not in text:
        print("WARN: price calculation block not found exactly; trying regex patch")
        pattern = re.compile(
            r"    manual_override_net = \([\s\S]*?final_gross_total = Decimal\(str\(final_net_total \+ final_vat_amount\)\)\.quantize\(Decimal\(\"0\.01\"\)\)\n",
            re.M,
        )
        text, n = pattern.subn(new_price_block, text, count=1)
        if n == 0:
            raise RuntimeError("Could not patch pricing VAT logic")

    text = text.replace(
        'manual_note=request.form.get("manual_note", "").strip() or None,',
        'manual_note=manual_note,',
        1,
    )

    write(ADMIN_PY, text)
    print(f"Patched {ADMIN_PY}")


def patch_detail_template() -> None:
    text = read(DETAIL_TEMPLATE)
    backup(DETAIL_TEMPLATE)

    if "school_pricing_mode" not in text:
        text = text.replace(
            "{% set latest_calc = item.calculations[-1] if item.calculations else None %}",
            "{% set latest_calc = item.calculations[-1] if item.calculations else None %}\n{% set school_pricing_mode = school_pricing_mode if school_pricing_mode is defined else ('schul' in (((item.trip_type or '') ~ ' ' ~ (item.customer_type or '') ~ ' ' ~ (item.route_description or ''))|lower)) %}",
            1,
        )

    old_latest = '''        <div class="mt-3 text-4xl font-black">{{ latest_calc.gross_total }} €</div>
        <div class="mt-1 text-sm text-slate-300">Brutto · Netto {{ latest_calc.net_total }} € · USt {{ latest_calc.vat_amount }} €</div>
        {% if latest_calc.manual_override_net %}
          <div class="mt-3 rounded-2xl bg-white/10 p-3 text-sm font-bold">Manual Override Netto: {{ latest_calc.manual_override_net }} €</div>
        {% endif %}'''
    new_latest = '''        {% if school_pricing_mode %}
          <div class="mt-3 text-4xl font-black">{{ latest_calc.display_gross_total|default(latest_calc.net_total) }} €</div>
          <div class="mt-1 text-sm text-slate-300">Endpreis lt. Schulpreis-Kalkulation · inkl. gesetzlicher USt.</div>
          <div class="mt-1 text-sm text-slate-300">Nettoanteil {{ latest_calc.display_net_total|default(latest_calc.net_total) }} € · enthaltene USt. {{ latest_calc.display_vat_amount|default(latest_calc.vat_amount) }} €</div>
        {% else %}
          <div class="mt-3 text-4xl font-black">{{ latest_calc.gross_total }} €</div>
          <div class="mt-1 text-sm text-slate-300">Brutto · Netto {{ latest_calc.net_total }} € · USt {{ latest_calc.vat_amount }} €</div>
        {% endif %}
        {% if latest_calc.manual_override_net %}
          <div class="mt-3 rounded-2xl bg-white/10 p-3 text-sm font-bold">Manual Override {% if school_pricing_mode %}Endpreis{% else %}Netto{% endif %}: {{ latest_calc.manual_override_net }} €</div>
        {% endif %}'''
    text = replace_once(text, old_latest, new_latest, "latest calculation display")

    old_label = '<label class="font-bold">Manual Override Netto<input class="field mt-2" name="manual_override_net" inputmode="decimal" placeholder="optional"></label>'
    new_label = '<label class="font-bold">Manual Override {% if school_pricing_mode %}Endpreis inkl. USt.{% else %}Netto{% endif %}<input class="field mt-2" name="manual_override_net" inputmode="decimal" placeholder="optional"></label>'
    text = text.replace(old_label, new_label, 1)

    old_history = '''            <div class="text-sm text-slate-500">Brutto</div>
            <div class="text-2xl font-black text-red-700">{{ c.gross_total }} €</div>
            <div class="text-xs text-slate-500">Netto {{ c.net_total }} € · USt {{ c.vat_amount }} €</div>'''
    new_history = '''            {% if school_pricing_mode %}
              <div class="text-sm text-slate-500">Endpreis inkl. USt.</div>
              <div class="text-2xl font-black text-red-700">{{ c.display_gross_total|default(c.net_total) }} €</div>
              <div class="text-xs text-slate-500">Nettoanteil {{ c.display_net_total|default(c.net_total) }} € · USt enthalten {{ c.display_vat_amount|default(c.vat_amount) }} €</div>
            {% else %}
              <div class="text-sm text-slate-500">Brutto</div>
              <div class="text-2xl font-black text-red-700">{{ c.gross_total }} €</div>
              <div class="text-xs text-slate-500">Netto {{ c.net_total }} € · USt {{ c.vat_amount }} €</div>
            {% endif %}'''
    text = replace_once(text, old_history, new_history, "calculation history display")

    write(DETAIL_TEMPLATE, text)
    print(f"Patched {DETAIL_TEMPLATE}")


def patch_offer_template() -> None:
    text = read(OFFER_TEMPLATE)
    backup(OFFER_TEMPLATE)

    old_price = '''          <div class="mt-3 text-4xl font-black">{{ calculation.gross_total }} €</div>
          <div class="mt-1 text-sm text-slate-300">Brutto · Netto {{ calculation.net_total }} € · USt {{ calculation.vat_amount }} €</div>
          <div class="mt-3 text-sm text-slate-300">{{ calculation.profile.name }} · {{ calculation.total_km }} km · {{ calculation.operating_hours }} h</div>'''
    new_price = '''          <div class="mt-3 text-4xl font-black">{{ offer.price_gross }} €</div>
          {% if offer.is_school_price %}
            <div class="mt-1 text-sm text-slate-300">Endpreis lt. Schulpreis-Kalkulation · inkl. gesetzlicher USt.</div>
            <div class="mt-1 text-sm text-slate-300">Nettoanteil {{ offer.price_net }} € · enthaltene USt. {{ offer.vat_amount }} €</div>
          {% else %}
            <div class="mt-1 text-sm text-slate-300">Brutto · Netto {{ offer.price_net }} € · USt {{ offer.vat_amount }} €</div>
          {% endif %}
          <div class="mt-3 text-sm text-slate-300">{{ calculation.profile.name }} · {{ calculation.total_km }} km · {{ calculation.operating_hours }} h</div>'''
    text = replace_once(text, old_price, new_price, "offer price display")

    write(OFFER_TEMPLATE, text)
    print(f"Patched {OFFER_TEMPLATE}")


def main() -> int:
    patch_admin_py()
    patch_detail_template()
    patch_offer_template()
    print("\nDone. Run now:")
    print("python -m py_compile app\\routes\\admin.py")
    print("git diff")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
