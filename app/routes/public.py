from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import asc, desc

from ..extensions import db
from ..models import BlogPost, BusRentalRequest, ContactRequest, CustomerReview, SchoolDestination, FleetVehicle
from ..utils.csrf import validate_csrf_token
from ..utils.email_notifications import notify_bus_rental_request, notify_contact_request


public_bp = Blueprint("public", __name__)


def _site_base_url() -> str:
    configured = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    return request.url_root.rstrip("/")


def _absolute_url(path: str) -> str:
    base = _site_base_url()
    return f"{base}/{path.lstrip('/')}"


def _iso_date(value):
    if not value:
        return datetime.now(timezone.utc).date().isoformat()
    try:
        return value.date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()


@public_bp.route("/robots.txt")
def robots_txt():
    body = f"""User-agent: *
Allow: /

Sitemap: {_absolute_url('/sitemap.xml')}
"""
    return Response(body, mimetype="text/plain; charset=utf-8")


@public_bp.route("/sitemap.xml")
def sitemap_xml():
    static_pages = [
        {"loc": "/", "priority": "1.0", "changefreq": "weekly"},
        {"loc": "/bus-rental", "priority": "0.9", "changefreq": "monthly"},
        {"loc": "/anfrage", "priority": "0.95", "changefreq": "monthly"},
        {"loc": "/schulen", "priority": "0.9", "changefreq": "monthly"},
        {"loc": "/fuhrpark", "priority": "0.8", "changefreq": "monthly"},
        {"loc": "/aktuelles-kundenstimmen", "priority": "0.7", "changefreq": "weekly"},
        {"loc": "/kontakt", "priority": "0.8", "changefreq": "monthly"},
        {"loc": "/impressum", "priority": "0.3", "changefreq": "yearly"},
        {"loc": "/datenschutz", "priority": "0.3", "changefreq": "yearly"},
        {"loc": "/agb", "priority": "0.3", "changefreq": "yearly"},
    ]

    now = datetime.now(timezone.utc).date().isoformat()
    urls = []

    for page in static_pages:
        urls.append({
            "loc": _absolute_url(page["loc"]),
            "lastmod": now,
            "changefreq": page["changefreq"],
            "priority": page["priority"],
        })

    posts = (
        BlogPost.query
        .filter_by(status="published")
        .order_by(BlogPost.published_at.desc(), BlogPost.updated_at.desc())
        .all()
    )

    for post in posts:
        urls.append({
            "loc": _absolute_url(url_for("public.post_detail", slug=post.slug)),
            "lastmod": _iso_date(post.updated_at or post.published_at),
            "changefreq": "monthly",
            "priority": "0.6",
        })

    xml_items = []
    for item in urls:
        xml_items.append(f"""  <url>
    <loc>{item['loc']}</loc>
    <lastmod>{item['lastmod']}</lastmod>
    <changefreq>{item['changefreq']}</changefreq>
    <priority>{item['priority']}</priority>
  </url>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(xml_items)}
</urlset>
"""
    return Response(xml, mimetype="application/xml; charset=utf-8")


def _load_fleet_filters():
    default_filters = [
        {"id": "all", "label": "Alle"},
        {"id": "grossgruppen", "label": "Großgruppen"},
        {"id": "doppeldecker", "label": "Doppeldecker"},
        {"id": "komfort", "label": "Komfort"},
        {"id": "schulen", "label": "Schulen"},
        {"id": "firmen", "label": "Firmen"},
        {"id": "vereine", "label": "Vereine"},
    ]

    try:
        path = Path(current_app.root_path) / "approved_source_data" / "austria_express_fleet_filters_v1.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        loaded = data.get("filters", [])
        if loaded:
            return loaded
    except Exception:
        pass

    return default_filters


@public_bp.route("/")
def index():
    return render_template("public/index.html")


@public_bp.route("/health")
def health():
    return {"status": "ok"}


@public_bp.route("/schulen")
def schulen():
    selected_filter = request.args.get("filter", "all").strip()
    destinations = (
        SchoolDestination.query
        .filter_by(is_active=True)
        .order_by(SchoolDestination.zone.asc(), SchoolDestination.sort_order.asc(), SchoolDestination.title.asc())
        .all()
    )

    zones = {
        "A": {"label": "Zone A", "distance": "bis 40 km", "price53": "ab 490 €", "price75": "ab 690 €", "tone": "red", "text": "Kurze Fahrten, ideal für Halbtagsprogramme oder kurze Ganztagesausflüge."},
        "B": {"label": "Zone B", "distance": "bis 90 km", "price53": "ab 690 €", "price75": "ab 890 €", "tone": "amber", "text": "Klassische Tagesfahrten rund um Wien mit gutem Verhältnis aus Fahrzeit und Aufenthalt."},
        "C": {"label": "Zone C", "distance": "bis 130 km", "price53": "ab 890 €", "price75": "ab 1.090 €", "tone": "emerald", "text": "Längere Tagesfahrten mit mehr Buszeit, aber sehr attraktiven Zielen für Kinder und Jugendliche."},
        "D": {"label": "Zone D", "distance": "bis 200 km", "price53": "ab 1.190 €", "price75": "ab 1.490 €", "tone": "indigo", "text": "Weit entfernte Ziele – höherer Preis und längere Buszeit, dafür besonderer Erlebniswert."},
    }

    filters = [
        {"id": "all", "label": "Alle"},
        {"id": "wandern", "label": "Wandern / Natur"},
        {"id": "geschichte", "label": "Geschichte"},
        {"id": "freizeit", "label": "Freizeit"},
        {"id": "tiere", "label": "Tiere"},
        {"id": "staedte", "label": "Städte"},
        {"id": "technik", "label": "Technik"},
    ]

    return render_template("public/schulen.html", destinations=destinations, zones=zones, filters=filters, selected_filter=selected_filter)


@public_bp.route("/fuhrpark")
def fuhrpark():
    selected_filter = request.args.get("filter", "all").strip()
    vehicles = (
        FleetVehicle.query
        .filter_by(is_active=True)
        .order_by(FleetVehicle.sort_order.asc(), FleetVehicle.seats.desc(), FleetVehicle.name.asc())
        .all()
    )
    filters = _load_fleet_filters()
    return render_template("public/fuhrpark.html", vehicles=vehicles, filters=filters, selected_filter=selected_filter)


@public_bp.route("/aktuelles-kundenstimmen")
def aktuelles():
    selected_category = request.args.get("category", "all").strip()

    categories = [
        row[0] for row in
        db.session.query(BlogPost.category)
        .filter(BlogPost.status == "published")
        .distinct()
        .order_by(BlogPost.category.asc())
        .all()
        if row[0]
    ]

    posts_query = BlogPost.query.filter(BlogPost.status == "published")
    if selected_category != "all":
        posts_query = posts_query.filter(BlogPost.category == selected_category)

    posts = (
        posts_query
        .order_by(asc(BlogPost.sort_order), desc(BlogPost.published_at), desc(BlogPost.created_at))
        .all()
    )

    reviews = (
        CustomerReview.query
        .filter(CustomerReview.status == "approved")
        .order_by(desc(CustomerReview.approved_at), desc(CustomerReview.created_at))
        .limit(12)
        .all()
    )

    return render_template(
        "public/aktuelles.html",
        posts=posts,
        reviews=reviews,
        categories=categories,
        selected_category=selected_category,
    )


@public_bp.route("/aktuelles/<slug>")
def post_detail(slug: str):
    post = BlogPost.query.filter_by(slug=slug, status="published").first_or_404()
    return render_template("public/post_detail.html", post=post)


@public_bp.route("/kontakt")
def contact():
    return render_template("public/contact.html")


@public_bp.route("/impressum")
def impressum():
    return render_template("public/impressum.html")


@public_bp.route("/datenschutz")
def datenschutz():
    return render_template("public/datenschutz.html")


@public_bp.route("/agb")
def agb():
    return render_template("public/agb.html")


# Legacy static filename redirects

@public_bp.route("/austria_express_index_v9_final.html")
@public_bp.route("/austria_express_index_v6.html")
@public_bp.route("/austria_express_index_v7.html")
@public_bp.route("/austria_express_index_v8.html")
def legacy_index():
    return redirect(url_for("public.index"), code=302)


@public_bp.route("/austria_express_schulen_v3.html")
@public_bp.route("/austria_express_schulen_prototype_v6.html")
@public_bp.route("/austria_express_schulen_v6.html")
def legacy_schulen():
    return redirect(url_for("public.schulen"), code=302)


@public_bp.route("/austria_express_fuhrpark_prototype_v5.html")
@public_bp.route("/austria_express_fuhrpark_v5.html")
def legacy_fuhrpark():
    return redirect(url_for("public.fuhrpark"), code=302)


@public_bp.route("/austria_express_bus_rental_prototype_v1.html")
def legacy_bus_rental():
    return redirect(url_for("public.bus_rental"), code=302)


@public_bp.route("/austria_express_aktuelles_kundenstimmen_v1.html")
def legacy_aktuelles():
    return redirect(url_for("public.aktuelles"), code=302)


@public_bp.route("/austria_express_kontakt_prototype_v3.html")
def legacy_kontakt():
    return redirect(url_for("public.contact"), code=302)


@public_bp.route("/austria_express_impressum_v7.html")
@public_bp.route("/austria_express_impressum_v8.html")
def legacy_impressum():
    return redirect(url_for("public.impressum"), code=302)


@public_bp.route("/austria_express_datenschutz_v1.html")
def legacy_datenschutz():
    return redirect(url_for("public.datenschutz"), code=302)


@public_bp.route("/austria_express_agb_v1.html")
def legacy_agb():
    return redirect(url_for("public.agb"), code=302)


def _to_int(value):
    try:
        parsed = int(value or 0)
        return parsed or None
    except (TypeError, ValueError):
        return None


def _format_euro(value) -> str:
    if value in (None, ""):
        return ""
    try:
        return f"ab {float(value):.0f} €"
    except (TypeError, ValueError):
        return ""


def _school_offer_options():
    destinations = (
        SchoolDestination.query
        .filter_by(is_active=True)
        .order_by(SchoolDestination.zone.asc(), SchoolDestination.sort_order.asc(), SchoolDestination.title.asc())
        .all()
    )

    return [
        {
            "slug": d.slug,
            "title": d.title,
            "zone": d.zone,
            "category": d.category,
            "travel_time": d.travel_time or "",
            "description": d.short_description or "",
            "price_53_label": _format_euro(d.price_53),
            "price_75_label": _format_euro(d.price_75),
        }
        for d in destinations
    ]


def _school_offer_summary(destination: SchoolDestination | None) -> str:
    if not destination:
        return ""

    lines = [
        "Gewähltes Schulangebot:",
        f"- Ziel: {destination.title}",
        f"- Zone: {destination.zone}",
    ]

    if destination.category:
        lines.append(f"- Kategorie: {destination.category}")
    if destination.travel_time:
        lines.append(f"- Fahrtzeit: {destination.travel_time}")
    if destination.price_53:
        lines.append(f"- Richtpreis 53 Plätze: {_format_euro(destination.price_53)}")
    if destination.price_75:
        lines.append(f"- Richtpreis Doppeldecker: {_format_euro(destination.price_75)}")
    if destination.short_description:
        lines.append(f"- Beschreibung: {destination.short_description}")

    return "\n".join(lines)


@public_bp.route("/bus-rental", methods=["GET", "POST"])
def bus_rental():
    if request.method == "POST":
        return redirect(url_for("public.anfrage"), code=303)
    return render_template("public/bus_rental.html")


@public_bp.route("/anfrage", methods=["GET", "POST"])
def anfrage():
    request_kind = request.args.get("type", "general").strip()
    if request_kind not in {"school", "general"}:
        request_kind = "general"

    selected_school_slug = (
        request.args.get("school")
        or request.args.get("destination")
        or ""
    ).strip()

    if request.method == "POST":
        if not validate_csrf_token(request.form.get("_csrf_token")):
            flash("Ihre Sitzung ist abgelaufen. Bitte versuchen Sie es erneut.", "error")
            return redirect(url_for("public.anfrage"))

        request_kind = request.form.get("request_kind", "general").strip()
        if request_kind not in {"school", "general"}:
            request_kind = "general"

        selected_school_slug = request.form.get("school_destination_slug", "").strip()
        selected_school = None
        if selected_school_slug:
            selected_school = SchoolDestination.query.filter_by(slug=selected_school_slug, is_active=True).first()

        labels = {
            "customer_type": "Kundentyp",
            "contact_name": "Ansprechperson",
            "email": "E-Mail",
            "trip_type": "Art der Fahrt",
            "departure_place": "Abfahrtsort",
            "destination": "Ziel / Route",
            "organisation": "Firma / Organisation / Schule",
            "date_start": "Startdatum",
            "passengers": "Anzahl Passagiere",
            "school_destination_slug": "Schulangebot",
            "privacy_consent": "Datenschutzhinweis",
        }

        required = ["contact_name", "email", "departure_place", "privacy_consent"]
        if request_kind == "school":
            required.extend(["organisation", "date_start", "passengers", "school_destination_slug"])
        else:
            required.extend(["customer_type", "trip_type", "destination"])

        errors = [
            f"Bitte füllen Sie das Feld {labels.get(field, field)} aus."
            for field in required
            if not request.form.get(field, "").strip()
        ]

        if request_kind == "school" and selected_school_slug and not selected_school:
            errors.append("Das ausgewählte Schulangebot konnte nicht gefunden werden.")

        if errors:
            for error in errors:
                flash(error, "error")
            return redirect(url_for("public.anfrage", type=request_kind, school=selected_school_slug))

        base_route_description = request.form.get("route_description", "").strip()
        school_summary = _school_offer_summary(selected_school)
        route_parts = []
        if school_summary:
            route_parts.append(school_summary)
        if base_route_description:
            route_parts.append("Zusätzliche Angaben:
" + base_route_description)
        route_description = "

".join(route_parts).strip() or None

        group_notes = request.form.get("group_notes", "").strip()
        class_level = request.form.get("class_level", "").strip()
        if class_level:
            group_notes = (group_notes + "
" if group_notes else "") + f"Schulstufe / Klasse: {class_level}"

        destination_value = request.form.get("destination", "").strip()
        if request_kind == "school" and selected_school:
            destination_value = selected_school.title

        inquiry = BusRentalRequest(
            customer_type="Institution / Schule" if request_kind == "school" else request.form.get("customer_type", "").strip(),
            organisation=request.form.get("organisation", "").strip() or None,
            contact_name=request.form.get("contact_name", "").strip(),
            email=request.form.get("email", "").strip(),
            phone=request.form.get("phone", "").strip() or None,
            trip_type="Schulfahrt" if request_kind == "school" else request.form.get("trip_type", "").strip(),
            departure_place=request.form.get("departure_place", "").strip(),
            destination=destination_value,
            date_start=request.form.get("date_start", "").strip() or None,
            date_end=request.form.get("date_end", "").strip() or None,
            time_departure=request.form.get("time_departure", "").strip() or None,
            time_return=request.form.get("time_return", "").strip() or None,
            days=_to_int(request.form.get("days")) or (1 if request_kind == "school" else None),
            passengers=_to_int(request.form.get("passengers")),
            bus_size=request.form.get("bus_size", "").strip() or None,
            bus_count=_to_int(request.form.get("bus_count")),
            route_description=route_description,
            group_notes=group_notes or None,
            special_needs=request.form.get("special_needs", "").strip() or None,
            req_wc=bool(request.form.get("req_wc")),
            req_usb=bool(request.form.get("req_usb")),
            req_power=bool(request.form.get("req_power")),
            req_wifi=bool(request.form.get("req_wifi")),
            req_doubledecker=bool(request.form.get("req_doubledecker")),
            req_kitchen=bool(request.form.get("req_kitchen")),
            status="new",
        )
        db.session.add(inquiry)
        db.session.commit()

        notify_bus_rental_request(inquiry)

        return render_template("public/bus_rental_thank_you.html")

    return render_template(
        "public/anfrage.html",
        school_destinations=_school_offer_options(),
        selected_school_slug=selected_school_slug,
        request_kind=request_kind,
    )


@public_bp.post("/bewertungen")
def submit_review():
    if not validate_csrf_token(request.form.get("_csrf_token")):
        flash("Ihre Sitzung ist abgelaufen. Bitte versuchen Sie es erneut.", "error")
        return redirect(url_for("public.aktuelles"))

    customer_name = request.form.get("customer_name", "").strip()
    organisation = request.form.get("organisation", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    trip_type = request.form.get("trip_type", "").strip() or "Allgemein"
    text = request.form.get("review_text", "").strip()
    privacy = request.form.get("privacy_consent")

    try:
        rating = int(request.form.get("rating", "5"))
    except ValueError:
        rating = 5
    rating = max(1, min(5, rating))

    errors = []
    if not customer_name:
        errors.append("Bitte geben Sie Ihren Namen an.")
    if not email:
        errors.append("Bitte geben Sie Ihre E-Mail-Adresse an.")
    if not text or len(text) < 20:
        errors.append("Bitte schreiben Sie eine Bewertung mit mindestens 20 Zeichen.")
    if not privacy:
        errors.append("Bitte bestätigen Sie die Datenschutz-Hinweise.")

    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("public.aktuelles"))

    db.session.add(CustomerReview(
        customer_name=customer_name,
        organisation=organisation or None,
        email_internal=email,
        phone_internal=phone or None,
        rating=rating,
        trip_type=trip_type,
        text=text,
        status="pending",
    ))
    db.session.commit()
    return render_template("public/review_thank_you.html")


@public_bp.post("/kontakt")
def contact_submit():
    if not validate_csrf_token(request.form.get("_csrf_token")):
        flash("Ihre Sitzung ist abgelaufen. Bitte versuchen Sie es erneut.", "error")
        return redirect(url_for("public.contact"))

    name = request.form.get("name", "").strip()
    organisation = request.form.get("organisation", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    request_type = request.form.get("request_type", "").strip()
    preferred_contact = request.form.get("preferred_contact", "").strip()
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()
    privacy = request.form.get("privacy_consent")

    errors = []
    if not name:
        errors.append("Bitte geben Sie Ihren Namen an.")
    if not email:
        errors.append("Bitte geben Sie Ihre E-Mail-Adresse an.")
    if not message or len(message) < 10:
        errors.append("Bitte schreiben Sie eine Nachricht mit mindestens 10 Zeichen.")
    if not privacy:
        errors.append("Bitte bestätigen Sie die Datenschutz-Hinweise.")

    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("public.contact"))

    contact_request = ContactRequest(
        name=name,
        organisation=organisation or None,
        email=email,
        phone=phone or None,
        request_type=request_type or None,
        preferred_contact=preferred_contact or None,
        subject=subject or None,
        message=message,
        status="new",
        ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
        user_agent=request.headers.get("User-Agent"),
    )
    db.session.add(contact_request)
    db.session.commit()

    notify_contact_request(contact_request)

    flash("Vielen Dank. Ihre Nachricht wurde erfolgreich übermittelt.", "success")
    return redirect(url_for("public.contact"))
