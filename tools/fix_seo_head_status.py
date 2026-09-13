# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import json
import py_compile
import shutil
import re

ROOT = Path(".")
content_path = ROOT / "app" / "routes" / "seo_landing_content.json"
base_path = ROOT / "app" / "templates" / "base.html"
public_templates_dir = ROOT / "app" / "templates" / "public"

TITLE_FIXES = {
    "bus-mieten-wien": "Bus mieten Wien – Reisebus mit Fahrer | Austria Express",
    "reisebus-mieten-wien": "Reisebus mieten Wien – Komfortbus für Gruppen | Austria Express",
    "schulfahrten-wien": "Schulfahrten Wien – Bus für Klassen | Austria Express",
    "schulausflug-wien": "Schulausflug Wien – Bus für Schulen | Austria Express",
    "kindertransport-wien": "Kindertransport Wien – Bus für Kindergruppen | Austria Express",
    "gruppentransfer-wien": "Gruppentransfer Wien – Flughafen, Hotel & Event | Austria Express",
    "firmenausflug-bus-wien": "Firmenausflug Bus Wien – Betriebsausflug | Austria Express",
    "vereinsausflug-bus-wien": "Vereinsausflug Bus Wien – Reisebus für Vereine | Austria Express",
    "tagesausflug-bus-wien": "Tagesausflug Bus Wien – Gruppenfahrt | Austria Express",
    "transportservice-wien": "Transportservice Wien – Bus & Gruppenbeförderung | Austria Express",
    "busunternehmen-wien": "Busunternehmen Wien – Gruppen, Schulen & Transfers | Austria Express",
}


def backup(path: Path):
    if path.exists():
        backup_path = path.with_suffix(path.suffix + ".bak_seo_head_fix_v1")
        if not backup_path.exists():
            shutil.copy2(path, backup_path)


def fix_titles():
    if not content_path.exists():
        print("WARN: app/routes/seo_landing_content.json nicht gefunden. Titles wurden nicht geändert.")
        return

    backup(content_path)

    pages = json.loads(content_path.read_text(encoding="utf-8"))
    changed = 0

    for page in pages:
        slug = page.get("slug")
        if slug in TITLE_FIXES and page.get("title") != TITLE_FIXES[slug]:
            page["title"] = TITLE_FIXES[slug]
            changed += 1

    content_path.write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")

    too_long = [(p.get("slug"), len(p.get("title", "")), p.get("title", "")) for p in pages if len(p.get("title", "")) > 75]
    too_short_desc = [(p.get("slug"), len(p.get("meta_description", ""))) for p in pages if len(p.get("meta_description", "")) < 50]
    too_long_desc = [(p.get("slug"), len(p.get("meta_description", ""))) for p in pages if len(p.get("meta_description", "")) > 180]

    if too_long:
        print("WARN: Some titles are still longer than 75 characters:")
        for item in too_long:
            print("  ", item)
    else:
        print(f"OK: landing page titles shortened/checked. Changed: {changed}")

    if too_short_desc or too_long_desc:
        print("WARN: Some meta descriptions are outside 50-180 chars.")
        print("  too short:", too_short_desc)
        print("  too long:", too_long_desc)


def ensure_base_canonical():
    if not base_path.exists():
        print("WARN: app/templates/base.html nicht gefunden. Base canonical wurde nicht eingefügt.")
        return

    text = base_path.read_text(encoding="utf-8")
    backup(base_path)

    if "SEO_CANONICAL_BASE_FIX_V1" in text:
        print("OK: base canonical already patched")
        return

    canonical_block = """  <!-- SEO_CANONICAL_BASE_FIX_V1 -->
  {% if canonical is defined %}
  <link rel="canonical" href="{{ canonical }}">
  {% elif page is defined and page.canonical is defined %}
  <link rel="canonical" href="{{ page.canonical }}">
  {% else %}
  <link rel="canonical" href="{{ request.base_url }}">
  {% endif %}
"""

    meta_match = re.search(r'^\s*<meta\s+name=["\']description["\'][^\n]*>\s*$', text, flags=re.M)
    if meta_match:
        insert_at = meta_match.end() + 1
        text = text[:insert_at] + canonical_block + text[insert_at:]
    else:
        head_pos = text.find("</head>")
        if head_pos == -1:
            print("WARN: </head> not found in base.html. Canonical not inserted.")
            return
        text = text[:head_pos] + canonical_block + text[head_pos:]

    base_path.write_text(text, encoding="utf-8")
    print("OK: canonical fallback inserted in base.html")


def ensure_public_template_canonicals():
    if not public_templates_dir.exists():
        print("WARN: app/templates/public nicht gefunden. Standalone canonical check übersprungen.")
        return

    changed = []
    for path in public_templates_dir.glob("*.html"):
        text = path.read_text(encoding="utf-8")

        # Templates extending base.html do not have their own <head>; base handles canonical now.
        if "<head" not in text.lower():
            continue

        backup(path)

        # Fix accidental double slash canonical caused by request.url_root + "/path".
        new_text = text.replace("{{ request.url_root }}/", "{{ request.url_root.rstrip('/') }}/")
        new_text = new_text.replace("{{request.url_root}}/", "{{ request.url_root.rstrip('/') }}/")

        # Add a canonical if this standalone template has none.
        if 'rel="canonical"' not in new_text and "rel='canonical'" not in new_text:
            canonical_line = '  <link rel="canonical" href="{{ request.base_url }}">\n'
            meta_match = re.search(r'^\s*<meta\s+name=["\']description["\'][^\n]*>\s*$', new_text, flags=re.M)
            if meta_match:
                insert_at = meta_match.end() + 1
                new_text = new_text[:insert_at] + canonical_line + new_text[insert_at:]
            else:
                head_pos = new_text.find("</head>")
                if head_pos != -1:
                    new_text = new_text[:head_pos] + canonical_line + new_text[head_pos:]

        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed.append(str(path))

    if changed:
        print("OK: standalone template canonicals checked/fixed:")
        for item in changed:
            print("  ", item)
    else:
        print("OK: standalone template canonicals already looked fine")


def compile_checks():
    for path in [
        ROOT / "app" / "routes" / "seo_landing.py",
        ROOT / "app" / "__init__.py",
        ROOT / "app" / "routes" / "public.py",
    ]:
        if path.exists():
            py_compile.compile(str(path), doraise=True)
            print("OK compiled:", path)

    if content_path.exists():
        json.loads(content_path.read_text(encoding="utf-8"))
        print("OK JSON:", content_path)


fix_titles()
ensure_base_canonical()
ensure_public_template_canonicals()
compile_checks()

print("\nDone.")
print("After commit/push/deploy, run:")
print("  python tools\\check_seo_status.py https://website-mq6h.onrender.com")
