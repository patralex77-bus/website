# -*- coding: utf-8 -*-
from pathlib import Path
import py_compile
import shutil
import traceback
import re

path = Path("app/routes/admin.py")

if not path.exists():
    raise SystemExit("ERROR: app/routes/admin.py wurde nicht gefunden. Bitte im Projektordner ausführen.")

backup = path.with_suffix(path.suffix + ".bak_fstring_fix_v3")
shutil.copy2(path, backup)

text = path.read_text(encoding="utf-8")

# Fix the exact problem introduced by the previous fixer:
# plain_text = f\"\"\"  ->  plain_text = f"""
# \"\"\"              ->  """
text = text.replace(r'f\"\"\"', 'f"""')
text = text.replace(r'\"\"\"', '"""')

# Fix price_lines if a physical newline is still inside the short f-strings.
text = re.sub(
    r'f"\{offer_money\(price_gross\)\} inkl\. gesetzlicher USt\.\s*\n\s*"',
    'f"{offer_money(price_gross)} inkl. gesetzlicher USt.\\n"',
    text,
    flags=re.S,
)
text = re.sub(
    r'f"\{offer_money\(price_gross\)\} brutto\s*\n\s*"',
    'f"{offer_money(price_gross)} brutto\\n"',
    text,
    flags=re.S,
)

# Fix manual_note newline if it was also split incorrectly.
text = re.sub(
    r'manual_note\s*=\s*\(manual_note\s*\+\s*"\s*\n\s*\n\s*"\s*\+\s*marker_note\)\s*if\s*manual_note\s*else\s*marker_note',
    'manual_note = (manual_note + "\\n\\n" + marker_note) if manual_note else marker_note',
    text,
    flags=re.S,
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
        print("\n--- Ausschnitt admin.py ---")
        for i in range(start, end + 1):
            pointer = ">>" if i == line_no else "  "
            print(f"{pointer} {i:04d}: {lines[i-1]}")

    raise SystemExit(1)

print("OK: app/routes/admin.py kompiliert wieder.")
print("Backup:", backup)
