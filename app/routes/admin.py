from __future__ import annotations

from functools import wraps
from decimal import Decimal
from urllib.parse import quote

from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash

from ..extensions import db
from ..models import (
    AdminUser, BlogPost, CustomerReview, MediaFile, SchoolDestination,
    FleetVehicle, BusRentalRequest, PricingProfile, PricingCalculation, utcnow
)
from ..utils.csrf import validate_csrf_token
from ..utils.slug import slugify
from ..utils.uploads import save_uploaded_image
from ..utils.pricing import calculate_price


admin_bp = Blueprint("admin", __name__)


def current_admin():
    admin_id = session.get("admin_id")
    if not admin_id:
        return None
    return AdminUser.query.get(admin_id)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_admin():
            return redirect(url_for("admin.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def require_csrf() -> bool:
    if not validate_csrf_token(request.form.get("_csrf_token")):
        flash("Sicherheitsprüfung fehlgeschlagen. Bitte erneut versuchen.", "error")
        return False
    return True


def form_bool(name: str) -> bool:
    return bool(request.form.get(name))


def to_int(value, default=None):
    try:
        if value in (None, ""):
            return default
        return int(value)
    except ValueError:
        return default


def to_float(value, default=0):
    try:
        if value in (None, ""):
            return default
        return float(str(value).replace(",", "."))
    except ValueError:
        return default


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not require_csrf():
            return redirect(url_for("admin.login"))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = AdminUser.query.filter_by(username=username, is_active=True).first()

        if admin and check_password_hash(admin.password_hash, password):
            session["admin_id"] = admin.id
            flash("Erfolgreich angemeldet.", "success")
            return redirect(request.args.get("next") or url_for("admin.dashboard"))

        flash("Login fehlgeschlagen.", "error")

    return render_template("admin/login.html")


@admin_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    if not require_csrf():
        return redirect(url_for("admin.dashboard"))
    session.pop("admin_id", None)
    flash("Abgemeldet.", "success")
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@login_required
def dashboard():
    counts = {
        "posts": BlogPost.query.count(),
        "reviews pending": CustomerReview.query.filter_by(status="pending").count(),
        "destinations": SchoolDestination.query.count(),
        "vehicles": FleetVehicle.query.count(),
        "bus requests": BusRentalRequest.query.filter_by(status="new").count(),
        "calculations": PricingCalculation.query.count(),
    }
    return render_template("admin/dashboard.html", counts=counts)


# ---------- Blog ----------
@admin_bp.route("/posts")
@login_required
def posts_list():
    status = request.args.get("status", "all")
    query = BlogPost.query
    if status != "all":
        query = query.filter_by(status=status)
    posts = query.order_by(BlogPost.sort_order.asc(), BlogPost.created_at.desc()).all()
    return render_template("admin/posts_list.html", posts=posts, selected_status=status)


@admin_bp.route("/posts/new", methods=["GET", "POST"])
@login_required
def post_new():
    if request.method == "POST":
        return save_post()
    return render_template("admin/post_form.html", post=None)


@admin_bp.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])
@login_required
def post_edit(post_id: int):
    post = BlogPost.query.get_or_404(post_id)
    if request.method == "POST":
        return save_post(post)
    return render_template("admin/post_form.html", post=post)


def save_post(post: BlogPost | None = None):
    if not require_csrf():
        return redirect(url_for("admin.posts_list"))

    title = request.form.get("title", "").strip()
    slug = request.form.get("slug", "").strip() or slugify(title)
    body = request.form.get("body", "").strip()
    status = request.form.get("status", "draft")
    if status not in {"draft", "published", "archived"}:
        status = "draft"

    if not title or not body:
        flash("Titel und Text sind Pflichtfelder.", "error")
        return render_template("admin/post_form.html", post=post)

    duplicate = BlogPost.query.filter(BlogPost.slug == slug)
    if post:
        duplicate = duplicate.filter(BlogPost.id != post.id)
    if duplicate.first():
        flash("Slug existiert bereits.", "error")
        return render_template("admin/post_form.html", post=post)

    if post is None:
        post = BlogPost(title=title, slug=slug, body=body)
        db.session.add(post)

    post.title = title
    post.slug = slug
    post.category = request.form.get("category", "Allgemein").strip() or "Allgemein"
    post.excerpt = request.form.get("excerpt", "").strip() or None
    post.body = body
    post.status = status
    post.seo_title = request.form.get("seo_title", "").strip() or None
    post.seo_description = request.form.get("seo_description", "").strip() or None
    post.alt_text = request.form.get("alt_text", "").strip() or None
    post.sort_order = to_int(request.form.get("sort_order"), 100)

    if status == "published" and not post.published_at:
        post.published_at = utcnow()

    try:
        image_path, original_name = save_uploaded_image(request.files.get("main_image"))
    except ValueError as exc:
        flash(str(exc), "error")
        return render_template("admin/post_form.html", post=post)

    if image_path:
        post.main_image = image_path
        db.session.add(MediaFile(file_name=image_path.split("/")[-1], original_name=original_name or image_path, file_path=image_path, alt_text=post.alt_text or post.title))

    db.session.commit()
    flash("Beitrag gespeichert.", "success")
    return redirect(url_for("admin.posts_list"))


@admin_bp.post("/posts/<int:post_id>/delete")
@login_required
def post_delete(post_id: int):
    if not require_csrf():
        return redirect(url_for("admin.posts_list"))
    db.session.delete(BlogPost.query.get_or_404(post_id))
    db.session.commit()
    flash("Beitrag gelöscht.", "success")
    return redirect(url_for("admin.posts_list"))


# ---------- Reviews ----------
@admin_bp.route("/reviews")
@login_required
def reviews_list():
    status = request.args.get("status", "pending")
    query = CustomerReview.query
    if status != "all":
        query = query.filter_by(status=status)
    reviews = query.order_by(CustomerReview.created_at.desc()).all()
    return render_template("admin/reviews_list.html", reviews=reviews, selected_status=status)


@admin_bp.route("/reviews/<int:review_id>", methods=["GET", "POST"])
@login_required
def review_detail(review_id: int):
    review = CustomerReview.query.get_or_404(review_id)
    if request.method == "POST":
        if not require_csrf():
            return redirect(url_for("admin.review_detail", review_id=review.id))
        action = request.form.get("action", "pending")
        if action not in {"pending", "approved", "rejected", "archived"}:
            action = "pending"
        review.public_display_name = request.form.get("public_display_name", "").strip() or None
        review.trip_type = request.form.get("trip_type", "").strip() or review.trip_type
        review.text = request.form.get("text", "").strip() or review.text
        review.rating = max(1, min(5, to_int(request.form.get("rating"), review.rating)))
        review.status = action
        if action == "approved":
            review.approved_at = utcnow()
            admin = current_admin()
            if admin:
                review.approved_by_id = admin.id
        db.session.commit()
        flash("Bewertung aktualisiert.", "success")
        return redirect(url_for("admin.reviews_list", status=action))
    return render_template("admin/review_detail.html", review=review)


# ---------- Schools ----------
@admin_bp.route("/school-destinations")
@login_required
def school_destinations_list():
    items = SchoolDestination.query.order_by(SchoolDestination.zone.asc(), SchoolDestination.sort_order.asc()).all()
    return render_template("admin/school_destinations_list.html", items=items)


@admin_bp.route("/school-destinations/new", methods=["GET", "POST"])
@login_required
def school_destination_new():
    if request.method == "POST":
        return save_school_destination()
    return render_template("admin/school_destination_form.html", item=None)


@admin_bp.route("/school-destinations/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def school_destination_edit(item_id: int):
    item = SchoolDestination.query.get_or_404(item_id)
    if request.method == "POST":
        return save_school_destination(item)
    return render_template("admin/school_destination_form.html", item=item)


def save_school_destination(item: SchoolDestination | None = None):
    if not require_csrf():
        return redirect(url_for("admin.school_destinations_list"))

    title = request.form.get("title", "").strip()
    slug = request.form.get("slug", "").strip() or slugify(title)
    short_description = request.form.get("short_description", "").strip()

    if not title or not short_description:
        flash("Titel und Kurzbeschreibung sind Pflichtfelder.", "error")
        return render_template("admin/school_destination_form.html", item=item)

    duplicate = SchoolDestination.query.filter(SchoolDestination.slug == slug)
    if item:
        duplicate = duplicate.filter(SchoolDestination.id != item.id)
    if duplicate.first():
        flash("Slug existiert bereits.", "error")
        return render_template("admin/school_destination_form.html", item=item)

    if item is None:
        item = SchoolDestination(title=title, slug=slug, short_description=short_description, zone="A", category="Allgemein")
        db.session.add(item)

    item.title = title
    item.slug = slug
    item.zone = request.form.get("zone", "A").strip() or "A"
    item.category = request.form.get("category", "Allgemein").strip() or "Allgemein"
    item.tags = request.form.get("tags", "").strip() or None
    item.short_description = short_description
    item.full_description = request.form.get("full_description", "").strip() or None
    item.age_group = request.form.get("age_group", "").strip() or None
    item.distance_km = to_float(request.form.get("distance_km"), None)
    item.travel_time = request.form.get("travel_time", "").strip() or None
    item.latitude = to_float(request.form.get("latitude"), None)
    item.longitude = to_float(request.form.get("longitude"), None)
    item.price_53 = Decimal(str(to_float(request.form.get("price_53"), 0))) if request.form.get("price_53") else None
    item.price_75 = Decimal(str(to_float(request.form.get("price_75"), 0))) if request.form.get("price_75") else None
    item.alt_text = request.form.get("alt_text", "").strip() or None
    item.is_active = form_bool("is_active")
    item.sort_order = to_int(request.form.get("sort_order"), 100)

    try:
        image_path, original_name = save_uploaded_image(request.files.get("main_image"))
    except ValueError as exc:
        flash(str(exc), "error")
        return render_template("admin/school_destination_form.html", item=item)

    if image_path:
        item.main_image = image_path
        db.session.add(MediaFile(file_name=image_path.split("/")[-1], original_name=original_name or image_path, file_path=image_path, alt_text=item.alt_text or item.title))

    db.session.commit()
    flash("Destination gespeichert.", "success")
    return redirect(url_for("admin.school_destinations_list"))


@admin_bp.post("/school-destinations/<int:item_id>/delete")
@login_required
def school_destination_delete(item_id: int):
    if not require_csrf():
        return redirect(url_for("admin.school_destinations_list"))
    db.session.delete(SchoolDestination.query.get_or_404(item_id))
    db.session.commit()
    flash("Destination gelöscht.", "success")
    return redirect(url_for("admin.school_destinations_list"))


# ---------- Fleet ----------
@admin_bp.route("/fleet")
@login_required
def fleet_list():
    items = FleetVehicle.query.order_by(FleetVehicle.sort_order.asc()).all()
    return render_template("admin/fleet_list.html", items=items)


@admin_bp.route("/fleet/new", methods=["GET", "POST"])
@login_required
def fleet_new():
    if request.method == "POST":
        return save_vehicle()
    return render_template("admin/fleet_form.html", item=None)


@admin_bp.route("/fleet/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def fleet_edit(item_id: int):
    item = FleetVehicle.query.get_or_404(item_id)
    if request.method == "POST":
        return save_vehicle(item)
    return render_template("admin/fleet_form.html", item=item)


def save_vehicle(item: FleetVehicle | None = None):
    if not require_csrf():
        return redirect(url_for("admin.fleet_list"))

    name = request.form.get("name", "").strip()
    slug = request.form.get("slug", "").strip() or slugify(name)

    if not name:
        flash("Name ist Pflichtfeld.", "error")
        return render_template("admin/fleet_form.html", item=item)

    duplicate = FleetVehicle.query.filter(FleetVehicle.slug == slug)
    if item:
        duplicate = duplicate.filter(FleetVehicle.id != item.id)
    if duplicate.first():
        flash("Slug existiert bereits.", "error")
        return render_template("admin/fleet_form.html", item=item)

    if item is None:
        item = FleetVehicle(name=name, slug=slug, seats=53, category="Reisebus")
        db.session.add(item)

    item.name = name
    item.slug = slug
    item.model = request.form.get("model", "").strip() or None
    item.seats = to_int(request.form.get("seats"), 53)
    item.quantity = to_int(request.form.get("quantity"), 1)
    item.category = request.form.get("category", "Reisebus").strip() or "Reisebus"
    item.star_rating = request.form.get("star_rating", "4★").strip() or None
    item.description = request.form.get("description", "").strip() or None
    item.suitable_for = request.form.get("suitable_for", "").strip() or None
    item.alt_text = request.form.get("alt_text", "").strip() or None
    item.is_active = form_bool("is_active")
    item.sort_order = to_int(request.form.get("sort_order"), 100)

    for feature in ["ac", "wc", "usb", "power_220", "euro6", "wifi", "tv", "dvd", "monitors_2", "kitchen", "coffee_machine", "fridge", "kettle", "tables", "leather_seats", "folding_tables", "adjustable_seats", "sleeping_seats"]:
        setattr(item, feature, form_bool(feature))

    try:
        image_path, original_name = save_uploaded_image(request.files.get("main_image"))
    except ValueError as exc:
        flash(str(exc), "error")
        return render_template("admin/fleet_form.html", item=item)

    if image_path:
        item.main_image = image_path
        db.session.add(MediaFile(file_name=image_path.split("/")[-1], original_name=original_name or image_path, file_path=image_path, alt_text=item.alt_text or item.name))

    db.session.commit()
    flash("Fahrzeug gespeichert.", "success")
    return redirect(url_for("admin.fleet_list"))


@admin_bp.post("/fleet/<int:item_id>/delete")
@login_required
def fleet_delete(item_id: int):
    if not require_csrf():
        return redirect(url_for("admin.fleet_list"))
    db.session.delete(FleetVehicle.query.get_or_404(item_id))
    db.session.commit()
    flash("Fahrzeug gelöscht.", "success")
    return redirect(url_for("admin.fleet_list"))


# ---------- Bus Rental Requests ----------
@admin_bp.route("/bus-rental-requests")
@login_required
def bus_requests_list():
    status = request.args.get("status", "all")
    query = BusRentalRequest.query
    if status != "all":
        query = query.filter_by(status=status)
    items = query.order_by(BusRentalRequest.created_at.desc()).all()
    return render_template("admin/bus_requests_list.html", items=items, selected_status=status)


@admin_bp.route("/bus-rental-requests/<int:item_id>", methods=["GET", "POST"])
@login_required
def bus_request_detail(item_id: int):
    item = BusRentalRequest.query.get_or_404(item_id)
    allowed_statuses = {
        "new", "reviewed", "offer_in_preparation", "offer_sent",
        "accepted", "declined", "archived"
    }

    if request.method == "POST":
        if not require_csrf():
            return redirect(url_for("admin.bus_request_detail", item_id=item.id))

        status = request.form.get("status", item.status)
        if status not in allowed_statuses:
            status = item.status

        item.status = status
        item.internal_notes = request.form.get("internal_notes", "").strip() or None
        db.session.commit()
        flash("Anfrage aktualisiert.", "success")
        return redirect(url_for("admin.bus_request_detail", item_id=item.id))

    profiles = PricingProfile.query.filter_by(is_active=True).order_by(PricingProfile.name.asc()).all()
    return render_template("admin/bus_request_detail.html", item=item, profiles=profiles)


@admin_bp.post("/bus-rental-requests/<int:item_id>/status")
@login_required
def bus_request_status(item_id: int):
    if not require_csrf():
        return redirect(url_for("admin.bus_request_detail", item_id=item_id))

    item = BusRentalRequest.query.get_or_404(item_id)
    allowed_statuses = {
        "new", "reviewed", "offer_in_preparation", "offer_sent",
        "accepted", "declined", "archived"
    }
    status = request.form.get("status", item.status)
    if status not in allowed_statuses:
        flash("Ungültiger Status.", "error")
        return redirect(url_for("admin.bus_request_detail", item_id=item.id))

    item.status = status
    db.session.commit()
    flash("Status aktualisiert.", "success")
    return redirect(url_for("admin.bus_request_detail", item_id=item.id))


@admin_bp.route("/bus-rental-requests/<int:item_id>/offer")
@login_required
def bus_request_offer(item_id: int):
    item = BusRentalRequest.query.get_or_404(item_id)
    calculation = None

    calculation_id = request.args.get("calculation_id", type=int)
    if calculation_id:
        calculation = PricingCalculation.query.filter_by(id=calculation_id, request_id=item.id).first()

    if calculation is None:
        calculation = (
            PricingCalculation.query
            .filter_by(request_id=item.id)
            .order_by(PricingCalculation.created_at.desc(), PricingCalculation.id.desc())
            .first()
        )

    offer = build_offer_context(item, calculation)
    return render_template("admin/bus_request_offer.html", item=item, calculation=calculation, offer=offer)


@admin_bp.post("/bus-rental-requests/<int:item_id>/mark-offer-sent")
@login_required
def bus_request_mark_offer_sent(item_id: int):
    if not require_csrf():
        return redirect(url_for("admin.bus_request_offer", item_id=item_id))

    item = BusRentalRequest.query.get_or_404(item_id)
    item.status = "offer_sent"
    db.session.commit()
    flash("Anfrage wurde als Angebot gesendet markiert.", "success")
    return redirect(url_for("admin.bus_request_detail", item_id=item.id))


def offer_money(value):
    if value is None:
        return "-"
    try:
        return f"{Decimal(value).quantize(Decimal('0.01'))} €"
    except Exception:
        return f"{value} €"


def offer_date(value):
    if not value:
        return "-"
    return str(value)


def build_offer_context(item: BusRentalRequest, calculation: PricingCalculation | None):
    price_gross = calculation.gross_total if calculation else None
    price_net = calculation.net_total if calculation else None
    vat_amount = calculation.vat_amount if calculation else None
    vat_percent = calculation.profile.vat_percent if calculation and calculation.profile else 10

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

    plain_text = f"""Sehr geehrte Damen und Herren,

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
{offer_money(price_gross)} brutto
{f"Netto {offer_money(price_net)} zzgl. {vat_percent}% USt. ({offer_money(vat_amount)})" if calculation else "Preis vorbehaltlich finaler Kalkulation."}

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
"""

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
        "plain_text": plain_text,
        "mailto_subject": mailto_subject,
        "mailto_body": mailto_body,
    }


@admin_bp.post("/bus-rental-requests/<int:item_id>/calculate")
@login_required
def bus_request_calculate(item_id: int):
    if not require_csrf():
        return redirect(url_for("admin.bus_request_detail", item_id=item_id))

    item = BusRentalRequest.query.get_or_404(item_id)
    profile = PricingProfile.query.get_or_404(to_int(request.form.get("profile_id"), 0))

    total_km = to_float(request.form.get("total_km"), 0)
    operating_hours = to_float(request.form.get("operating_hours"), 0)
    waiting_hours = to_float(request.form.get("waiting_hours"), 0)
    days = to_int(request.form.get("days"), item.days or 1)
    tolls = Decimal(str(to_float(request.form.get("tolls"), 0)))
    parking = Decimal(str(to_float(request.form.get("parking"), 0)))
    driver_hotel_cost = Decimal(str(to_float(request.form.get("driver_hotel_cost"), 0)))

    result = calculate_price(
        profile,
        total_km=total_km,
        operating_hours=operating_hours,
        waiting_hours=waiting_hours,
        days=days,
        tolls=tolls,
        parking=parking,
        driver_hotel_cost=driver_hotel_cost,
        is_international=form_bool("is_international"),
        is_weekend=form_bool("is_weekend"),
        is_holiday=form_bool("is_holiday"),
        is_night=form_bool("is_night"),
    )

    manual_override_net = (
        Decimal(str(to_float(request.form.get("manual_override_net"), 0)))
        if request.form.get("manual_override_net")
        else None
    )

    # The customer-facing offer amount should use the manual override when present.
    # The component calculation remains visible for control, but final net/vat/gross
    # reflect the override.
    final_net_total = manual_override_net if manual_override_net is not None else result.net_total
    final_vat_amount = Decimal(str(final_net_total * Decimal(str(profile.vat_percent or 0)) / Decimal("100"))).quantize(Decimal("0.01"))
    final_gross_total = Decimal(str(final_net_total + final_vat_amount)).quantize(Decimal("0.01"))

    calc = PricingCalculation(
        request=item,
        profile=profile,
        total_km=total_km,
        operating_hours=operating_hours,
        waiting_hours=waiting_hours,
        days=days,
        tolls=tolls,
        parking=parking,
        driver_hotel_cost=driver_hotel_cost,
        is_international=form_bool("is_international"),
        is_weekend=form_bool("is_weekend"),
        is_holiday=form_bool("is_holiday"),
        is_night=form_bool("is_night"),
        km_cost=result.km_cost,
        time_cost=result.time_cost,
        waiting_cost=result.waiting_cost,
        direct_cost=result.direct_cost,
        minimum_total=result.minimum_total,
        surcharge_total=result.surcharge_total,
        net_total=final_net_total,
        vat_amount=final_vat_amount,
        gross_total=final_gross_total,
        manual_override_net=manual_override_net,
        manual_note=request.form.get("manual_note", "").strip() or None,
    )
    db.session.add(calc)
    item.status = "offer_in_preparation"
    db.session.commit()
    flash("Preisberechnung gespeichert.", "success")
    return redirect(url_for("admin.bus_request_detail", item_id=item.id))


# ---------- Pricing Profiles ----------
@admin_bp.route("/pricing")
@login_required
def pricing_profiles():
    status = request.args.get("status", "active")
    query = PricingProfile.query
    if status == "active":
        query = query.filter_by(is_active=True)
    elif status == "inactive":
        query = query.filter_by(is_active=False)

    profiles = query.order_by(PricingProfile.bus_category.asc(), PricingProfile.name.asc()).all()

    usage_counts = {
        profile_id: count for profile_id, count in
        db.session.query(PricingCalculation.profile_id, db.func.count(PricingCalculation.id))
        .group_by(PricingCalculation.profile_id)
        .all()
    }

    return render_template(
        "admin/pricing_profiles.html",
        profiles=profiles,
        selected_status=status,
        usage_counts=usage_counts,
    )


@admin_bp.route("/pricing/new", methods=["GET", "POST"])
@login_required
def pricing_profile_new():
    if request.method == "POST":
        return save_pricing_profile()
    return render_template("admin/pricing_profile_form.html", profile=None)


@admin_bp.route("/pricing/<int:profile_id>/edit", methods=["GET", "POST"])
@login_required
def pricing_profile_edit(profile_id: int):
    profile = PricingProfile.query.get_or_404(profile_id)
    if request.method == "POST":
        return save_pricing_profile(profile)
    return render_template("admin/pricing_profile_form.html", profile=profile)


@admin_bp.post("/pricing/<int:profile_id>/duplicate")
@login_required
def pricing_profile_duplicate(profile_id: int):
    if not require_csrf():
        return redirect(url_for("admin.pricing_profiles"))

    profile = PricingProfile.query.get_or_404(profile_id)
    base_name = f"{profile.name} Kopie"
    name = base_name
    counter = 2
    while PricingProfile.query.filter_by(name=name).first():
        name = f"{base_name} {counter}"
        counter += 1

    clone = PricingProfile(
        name=name,
        bus_category=profile.bus_category,
        price_per_km=profile.price_per_km,
        hourly_rate=profile.hourly_rate,
        waiting_hourly_rate=profile.waiting_hourly_rate,
        minimum_day_rate=profile.minimum_day_rate,
        international_surcharge_pct=profile.international_surcharge_pct,
        weekend_surcharge_pct=profile.weekend_surcharge_pct,
        holiday_surcharge_pct=profile.holiday_surcharge_pct,
        night_surcharge_pct=profile.night_surcharge_pct,
        vat_percent=profile.vat_percent,
        is_active=False,
    )
    db.session.add(clone)
    db.session.commit()
    flash("Profil wurde kopiert. Die Kopie ist zunächst inaktiv.", "success")
    return redirect(url_for("admin.pricing_profile_edit", profile_id=clone.id))


@admin_bp.post("/pricing/<int:profile_id>/delete")
@login_required
def pricing_profile_delete(profile_id: int):
    if not require_csrf():
        return redirect(url_for("admin.pricing_profiles"))

    profile = PricingProfile.query.get_or_404(profile_id)
    usage_count = PricingCalculation.query.filter_by(profile_id=profile.id).count()

    if usage_count:
        profile.is_active = False
        db.session.commit()
        flash("Profil wird bereits in Kalkulationen verwendet und wurde daher nur deaktiviert.", "success")
        return redirect(url_for("admin.pricing_profiles", status="inactive"))

    db.session.delete(profile)
    db.session.commit()
    flash("Profil gelöscht.", "success")
    return redirect(url_for("admin.pricing_profiles"))


def pricing_decimal(name: str, default=None, minimum=None):
    raw = request.form.get(name, "")
    if raw in (None, ""):
        return default
    value = Decimal(str(to_float(raw, 0))).quantize(Decimal("0.01"))
    if minimum is not None and value < Decimal(str(minimum)):
        raise ValueError(name)
    return value


def save_pricing_profile(profile: PricingProfile | None = None):
    if not require_csrf():
        return redirect(url_for("admin.pricing_profiles"))

    name = request.form.get("name", "").strip()
    bus_category = request.form.get("bus_category", "").strip()

    if not name or not bus_category:
        flash("Name und Bus-Kategorie sind Pflichtfelder.", "error")
        return render_template("admin/pricing_profile_form.html", profile=profile)

    duplicate = PricingProfile.query.filter(PricingProfile.name == name)
    if profile:
        duplicate = duplicate.filter(PricingProfile.id != profile.id)
    if duplicate.first():
        flash("Ein Pricing Profil mit diesem Namen existiert bereits.", "error")
        return render_template("admin/pricing_profile_form.html", profile=profile)

    try:
        price_per_km = pricing_decimal("price_per_km", minimum=0)
        hourly_rate = pricing_decimal("hourly_rate", minimum=0)
        waiting_hourly_rate = pricing_decimal("waiting_hourly_rate", minimum=0)
        minimum_day_rate = pricing_decimal("minimum_day_rate", minimum=0)
        international_surcharge_pct = pricing_decimal("international_surcharge_pct", default=Decimal("0"), minimum=0)
        weekend_surcharge_pct = pricing_decimal("weekend_surcharge_pct", default=Decimal("0"), minimum=0)
        holiday_surcharge_pct = pricing_decimal("holiday_surcharge_pct", default=Decimal("0"), minimum=0)
        night_surcharge_pct = pricing_decimal("night_surcharge_pct", default=Decimal("0"), minimum=0)
        vat_percent = pricing_decimal("vat_percent", default=Decimal("10"), minimum=0)
    except ValueError:
        flash("Bitte geben Sie gültige positive Zahlen ein.", "error")
        return render_template("admin/pricing_profile_form.html", profile=profile)

    required_values = [price_per_km, hourly_rate, waiting_hourly_rate, minimum_day_rate]
    if any(value is None for value in required_values):
        flash("€/km, €/h, Wartezeit €/h und Minimum/Tag sind Pflichtfelder.", "error")
        return render_template("admin/pricing_profile_form.html", profile=profile)

    if profile is None:
        profile = PricingProfile(
            name=name,
            bus_category=bus_category,
            price_per_km=price_per_km,
            hourly_rate=hourly_rate,
            waiting_hourly_rate=waiting_hourly_rate,
            minimum_day_rate=minimum_day_rate,
        )
        db.session.add(profile)

    profile.name = name
    profile.bus_category = bus_category
    profile.price_per_km = price_per_km
    profile.hourly_rate = hourly_rate
    profile.waiting_hourly_rate = waiting_hourly_rate
    profile.minimum_day_rate = minimum_day_rate
    profile.international_surcharge_pct = international_surcharge_pct
    profile.weekend_surcharge_pct = weekend_surcharge_pct
    profile.holiday_surcharge_pct = holiday_surcharge_pct
    profile.night_surcharge_pct = night_surcharge_pct
    profile.vat_percent = vat_percent
    profile.is_active = form_bool("is_active")

    db.session.commit()
    flash("Pricing Profil gespeichert.", "success")
    return redirect(url_for("admin.pricing_profiles", status="all"))


# ---------- Contact Requests ----------
@admin_bp.route("/contact-requests")
@login_required
def contact_requests_list():
    status = request.args.get("status", "new")
    query = ContactRequest.query

    if status != "all":
        query = query.filter_by(status=status)

    items = query.order_by(ContactRequest.created_at.desc(), ContactRequest.id.desc()).all()

    counts = {
        row[0]: row[1] for row in
        db.session.query(ContactRequest.status, db.func.count(ContactRequest.id))
        .group_by(ContactRequest.status)
        .all()
    }

    return render_template(
        "admin/contact_requests_list.html",
        items=items,
        selected_status=status,
        counts=counts,
    )


@admin_bp.route("/contact-requests/<int:item_id>", methods=["GET", "POST"])
@login_required
def contact_request_detail(item_id: int):
    item = ContactRequest.query.get_or_404(item_id)
    allowed_statuses = {"new", "read", "answered", "archived"}

    if request.method == "POST":
        if not require_csrf():
            return redirect(url_for("admin.contact_request_detail", item_id=item.id))

        status = request.form.get("status", item.status)
        if status not in allowed_statuses:
            status = item.status

        item.status = status
        item.internal_notes = request.form.get("internal_notes", "").strip() or None
        db.session.commit()

        flash("Kontaktanfrage aktualisiert.", "success")
        return redirect(url_for("admin.contact_request_detail", item_id=item.id))

    return render_template("admin/contact_request_detail.html", item=item)


@admin_bp.post("/contact-requests/<int:item_id>/status")
@login_required
def contact_request_status(item_id: int):
    if not require_csrf():
        return redirect(url_for("admin.contact_request_detail", item_id=item_id))

    item = ContactRequest.query.get_or_404(item_id)
    allowed_statuses = {"new", "read", "answered", "archived"}
    status = request.form.get("status", item.status)

    if status not in allowed_statuses:
        flash("Ungültiger Status.", "error")
        return redirect(url_for("admin.contact_request_detail", item_id=item.id))

    item.status = status
    db.session.commit()
    flash("Status aktualisiert.", "success")
    return redirect(url_for("admin.contact_request_detail", item_id=item.id))


@admin_bp.post("/contact-requests/<int:item_id>/delete")
@login_required
def contact_request_delete(item_id: int):
    if not require_csrf():
        return redirect(url_for("admin.contact_requests_list"))

    item = ContactRequest.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()

    flash("Kontaktanfrage gelöscht.", "success")
    return redirect(url_for("admin.contact_requests_list", status="all"))


# ---------- Email Notifications ----------
@admin_bp.route("/email-settings", methods=["GET", "POST"])
@login_required
def email_settings():
    settings = get_email_settings()

    if request.method == "POST":
        if not require_csrf():
            return redirect(url_for("admin.email_settings"))

        ok, message = send_test_notification()
        if ok:
            flash("Test-E-Mail wurde erfolgreich gesendet.", "success")
        else:
            flash(f"Test-E-Mail konnte nicht gesendet werden: {message}", "error")

        return redirect(url_for("admin.email_settings"))

    return render_template("admin/email_settings.html", settings=settings)


# ---------- Media ----------
@admin_bp.route("/media", methods=["GET", "POST"])
@login_required
def media_list():
    if request.method == "POST":
        if not require_csrf():
            return redirect(url_for("admin.media_list"))
        try:
            image_path, original_name = save_uploaded_image(request.files.get("file"))
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin.media_list"))
        if not image_path:
            flash("Bitte wählen Sie eine Datei.", "error")
            return redirect(url_for("admin.media_list"))
        db.session.add(MediaFile(
            file_name=image_path.split("/")[-1],
            original_name=original_name or image_path,
            file_path=image_path,
            alt_text=request.form.get("alt_text", "").strip() or None,
        ))
        db.session.commit()
        flash("Datei hochgeladen.", "success")
        return redirect(url_for("admin.media_list"))

    media_files = MediaFile.query.order_by(MediaFile.uploaded_at.desc()).all()
    return render_template("admin/media_list.html", media_files=media_files)
