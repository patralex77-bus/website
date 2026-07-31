from __future__ import annotations

import json
import re
from pathlib import Path
from decimal import Decimal

import click
from flask import Flask
from werkzeug.security import generate_password_hash

from .config import Config
from .extensions import db
from .models import (
    AdminUser, BlogPost, CustomerReview, SchoolDestination, FleetVehicle,
    PricingProfile, utcnow
)
from .utils.csrf import get_csrf_token


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_FOLDER"].mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    from .routes.public import public_bp
    from .routes.admin import admin_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.context_processor
    def inject_csrf():
        return {"csrf_token": get_csrf_token}

    register_cli(app)
    return app


def _parse_price(value: str | None):
    if not value:
        return None
    clean = str(value).replace("€", "").replace("ab", "").strip()
    clean = clean.replace(".", "").replace(",", ".")
    match = re.search(r"\d+(?:\.\d+)?", clean)
    if not match:
        return None
    return Decimal(match.group(0))


def _parse_distance(value: str | None):
    if not value:
        return None
    match = re.search(r"\d+", str(value))
    if not match:
        return None
    return float(match.group(0))


def _parse_int(value, default: int = 0) -> int:
    if value is None:
        return default
    match = re.search(r"\d+", str(value))
    if not match:
        return default
    return int(match.group(0))


def _category_from_tags(tags: list[str]) -> str:
    labels = {
        "wandern": "Wandern / Natur",
        "geschichte": "Geschichte",
        "freizeit": "Freizeit",
        "tiere": "Tiere",
        "staedte": "Städte",
        "technik": "Technik",
    }
    selected = [labels.get(tag, tag.title()) for tag in tags or []]
    if not selected:
        return "Allgemein"
    return " / ".join(selected[:2])


def _fleet_category(item: dict) -> str:
    raw_type = (item.get("type") or "").lower()
    title = (item.get("title") or "").lower()
    seats = _parse_int(item.get("seats"), 0)

    if "doppeldecker" in raw_type or "skyliner" in title or seats >= 70:
        return "Doppeldecker"
    if seats <= 46:
        return "Kleine Gruppen"
    return "Reisebus"


def _set_fleet_features(vehicle: FleetVehicle, item: dict) -> None:
    features_text = " ".join(item.get("features", []) or []).lower()
    full_text = " ".join([
        str(item.get("title", "")),
        str(item.get("type", "")),
        str(item.get("class", "")),
        str(item.get("best_for", "")),
        features_text,
    ]).lower()

    vehicle.ac = True
    vehicle.wc = True
    vehicle.usb = True
    vehicle.power_220 = True
    vehicle.euro6 = True
    vehicle.tv = True
    vehicle.monitors_2 = True
    vehicle.adjustable_seats = True
    vehicle.sleeping_seats = True

    vehicle.wifi = ("wlan" in full_text) or ("wifi" in full_text)
    vehicle.kitchen = ("bordküche" in full_text) or ("kueche" in full_text) or ("kitchen" in full_text)
    vehicle.coffee_machine = ("kaffee" in full_text)
    vehicle.fridge = ("kühlschrank" in full_text) or ("kuehlschrank" in full_text) or ("fridge" in full_text)
    vehicle.kettle = ("wasserkocher" in full_text)
    vehicle.tables = ("tische" in full_text)
    vehicle.leather_seats = ("leder" in full_text)
    vehicle.folding_tables = ("klapptisch" in full_text)
    vehicle.dvd = ("dvd" in full_text)


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db():
        db.create_all()

        username = app.config["ADMIN_USERNAME"]
        password = app.config["ADMIN_PASSWORD"]

        admin = AdminUser.query.filter_by(username=username).first()
        if not admin:
            admin = AdminUser(
                username=username,
                password_hash=generate_password_hash(password),
                is_active=True,
            )
            db.session.add(admin)
            db.session.commit()
            click.echo(f"Created admin user: {username}")
        else:
            click.echo(f"Admin user already exists: {username}")

        click.echo("Database initialized.")

    @app.cli.command("import-school-destinations")
    def import_school_destinations():
        db.create_all()

        json_path = Path(app.root_path) / "approved_source_data" / "austria_express_school_destinations_v4.json"
        if not json_path.exists():
            raise click.ClickException(f"JSON source not found: {json_path}")

        data = json.loads(json_path.read_text(encoding="utf-8"))
        zones = data.get("zones", {})
        destinations = data.get("destinations", [])

        created = 0
        updated = 0

        for index, item in enumerate(destinations, start=1):
            slug = item.get("id") or item.get("slug")
            if not slug:
                continue

            zone_key = item.get("zone", "A")
            zone_data = zones.get(zone_key, {})
            tags = item.get("tags", []) or []
            tags_str = ",".join(tags)

            destination = SchoolDestination.query.filter_by(slug=slug).first()
            if destination:
                updated += 1
            else:
                destination = SchoolDestination(
                    slug=slug,
                    title=item.get("title", slug),
                    short_description=item.get("short", ""),
                    zone=zone_key,
                    category="Allgemein",
                )
                db.session.add(destination)
                created += 1

            destination.title = item.get("title", slug)
            destination.zone = zone_key
            destination.category = _category_from_tags(tags)
            destination.tags = tags_str
            destination.short_description = item.get("short") or item.get("title", slug)
            destination.full_description = item.get("desc") or item.get("description") or item.get("short")
            destination.age_group = item.get("age")
            destination.travel_time = item.get("time")
            destination.distance_km = _parse_distance(zone_data.get("distance"))
            destination.latitude = item.get("lat")
            destination.longitude = item.get("lon")
            destination.price_53 = _parse_price(item.get("price53") or zone_data.get("price53"))
            destination.price_75 = _parse_price(item.get("price75") or zone_data.get("price75"))
            destination.alt_text = item.get("icon") or "🎒"
            destination.is_active = True
            destination.sort_order = index * 10

        db.session.commit()
        click.echo(f"School destinations imported. Created: {created}, updated: {updated}, total source: {len(destinations)}")
        click.echo("Existing custom destinations were not deleted.")

    @app.cli.command("import-fleet")
    def import_fleet():
        db.create_all()

        json_path = Path(app.root_path) / "approved_source_data" / "austria_express_fleet_backend_seed_v1.json"
        if not json_path.exists():
            raise click.ClickException(f"JSON source not found: {json_path}")

        data = json.loads(json_path.read_text(encoding="utf-8"))
        fleet = data.get("fleet", [])

        created = 0
        updated = 0

        for index, item in enumerate(fleet, start=1):
            slug = item.get("id") or re.sub(r"[^a-z0-9]+", "-", (item.get("title", "") or "").lower()).strip("-")
            if not slug:
                continue

            vehicle = FleetVehicle.query.filter_by(slug=slug).first()
            if vehicle:
                updated += 1
            else:
                vehicle = FleetVehicle(
                    slug=slug,
                    name=item.get("title", slug),
                    seats=_parse_int(item.get("seats"), 53),
                    category=_fleet_category(item),
                )
                db.session.add(vehicle)
                created += 1

            vehicle.name = item.get("title", slug)
            vehicle.model = item.get("type") or item.get("short")
            vehicle.seats = _parse_int(item.get("seats"), vehicle.seats or 53)
            vehicle.quantity = _parse_int(item.get("quantity"), 1)
            vehicle.category = _fleet_category(item)
            vehicle.star_rating = item.get("class") or "4★ Reisebus"
            vehicle.description = item.get("best_for") or item.get("short") or ""
            vehicle.suitable_for = ", ".join(item.get("tags", []) or [])
            vehicle.alt_text = item.get("icon") or "🚌"
            vehicle.is_active = True
            vehicle.sort_order = index * 10

            _set_fleet_features(vehicle, item)

        db.session.commit()
        click.echo(f"Fleet imported. Created: {created}, updated: {updated}, total source: {len(fleet)}")
        click.echo("Existing custom vehicles were not deleted.")

    @app.cli.command("import-aktuelles")
    def import_aktuelles():
        """
        Import approved Aktuelles/Kundenstimmen starter content.
        Safe/idempotent: creates missing posts/reviews and updates matching posts by slug.
        Does not delete existing posts or reviews.
        """
        db.create_all()

        json_path = Path(app.root_path) / "approved_source_data" / "austria_express_aktuelles_seed_v1.json"
        if not json_path.exists():
            raise click.ClickException(f"JSON source not found: {json_path}")

        data = json.loads(json_path.read_text(encoding="utf-8"))

        created_posts = 0
        updated_posts = 0
        for post_data in data.get("posts", []):
            slug = post_data.get("slug")
            if not slug:
                continue

            post = BlogPost.query.filter_by(slug=slug).first()
            if post:
                updated_posts += 1
            else:
                post = BlogPost(slug=slug)
                db.session.add(post)
                created_posts += 1

            post.title = post_data.get("title", slug)
            post.category = post_data.get("category", "Aktuelles")
            post.excerpt = post_data.get("excerpt")
            post.body = post_data.get("body") or post_data.get("excerpt") or ""
            post.status = post_data.get("status", "published")
            post.sort_order = post_data.get("sort_order", 100)
            if not post.published_at:
                post.published_at = utcnow()

        created_reviews = 0
        for review_data in data.get("reviews", []):
            existing = CustomerReview.query.filter_by(
                customer_name=review_data.get("customer_name"),
                text=review_data.get("text"),
            ).first()
            if existing:
                continue

            review = CustomerReview(
                customer_name=review_data.get("customer_name", "Kunde"),
                organisation=review_data.get("organisation"),
                email_internal="demo@example.com",
                public_display_name=review_data.get("public_display_name"),
                rating=int(review_data.get("rating", 5)),
                trip_type=review_data.get("trip_type", "Allgemein"),
                text=review_data.get("text", ""),
                status=review_data.get("status", "approved"),
                approved_at=utcnow() if review_data.get("status", "approved") == "approved" else None,
            )
            db.session.add(review)
            created_reviews += 1

        db.session.commit()
        click.echo(f"Aktuelles imported. Posts created: {created_posts}, posts updated: {updated_posts}, reviews created: {created_reviews}")
        click.echo("Existing custom posts and reviews were not deleted.")

    @app.cli.command("seed-demo")
    def seed_demo():
        db.create_all()

        profiles = [
            ("46 Sitze", "Kleine Gruppen", 1.65, 58, 35, 650, 8, 10, 15, 12, 10),
            ("53 Sitze", "Reisebus", 1.85, 65, 38, 750, 8, 10, 15, 12, 10),
            ("55 Sitze", "Reisebus", 1.90, 68, 40, 780, 8, 10, 15, 12, 10),
            ("77 Sitze", "Doppeldecker", 2.35, 85, 50, 980, 10, 12, 18, 15, 10),
        ]
        for name, cat, pkm, hr, whr, min_day, intl, weekend, holiday, night, vat in profiles:
            if not PricingProfile.query.filter_by(name=name).first():
                db.session.add(PricingProfile(
                    name=name,
                    bus_category=cat,
                    price_per_km=pkm,
                    hourly_rate=hr,
                    waiting_hourly_rate=whr,
                    minimum_day_rate=min_day,
                    international_surcharge_pct=intl,
                    weekend_surcharge_pct=weekend,
                    holiday_surcharge_pct=holiday,
                    night_surcharge_pct=night,
                    vat_percent=vat,
                ))

        db.session.commit()
        click.echo("Demo data seeded.")
