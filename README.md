# Austria Express Backend Full v2

This package extends the previous backend and adds:

- Aktuelles & Kundenstimmen
- Schulen destinations CMS
- Fuhrpark CMS
- Bus Rental inquiry forms
- first internal Pricing Engine
- Admin panel for all modules
- Image/media upload
- SQLite local database, prepared for PostgreSQL later

## Run locally

```bash
cd austria_express_backend_full_v2
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
flask --app run.py init-db
flask --app run.py seed-demo
flask --app run.py run --debug
```

Open:

```text
http://127.0.0.1:5000/
http://127.0.0.1:5000/schulen
http://127.0.0.1:5000/fuhrpark
http://127.0.0.1:5000/bus-rental
http://127.0.0.1:5000/aktuelles-kundenstimmen
http://127.0.0.1:5000/admin/login
```

Default admin is defined in `.env`.

## Modules

### Schulen destinations

Admin can manage:

- title
- slug
- zone
- category
- tags
- short and full description
- age group
- distance
- travel time
- map latitude/longitude
- prices for 53-seat and 75-seat buses
- main image
- active status
- sort order

Public:

- list with filters
- detail page

### Fuhrpark

Admin can manage:

- vehicle name
- model
- seats
- quantity
- category
- star rating
- description
- suitability tags
- active status
- image
- equipment/features as boolean flags

Public:

- vehicle list
- detail view through page cards

### Bus Rental

Public:

- detailed inquiry form
- saves request to backend
- request status: new / reviewed / offer_in_preparation / offer_sent / accepted / declined / archived

Admin:

- list requests
- view request
- update status and internal notes
- run internal price calculation
- manual override

### Pricing Engine v1

This is an internal calculator, not a public customer price.

Inputs:

- bus category
- total km
- operating hours
- days
- waiting hours
- tolls/parking
- driver hotel costs
- international route
- weekend/holiday/night flags

Settings are stored in database and editable in code for now through seeded `PricingProfile`.

Formula:

```text
km_cost = total_km * price_per_km
time_cost = operating_hours * hourly_rate
waiting_cost = waiting_hours * waiting_hourly_rate
direct_cost = km_cost + time_cost + waiting_cost + tolls + parking + driver_hotel_cost
minimum = days * minimum_day_rate
subtotal = max(direct_cost, minimum)

surcharges:
- international %
- weekend %
- holiday %
- night %

net_total = subtotal + surcharges
vat = net_total * vat_percent
gross_total = net_total + vat
```

Admin can override final price manually.

## Production notes

Before production:

- use PostgreSQL;
- add Flask-Migrate;
- put uploads in Cloudflare R2 / S3 / Supabase Storage, not local Render disk;
- add email notifications;
- add role-based admin users;
- add CSRF library such as Flask-WTF for complex forms;
- review Datenschutz and AGB legally;
- connect Google Maps or another route API for automatic km/duration;
- pricing engine should remain internal until rules are stable.
