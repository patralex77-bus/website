from __future__ import annotations

from datetime import datetime, timezone
from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AdminUser(db.Model):
    __tablename__ = "admin_users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    approved_reviews = db.relationship("CustomerReview", back_populates="approved_by_user")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False)
    slug = db.Column(db.String(240), unique=True, nullable=False, index=True)
    category = db.Column(db.String(80), default="Allgemein", nullable=False, index=True)
    excerpt = db.Column(db.Text, nullable=True)
    body = db.Column(db.Text, nullable=False)
    main_image = db.Column(db.String(500), nullable=True)
    alt_text = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), default="draft", nullable=False, index=True)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    seo_title = db.Column(db.String(255), nullable=True)
    seo_description = db.Column(db.String(320), nullable=True)
    sort_order = db.Column(db.Integer, default=100, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class CustomerReview(db.Model):
    __tablename__ = "customer_reviews"

    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(160), nullable=False)
    organisation = db.Column(db.String(160), nullable=True)
    email_internal = db.Column(db.String(255), nullable=False)
    phone_internal = db.Column(db.String(80), nullable=True)
    public_display_name = db.Column(db.String(160), nullable=True)
    rating = db.Column(db.Integer, nullable=False, default=5)
    trip_type = db.Column(db.String(80), nullable=False, default="Allgemein")
    text = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="pending", nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"), nullable=True)
    approved_by_user = db.relationship("AdminUser", back_populates="approved_reviews")

    @property
    def display_name(self) -> str:
        return self.public_display_name or self.organisation or self.customer_name

    @property
    def stars(self) -> str:
        safe_rating = max(1, min(5, int(self.rating or 5)))
        return "★" * safe_rating


class ContactRequest(db.Model):
    __tablename__ = "contact_requests"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(160), nullable=False)
    organisation = db.Column(db.String(200))
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(80))

    request_type = db.Column(db.String(120))
    preferred_contact = db.Column(db.String(80))
    subject = db.Column(db.String(255))
    message = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(40), nullable=False, default="new", index=True)
    internal_notes = db.Column(db.Text)

    ip_address = db.Column(db.String(80))
    user_agent = db.Column(db.String(500))

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def __repr__(self):
        return f"<ContactRequest {self.id} {self.email}>"


class MediaFile(db.Model):
    __tablename__ = "media_files"

    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    alt_text = db.Column(db.String(255), nullable=True)
    uploaded_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class SchoolDestination(db.Model):
    __tablename__ = "school_destinations"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False)
    slug = db.Column(db.String(240), unique=True, nullable=False, index=True)
    zone = db.Column(db.String(40), nullable=False, index=True)  # A/B/C/D
    category = db.Column(db.String(100), nullable=False, index=True)
    tags = db.Column(db.String(300), nullable=True)
    short_description = db.Column(db.Text, nullable=False)
    full_description = db.Column(db.Text, nullable=True)
    age_group = db.Column(db.String(120), nullable=True)
    distance_km = db.Column(db.Float, nullable=True)
    travel_time = db.Column(db.String(120), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    price_53 = db.Column(db.Numeric(10, 2), nullable=True)
    price_75 = db.Column(db.Numeric(10, 2), nullable=True)
    main_image = db.Column(db.String(500), nullable=True)
    alt_text = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    sort_order = db.Column(db.Integer, default=100, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    images = db.relationship("DestinationImage", back_populates="destination", cascade="all, delete-orphan")


class DestinationImage(db.Model):
    __tablename__ = "destination_images"

    id = db.Column(db.Integer, primary_key=True)
    destination_id = db.Column(db.Integer, db.ForeignKey("school_destinations.id"), nullable=False)
    image_path = db.Column(db.String(500), nullable=False)
    alt_text = db.Column(db.String(255), nullable=True)
    sort_order = db.Column(db.Integer, default=100, nullable=False)
    destination = db.relationship("SchoolDestination", back_populates="images")


class FleetVehicle(db.Model):
    __tablename__ = "fleet_vehicles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(220), nullable=False)
    slug = db.Column(db.String(240), unique=True, nullable=False, index=True)
    model = db.Column(db.String(160), nullable=True)
    seats = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    category = db.Column(db.String(100), nullable=False, index=True)
    star_rating = db.Column(db.String(20), default="4★", nullable=True)
    description = db.Column(db.Text, nullable=True)
    suitable_for = db.Column(db.String(300), nullable=True)
    main_image = db.Column(db.String(500), nullable=True)
    alt_text = db.Column(db.String(255), nullable=True)

    ac = db.Column(db.Boolean, default=True, nullable=False)
    wc = db.Column(db.Boolean, default=True, nullable=False)
    usb = db.Column(db.Boolean, default=True, nullable=False)
    power_220 = db.Column(db.Boolean, default=True, nullable=False)
    euro6 = db.Column(db.Boolean, default=True, nullable=False)
    wifi = db.Column(db.Boolean, default=False, nullable=False)
    tv = db.Column(db.Boolean, default=True, nullable=False)
    dvd = db.Column(db.Boolean, default=False, nullable=False)
    monitors_2 = db.Column(db.Boolean, default=True, nullable=False)
    kitchen = db.Column(db.Boolean, default=False, nullable=False)
    coffee_machine = db.Column(db.Boolean, default=False, nullable=False)
    fridge = db.Column(db.Boolean, default=False, nullable=False)
    kettle = db.Column(db.Boolean, default=False, nullable=False)
    tables = db.Column(db.Boolean, default=False, nullable=False)
    leather_seats = db.Column(db.Boolean, default=False, nullable=False)
    folding_tables = db.Column(db.Boolean, default=False, nullable=False)
    adjustable_seats = db.Column(db.Boolean, default=True, nullable=False)
    sleeping_seats = db.Column(db.Boolean, default=True, nullable=False)

    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    sort_order = db.Column(db.Integer, default=100, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    images = db.relationship("VehicleImage", back_populates="vehicle", cascade="all, delete-orphan")

    @property
    def feature_list(self) -> list[tuple[str, bool]]:
        return [
            ("Klimaanlage", self.ac),
            ("Toilette", self.wc),
            ("USB-Ladeanschlüsse", self.usb),
            ("220V-Steckdosen", self.power_220),
            ("Euro 6", self.euro6),
            ("WLAN", self.wifi),
            ("TV", self.tv),
            ("DVD", self.dvd),
            ("2 Monitore", self.monitors_2),
            ("Bordküche", self.kitchen),
            ("Kaffeemaschine", self.coffee_machine),
            ("Kühlschrank", self.fridge),
            ("Wasserkocher", self.kettle),
            ("Tische", self.tables),
            ("Teilleder Sitze", self.leather_seats),
            ("Klapptische", self.folding_tables),
            ("Seitlich verstellbare Sitze", self.adjustable_seats),
            ("Schlafsitze", self.sleeping_seats),
        ]


class VehicleImage(db.Model):
    __tablename__ = "vehicle_images"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("fleet_vehicles.id"), nullable=False)
    image_path = db.Column(db.String(500), nullable=False)
    alt_text = db.Column(db.String(255), nullable=True)
    sort_order = db.Column(db.Integer, default=100, nullable=False)
    vehicle = db.relationship("FleetVehicle", back_populates="images")


class BusRentalRequest(db.Model):
    __tablename__ = "bus_rental_requests"

    id = db.Column(db.Integer, primary_key=True)
    customer_type = db.Column(db.String(100), nullable=False)
    organisation = db.Column(db.String(180), nullable=True)
    contact_name = db.Column(db.String(160), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(80), nullable=True)

    trip_type = db.Column(db.String(100), nullable=False)
    departure_place = db.Column(db.String(255), nullable=False)
    destination = db.Column(db.String(255), nullable=False)
    date_start = db.Column(db.String(40), nullable=True)
    date_end = db.Column(db.String(40), nullable=True)
    time_departure = db.Column(db.String(40), nullable=True)
    time_return = db.Column(db.String(40), nullable=True)
    days = db.Column(db.Integer, nullable=True)
    passengers = db.Column(db.Integer, nullable=True)
    bus_size = db.Column(db.String(100), nullable=True)
    bus_count = db.Column(db.Integer, nullable=True)

    route_description = db.Column(db.Text, nullable=True)
    group_notes = db.Column(db.Text, nullable=True)
    special_needs = db.Column(db.Text, nullable=True)

    req_wc = db.Column(db.Boolean, default=False)
    req_usb = db.Column(db.Boolean, default=False)
    req_power = db.Column(db.Boolean, default=False)
    req_wifi = db.Column(db.Boolean, default=False)
    req_doubledecker = db.Column(db.Boolean, default=False)
    req_kitchen = db.Column(db.Boolean, default=False)

    status = db.Column(db.String(40), default="new", nullable=False, index=True)
    internal_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    calculations = db.relationship("PricingCalculation", back_populates="request", cascade="all, delete-orphan")


class PricingProfile(db.Model):
    __tablename__ = "pricing_profiles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    bus_category = db.Column(db.String(100), nullable=False, index=True)

    price_per_km = db.Column(db.Numeric(10, 2), nullable=False)
    hourly_rate = db.Column(db.Numeric(10, 2), nullable=False)
    waiting_hourly_rate = db.Column(db.Numeric(10, 2), nullable=False)
    minimum_day_rate = db.Column(db.Numeric(10, 2), nullable=False)

    international_surcharge_pct = db.Column(db.Numeric(5, 2), default=0)
    weekend_surcharge_pct = db.Column(db.Numeric(5, 2), default=0)
    holiday_surcharge_pct = db.Column(db.Numeric(5, 2), default=0)
    night_surcharge_pct = db.Column(db.Numeric(5, 2), default=0)
    vat_percent = db.Column(db.Numeric(5, 2), default=10)

    is_active = db.Column(db.Boolean, default=True, nullable=False)


class PricingCalculation(db.Model):
    __tablename__ = "pricing_calculations"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("bus_rental_requests.id"), nullable=True)
    request = db.relationship("BusRentalRequest", back_populates="calculations")

    profile_id = db.Column(db.Integer, db.ForeignKey("pricing_profiles.id"), nullable=False)
    profile = db.relationship("PricingProfile")

    total_km = db.Column(db.Float, nullable=False)
    operating_hours = db.Column(db.Float, nullable=False)
    waiting_hours = db.Column(db.Float, default=0, nullable=False)
    days = db.Column(db.Integer, default=1, nullable=False)
    tolls = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    parking = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    driver_hotel_cost = db.Column(db.Numeric(10, 2), default=0, nullable=False)

    is_international = db.Column(db.Boolean, default=False, nullable=False)
    is_weekend = db.Column(db.Boolean, default=False, nullable=False)
    is_holiday = db.Column(db.Boolean, default=False, nullable=False)
    is_night = db.Column(db.Boolean, default=False, nullable=False)

    km_cost = db.Column(db.Numeric(10, 2), nullable=False)
    time_cost = db.Column(db.Numeric(10, 2), nullable=False)
    waiting_cost = db.Column(db.Numeric(10, 2), nullable=False)
    direct_cost = db.Column(db.Numeric(10, 2), nullable=False)
    minimum_total = db.Column(db.Numeric(10, 2), nullable=False)
    surcharge_total = db.Column(db.Numeric(10, 2), nullable=False)
    net_total = db.Column(db.Numeric(10, 2), nullable=False)
    vat_amount = db.Column(db.Numeric(10, 2), nullable=False)
    gross_total = db.Column(db.Numeric(10, 2), nullable=False)

    manual_override_net = db.Column(db.Numeric(10, 2), nullable=True)
    manual_note = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
