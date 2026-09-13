from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, abort, render_template, request

seo_landing_bp = Blueprint("seo_landing", __name__)

_CONTENT_PATH = Path(__file__).with_name("seo_landing_content.json")


def _load_pages() -> list[dict]:
    return json.loads(_CONTENT_PATH.read_text(encoding="utf-8"))


LANDING_PAGES = _load_pages()
LANDING_URLS = ["/" + page["slug"] for page in LANDING_PAGES]


def _site_url(path: str) -> str:
    return request.url_root.rstrip("/") + "/" + path.lstrip("/")


def _schema_for(page: dict) -> str:
    faq_entities = [
        {
            "@type": "Question",
            "name": item["q"],
            "acceptedAnswer": {
                "@type": "Answer",
                "text": item["a"],
            },
        }
        for item in page.get("faq", [])
    ]

    schema = [
        {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": "Austria Express",
            "legalName": "AUSTRIAN INCENTIVE SERVICE GmbH",
            "url": request.url_root.rstrip("/"),
            "telephone": "+43 676 849 113 200",
            "email": "office@austria-express.eu",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "Landstraßer Hauptstraße 2, Büro Top Nr. M2.01.27",
                "postalCode": "1030",
                "addressLocality": "Wien",
                "addressCountry": "AT",
            },
            "areaServed": ["Wien", "Niederösterreich", "Österreich", "Europa"],
        },
        {
            "@context": "https://schema.org",
            "@type": "Service",
            "name": page["h1"],
            "description": page["meta_description"],
            "provider": {
                "@type": "LocalBusiness",
                "name": "Austria Express",
            },
            "areaServed": ["Wien", "Österreich", "Europa"],
            "url": _site_url(page["slug"]),
        },
        {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": page["h1"],
            "url": _site_url(page["slug"]),
            "description": page["meta_description"],
            "dateModified": datetime.now(timezone.utc).date().isoformat(),
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": "Startseite",
                    "item": request.url_root.rstrip("/"),
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": page["badge"],
                    "item": _site_url(page["slug"]),
                },
            ],
        },
    ]

    if faq_entities:
        schema.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faq_entities,
        })

    return json.dumps(schema, ensure_ascii=False)


def _render(slug: str):
    page = next((item for item in LANDING_PAGES if item["slug"] == slug), None)
    if not page:
        abort(404)

    prepared = deepcopy(page)
    prepared["canonical"] = _site_url(prepared["slug"])
    prepared["schema_json"] = _schema_for(prepared)

    return render_template(
        "public/seo_landing.html",
        page=prepared,
        landing_pages=LANDING_PAGES,
    )


for _page in LANDING_PAGES:
    _slug = _page["slug"]
    seo_landing_bp.add_url_rule(
        "/" + _slug,
        endpoint=_slug.replace("-", "_"),
        view_func=(lambda slug=_slug: _render(slug)),
    )
