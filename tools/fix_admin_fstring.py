from pathlib import Path
import re
import py_compile
import shutil

path = Path("app/routes/admin.py")

if not path.exists():
    raise SystemExit("ERROR: app/routes/admin.py wurde nicht gefunden. Bitte im Projektordner ausführen.")

text = path.read_text(encoding="utf-8")
backup = path.with_suffix(path.suffix + ".bak_fstring_fix")
backup.write_text(text, encoding="utf-8")

# Fix broken multiline f-string around: inkl. gesetzlicher USt.
# Typical broken shape:
# f"{offer_money(price_gross)} inkl. gesetzlicher USt.
# ..."
text = re.sub(
    r'f"\{offer_money\(price_gross\)\} inkl\. gesetzlicher USt\.\s*\n\s*"',
    'f"{offer_money(price_gross)} inkl. gesetzlicher USt."',
    text,
)

# More tolerant fallback: replace any f-string that starts with this exact text and is broken by a physical newline.
text = re.sub(
    r'f"\{offer_money\(price_gross\)\} inkl\. gesetzlicher USt\.\s*\n\s*([^\\n"]*)',
    'f"{offer_money(price_gross)} inkl. gesetzlicher USt."',
    text,
)

# Fix another possible shape created by replacement with a literal newline before closing quote.
text = text.replace(
    'f"{offer_money(price_gross)} inkl. gesetzlicher USt.\n"',
    'f"{offer_money(price_gross)} inkl. gesetzlicher USt."',
)

path.write_text(text, encoding="utf-8")

try:
    py_compile.compile(str(path), doraise=True)
except Exception as exc:
    print("Noch nicht vollständig behoben. Backup liegt hier:", backup)
    print("Fehler:", exc)
    raise

print("OK: admin.py kompiliert wieder.")
print("Backup:", backup)
