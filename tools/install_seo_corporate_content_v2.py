# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import py_compile
import re
import shutil

ROOT = Path(".")
init_path = ROOT / "app" / "__init__.py"
public_path = ROOT / "app" / "routes" / "public.py"
index_path = ROOT / "app" / "templates" / "public" / "index.html"
seo_route_path = ROOT / "app" / "routes" / "seo_landing.py"
content_path = ROOT / "app" / "routes" / "seo_landing_content.json"

LANDING_PAGES = [
    "/bus-mieten-wien",
    "/reisebus-mieten-wien",
    "/schulfahrten-wien",
    "/schulausflug-wien",
    "/kindertransport-wien",
    "/gruppentransfer-wien",
    "/firmenausflug-bus-wien",
    "/vereinsausflug-bus-wien",
    "/tagesausflug-bus-wien",
    "/transportservice-wien",
    "/busunternehmen-wien",
]


def backup(path: Path):
    if path.exists():
        backup_path = path.with_suffix(path.suffix + ".bak_seo_corporate_v2")
        if not backup_path.exists():
            shutil.copy2(path, backup_path)


def patch_init():
    if not init_path.exists():
        raise SystemExit("ERROR: app/__init__.py nicht gefunden.")

    text = init_path.read_text(encoding="utf-8")
    backup(init_path)

    if "from .routes.seo_landing import seo_landing_bp" not in text:
        text = text.replace(
            "    from .routes.admin import admin_bp\n",
            "    from .routes.admin import admin_bp\n    from .routes.seo_landing import seo_landing_bp\n",
            1,
        )

    if "app.register_blueprint(seo_landing_bp)" not in text:
        text = text.replace(
            "    app.register_blueprint(public_bp)\n",
            "    app.register_blueprint(public_bp)\n    app.register_blueprint(seo_landing_bp)\n",
            1,
        )

    init_path.write_text(text, encoding="utf-8")
    print("OK: blueprint registration checked")


def patch_sitemap():
    if not public_path.exists():
        print("WARN: app/routes/public.py nicht gefunden. Sitemap wurde nicht erweitert.")
        return

    text = public_path.read_text(encoding="utf-8")
    backup(public_path)

    missing = [url for url in LANDING_PAGES if f'"loc": "{url}"' not in text and f"'loc': '{url}'" not in text]
    if not missing:
        print("OK: all landing pages already in sitemap")
        return

    lines = ["        # SEO_CORPORATE_LANDING_PAGES_V2_START"]
    for url in missing:
        lines.append(f'        {{"loc": "{url}", "priority": "0.75", "changefreq": "monthly"}},')
    lines.append("        # SEO_CORPORATE_LANDING_PAGES_V2_END")
    block = "\n".join(lines) + "\n"

    patterns = [
        r'(\s*\{"loc": "/anfrage", "priority": "[^"]+", "changefreq": "[^"]+"\},\n)',
        r'(\s*\{"loc": "/bus-rental", "priority": "[^"]+", "changefreq": "[^"]+"\},\n)',
        r'(\s*static_pages\s*=\s*\[\n)',
    ]

    for pattern in patterns:
        new_text, count = re.subn(pattern, r"\1" + block, text, count=1)
        if count:
            public_path.write_text(new_text, encoding="utf-8")
            print("OK: sitemap entries checked/added")
            return

    print("WARN: sitemap insertion point not found. Bitte /sitemap.xml später prüfen.")


def patch_home_links():
    if not index_path.exists():
        print("WARN: homepage template nicht gefunden. Interne SEO-Links wurden nicht eingefügt.")
        return

    text = index_path.read_text(encoding="utf-8")
    backup(index_path)

    if "<!-- SEO_LANDING_INTERNAL_LINKS_V1 -->" in text:
        start = text.find("<!-- SEO_LANDING_INTERNAL_LINKS_V1 -->")
        footer = text.find("  <footer", start)
        if footer != -1:
            text = text[:start] + text[footer:]

    if "SEO_CORPORATE_LANDING_LINKS_V2" in text:
        index_path.write_text(text, encoding="utf-8")
        print("OK: homepage link block already present")
        return

    block = """
  <!-- SEO_CORPORATE_LANDING_LINKS_V2 -->
  <section class="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
    <div class="rounded-[2rem] border border-slate-200 bg-white p-8 shadow-sm">
      <p class="text-sm font-black uppercase tracking-[.18em] text-red-700">Beliebte Leistungen</p>
      <h2 class="mt-3 text-3xl font-black">Bus, Transport und Ausflüge ab Wien</h2>
      <p class="mt-4 max-w-3xl leading-7 text-slate-600">Für viele Gruppen beginnt die Suche mit einer konkreten Situation: Schule, Kindergruppe, Firmenfahrt, Vereinsausflug oder Transfer. Diese Seiten führen direkt zu den passenden Informationen.</p>
      <div class="mt-6 flex flex-wrap gap-3 text-sm font-bold">
        <a href="/bus-mieten-wien" class="rounded-2xl bg-slate-100 px-4 py-3 hover:bg-red-700 hover:text-white">Bus mieten Wien</a>
        <a href="/reisebus-mieten-wien" class="rounded-2xl bg-slate-100 px-4 py-3 hover:bg-red-700 hover:text-white">Reisebus mieten Wien</a>
        <a href="/schulfahrten-wien" class="rounded-2xl bg-slate-100 px-4 py-3 hover:bg-red-700 hover:text-white">Schulfahrten Wien</a>
        <a href="/schulausflug-wien" class="rounded-2xl bg-slate-100 px-4 py-3 hover:bg-red-700 hover:text-white">Schulausflug Wien</a>
        <a href="/kindertransport-wien" class="rounded-2xl bg-slate-100 px-4 py-3 hover:bg-red-700 hover:text-white">Kindertransport Wien</a>
        <a href="/gruppentransfer-wien" class="rounded-2xl bg-slate-100 px-4 py-3 hover:bg-red-700 hover:text-white">Gruppentransfer Wien</a>
        <a href="/firmenausflug-bus-wien" class="rounded-2xl bg-slate-100 px-4 py-3 hover:bg-red-700 hover:text-white">Firmenausflug Bus Wien</a>
        <a href="/vereinsausflug-bus-wien" class="rounded-2xl bg-slate-100 px-4 py-3 hover:bg-red-700 hover:text-white">Vereinsausflug Bus Wien</a>
        <a href="/tagesausflug-bus-wien" class="rounded-2xl bg-slate-100 px-4 py-3 hover:bg-red-700 hover:text-white">Tagesausflug Bus Wien</a>
        <a href="/transportservice-wien" class="rounded-2xl bg-slate-100 px-4 py-3 hover:bg-red-700 hover:text-white">Transportservice Wien</a>
      </div>
    </div>
  </section>
"""

    footer_pos = text.find("  <footer")
    if footer_pos != -1:
        text = text[:footer_pos] + block + text[footer_pos:]
        index_path.write_text(text, encoding="utf-8")
        print("OK: homepage landing links inserted")
    else:
        print("WARN: footer not found. Homepage links were not inserted.")


def compile_check():
    for p in [seo_route_path, init_path, public_path]:
        if p.exists():
            py_compile.compile(str(p), doraise=True)
            print("OK compiled:", p)

    if content_path.exists():
        import json
        json.loads(content_path.read_text(encoding="utf-8"))
        print("OK JSON:", content_path)


patch_init()
patch_sitemap()
patch_home_links()
compile_check()
print("SEO corporate content v2 installed.")
