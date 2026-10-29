-- =====================================================================
-- SAKAYGUIDE MIGRATION: Map coordinates for the Interactive Route Map
-- Database : sakayguide_db
-- Target   : MariaDB 10.4+ / MySQL 8 (XAMPP)
--
-- WHAT THIS DOES
--   1. Adds two NULLable columns to the existing `locations` table:
--        latitude  DECIMAL(10,7) NULL
--        longitude DECIMAL(10,7) NULL
--      DECIMAL is used (not FLOAT/DOUBLE) to match the database
--      conventions; 7 decimal places is ~1 cm of map precision.
--      No new table is created and no existing table is touched.
--
--   2. Fills the columns ONLY with verified coordinates for
--      Kabankalan City, Negros Occidental, taken from OpenStreetMap
--      (state of the OSM database, October 2026). Each row below was
--      matched to an existing OpenStreetMap object by its recorded
--      address; the OSM object name is listed in the comment so the
--      value can be re-checked later at https://www.openstreetmap.org.
--
--   3. Locations without a verified OSM match stay NULL. The Django
--      app then shows such a place in the journey instructions and
--      labels it "map position not yet verified" instead of guessing.
--
-- NOTES
--   * `ADD COLUMN IF NOT EXISTS` is MariaDB syntax. On MySQL 8 remove
--     the `IF NOT EXISTS` words (running it twice would error there).
--   * The script is safe to re-run: the UPDATEs simply rewrite the
--     same verified values.
-- =====================================================================

USE sakayguide_db;

-- 1. SCHEMA -----------------------------------------------------------
ALTER TABLE locations
  ADD COLUMN IF NOT EXISTS latitude  DECIMAL(10,7) NULL
    COMMENT 'Verified latitude (WGS 84) from OpenStreetMap; NULL = not yet verified',
  ADD COLUMN IF NOT EXISTS longitude DECIMAL(10,7) NULL
    COMMENT 'Verified longitude (WGS 84) from OpenStreetMap; NULL = not yet verified';

START TRANSACTION;

-- 2. VERIFIED KABANKALAN CITY COORDINATES (OpenStreetMap, Oct 2026) ----
-- location 1 - City of Kabankalan Government Center, JY Perez Ave, Isidro Village, Talubangi
UPDATE locations SET latitude = 10.0039235, longitude = 122.8059206 WHERE location_id = 1;
-- location 2 - OSM "Public Terminal", Tan Lorenzo Street, Barangay 1 (Poblacion)
UPDATE locations SET latitude = 9.9927829, longitude = 122.8211682 WHERE location_id = 2;
-- location 3 - OSM "CityMall Kabankalan", Bacolod South Road, Talubangi
UPDATE locations SET latitude = 10.0016473, longitude = 122.8104748 WHERE location_id = 3;
-- location 4 - OSM "Ceres Bus Terminal", Justice Y. Perez Avenue, Barangay 2 (Poblacion)
UPDATE locations SET latitude = 9.9971055, longitude = 122.8117427 WHERE location_id = 4;
-- location 5 - OSM "New-St Francis Xavier Cathedral", JY Perez Avenue, Isidro Village, Talubangi
UPDATE locations SET latitude = 10.0083180, longitude = 122.8089265 WHERE location_id = 5;
-- location 6 - OSM "Kabankalan City Hospital", Tapi-Tabugon Road, Barangay Tabugon
UPDATE locations SET latitude = 9.7874050, longitude = 122.8032163 WHERE location_id = 6;
-- location 7 - OSM "Central Philippines State University", Kabankalan-Bais Road, Camingawan
UPDATE locations SET latitude = 9.8507831, longitude = 122.8898297 WHERE location_id = 7;
-- location 8 - OSM "Kabankalan Public Market", Tan Lorenzo Street, Barangay 1 (Poblacion)
UPDATE locations SET latitude = 9.9928114, longitude = 122.8199984 WHERE location_id = 8;
-- location 9 - OSM "Kabankalan City Domestic Airport", Hilamonan (inactive location)
UPDATE locations SET latitude = 10.0062151, longitude = 122.8514556 WHERE location_id = 9;
-- location 10 - OSM "Kabankalan Plaza" (city plaza park), Barangay 7 (Poblacion)
UPDATE locations SET latitude = 9.9887230, longitude = 122.8133402 WHERE location_id = 10;
-- location 11 - OSM "Kabankalan National High School", Cordero Street, Barangay 8 (Poblacion)
UPDATE locations SET latitude = 9.9877156, longitude = 122.8171197 WHERE location_id = 11;
-- location 12 - OSM "Kabankalan Old City Hall", Cordova Street, Barangay 7 (Poblacion)
UPDATE locations SET latitude = 9.9894904, longitude = 122.8138187 WHERE location_id = 12;
-- location 13 - OSM "Kabankalan City Fire Station", Repollo Street, Barangay 2 (Poblacion)
UPDATE locations SET latitude = 9.9950710, longitude = 122.8125888 WHERE location_id = 13;
-- location 14 - OSM "Kabankalan Catholic College", Guanzon Street, Barangay 1 (Poblacion)
UPDATE locations SET latitude = 9.9973349, longitude = 122.8148183 WHERE location_id = 14;
-- location 15 - OSM "Florentino Galang National High School", Kabankalan-Bais Road, Oringao
UPDATE locations SET latitude = 9.9019081, longitude = 122.8608608 WHERE location_id = 15;
-- location 16 - OSM "Daan Banua National High School", Barangay Daan Banua
UPDATE locations SET latitude = 10.0381477, longitude = 122.8184282 WHERE location_id = 16;
-- location 17 - OSM "Bahay Pamahalaan ng Barangay Talubangi", JY Perez Avenue, Talubangi
UPDATE locations SET latitude = 10.0079488, longitude = 122.8033997 WHERE location_id = 17;
-- location 18 - OSM "Tabugon Barangay Hall", Barangay Tabugon
UPDATE locations SET latitude = 9.7875682, longitude = 122.8016141 WHERE location_id = 18;

COMMIT;

-- 3. VERIFICATION ------------------------------------------------------
SELECT
  COUNT(*)                               AS total_locations,
  COUNT(latitude)                        AS with_coordinates,
  COUNT(*) - COUNT(latitude)             AS still_missing
FROM locations;

SELECT location_id, location_name, latitude, longitude, status
FROM locations
ORDER BY location_id;
