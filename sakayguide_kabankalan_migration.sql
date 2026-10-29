-- =====================================================================
-- SakayGuide: Convert all sample data from Butuan City to
-- Kabankalan City, Negros Occidental.
-- No DROP, no DELETE. Only UPDATE + INSERT inside one transaction.
-- IDs are preserved so all foreign keys stay valid.
-- =====================================================================

USE sakayguide_db;
START TRANSACTION;

-- 1. MUNICIPALITY ----------------------------------------------------
UPDATE municipalities
SET municipality_name = 'Kabankalan City', province = 'Negros Occidental',
    description = 'Sample coverage area for the SakayGuide student project. Route and fare data are illustrative, not official.'
WHERE municipality_id = 1;

-- 2. BARANGAYS 1-10 (renamed) ---------------------------------------
UPDATE barangays SET barangay_name = 'Barangay 1 (Poblacion)' WHERE barangay_id = 1;
UPDATE barangays SET barangay_name = 'Barangay 2 (Poblacion)' WHERE barangay_id = 2;
UPDATE barangays SET barangay_name = 'Barangay 3 (Poblacion)' WHERE barangay_id = 3;
UPDATE barangays SET barangay_name = 'Barangay 4 (Poblacion)' WHERE barangay_id = 4;
UPDATE barangays SET barangay_name = 'Barangay 5 (Poblacion)' WHERE barangay_id = 5;
UPDATE barangays SET barangay_name = 'Barangay 6 (Poblacion)' WHERE barangay_id = 6;
UPDATE barangays SET barangay_name = 'Barangay 7 (Poblacion)' WHERE barangay_id = 7;
UPDATE barangays SET barangay_name = 'Barangay 8 (Poblacion)' WHERE barangay_id = 8;
UPDATE barangays SET barangay_name = 'Barangay 9 (Poblacion)' WHERE barangay_id = 9;
UPDATE barangays SET barangay_name = 'Bantayan' WHERE barangay_id = 10;

-- 2b. BARANGAYS 11-32 (added) ---------------------------------------
INSERT INTO barangays (barangay_id, municipality_id, barangay_name, description) VALUES
  (11, 1, 'Binicuil', 'Official barangay of Kabankalan City.'),
  (12, 1, 'Camansi', 'Official barangay of Kabankalan City.'),
  (13, 1, 'Camingawan', 'Official barangay of Kabankalan City; CPSU campus.'),
  (14, 1, 'Camugao', 'Official barangay of Kabankalan City.'),
  (15, 1, 'Carol-an', 'Official barangay of Kabankalan City.'),
  (16, 1, 'Daan Banua', 'Official barangay of Kabankalan City.'),
  (17, 1, 'Hilamonan', 'Official barangay of Kabankalan City; airport site.'),
  (18, 1, 'Inapoy', 'Official barangay of Kabankalan City.'),
  (19, 1, 'Linao', 'Official barangay of Kabankalan City.'),
  (20, 1, 'Locotan', 'Official barangay of Kabankalan City.'),
  (21, 1, 'Magballo', 'Official barangay of Kabankalan City.'),
  (22, 1, 'Oringao', 'Official barangay of Kabankalan City.'),
  (23, 1, 'Orong', 'Official barangay of Kabankalan City.'),
  (24, 1, 'Pinaguinpinan', 'Official barangay of Kabankalan City.'),
  (25, 1, 'Salong', 'Official barangay of Kabankalan City.'),
  (26, 1, 'Tabugon', 'Official barangay of Kabankalan City; city hospital.'),
  (27, 1, 'Tagoc', 'Official barangay of Kabankalan City.'),
  (28, 1, 'Tagukon', 'Official barangay of Kabankalan City.'),
  (29, 1, 'Talubangi', 'Official barangay of Kabankalan City; city government center.'),
  (30, 1, 'Tampalon', 'Official barangay of Kabankalan City.'),
  (31, 1, 'Tan-Awan', 'Official barangay of Kabankalan City.'),
  (32, 1, 'Tapi', 'Official barangay of Kabankalan City.');

-- 3. LOCATIONS 1-18 (all within Kabankalan City) ---------------------
UPDATE locations SET barangay_id = 29, location_name = 'Kabankalan City Government Center', location_type = 'government',
  address = 'JY Perez Avenue, Talubangi, Kabankalan City',
  description = 'Verified city government address from the official city contact page. Not a confirmed transport terminal.' WHERE location_id = 1;
UPDATE locations SET barangay_id = 1, location_name = 'Public Terminal', location_type = 'terminal',
  address = 'Tan Lorenzo Street, Barangay 1 (Poblacion), Kabankalan City',
  description = 'Verified public terminal on Tan Lorenzo Street. Used as transfer point in provisional test routes.' WHERE location_id = 2;
UPDATE locations SET barangay_id = 29, location_name = 'CityMall Kabankalan', location_type = 'establishment',
  address = 'JY Perez Highway cor. NOCECO Road, Talubangi, Kabankalan City',
  description = 'Verified shopping mall location; not automatically a public transport stop.' WHERE location_id = 3;
UPDATE locations SET barangay_id = 2, location_name = 'Ceres Bus Terminal', location_type = 'terminal',
  address = 'JY Perez Avenue, Barangay 2 (Poblacion), Kabankalan City',
  description = 'Verified Ceres bus terminal. Used as transfer point in provisional test routes.' WHERE location_id = 4;
UPDATE locations SET barangay_id = 29, location_name = 'New St. Francis Xavier Cathedral', location_type = 'landmark',
  address = 'Hacienda Clementina, Talubangi, Kabankalan City',
  description = 'New cathedral in Talubangi. Verify public visiting details before real use.' WHERE location_id = 5;
UPDATE locations SET barangay_id = 26, location_name = 'Kabankalan City Hospital', location_type = 'hospital',
  address = 'Tapi-Tabugon Road, Tabugon, Kabankalan City',
  description = 'City hospital on Tapi-Tabugon Road (OSM and official city health page).' WHERE location_id = 6;
UPDATE locations SET barangay_id = 13, location_name = 'Central Philippines State University', location_type = 'school',
  address = 'Kabankalan-Bais Road, Camingawan, Kabankalan City',
  description = 'Main campus of Central Philippines State University (OSM record).' WHERE location_id = 7;
UPDATE locations SET barangay_id = 1, location_name = 'Kabankalan Public Market', location_type = 'market',
  address = 'Tan Lorenzo Street, Barangay 1 (Poblacion), Kabankalan City',
  description = 'Public market on Tan Lorenzo Street, adjacent to the public terminal.' WHERE location_id = 8;
UPDATE locations SET barangay_id = 17, location_name = 'Kabankalan City Domestic Airport', location_type = 'terminal',
  address = 'Hilamonan, Kabankalan City',
  description = 'Airport site in Hilamonan; no commercial service. Marked inactive; no route serves it.',
  status = 'inactive' WHERE location_id = 9;
UPDATE locations SET barangay_id = 7, location_name = 'Kabankalan City Public Plaza', location_type = 'landmark',
  address = 'Barangay 7 (Poblacion), Kabankalan City',
  description = 'City plaza in the Poblacion (OSM park record). Landmark, not a terminal.' WHERE location_id = 10;
UPDATE locations SET barangay_id = 8, location_name = 'Kabankalan National High School', location_type = 'school',
  address = 'Barangay 8 (Poblacion), Kabankalan City',
  description = 'Public national high school in the Poblacion (OSM record).' WHERE location_id = 11;
UPDATE locations SET barangay_id = 7, location_name = 'Old Kabankalan City Hall', location_type = 'government',
  address = 'Barangay 7 (Poblacion), Kabankalan City',
  description = 'Historic old city hall (OSM record). Landmark only.' WHERE location_id = 12;
UPDATE locations SET barangay_id = 2, location_name = 'Kabankalan City Fire Station', location_type = 'government',
  address = 'Barangay 2 (Poblacion), Kabankalan City',
  description = 'City fire station (OSM record).' WHERE location_id = 13;
UPDATE locations SET barangay_id = 1, location_name = 'Kabankalan Catholic College', location_type = 'school',
  address = 'Barangay 1 (Poblacion), Kabankalan City',
  description = 'Catholic college in the Poblacion (OSM record).' WHERE location_id = 14;
UPDATE locations SET barangay_id = 22, location_name = 'Florentino Galang National High School', location_type = 'school',
  address = 'Oringao, Kabankalan City',
  description = 'Public high school in Barangay Oringao (OSM record).' WHERE location_id = 15;
UPDATE locations SET barangay_id = 16, location_name = 'Daan Banua National High School', location_type = 'school',
  address = 'Daan Banua, Kabankalan City',
  description = 'Public high school in Barangay Daan Banua (OSM record).' WHERE location_id = 16;
UPDATE locations SET barangay_id = 29, location_name = 'Talubangi Barangay Hall', location_type = 'government',
  address = 'Talubangi, Kabankalan City',
  description = 'Barangay hall in Talubangi (OSM record).' WHERE location_id = 17;
UPDATE locations SET barangay_id = 26, location_name = 'Tabugon Barangay Hall', location_type = 'government',
  address = 'Tabugon, Kabankalan City',
  description = 'Barangay hall in Tabugon (OSM record).' WHERE location_id = 18;

-- 4. TRANSPORTATION TYPES (names kept, descriptions localized) -------
UPDATE transportation_types SET description = 'Sample public jeepney service within Kabankalan City; actual franchise coverage not independently verified.' WHERE transport_type_id = 1;
UPDATE transportation_types SET description = 'Provincial bus service passing through the Ceres Bus Terminal in Barangay 2, Kabankalan City.' WHERE transport_type_id = 2;
UPDATE transportation_types SET description = 'Sample short-distance tricycle service around Kabankalan City; local operation not independently verified.' WHERE transport_type_id = 3;
-- 5. FARE TYPES (localized, legally referenced discounts) ------------
UPDATE fare_types SET description = 'Standard fare for regular passengers.' WHERE fare_type_id = 1;
UPDATE fare_types SET description = 'Sample 20% student fare discount under RA 11314; confirm per transport mode.' WHERE fare_type_id = 2;
UPDATE fare_types SET description = 'Sample 20% senior citizen fare discount under RA 9994; confirm per transport mode.' WHERE fare_type_id = 3;
UPDATE fare_types SET description = 'Sample 20% PWD fare discount under RA 10754/RA 7277; confirm per transport mode.' WHERE fare_type_id = 4;

-- 6. USERS: 1 admin + 6 commuters (hashes from PHP password_hash) ----
UPDATE users SET email = 'admin@kabankalan.sakayguide.test',
  password = '$2y$10$13eDc0ZZYurvWIlcZzt6oOFbqaCcBmJ6/5UtIH2Tx.eDrCY.LPsye'
WHERE user_id = 1;
UPDATE users SET email = 'juan.kabankalan@sakayguide.test',
  password = '$2y$10$kj8Psr0Hq61cdqEHspl.e.gULk5QfLTllu.lrzJAP2tJWS.M/Ut8S'
WHERE user_id = 2;
UPDATE users SET email = 'ana.kabankalan@sakayguide.test',
  password = '$2y$10$UibYL8uKa5iJePx/Pq6Lj.mFUdGe/T1DcPqjeAT2XENsmhmafffW6'
WHERE user_id = 3;

INSERT INTO users (user_id, full_name, email, password, role, status, created_at, updated_at) VALUES
  (4, 'Mark Villanueva', 'mark.kabankalan@sakayguide.test',
   '$2y$10$5IzuhydeM2pdl7.Zpc8.ZOjmUlpIWotV.KuzBIK8EEkwUJfMqDJim',
   'commuter', 'active', '2026-10-01 09:00:00', '2026-10-01 09:00:00'),
  (5, 'Liza Montelibano', 'liza.kabankalan@sakayguide.test',
   '$2y$10$nYYeWLm.LKJmOP67eGmGwuaDtZC1Z2fYe3XUpDvAk.0qeA6xPUi6y',
   'commuter', 'active', '2026-10-02 09:00:00', '2026-10-02 09:00:00'),
  (6, 'Paolo Garcia', 'paolo.kabankalan@sakayguide.test',
   '$2y$10$ZdY3v6C/HDXcRB2vnudwde.ztFBhtjQM9rRiJolYTSDUWX7irkEkW',
   'commuter', 'active', '2026-10-03 09:00:00', '2026-10-03 09:00:00'),
  (7, 'Grace Tan', 'grace.kabankalan@sakayguide.test',
   '$2y$10$hg5LylPyQnyHsVcJLwl/8u8rDplkb8SXwoC73BnNt2rOwYHoXYFO2',
   'commuter', 'active', '2026-10-04 09:00:00', '2026-10-04 09:00:00');

-- 7. ROUTES 1-6 (new Kabankalan sample routes, all provisional) -----
UPDATE routes SET route_name = 'Public Terminal - City Government Center Jeepney', route_code = 'KAB-JP-01',
  origin_id = 2, destination_id = 1, transport_type_id = 1, estimated_travel_time = 20,
  route_description = 'PROVISIONAL TEST ROUTE: Public Terminal to City Government Center via the public market, CityMall and the cathedral. Not an official route.' WHERE route_id = 1;
UPDATE routes SET route_name = 'CPSU - Public Terminal Jeepney', route_code = 'KAB-JP-02',
  origin_id = 7, destination_id = 2, transport_type_id = 1, estimated_travel_time = 35,
  route_description = 'PROVISIONAL TEST ROUTE: CPSU in Camingawan to the Public Terminal via Kabankalan NHS and Oringao. Not an official route.' WHERE route_id = 2;
UPDATE routes SET route_name = 'CPSU - Kabankalan City Hospital Bus', route_code = 'KAB-BUS-03',
  origin_id = 7, destination_id = 6, transport_type_id = 2, estimated_travel_time = 40,
  route_description = 'PROVISIONAL TEST ROUTE: CPSU to Kabankalan City Hospital via the Public Terminal and Ceres Bus Terminal. Not an official route.' WHERE route_id = 3;
UPDATE routes SET route_name = 'Public Plaza - CityMall Kabankalan Jeepney', route_code = 'KAB-JP-04',
  origin_id = 10, destination_id = 3, transport_type_id = 1, estimated_travel_time = 25,
  route_description = 'PROVISIONAL TEST ROUTE: Public Plaza to CityMall via the old city hall and Public Terminal. Not an official route.' WHERE route_id = 4;
UPDATE routes SET route_name = 'Public Terminal - Tabugon Barangay Hall Jeepney', route_code = 'KAB-JP-05',
  origin_id = 2, destination_id = 18, transport_type_id = 1, estimated_travel_time = 40,
  route_description = 'PROVISIONAL TEST ROUTE: Public Terminal to Tabugon via Ceres Bus Terminal and Daan Banua. Not an official route.' WHERE route_id = 5;
UPDATE routes SET route_name = 'Public Terminal - Kabankalan Catholic College Tricycle', route_code = 'KAB-TRI-06',
  origin_id = 2, destination_id = 14, transport_type_id = 3, estimated_travel_time = 15,
  route_description = 'PROVISIONAL TEST ROUTE: Public Terminal to the Catholic College via the fire station. Not an official route.' WHERE route_id = 6;

-- 8. ROUTE STOPS (24 rows, IDs unchanged; order avoids unique clashes)
-- Route 1 stops already match the new design: no change needed.
UPDATE route_stops SET location_id = 7 WHERE stop_id = 6;
UPDATE route_stops SET location_id = 15, estimated_stop_time = 15 WHERE stop_id = 7;
UPDATE route_stops SET location_id = 11, estimated_stop_time = 30 WHERE stop_id = 8;

UPDATE route_stops SET location_id = 7 WHERE stop_id = 10;
UPDATE route_stops SET location_id = 2, is_transfer_point = 1, estimated_stop_time = 5 WHERE stop_id = 11;
UPDATE route_stops SET estimated_stop_time = 25 WHERE stop_id = 12;
UPDATE route_stops SET location_id = 6, estimated_stop_time = 40 WHERE stop_id = 13;

UPDATE route_stops SET location_id = 2, is_transfer_point = 1, estimated_stop_time = 8 WHERE stop_id = 16;  -- before 17
UPDATE route_stops SET location_id = 3, estimated_stop_time = 20 WHERE stop_id = 17;
UPDATE route_stops SET location_id = 10, is_transfer_point = 0 WHERE stop_id = 14;
UPDATE route_stops SET location_id = 12, estimated_stop_time = 4 WHERE stop_id = 15;

UPDATE route_stops SET estimated_stop_time = 5 WHERE stop_id = 19;
UPDATE route_stops SET location_id = 16 WHERE stop_id = 20;
UPDATE route_stops SET location_id = 18 WHERE stop_id = 21;

UPDATE route_stops SET location_id = 2, is_transfer_point = 1 WHERE stop_id = 22;  -- before 24
UPDATE route_stops SET location_id = 13, estimated_stop_time = 5 WHERE stop_id = 23;
UPDATE route_stops SET location_id = 14, is_transfer_point = 0 WHERE stop_id = 24;

-- 9. ROUTE FARES (routes 3 and 5 follow their new mode; history kept)
UPDATE route_fares SET minimum_fare = 25.00, fare_per_km = 2.00, total_estimated_fare = 30.00 WHERE fare_id = 10;
UPDATE route_fares SET minimum_fare = 20.00, fare_per_km = 1.60, total_estimated_fare = 24.00 WHERE fare_id IN (11, 12, 13);
UPDATE route_fares SET minimum_fare = 20.00, fare_per_km = 1.70, total_estimated_fare = 25.00 WHERE fare_id = 18;
UPDATE route_fares SET minimum_fare = 16.00, fare_per_km = 1.36, total_estimated_fare = 20.00 WHERE fare_id IN (19, 20, 21);

-- 10. ROUTE TRANSFERS (after route_stops; triggers re-validate) ------
UPDATE route_transfers SET transfer_instructions = 'PROVISIONAL: Alight at the Public Terminal. Board the jeepney heading to the City Government Center (KAB-JP-01).'
WHERE transfer_id = 1;
UPDATE route_transfers SET transfer_location_id = 2,
  transfer_instructions = 'PROVISIONAL: Alight at the Public Terminal. Board the jeepney heading to the City Government Center (KAB-JP-01).'
WHERE transfer_id = 2;
UPDATE route_transfers SET transfer_location_id = 2,
  transfer_instructions = 'PROVISIONAL: Alight at the Public Terminal. Board the jeepney heading to CityMall Kabankalan (KAB-JP-04).'
WHERE transfer_id = 3;
UPDATE route_transfers SET transfer_instructions = 'PROVISIONAL: Alight at Ceres Bus Terminal. Board the jeepney heading to Tabugon (KAB-JP-05).'
WHERE transfer_id = 4;

-- 11. SAVED ROUTES (3 updated + 3 added = 6) ------------------------
UPDATE saved_routes SET nickname = 'Daily commute to City Government Center' WHERE saved_route_id = 1;
UPDATE saved_routes SET origin_id = 10, destination_id = 3, nickname = 'Plaza to CityMall' WHERE saved_route_id = 2;
UPDATE saved_routes SET origin_id = 2, destination_id = 7, nickname = 'School commute to CPSU' WHERE saved_route_id = 3;
INSERT INTO saved_routes (saved_route_id, user_id, origin_id, destination_id, nickname, saved_at) VALUES
  (4, 4, 2, 6, 'Hospital trip', '2026-10-24 09:00:00'),
  (5, 5, 2, 14, 'Catholic College route', '2026-10-25 13:30:00'),
  (6, 6, 2, 16, 'Daan Banua commute', '2026-10-25 18:15:00');

-- 12. SEARCH HISTORY (6 updated + 5 added = 11) ---------------------
UPDATE search_history SET origin_id = 4, destination_id = 6 WHERE search_id = 1;
UPDATE search_history SET origin_id = 2, destination_id = 7 WHERE search_id = 3;
UPDATE search_history SET origin_id = 7, destination_id = 2 WHERE search_id = 4;
UPDATE search_history SET origin_id = 8, destination_id = 3 WHERE search_id = 5;
UPDATE search_history SET origin_id = 10, destination_id = 1 WHERE search_id = 6;
INSERT INTO search_history (search_id, user_id, origin_id, destination_id, search_date) VALUES
  (7, 4, 2, 6, '2026-10-26 07:45:00'),
  (8, 5, 2, 14, '2026-10-26 08:30:00'),
  (9, 6, 4, 16, '2026-10-26 09:10:00'),
  (10, 7, 2, 3, '2026-10-26 10:20:00'),
  (11, NULL, 10, 1, '2026-10-26 11:05:00');

-- 13. ROUTE LANDMARKS (22 rows, IDs unchanged) ----------------------
UPDATE route_landmarks SET landmark_description = 'Kabankalan Public Market, a recognizable stop near the route origin.' WHERE route_landmark_id = 1;
UPDATE route_landmarks SET landmark_description = 'CityMall Kabankalan along JY Perez Highway.' WHERE route_landmark_id = 2;
UPDATE route_landmarks SET landmark_description = 'New St. Francis Xavier Cathedral near Talubangi.' WHERE route_landmark_id = 3;
UPDATE route_landmarks SET landmark_description = 'Kabankalan City Government Center, the route destination.' WHERE route_landmark_id = 4;

UPDATE route_landmarks SET location_id = 7, landmark_description = 'Central Philippines State University, the route origin.', distance_from_origin = 0.00 WHERE route_landmark_id = 5;
UPDATE route_landmarks SET location_id = 11, landmark_description = 'Kabankalan National High School along the route.', distance_from_origin = 6.00 WHERE route_landmark_id = 6;
UPDATE route_landmarks SET landmark_description = 'Public Terminal, the route destination and transfer point.', distance_from_origin = 10.00 WHERE route_landmark_id = 7;

UPDATE route_landmarks SET location_id = 7, landmark_description = 'Central Philippines State University, the route origin.', distance_from_origin = 0.00 WHERE route_landmark_id = 8;
UPDATE route_landmarks SET location_id = 2, landmark_description = 'Public Terminal, a major transfer point along the route.', distance_from_origin = 4.50 WHERE route_landmark_id = 9;
UPDATE route_landmarks SET landmark_description = 'Ceres Bus Terminal along the route.', distance_from_origin = 8.00 WHERE route_landmark_id = 10;
UPDATE route_landmarks SET location_id = 6, landmark_description = 'Kabankalan City Hospital, the route destination.', distance_from_origin = 14.00 WHERE route_landmark_id = 11;

UPDATE route_landmarks SET location_id = 2, landmark_description = 'Public Terminal, a transfer point along the route.', distance_from_origin = 1.50 WHERE route_landmark_id = 14; -- before 15
UPDATE route_landmarks SET location_id = 3, landmark_description = 'CityMall Kabankalan, the route destination.', distance_from_origin = 3.20 WHERE route_landmark_id = 15;
UPDATE route_landmarks SET location_id = 10, landmark_description = 'Kabankalan City Public Plaza, the route origin.', distance_from_origin = 0.00 WHERE route_landmark_id = 12;
UPDATE route_landmarks SET location_id = 12, landmark_description = 'Old Kabankalan City Hall along the Poblacion segment.', distance_from_origin = 0.60 WHERE route_landmark_id = 13;

UPDATE route_landmarks SET landmark_description = 'Public Terminal, the route origin.', distance_from_origin = 0.00 WHERE route_landmark_id = 16;
UPDATE route_landmarks SET landmark_description = 'Ceres Bus Terminal along the route.', distance_from_origin = 1.20 WHERE route_landmark_id = 17;
UPDATE route_landmarks SET location_id = 16, landmark_description = 'Daan Banua National High School along the route.', distance_from_origin = 6.00 WHERE route_landmark_id = 18;
UPDATE route_landmarks SET location_id = 18, landmark_description = 'Tabugon Barangay Hall, the route destination.', distance_from_origin = 9.50 WHERE route_landmark_id = 19;

UPDATE route_landmarks SET location_id = 2, landmark_description = 'Public Terminal, the route origin.', distance_from_origin = 0.00 WHERE route_landmark_id = 20; -- before 22
UPDATE route_landmarks SET location_id = 14, landmark_description = 'Kabankalan Catholic College, the route destination.', distance_from_origin = 1.50 WHERE route_landmark_id = 22;
UPDATE route_landmarks SET location_id = 13, landmark_description = 'Kabankalan City Fire Station along the route.', distance_from_origin = 0.70 WHERE route_landmark_id = 21;

-- 14. ADMIN LOGS (4 updated + 2 added = 6) --------------------------
UPDATE admin_activity_logs SET action_description = 'Created sample jeepney route KAB-JP-01 for Kabankalan City.' WHERE log_id = 1;
UPDATE admin_activity_logs SET action_description = 'Updated the regular fare for KAB-JP-01 effective 2026-01-01; previous record retained as expired.' WHERE log_id = 2;
UPDATE admin_activity_logs SET action_description = 'Added transfer connection from KAB-JP-02 to KAB-JP-01 at the Public Terminal.' WHERE log_id = 3;
INSERT INTO admin_activity_logs (log_id, admin_id, action_type, table_affected, record_id, action_description, created_at) VALUES
  (5, 1, 'CREATE', 'locations', 1, 'Added the Kabankalan City Government Center location record.', '2026-10-01 09:30:00'),
  (6, 1, 'DEACTIVATE', 'locations', 9, 'Marked the Kabankalan City Domestic Airport inactive because it is not yet operational.', '2026-10-06 14:00:00');

-- 15. REMOVE MULTICAB TRANSPORT TYPE (route 5 reassigned to jeepney)
DELETE FROM transportation_types WHERE transport_type_id = 4;

-- 16. ROUTES 7-8: Bantayan - Barangay 1 (Poblacion) connects upland Bantayan
--     to Barangay 1 and the central Public Terminal hub.
INSERT INTO routes (route_id, route_name, route_code, origin_id, destination_id, transport_type_id, estimated_travel_time, route_description, status, created_at, updated_at)
VALUES
  (7, 'Bantayan - Barangay 1 (Poblacion) Jeepney', 'KAB-JP-07', 19, 34, 1, 40,
   'PROVISIONAL TEST ROUTE: Bantayan to Barangay 1 (Poblacion) via the Public Terminal and Bacolod South Road.',
   'active', '2026-10-29 08:00:00', '2026-10-29 08:00:00'),
  (8, 'Barangay 1 (Poblacion) - Bantayan Jeepney', 'KAB-JP-08', 34, 19, 1, 40,
   'PROVISIONAL TEST ROUTE: Barangay 1 (Poblacion) to Bantayan via the Public Terminal and Bacolod South Road.',
   'active', '2026-10-29 08:00:00', '2026-10-29 08:00:00')
ON DUPLICATE KEY UPDATE
  route_name = VALUES(route_name),
  route_code = VALUES(route_code),
  origin_id = VALUES(origin_id),
  destination_id = VALUES(destination_id),
  transport_type_id = VALUES(transport_type_id),
  estimated_travel_time = VALUES(estimated_travel_time),
  route_description = VALUES(route_description),
  status = VALUES(status);

INSERT INTO route_stops (route_id, location_id, stop_order, is_transfer_point, estimated_stop_time) VALUES
  (7, 19, 1, 0, 0),
  (7, 2,  2, 1, 35),
  (7, 34, 3, 0, 40),
  (8, 34, 1, 0, 0),
  (8, 2,  2, 1, 5),
  (8, 19, 3, 0, 40)
ON DUPLICATE KEY UPDATE
  stop_order = VALUES(stop_order),
  is_transfer_point = VALUES(is_transfer_point),
  estimated_stop_time = VALUES(estimated_stop_time);

INSERT INTO route_fares (route_id, fare_type_id, minimum_fare, fare_per_km, total_estimated_fare, effective_date, status) VALUES
  (7, 1, 35.00, 0.00, 35.00, '2026-01-01', 'active'),
  (7, 2, 28.00, 0.00, 28.00, '2026-01-01', 'active'),
  (7, 3, 28.00, 0.00, 28.00, '2026-01-01', 'active'),
  (7, 4, 28.00, 0.00, 28.00, '2026-01-01', 'active'),
  (8, 1, 35.00, 0.00, 35.00, '2026-01-01', 'active'),
  (8, 2, 28.00, 0.00, 28.00, '2026-01-01', 'active'),
  (8, 3, 28.00, 0.00, 28.00, '2026-01-01', 'active'),
  (8, 4, 28.00, 0.00, 28.00, '2026-01-01', 'active')
ON DUPLICATE KEY UPDATE
  minimum_fare = VALUES(minimum_fare),
  total_estimated_fare = VALUES(total_estimated_fare),
  status = VALUES(status);

INSERT INTO route_transfers (from_route_id, to_route_id, transfer_location_id, transfer_instructions, estimated_transfer_time, additional_estimated_fare) VALUES
  (7, 1, 2, 'PROVISIONAL: Alight at the Public Terminal. Board the jeepney heading to the City Government Center (KAB-JP-01).', 5, 0.00),
  (7, 5, 2, 'PROVISIONAL: Alight at the Public Terminal. Board the jeepney heading to Tabugon (KAB-JP-05).', 5, 0.00),
  (7, 6, 2, 'PROVISIONAL: Alight at the Public Terminal. Board the tricycle heading to Kabankalan Catholic College (KAB-TRI-06).', 5, 0.00),
  (2, 8, 2, 'PROVISIONAL: Alight at the Public Terminal. Board the jeepney heading to Bantayan (KAB-JP-08).', 5, 0.00),
  (3, 8, 2, 'PROVISIONAL: Alight at the Public Terminal. Board the jeepney heading to Bantayan (KAB-JP-08).', 5, 0.00)
ON DUPLICATE KEY UPDATE
  transfer_instructions = VALUES(transfer_instructions),
  estimated_transfer_time = VALUES(estimated_transfer_time);

COMMIT;

-- =====================================================================
-- VERIFICATION
-- =====================================================================
SELECT
  (SELECT COUNT(*) FROM users) AS users,
  (SELECT COUNT(*) FROM municipalities) AS municipalities,
  (SELECT COUNT(*) FROM barangays) AS barangays,
  (SELECT COUNT(*) FROM locations) AS locations,
  (SELECT COUNT(*) FROM transportation_types) AS transportation_types,
  (SELECT COUNT(*) FROM routes) AS routes,
  (SELECT COUNT(*) FROM route_stops) AS route_stops,
  (SELECT COUNT(*) FROM fare_types) AS fare_types,
  (SELECT COUNT(*) FROM route_fares) AS route_fares,
  (SELECT COUNT(*) FROM route_transfers) AS route_transfers,
  (SELECT COUNT(*) FROM saved_routes) AS saved_routes,
  (SELECT COUNT(*) FROM search_history) AS search_history,
  (SELECT COUNT(*) FROM route_landmarks) AS route_landmarks,
  (SELECT COUNT(*) FROM admin_activity_logs) AS admin_activity_logs;
SELECT location_id, location_name, location_type, status FROM locations ORDER BY location_id;
