# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import py_compile
import re
import shutil
import traceback

path = Path("app/routes/admin.py")

if not path.exists():
    raise SystemExit("ERROR: app/routes/admin.py wurde nicht gefunden. Bitte im Projektordner ausführen.")

text = path.read_text(encoding="utf-8")
backup = path.with_suffix(path.suffix + ".bak_fstring_fix_v2")
shutil.copy2(path, backup)


def replace_build_offer_context(source: str) -> str:
    start = source.find("def build_offer_context(")
    if start == -1:
        print("WARN: def build_offer_context(...) nicht gefunden; überspringe Funktionsersetzung.")
        return source

    end = source.find("\n\n@admin_bp", start)
    if end == -1:
        print("WARN: Ende von build_offer_context nicht gefunden; überspringe Funktionsersetzung.")
        return source

    new_function = """def build_offer_context(item: BusRentalRequest, calculation: PricingCalculation | None):
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
            f"{offer_money(price_gross)} inkl. gesetzlicher USt.\\\\n"
            f"Enthaltene USt. ({vat_percent}%): {offer_money(vat_amount)}; Nettoanteil: {offer_money(price_net)}."
        )
    elif calculation:
        price_lines = (
            f"{offer_money(price_gross)} brutto\\\\n"
            f"Netto {offer_money(price_net)} zzgl. {vat_percent}% USt. ({offer_money(vat_amount)})"
        )
    else:
        price_lines = "Preis vorbehaltlich finaler Kalkulation."

    plain_text = f\\\"\\\"\\\"Sehr geehrte Damen und Herren,

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
\\\"\\\"\\\"

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
"""
    print("OK: build_offer_context ersetzt.")
    return source[:start] + new_function + source[end:]


text = replace_build_offer_context(text)

# Repair broken normal string caused by an older patch:
# manual_note = (manual_note + "
#
# " + marker_note) ...
text = re.sub(
    r'manual_note\s*=\s*\(manual_note\s*\+\s*"\s*\n\s*\n\s*"\s*\+\s*marker_note\)\s*if\s*manual_note\s*else\s*marker_note',
    'manual_note = (manual_note + "\\\\n\\\\n" + marker_note) if manual_note else marker_note',
    text,
    flags=re.S,
)

# Additional targeted repairs, in case a broken block remains outside build_offer_context.
text = text.replace(
    'f"{offer_money(price_gross)} inkl. gesetzlicher USt.\n"',
    'f"{offer_money(price_gross)} inkl. gesetzlicher USt.\\\\n"',
)
text = text.replace(
    'f"{offer_money(price_gross)} brutto\n"',
    'f"{offer_money(price_gross)} brutto\\\\n"',
)

path.write_text(text, encoding="utf-8")

try:
    py_compile.compile(str(path), doraise=True)
except Exception:
    print("Noch nicht vollständig behoben.")
    print("Backup liegt hier:", backup)

    tb = traceback.format_exc()
    print(tb)
    m = re.search(r'line (\d+)', tb)
    if m:
        line_no = int(m.group(1))
        lines = path.read_text(encoding="utf-8").splitlines()
        start = max(1, line_no - 8)
        end = min(len(lines), line_no + 8)
        print("\\n--- Ausschnitt admin.py ---")
        for i in range(start, end + 1):
            pointer = ">>" if i == line_no else "  "
            print(f"{pointer} {i:04d}: {lines[i-1]}")
    raise SystemExit(1)

print("OK: app/routes/admin.py kompiliert wieder.")
print("Backup:", backup)
