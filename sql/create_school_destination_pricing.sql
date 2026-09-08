-- Optional manual SQL for the new school pricing support table.
-- Normally not needed when render_start.sh runs: flask --app run.py init-db
-- because db.create_all() creates this table automatically.

CREATE TABLE IF NOT EXISTS school_destination_pricing (
  id SERIAL PRIMARY KEY,
  destination_id INTEGER NOT NULL UNIQUE REFERENCES school_destinations(id),
  drive_minutes_one_way INTEGER,
  stay_minutes INTEGER,
  price_profile_53_id INTEGER REFERENCES pricing_profiles(id),
  price_profile_75_id INTEGER REFERENCES pricing_profiles(id),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_school_destination_pricing_destination_id
  ON school_destination_pricing(destination_id);
