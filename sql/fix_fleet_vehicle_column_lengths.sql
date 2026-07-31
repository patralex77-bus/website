-- PostgreSQL Fleet schema fix
-- Safe to run multiple times.

ALTER TABLE fleet_vehicles
  ALTER COLUMN star_rating TYPE VARCHAR(120);

ALTER TABLE fleet_vehicles
  ALTER COLUMN suitable_for TYPE VARCHAR(500);

ALTER TABLE fleet_vehicles
  ALTER COLUMN alt_text TYPE VARCHAR(500);
