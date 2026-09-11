from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import asc, desc

from ..extensions import db
from ..models import BlogPost, BusRentalRequest, ContactRequest, CustomerReview, SchoolDestination, FleetVehicle, PricingProfile
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


def _to_decimal(value, default=None):
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _format_euro(value) -> str:
    if value in (None, ""):
        return ""
    try:
        return f"ab {float(value):.0f} €"
    except (TypeError, ValueError):
        return ""


def _format_euro_plain(value) -> str:
    if value in (None, ""):
        return ""
    try:
        return f"{float(value):.0f} €"
    except (TypeError, ValueError):
        return ""


def _format_hours(value) -> str:
    if value in (None, ""):
        return ""
    try:
        dec = Decimal(str(value)).quantize(Decimal("0.01"))
        text = f"{dec}"
        return text.rstrip("0").rstrip(".")
    except Exception:
        return ""


def _default_school_profile(seat_hint: str):
    profiles = PricingProfile.query.filter_by(is_active=True).order_by(PricingProfile.name.asc()).all()
    hint = seat_hint.lower()

    for profile in profiles:
        haystack = f"{profile.name} {profile.bus_category}".lower()
        if hint in haystack:
            return profile

    if hint in {"77", "75", "doppeldecker"}:
        for profile in profiles:
            haystack = f"{profile.name} {profile.bus_category}".lower()
            if "doppel" in haystack or "77" in haystack or "75" in haystack:
                return profile

    return profiles[0] if profiles else None


def _profile_payload(profile: PricingProfile | None) -> dict:
    if not profile:
        return {
            "id": "",
            "name": "",
            "km": "",
            "hour": "",
            "wait": "",
            "minimum": "",
        }

    return {
        "id": profile.id,
        "name": profile.name or "",
        "km": float(profile.price_per_km or 0),
        "hour": float(profile.hourly_rate or 0),
        "wait": float(profile.waiting_hourly_rate or 0),
        "minimum": float(profile.minimum_day_rate or 0),
    }


def _time_to_minutes(value: str | None):
    if not value:
        return None
    try:
        parts = value.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return None


def _duration_hours(start_time: str | None, end_time: str | None):
    start_minutes = _time_to_minutes(start_time)
    end_minutes = _time_to_minutes(end_time)
    if start_minutes is None or end_minutes is None:
        return None

    if end_minutes <= start_minutes:
        end_minutes += 24 * 60

    duration = Decimal(end_minutes - start_minutes) / Decimal("60")
    if duration <= 0 or duration > 18:
        return None
    return duration


def _school_price_value(profile: PricingProfile | None, distance_km_one_way, drive_hours_one_way, wait_hours):
    if not profile:
        return None

    distance = _to_decimal(distance_km_one_way)
    drive_hours = _to_decimal(drive_hours_one_way)
    waiting_hours = _to_decimal(wait_hours, Decimal("0"))

    if distance is None or drive_hours is None or distance <= 0 or drive_hours <= 0:
        return None

    total_km = distance * Decimal("2")
    total_drive_hours = drive_hours * Decimal("2")

    calculated = (
        total_km * Decimal(profile.price_per_km or 0)
        + total_drive_hours * Decimal(profile.hourly_rate or 0)
        + waiting_hours * Decimal(profile.waiting_hourly_rate or 0)
    )
    minimum = Decimal(profile.minimum_day_rate or 0)
    final = calculated if calculated >= minimum else minimum
    return final.quantize(Decimal("1"))


def _school_pricing_context(destination: SchoolDestination, start_time: str | None = None, end_time: str | None = None) -> dict:
    pricing = destination.pricing

    drive_minutes = pricing.drive_minutes_one_way if pricing else None
    stay_minutes = pricing.stay_minutes if pricing else None

    drive_hours_one_way = (Decimal(drive_minutes) / Decimal("60")) if drive_minutes is not None else None
    standard_wait_hours = (Decimal(stay_minutes) / Decimal("60")) if stay_minutes is not None else Decimal("4")

    customer_total_hours = _duration_hours(start_time, end_time)
    adjusted_wait_hours = standard_wait_hours
    time_warning = ""

    if customer_total_hours is not None and drive_hours_one_way is not None:
        adjusted_wait_hours = customer_total_hours - (drive_hours_one_way * Decimal("2"))
        if adjusted_wait_hours < 0:
            adjusted_wait_hours = Decimal("0")
            time_warning = "Die gewünschte Zeitspanne ist kürzer als die hinterlegte reine Fahrzeit. Bitte Zeiten prüfen."

    profile_53 = pricing.profile_53 if pricing and pricing.profile_53 else _default_school_profile("53")
    profile_75 = pricing.profile_75 if pricing and pricing.profile_75 else _default_school_profile("doppeldecker")

    price_53 = _school_price_value(profile_53, destination.distance_km, drive_hours_one_way, adjusted_wait_hours)
    price_75 = _school_price_value(profile_75, destination.distance_km, drive_hours_one_way, adjusted_wait_hours)

    return {
        "drive_hours_one_way": drive_hours_one_way,
        "standard_wait_hours": standard_wait_hours,
        "customer_total_hours": customer_total_hours,
        "adjusted_wait_hours": adjusted_wait_hours,
        "time_warning": time_warning,
        "profile_53": profile_53,
        "profile_75": profile_75,
        "price_53": price_53,
        "price_75": price_75,
    }


def _school_offer_options():
    destinations = (
        SchoolDestination.query
        .filter_by(is_active=True)
        .order_by(SchoolDestination.zone.asc(), SchoolDestination.sort_order.asc(), SchoolDestination.title.asc())
        .all()
    )

    options = []
    for d in destinations:
        ctx = _school_pricing_context(d)
        options.append({
            "slug": d.slug,
            "title": d.title,
            "zone": d.zone,
            "category": d.category,
            "travel_time": d.travel_time or "",
            "description": d.short_description or "",
            "distance_km": float(d.distance_km or 0),
            "drive_hours_one_way": float(ctx["drive_hours_one_way"] or 0),
            "standard_wait_hours": float(ctx["standard_wait_hours"] or 0),
            "price_53_label": _format_euro(ctx["price_53"] or d.price_53),
            "price_75_label": _format_euro(ctx["price_75"] or d.price_75),
            "price_53_amount": float(ctx["price_53"] or d.price_53 or 0),
            "price_75_amount": float(ctx["price_75"] or d.price_75 or 0),
            "profile_53": _profile_payload(ctx["profile_53"]),
            "profile_75": _profile_payload(ctx["profile_75"]),
        })
    return options


def _school_offer_summary(destination: SchoolDestination | None, start_time: str | None = None, end_time: str | None = None) -> str:
    if not destination:
        return ""

    ctx = _school_pricing_context(destination, start_time, end_time)

    lines = [
        "Gewähltes Schulangebot:",
        f"- Ziel: {destination.title}",
        f"- Zone: {destination.zone}",
    ]

    if destination.category:
        lines.append(f"- Kategorie: {destination.category}")
    if destination.travel_time:
        lines.append(f"- Fahrtzeit Info: {destination.travel_time}")
    if destination.distance_km:
        lines.append(f"- Entfernung: {_format_hours(destination.distance_km)} km einfach / {_format_hours(Decimal(destination.distance_km) * Decimal('2'))} km Hin + Retour")

    if ctx["drive_hours_one_way"] is not None:
        lines.append(f"- Hinterlegte Fahrzeit: {_format_hours(ctx['drive_hours_one_way'])} h einfach / {_format_hours(ctx['drive_hours_one_way'] * Decimal('2'))} h Hin + Retour")

    if start_time and end_time and ctx["customer_total_hours"] is not None:
        lines.append(f"- Kundenvorgabe Zeit: {start_time}–{end_time} = {_format_hours(ctx['customer_total_hours'])} h gesamt")
        lines.append(f"- Daraus berechnete Wartezeit/Aufenthalt: {_format_hours(ctx['adjusted_wait_hours'])} h")
    else:
        lines.append(f"- Standard-Wartezeit/Aufenthalt: {_format_hours(ctx['standard_wait_hours'])} h")

    if ctx["time_warning"]:
        lines.append(f"- Hinweis: {ctx['time_warning']}")

    if ctx["price_53"]:
        lines.append(f"- Angepasster Richtpreis 53 Plätze: {_format_euro_plain(ctx['price_53'])} inkl. 10% USt")
    elif destination.price_53:
        lines.append(f"- Richtpreis 53 Plätze: {_format_euro(destination.price_53)} inkl. 10% USt")

    if ctx["price_75"]:
        lines.append(f"- Angepasster Richtpreis Doppeldecker: {_format_euro_plain(ctx['price_75'])} inkl. 10% USt")
    elif destination.price_75:
        lines.append(f"- Richtpreis Doppeldecker: {_format_euro(destination.price_75)} inkl. 10% USt")

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
            "date_start": "Gewünschtes Datum",
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
        school_summary = _school_offer_summary(selected_school, request.form.get("time_departure"), request.form.get("time_return"))
        route_parts = []
        if school_summary:
            route_parts.append(school_summary)
        if base_route_description:
            details_label = "Wünsche / Anmerkungen zum Programm" if request_kind == "school" else "Zusätzliche Angaben"
            route_parts.append(details_label + ":\n" + base_route_description)
        route_description = "\n\n".join(route_parts).strip() or None

        group_notes = request.form.get("group_notes", "").strip()

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
            date_end=None if request_kind == "school" else (request.form.get("date_end", "").strip() or None),
            time_departure=request.form.get("time_departure", "").strip() or None,
            time_return=request.form.get("time_return", "").strip() or None,
            days=1 if request_kind == "school" else _to_int(request.form.get("days")),
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
