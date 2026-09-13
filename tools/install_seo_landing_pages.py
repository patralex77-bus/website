# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import py_compile
import shutil
import re

ROOT = Path(".")
init_path = ROOT / "app" / "__init__.py"
public_path = ROOT / "app" / "routes" / "public.py"
seo_route_path = ROOT / "app" / "routes" / "seo_landing.py"

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
    "/busunternehmen-wien",
    "/transportservice-wien",
]


def backup(path: Path):
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak_seo_landing_v1"))


def patch_init():
    if not init_path.exists():
        raise SystemExit("ERROR: app/__init__.py nicht gefunden.")

    text = init_path.read_text(encoding="utf-8")
    backup(init_path)

    if "seo_landing_bp" not in text:
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
    print("OK: app/__init__.py patched")


def patch_sitemap():
    if not public_path.exists():
        print("WARN: app/routes/public.py nicht gefunden. Sitemap wurde nicht erweitert.")
        return

    text = public_path.read_text(encoding="utf-8")
    backup(public_path)

    if "SEO_LANDING_PAGES_V1_START" in text:
        print("OK: Sitemap entries already present")
        return

    lines = [
        '        # SEO_LANDING_PAGES_V1_START',
    ]
    for url in LANDING_PAGES:
        lines.append(f'        {{"loc": "{url}", "priority": "0.75", "changefreq": "monthly"}},')
    lines.append('        # SEO_LANDING_PAGES_V1_END')
    block = "\n".join(lines) + "\n"

    # Prefer insertion after /anfrage, fallback after /bus-rental.
    patterns = [
        r'(\s*\{"loc": "/anfrage", "priority": "[^"]+", "changefreq": "[^"]+"\},\n)',
        r'(\s*\{"loc": "/bus-rental", "priority": "[^"]+", "changefreq": "[^"]+"\},\n)',
    ]

    patched = False
    for pattern in patterns:
        new_text, count = re.subn(pattern, r"\1" + block, text, count=1)
        if count:
            text = new_text
            patched = True
            break

    if not patched:
        print("WARN: static_pages insertion point not found. Sitemap unchanged.")
        return

    public_path.write_text(text, encoding="utf-8")
    print("OK: app/routes/public.py sitemap patched")


def compile_check():
    for p in [seo_route_path, init_path, public_path]:
        if p.exists():
            py_compile.compile(str(p), doraise=True)
            print("OK compiled:", p)


patch_init()
patch_sitemap()
compile_check()
print("SEO landing pages installed.")
