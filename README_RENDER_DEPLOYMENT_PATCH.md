# Render Deployment Patch v1

This patch prepares the Austria Express Flask backend for Render deployment.

## What it adds

```text
requirements.txt
Procfile
render.yaml
render_start.sh
.env.render.example
RENDER_FIRST_RUN_COMMANDS.txt
app/config.py
```

## What it fixes/prepares

```text
1. Adds gunicorn for production start.
2. Adds psycopg v3 PostgreSQL driver.
3. Supports Render PostgreSQL URLs:
   postgres://
   postgresql://
   postgresql+psycopg://

4. Keeps local SQLite working.
5. Keeps Windows/OneDrive SQLite fix.
6. Adds render.yaml for Blueprint deployment.
7. Adds render_start.sh:
   - runs flask --app run.py init-db
   - starts gunicorn run:app
8. Keeps SMTP notification environment variables ready.
```

## Install locally before pushing to GitHub

Copy the patch contents into:

```text
C:\Users\offic\OneDrive\Dokumente\all\austria_express_backend_full_v2
```

Overwrite:

```text
requirements.txt
app/config.py
```

Add:

```text
Procfile
render.yaml
render_start.sh
.env.render.example
RENDER_FIRST_RUN_COMMANDS.txt
```

Then locally run:

```bat
pip install -r requirements.txt
flask --app run.py run --debug
```

## Render setup

Create a Render Web Service from your GitHub repository.

Use:

```text
Build Command:
pip install -r requirements.txt

Start Command:
bash render_start.sh
```

Or use the included `render.yaml`.

## Required Render Environment Variables

```text
SECRET_KEY
ADMIN_USERNAME
ADMIN_PASSWORD
DATABASE_URL
PUBLIC_BASE_URL
```

For PostgreSQL, create a Render PostgreSQL database and copy its database URL to:

```text
DATABASE_URL
```

## Email variables

```text
EMAIL_NOTIFICATIONS_ENABLED=false
NOTIFICATION_TO=office@austria-express.eu
MAIL_FROM=office@austria-express.eu
MAIL_FROM_NAME=Austria Express Website
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
SMTP_USE_TLS
SMTP_USE_SSL
```

Keep `EMAIL_NOTIFICATIONS_ENABLED=false` until SMTP test is configured.

## First run after deploy

Open Render Shell and run once:

```bash
flask --app run.py import-school-destinations
flask --app run.py import-fleet
flask --app run.py import-aktuelles
```

`init-db` is already run automatically by `render_start.sh`.

## Notes

- This patch does not configure persistent image storage. Render local disk is not a safe long-term place for uploaded images.
- Before serious production use, Cloudflare R2 / S3 / Supabase Storage should be added for uploaded media.
