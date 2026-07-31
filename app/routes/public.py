from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import asc, desc

from ..extensions import db
from ..models import BlogPost, BusRentalRequest, ContactRequest, CustomerReview, SchoolDestination, FleetVehicle
from ..utils.csrf import validate_csrf_token
from ..utils.email_notifications import notify_bus_rental_request, notify_contact_request


public_bp = Blueprint("public", __name__)


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


@public_bp.route("/bus-rental", methods=["GET", "POST"])
def bus_rental():
    if request.method == "POST":
        if not validate_csrf_token(request.form.get("_csrf_token")):
            flash("Ihre Sitzung ist abgelaufen. Bitte versuchen Sie es erneut.", "error")
            return redirect(url_for("public.bus_rental"))

        required = ["customer_type", "contact_name", "email", "trip_type", "departure_place", "destination"]
        errors = [f"Bitte füllen Sie das Feld {field} aus." for field in required if not request.form.get(field, "").strip()]

        def to_int(value):
            try:
                return int(value or 0) or None
            except ValueError:
                return None

        if errors:
            for error in errors:
                flash(error, "error")
            return redirect(url_for("public.bus_rental"))

        inquiry = BusRentalRequest(
            customer_type=request.form.get("customer_type", "").strip(),
            organisation=request.form.get("organisation", "").strip() or None,
            contact_name=request.form.get("contact_name", "").strip(),
            email=request.form.get("email", "").strip(),
            phone=request.form.get("phone", "").strip() or None,
            trip_type=request.form.get("trip_type", "").strip(),
            departure_place=request.form.get("departure_place", "").strip(),
            destination=request.form.get("destination", "").strip(),
            date_start=request.form.get("date_start", "").strip() or None,
            date_end=request.form.get("date_end", "").strip() or None,
            time_departure=request.form.get("time_departure", "").strip() or None,
            time_return=request.form.get("time_return", "").strip() or None,
            days=to_int(request.form.get("days")),
            passengers=to_int(request.form.get("passengers")),
            bus_size=request.form.get("bus_size", "").strip() or None,
            bus_count=to_int(request.form.get("bus_count")),
            route_description=request.form.get("route_description", "").strip() or None,
            group_notes=request.form.get("group_notes", "").strip() or None,
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

    return render_template("public/bus_rental.html")


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
