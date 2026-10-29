-- =====================================================================
-- SAKAYGUIDE DATA: All 32 Kabankalan City barangays as locations
-- Database : sakayguide_db
--
-- WHAT THIS DOES
--   Adds one active "barangay" location for every barangay of
--   Kabankalan City so every barangay can be selected in Find My Route
--   and pinned on the Kabankalan City map.
--
--   Coordinates are the OpenStreetMap barangay boundary centres
--   (state of the OSM database, October 2026). Each row names the OSM
--   relation so the position can be re-checked at openstreetmap.org.
--   No route stops, routes or fares are invented by this script:
--   searches only return journeys already supported by route data.
--
-- NOTES
--   * Safe to re-run: the unique key (barangay_id, location_name,
--     location_type) makes the INSERT update the existing row instead.
--   * The official barangay names keep the "(Poblacion)" suffix for
--     Barangays 1-9; the location labels use the shorter names shown
--     in the Find My Route list.
-- =====================================================================

USE sakayguide_db;

START TRANSACTION;

-- ONE LOCATION PER BARANGAY (32 rows) ---------------------------------

-- Bantayan - OSM relation 11521441 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Bantayan', 'barangay', 'Bantayan, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11521441, October 2026).', 'active', 9.7234789, 122.7890240
FROM barangays b
WHERE b.barangay_name = 'Bantayan'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Binicuil - OSM relation 11520264 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Binicuil', 'barangay', 'Binicuil, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11520264, October 2026).', 'active', 10.0216070, 122.8219938
FROM barangays b
WHERE b.barangay_name = 'Binicuil'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Camansi - OSM relation 11522030 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Camansi', 'barangay', 'Camansi, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11522030, October 2026).', 'active', 9.9477256, 122.7993598
FROM barangays b
WHERE b.barangay_name = 'Camansi'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Camingawan - OSM relation 11522026 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Camingawan', 'barangay', 'Camingawan, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11522026, October 2026).', 'active', 9.8662912, 122.8723651
FROM barangays b
WHERE b.barangay_name = 'Camingawan'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Camugao - OSM relation 11520268 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Camugao', 'barangay', 'Camugao, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11520268, October 2026).', 'active', 9.9865232, 122.8095880
FROM barangays b
WHERE b.barangay_name = 'Camugao'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Carol-an - OSM relation 11522024 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Carol-an', 'barangay', 'Carol-an, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11522024, October 2026).', 'active', 9.8996939, 122.9441718
FROM barangays b
WHERE b.barangay_name = 'Carol-an'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Daan Banua - OSM relation 11520263 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Daan Banua', 'barangay', 'Daan Banua, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11520263, October 2026).', 'active', 10.0360948, 122.8166723
FROM barangays b
WHERE b.barangay_name = 'Daan Banua'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Hilamonan - OSM relation 11520265 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Hilamonan', 'barangay', 'Hilamonan, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11520265, October 2026).', 'active', 10.0017116, 122.8338656
FROM barangays b
WHERE b.barangay_name = 'Hilamonan'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Inapoy - OSM relation 11522022 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Inapoy', 'barangay', 'Inapoy, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11522022, October 2026).', 'active', 9.8151934, 122.8635163
FROM barangays b
WHERE b.barangay_name = 'Inapoy'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Linao - OSM relation 11520267 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Linao', 'barangay', 'Linao, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11520267, October 2026).', 'active', 9.9878992, 122.7941246
FROM barangays b
WHERE b.barangay_name = 'Linao'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Locotan - OSM relation 11521440 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Locotan', 'barangay', 'Locotan, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11521440, October 2026).', 'active', 9.6986681, 122.7587476
FROM barangays b
WHERE b.barangay_name = 'Locotan'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Magballo - OSM relation 11521358 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Magballo', 'barangay', 'Magballo, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11521358, October 2026).', 'active', 9.7659521, 122.7362437
FROM barangays b
WHERE b.barangay_name = 'Magballo'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Oringao - OSM relation 11522027 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Oringao', 'barangay', 'Oringao, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11522027, October 2026).', 'active', 9.9042936, 122.8616906
FROM barangays b
WHERE b.barangay_name = 'Oringao'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Orong - OSM relation 11522029 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Orong', 'barangay', 'Orong, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11522029, October 2026).', 'active', 9.9372132, 122.8286633
FROM barangays b
WHERE b.barangay_name = 'Orong'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Pinaguinpinan - OSM relation 11521443 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Pinaguinpinan', 'barangay', 'Pinaguinpinan, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11521443, October 2026).', 'active', 9.7687478, 122.8291817
FROM barangays b
WHERE b.barangay_name = 'Pinaguinpinan'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Barangay 1 - OSM relation 11523836 (quarter)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Barangay 1', 'barangay', 'Barangay 1 (Poblacion), Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11523836, October 2026).', 'active', 9.9986187, 122.8151670
FROM barangays b
WHERE b.barangay_name = 'Barangay 1 (Poblacion)'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Barangay 2 - OSM relation 11523837 (quarter)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Barangay 2', 'barangay', 'Barangay 2 (Poblacion), Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11523837, October 2026).', 'active', 9.9955150, 122.8131258
FROM barangays b
WHERE b.barangay_name = 'Barangay 2 (Poblacion)'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Barangay 3 - OSM relation 11523838 (quarter)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Barangay 3', 'barangay', 'Barangay 3 (Poblacion), Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11523838, October 2026).', 'active', 9.9928708, 122.8138232
FROM barangays b
WHERE b.barangay_name = 'Barangay 3 (Poblacion)'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Barangay 4 - OSM relation 11523839 (quarter)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Barangay 4', 'barangay', 'Barangay 4 (Poblacion), Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11523839, October 2026).', 'active', 9.9896851, 122.8176346
FROM barangays b
WHERE b.barangay_name = 'Barangay 4 (Poblacion)'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Barangay 5 - OSM relation 11524944 (quarter)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Barangay 5', 'barangay', 'Barangay 5 (Poblacion), Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11524944, October 2026).', 'active', 9.9912740, 122.8121214
FROM barangays b
WHERE b.barangay_name = 'Barangay 5 (Poblacion)'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Barangay 6 - OSM relation 11524945 (quarter)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Barangay 6', 'barangay', 'Barangay 6 (Poblacion), Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11524945, October 2026).', 'active', 9.9906315, 122.8094084
FROM barangays b
WHERE b.barangay_name = 'Barangay 6 (Poblacion)'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Barangay 7 - OSM relation 11524946 (quarter)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Barangay 7', 'barangay', 'Barangay 7 (Poblacion), Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11524946, October 2026).', 'active', 9.9891780, 122.8125304
FROM barangays b
WHERE b.barangay_name = 'Barangay 7 (Poblacion)'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Barangay 8 - OSM relation 11524947 (quarter)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Barangay 8', 'barangay', 'Barangay 8 (Poblacion), Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11524947, October 2026).', 'active', 9.9873764, 122.8144643
FROM barangays b
WHERE b.barangay_name = 'Barangay 8 (Poblacion)'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Barangay 9 - OSM relation 11524948 (quarter)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Barangay 9', 'barangay', 'Barangay 9 (Poblacion), Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11524948, October 2026).', 'active', 9.9850994, 122.8193244
FROM barangays b
WHERE b.barangay_name = 'Barangay 9 (Poblacion)'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Salong - OSM relation 11520269 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Salong', 'barangay', 'Salong, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11520269, October 2026).', 'active', 9.9650148, 122.7785378
FROM barangays b
WHERE b.barangay_name = 'Salong'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Tabugon - OSM relation 11521442 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Tabugon', 'barangay', 'Tabugon, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11521442, October 2026).', 'active', 9.7867823, 122.7988263
FROM barangays b
WHERE b.barangay_name = 'Tabugon'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Tagoc - OSM relation 11521444 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Tagoc', 'barangay', 'Tagoc, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11521444, October 2026).', 'active', 9.7861644, 122.8265874
FROM barangays b
WHERE b.barangay_name = 'Tagoc'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Tagukon - OSM relation 11522025 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Tagukon', 'barangay', 'Tagukon, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11522025, October 2026).', 'active', 9.8248323, 122.9067291
FROM barangays b
WHERE b.barangay_name = 'Tagukon'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Talubangi - OSM relation 11520266 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Talubangi', 'barangay', 'Talubangi, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11520266, October 2026).', 'active', 10.0081267, 122.8031228
FROM barangays b
WHERE b.barangay_name = 'Talubangi'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Tampalon - OSM relation 11522023 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Tampalon', 'barangay', 'Tampalon, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11522023, October 2026).', 'active', 9.8727865, 122.7986540
FROM barangays b
WHERE b.barangay_name = 'Tampalon'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Tan-Awan - OSM relation 11522028 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Tan-Awan', 'barangay', 'Tan-Awan, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11522028, October 2026).', 'active', 9.9648228, 122.9036133
FROM barangays b
WHERE b.barangay_name = 'Tan-Awan'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

-- Tapi - OSM relation 11520384 (village)
INSERT INTO locations
  (barangay_id, location_name, location_type, address, description,
   status, latitude, longitude)
SELECT b.barangay_id, 'Tapi', 'barangay', 'Tapi, Kabankalan City',
       'Barangay location for the Find My Route search. Map position is the OpenStreetMap barangay boundary centre (OSM relation 11520384, October 2026).', 'active', 9.8289831, 122.7548083
FROM barangays b
WHERE b.barangay_name = 'Tapi'
ON DUPLICATE KEY UPDATE
  address = VALUES(address),
  description = VALUES(description),
  status = VALUES(status),
  latitude = VALUES(latitude),
  longitude = VALUES(longitude);

COMMIT;

-- VERIFICATION --------------------------------------------------------
SELECT COUNT(*) AS barangay_locations
FROM locations WHERE location_type = 'barangay';

SELECT b.barangay_id, b.barangay_name, l.location_name,
       l.latitude, l.longitude, l.status
FROM locations l
JOIN barangays b ON b.barangay_id = l.barangay_id
WHERE l.location_type = 'barangay'
ORDER BY b.barangay_id;
