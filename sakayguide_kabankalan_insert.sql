-- =====================================================================
-- SAKAYGUIDE: KABANKALAN CITY SAMPLE DATA
-- Database: sakayguide_db
-- Service area: Kabankalan City, Negros Occidental, Philippines
-- Purpose: Complete insert script for the 14-table SakayGuide schema.
-- NOTE: All barangays, locations, routes, fares, landmarks, and transfers
--       below are within Kabankalan City only. All transportation details
--       are provisional unless clearly marked verified.
-- Passwords must be generated with PHP password_hash(); the hashes below are
-- generated for local test accounts only and must be replaced before real use.
-- =====================================================================

USE sakayguide_db;
SET FOREIGN_KEY_CHECKS = 1;

START TRANSACTION;

-- =====================================================================
-- TABLE 1: users
-- =====================================================================
INSERT INTO users (user_id, full_name, email, password, role, status, created_at, updated_at)
VALUES
  (1001, 'Abegail Gilgon', 'abegail.gilgon@sakayguide.test',
   '$2y$10$13eDc0ZZYurvWIlcZzt6oOFbqaCcBmJ6/5UtIH2Tx.eDrCY.LPsye',
   'admin', 'active', '2026-10-01 08:00:00', '2026-10-01 08:00:00'),
  (1002, 'Juan Dela Cruz', 'juan.kabankalan@sakayguide.test',
   '$2y$10$kj8Psr0Hq61cdqEHspl.e.gULk5QfLTllu.lrzJAP2tJWS.M/Ut8S',
   'commuter', 'active', '2026-10-01 09:00:00', '2026-10-01 09:00:00'),
  (1003, 'Ana Reyes', 'ana.kabankalan@sakayguide.test',
   '$2y$10$UibYL8uKa5iJePx/Pq6Lj.mFUdGe/T1DcPqjeAT2XENsmhmafffW6',
   'commuter', 'active', '2026-10-02 09:00:00', '2026-10-02 09:00:00'),
  (1004, 'Mark Villanueva', 'mark.kabankalan@sakayguide.test',
   '$2y$10$5IzuhydeM2pdl7.Zpc8.ZOjmUlpIWotV.KuzBIK8EEkwUJfMqDJim',
   'commuter', 'active', '2026-10-03 09:00:00', '2026-10-03 09:00:00'),
  (1005, 'Liza Montelibano', 'liza.kabankalan@sakayguide.test',
   '$2y$10$nYYeWLm.LKJmOP67eGmGwuaDtZC1Z2fYe3XUpDvAk.0qeA6xPUi6y',
   'commuter', 'active', '2026-10-04 09:00:00', '2026-10-04 09:00:00'),
  (1006, 'Paolo Garcia', 'paolo.kabankalan@sakayguide.test',
   '$2y$10$ZdY3v6C/HDXcRB2vnudwde.ztFBhtjQM9rRiJolYTSDUWX7irkEkW',
   'commuter', 'active', '2026-10-05 09:00:00', '2026-10-05 09:00:00'),
  (1007, 'Grace Tan', 'grace.kabankalan@sakayguide.test',
   '$2y$10$hg5LylPyQnyHsVcJLwl/8u8rDplkb8SXwoC73BnNt2rOwYHoXYFO2',
   'commuter', 'active', '2026-10-06 09:00:00', '2026-10-06 09:00:00');

-- =====================================================================
-- TABLE 2: municipalities
-- =====================================================================
INSERT INTO municipalities (municipality_id, municipality_name, province, description, status)
VALUES
  (1001, 'Kabankalan City', 'Negros Occidental',
   'Initial SakayGuide coverage area. All routes, locations, and fares are provisional unless marked otherwise.',
   'active');

-- =====================================================================
-- TABLE 3: barangays
-- All barangays belong to Kabankalan City only.
-- =====================================================================
INSERT INTO barangays (barangay_id, municipality_id, barangay_name, description) VALUES
  (1101, 1001, 'Barangay 1 (Poblacion)', 'Official barangay of Kabankalan City.'),
  (1102, 1001, 'Barangay 2 (Poblacion)', 'Official barangay of Kabankalan City.'),
  (1103, 1001, 'Barangay 3 (Poblacion)', 'Official barangay of Kabankalan City.'),
  (1104, 1001, 'Barangay 4 (Poblacion)', 'Official barangay of Kabankalan City.'),
  (1105, 1001, 'Barangay 5 (Poblacion)', 'Official barangay of Kabankalan City.'),
  (1106, 1001, 'Barangay 6 (Poblacion)', 'Official barangay of Kabankalan City.'),
  (1107, 1001, 'Barangay 7 (Poblacion)', 'Official barangay of Kabankalan City.'),
  (1108, 1001, 'Barangay 8 (Poblacion)', 'Official barangay of Kabankalan City.'),
  (1109, 1001, 'Barangay 9 (Poblacion)', 'Official barangay of Kabankalan City.'),
  (1110, 1001, 'Bantayan', 'Official barangay of Kabankalan City.'),
  (1111, 1001, 'Binicuil', 'Official barangay of Kabankalan City.'),
  (1112, 1001, 'Camansi', 'Official barangay of Kabankalan City.'),
  (1113, 1001, 'Camingawan', 'Official barangay of Kabankalan City.'),
  (1114, 1001, 'Camugao', 'Official barangay of Kabankalan City.'),
  (1115, 1001, 'Carol-an', 'Official barangay of Kabankalan City.'),
  (1116, 1001, 'Daan Banua', 'Official barangay of Kabankalan City.'),
  (1117, 1001, 'Hilamonan', 'Official barangay of Kabankalan City.'),
  (1118, 1001, 'Inapoy', 'Official barangay of Kabankalan City.'),
  (1119, 1001, 'Linao', 'Official barangay of Kabankalan City.'),
  (1120, 1001, 'Locotan', 'Official barangay of Kabankalan City.'),
  (1121, 1001, 'Magballo', 'Official barangay of Kabankalan City.'),
  (1122, 1001, 'Oringao', 'Official barangay of Kabankalan City.'),
  (1123, 1001, 'Orong', 'Official barangay of Kabankalan City.'),
  (1124, 1001, 'Pinaguinpinan', 'Official barangay of Kabankalan City.'),
  (1125, 1001, 'Salong', 'Official barangay of Kabankalan City.'),
  (1126, 1001, 'Tabugon', 'Official barangay of Kabankalan City.'),
  (1127, 1001, 'Tagoc', 'Official barangay of Kabankalan City.'),
  (1128, 1001, 'Tagukon', 'Official barangay of Kabankalan City.'),
  (1129, 1001, 'Talubangi', 'Official barangay of Kabankalan City.'),
  (1130, 1001, 'Tampalon', 'Official barangay of Kabankalan City.'),
  (1131, 1001, 'Tan-Awan', 'Official barangay of Kabankalan City.'),
  (1132, 1001, 'Tapi', 'Official barangay of Kabankalan City.');

-- =====================================================================
-- TABLE 4: locations
-- All locations below are within Kabankalan City only.
-- =====================================================================
INSERT INTO locations (location_id, barangay_id, location_name, location_type, address, description, status) VALUES
  (2001, 1129, 'Kabankalan City Government Center', 'government',
   'Justice Y. Perez Avenue, Isidro Village, Barangay Talubangi, Kabankalan City',
   'Verified city government address from official contact page. Not confirmed as a public transport terminal.',
   'active'),
  (2002, 1129, 'New St. Francis Xavier Cathedral', 'landmark',
   'Hacienda Clementina, Barangay Talubangi, Kabankalan City',
   'New cathedral reported in Hacienda Clementina, Barangay Talubangi. Verify public visiting details.',
   'active'),
  (2003, 1129, 'CityMall Kabankalan', 'establishment',
   'Justice Y. Perez Highway corner NOCECO Road, Barangay Talubangi, Kabankalan City',
   'Verified shopping mall location; not automatically a public transport stop.',
   'active'),
  (2004, 1107, 'Kabankalan City Public Plaza', 'landmark',
   'Poblacion, Barangay 7, Kabankalan City',
   'City plaza in Barangay 7; OSM park record. Public landmark, not a confirmed terminal.',
   'active'),
  (2005, 1101, 'Kabankalan Public Market', 'market',
   'Tan Lorenzo Street, Barangay 1 (Poblacion), Kabankalan City',
   'Public market on Tan Lorenzo Street; OSM marketplace record. Adjacent to public terminal.',
   'active'),
  (2006, 1101, 'Public Terminal', 'terminal',
   'Tan Lorenzo Street, Barangay 1 (Poblacion), Kabankalan City',
   'Verified public terminal on Tan Lorenzo Street; OSM bus_station record. Used as transfer point in provisional test routes.',
   'active'),
  (2007, 1102, 'Ceres Bus Terminal', 'terminal',
   'Justice Y. Perez Avenue, Barangay 2 (Poblacion), Kabankalan City',
   'Verified Ceres bus terminal on Justice Y. Perez Avenue; OSM bus_station record. Used as transfer point in provisional test routes.',
   'active'),
  (2008, 1108, 'Kabankalan National High School', 'school',
   'Cordero Street, Barangay 8 (Poblacion), Kabankalan City',
   'Public national high school in Barangay 8; OSM school record.',
   'active'),
  (2009, 1126, 'Kabankalan City Hospital', 'hospital',
   'Tapi-Tabugon Road, Barangay Tabugon, Kabankalan City',
   'City hospital on Tapi-Tabugon Road; OSM hospital record and official city health page.',
   'active'),
  (2010, 1113, 'Central Philippines State University', 'school',
   'Kabankalan-Bais Road, Barangay Camingawan, Kabankalan City',
   'Main campus of Central Philippines State University; OSM university record.',
   'active'),
  (2011, 1117, 'Kabankalan City Domestic Airport', 'terminal',
   'Kabankalan Airport Road, Barangay Hilamonan, Kabankalan City',
   'Airport under construction; no commercial service. Location marked inactive and not served by any active route.',
   'inactive'),
  (2012, 1107, 'Old Kabankalan City Hall', 'government',
   'Cordova Street, Barangay 7 (Poblacion), Kabankalan City',
   'Historic old city hall on Cordova Street; OSM record. Landmark only.',
   'active'),
  (2013, 1102, 'Kabankalan City Fire Station', 'government',
   'Repollo Street, Barangay 2 (Poblacion), Kabankalan City',
   'City fire station on Repollo Street; OSM record.',
   'active'),
  (2014, 1101, 'Kabankalan Catholic College', 'school',
   'Guanzon Street, Barangay 1 (Poblacion), Kabankalan City',
   'Catholic college on Guanzon Street; OSM record.',
   'active'),
  (2015, 1122, 'Florentino Galang National High School', 'school',
   'Kabankalan-Bais Road, Barangay Oringao, Kabankalan City',
   'Public high school on Kabankalan-Bais Road; OSM record.',
   'active'),
  (2016, 1113, 'Camingawan National High School', 'school',
   'Barangay Camingawan, Kabankalan City',
   'Public high school in Camingawan; OSM record.',
   'active'),
  (2017, 1111, 'Binicuil National High School', 'school',
   'Dalawidaw, Barangay Binicuil, Kabankalan City',
   'Public high school in Binicuil; OSM record.',
   'active'),
  (2018, 1116, 'Daan Banua National High School', 'school',
   'Barangay Daan Banua, Kabankalan City',
   'Public high school in Daan Banua; OSM record.',
   'active'),
  (2019, 1116, 'Daan Banua Barangay Hall', 'government',
   'Proper, Barangay Daan Banua, Kabankalan City',
   'Barangay hall in Daan Banua; OSM record.',
   'active'),
  (2020, 1126, 'Tabugon National High School', 'school',
   'Bugo, Barangay Tabugon, Kabankalan City',
   'Public high school in Tabugon; OSM record.',
   'active'),
  (2021, 1126, 'Tabugon Barangay Hall', 'government',
   'Barangay Tabugon, Kabankalan City',
   'Barangay hall in Tabugon; OSM record.',
   'active'),
  (2022, 1112, 'Camansi National High School', 'school',
   'Kabankalan-Tampalon Road, Barangay Camansi, Kabankalan City',
   'Public high school in Camansi; OSM record.',
   'active'),
  (2023, 1130, 'Tampalon National High School', 'school',
   'Kabankalan-Tampalon Road, Barangay Tampalon, Kabankalan City',
   'Public high school in Tampalon; OSM record.',
   'active'),
  (2024, 1130, 'Tampalon Barangay Hall', 'government',
   'Kabankalan-Tampalon Road, Barangay Tampalon, Kabankalan City',
   'Barangay hall in Tampalon; OSM record.',
   'active'),
  (2025, 1129, 'Talubangi Barangay Hall', 'government',
   'Justice Y. Perez Avenue, Barangay Talubangi, Kabankalan City',
   'Barangay hall on Justice Y. Perez Avenue; OSM record.',
   'active');

-- =====================================================================
-- TABLE 5: transportation_types
-- All are within the Kabankalan City service area. Multicab is provisional.
-- =====================================================================
INSERT INTO transportation_types (transport_type_id, transport_name, description, status) VALUES
  (1, 'Jeepney', 'Locally observed public utility vehicle in Kabankalan; actual franchise coverage should be verified.', 'active'),
  (2, 'Bus', 'Ceres Bus Terminal is present in Barangay 2; intercity/provincial bus service passes through Kabankalan.', 'active'),
  (3, 'Tricycle', 'Short-distance public transport in Kabankalan; local operation should be verified.', 'active'),
  (4, 'Multicab', 'Provisional category; local multicab service availability not independently verified.', 'active')
ON DUPLICATE KEY UPDATE description = VALUES(description), status = VALUES(status);

-- =====================================================================
-- TABLE 6: routes
-- All routes are within Kabankalan City only. Unverified details are provisional.
-- =====================================================================
INSERT INTO routes (route_id, route_name, route_code, origin_id, destination_id, transport_type_id, estimated_travel_time, route_description, status, created_at, updated_at)
VALUES
  (3001, '[PROVISIONAL] Poblacion - Talubangi via JY Perez Highway', 'KAB-PROV-01', 2005, 2001, 1, 25,
   'PROVISIONAL TEST ROUTE. Public market to city government center via JY Perez Highway. Not an official route.',
   'active', '2026-10-10 08:00:00', '2026-10-10 08:00:00'),
  (3002, '[PROVISIONAL] Poblacion - Camingawan via Kabankalan-Bais Road', 'KAB-PROV-02', 2006, 2010, 2, 35,
   'PROVISIONAL TEST ROUTE. Public terminal to Central Philippines State University via Kabankalan-Bais Road. Not an official route.',
   'active', '2026-10-10 09:00:00', '2026-10-10 09:00:00'),
  (3003, '[PROVISIONAL] Poblacion - Binicuil via Bacolod South Road', 'KAB-PROV-03', 2006, 2017, 1, 30,
   'PROVISIONAL TEST ROUTE. Public terminal to Binicuil National High School via Bacolod South Road. Not an official route.',
   'active', '2026-10-11 08:00:00', '2026-10-11 08:00:00'),
  (3004, '[PROVISIONAL] Poblacion - Tabugon via Tapi-Tabugon Road', 'KAB-PROV-04', 2006, 2021, 1, 40,
   'PROVISIONAL TEST ROUTE. Public terminal to Tabugon Barangay Hall via Tapi-Tabugon Road. Not an official route.',
   'active', '2026-10-11 09:00:00', '2026-10-11 09:00:00'),
  (3005, '[PROVISIONAL] Poblacion - Tampalon via Kabankalan-Tampalon Road', 'KAB-PROV-05', 2006, 2024, 4, 40,
   'PROVISIONAL TEST ROUTE. Public terminal to Tampalon Barangay Hall via Kabankalan-Tampalon Road. Not an official route.',
   'active', '2026-10-12 08:00:00', '2026-10-12 08:00:00'),
  (3006, '[PROVISIONAL] Poblacion - Daan Banua via Bacolod South Road', 'KAB-PROV-06', 2006, 2019, 3, 25,
   'PROVISIONAL TEST ROUTE. Public terminal to Daan Banua Barangay Hall via Bacolod South Road. Not an official route.',
   'active', '2026-10-12 09:00:00', '2026-10-12 09:00:00'),
  (3007, '[PROVISIONAL][INACTIVE] Poblacion - Airport Road', 'KAB-PROV-07-OLD', 2006, 2011, 1, 20,
   'Historical demonstration record; airport is under construction and not operational. No service is claimed.',
   'inactive', '2026-09-01 08:00:00', '2026-10-06 08:00:00');

-- =====================================================================
-- TABLE 7: route_stops
-- =====================================================================
INSERT INTO route_stops (stop_id, route_id, location_id, stop_order, is_transfer_point, estimated_stop_time) VALUES
  -- Route 3001: Public Market -> City Government Center
  (4001, 3001, 2005, 1, 0, 0),
  (4002, 3001, 2006, 2, 1, 5),
  (4003, 3001, 2003, 3, 0, 14),
  (4004, 3001, 2002, 4, 0, 20),
  (4005, 3001, 2001, 5, 0, 25),

  -- Route 3002: Public Terminal -> CPSU
  (4006, 3002, 2006, 1, 1, 0),
  (4007, 3002, 2008, 2, 0, 5),
  (4008, 3002, 2015, 3, 0, 18),
  (4009, 3002, 2016, 4, 0, 28),
  (4010, 3002, 2010, 5, 0, 35),

  -- Route 3003: Public Terminal -> Binicuil
  (4011, 3003, 2006, 1, 1, 0),
  (4012, 3003, 2007, 2, 1, 4),
  (4013, 3003, 2018, 3, 0, 18),
  (4014, 3003, 2017, 4, 0, 30),

  -- Route 3004: Public Terminal -> Tabugon
  (4015, 3004, 2006, 1, 1, 0),
  (4016, 3004, 2009, 2, 0, 18),
  (4017, 3004, 2020, 3, 0, 30),
  (4018, 3004, 2021, 4, 0, 40),

  -- Route 3005: Public Terminal -> Tampalon
  (4019, 3005, 2006, 1, 1, 0),
  (4020, 3005, 2022, 2, 0, 20),
  (4021, 3005, 2023, 3, 0, 32),
  (4022, 3005, 2024, 4, 0, 40),

  -- Route 3006: Public Terminal -> Daan Banua
  (4023, 3006, 2006, 1, 1, 0),
  (4024, 3006, 2007, 2, 1, 4),
  (4025, 3006, 2019, 3, 0, 20),
  (4026, 3006, 2018, 4, 0, 25);

-- =====================================================================
-- TABLE 8: fare_types
-- =====================================================================
INSERT INTO fare_types (fare_type_id, fare_type_name, description, discount_percentage, status) VALUES
  (1, 'Regular', 'Standard fare for regular passengers.', 0.00, 'active'),
  (2, 'Student', '20% student fare discount under RA 11314; subject to valid ID and applicable transport rules.', 20.00, 'active'),
  (3, 'Senior Citizen', '20% senior citizen fare discount under RA 9994; subject to valid ID and applicable transport rules.', 20.00, 'active'),
  (4, 'Person with Disability', '20% PWD fare discount under RA 10754/RA 7277; subject to valid ID and applicable transport rules.', 20.00, 'active')
ON DUPLICATE KEY UPDATE description = VALUES(description), discount_percentage = VALUES(discount_percentage), status = VALUES(status);

-- =====================================================================
-- TABLE 9: route_fares
-- Current and historical provisional fares. Historical rows remain expired.
-- =====================================================================
INSERT INTO route_fares (fare_id, route_id, fare_type_id, minimum_fare, fare_per_km, total_estimated_fare, effective_date, expiry_date, status, created_at) VALUES
  (5001, 3001, 1, 13.00, 1.50, 15.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5002, 3001, 2, 10.40, 1.20, 12.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5003, 3001, 3, 10.40, 1.20, 12.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5004, 3001, 4, 10.40, 1.20, 12.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5005, 3001, 1, 12.00, 1.40, 14.00, '2025-06-01', '2025-12-31', 'expired', '2025-06-01 00:00:00'),
  (5006, 3002, 1, 25.00, 2.00, 35.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5007, 3002, 2, 20.00, 1.60, 28.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5008, 3002, 3, 20.00, 1.60, 28.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5009, 3002, 4, 20.00, 1.60, 28.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5010, 3003, 1, 13.00, 1.50, 18.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5011, 3003, 2, 10.40, 1.20, 14.40, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5012, 3003, 3, 10.40, 1.20, 14.40, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5013, 3003, 4, 10.40, 1.20, 14.40, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5014, 3004, 1, 13.00, 1.50, 22.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5015, 3004, 2, 10.40, 1.20, 17.60, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5016, 3004, 3, 10.40, 1.20, 17.60, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5017, 3004, 4, 10.40, 1.20, 17.60, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5018, 3005, 1, 15.00, 1.50, 25.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5019, 3005, 2, 12.00, 1.20, 20.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5020, 3005, 3, 12.00, 1.20, 20.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5021, 3005, 4, 12.00, 1.20, 20.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5022, 3006, 1, 10.00, 1.20, 12.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5023, 3006, 2, 8.00, 0.96, 9.60, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5024, 3006, 3, 8.00, 0.96, 9.60, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5025, 3006, 4, 8.00, 0.96, 9.60, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5026, 3002, 1, 20.00, 1.90, 32.00, '2025-01-01', '2025-12-31', 'expired', '2025-01-01 00:00:00');

-- =====================================================================
-- TABLE 10: route_transfers
-- =====================================================================
INSERT INTO route_transfers (transfer_id, from_route_id, to_route_id, transfer_location_id, transfer_instructions, estimated_transfer_time, additional_estimated_fare) VALUES
  (6001, 3002, 3001, 2006,
   'Alight at Public Terminal. Board the [PROVISIONAL] Poblacion - Talubangi via JY Perez Highway route.',
   5, 0.00),
  (6002, 3003, 3006, 2007,
   'Alight at Ceres Bus Terminal. Board the [PROVISIONAL] Poblacion - Daan Banua via Bacolod South Road route.',
   4, 0.00),
  (6003, 3004, 3001, 2006,
   'Alight at Public Terminal. Board the [PROVISIONAL] Poblacion - Talubangi via JY Perez Highway route.',
   5, 0.00),
  (6004, 3005, 3003, 2006,
   'Alight at Public Terminal. Board the [PROVISIONAL] Poblacion - Binicuil via Bacolod South Road route.',
   5, 0.00);

-- =====================================================================
-- TABLE 11: saved_routes
-- =====================================================================
INSERT INTO saved_routes (saved_route_id, user_id, origin_id, destination_id, nickname, saved_at) VALUES
  (7001, 1002, 2006, 2001, 'Terminal to City Hall', '2026-10-21 07:35:00'),
  (7002, 1002, 2010, 2006, 'CPSU to Terminal', '2026-10-20 17:10:00'),
  (7003, 1003, 2005, 2003, 'Market to CityMall', '2026-10-21 09:15:00'),
  (7004, 1004, 2006, 2009, 'Hospital Trip', '2026-10-21 14:40:00'),
  (7005, 1005, 2006, 2002, 'Sunday Mass', '2026-10-22 08:05:00'),
  (7006, 1006, 2006, 2010, 'School Commute', '2026-10-22 16:20:00'),
  (7007, 1007, 2004, 2001, 'Plaza to Government Center', '2026-10-23 10:00:00');

-- =====================================================================
-- TABLE 12: search_history
-- =====================================================================
INSERT INTO search_history (search_id, user_id, origin_id, destination_id, search_date) VALUES
  (8001, 1002, 2006, 2001, '2026-10-20 07:30:00'),
  (8002, 1002, 2010, 2006, '2026-10-20 17:10:00'),
  (8003, 1003, 2005, 2003, '2026-10-21 09:15:00'),
  (8004, 1004, 2006, 2009, '2026-10-21 14:40:00'),
  (8005, 1005, 2006, 2002, '2026-10-22 08:05:00'),
  (8006, 1006, 2006, 2010, '2026-10-22 16:20:00'),
  (8007, 1007, 2004, 2001, '2026-10-23 10:00:00'),
  (8008, NULL, 2006, 2019, '2026-10-23 12:30:00'),
  (8009, NULL, 2005, 2001, '2026-10-24 07:50:00'),
  (8010, 1002, 2006, 2010, '2026-10-24 18:05:00'),
  (8011, 1003, 2006, 2017, '2026-10-25 08:40:00'),
  (8012, 1004, 2006, 2021, '2026-10-25 15:15:00');

-- =====================================================================
-- TABLE 13: route_landmarks
-- =====================================================================
INSERT INTO route_landmarks (route_landmark_id, route_id, location_id, landmark_description, distance_from_origin, display_order) VALUES
  (9001, 3001, 2005, 'Kabankalan Public Market near the route origin.', 0.30, 1),
  (9002, 3001, 2006, 'Public Terminal; verified terminal and transfer point.', 0.60, 2),
  (9003, 3001, 2003, 'CityMall Kabankalan along JY Perez Highway.', 3.20, 3),
  (9004, 3001, 2002, 'New St. Francis Xavier Cathedral in Talubangi.', 5.00, 4),
  (9005, 3001, 2001, 'Kabankalan City Government Center, route destination.', 6.20, 5),
  (9006, 3002, 2006, 'Public Terminal; route origin.', 0.00, 1),
  (9007, 3002, 2008, 'Kabankalan National High School.', 0.90, 2),
  (9008, 3002, 2015, 'Florentino Galang National High School, Oringao.', 5.50, 3),
  (9009, 3002, 2016, 'Camingawan National High School.', 8.80, 4),
  (9010, 3002, 2010, 'CPSU main campus, route destination.', 9.80, 5),
  (9011, 3003, 2006, 'Public Terminal.', 0.00, 1),
  (9012, 3003, 2007, 'Ceres Bus Terminal.', 1.20, 2),
  (9013, 3003, 2018, 'Daan Banua National High School.', 7.00, 3),
  (9014, 3003, 2017, 'Binicuil National High School, route destination.', 9.00, 4),
  (9015, 3004, 2006, 'Public Terminal.', 0.00, 1),
  (9016, 3004, 2009, 'Kabankalan City Hospital.', 7.50, 2),
  (9017, 3004, 2020, 'Tabugon National High School.', 12.50, 3),
  (9018, 3004, 2021, 'Tabugon Barangay Hall, route destination.', 13.50, 4),
  (9019, 3005, 2006, 'Public Terminal.', 0.00, 1),
  (9020, 3005, 2022, 'Camansi National High School.', 8.50, 2),
  (9021, 3005, 2023, 'Tampalon National High School.', 13.50, 3),
  (9022, 3005, 2024, 'Tampalon Barangay Hall, route destination.', 14.50, 4),
  (9023, 3006, 2006, 'Public Terminal.', 0.00, 1),
  (9024, 3006, 2007, 'Ceres Bus Terminal.', 1.20, 2),
  (9025, 3006, 2019, 'Daan Banua Barangay Hall.', 8.50, 3),
  (9026, 3006, 2018, 'Daan Banua National High School, route destination.', 9.50, 4);

-- =====================================================================
-- TABLE 14: admin_activity_logs
-- Demonstration logs only; not claims of actual historical actions.
-- =====================================================================
INSERT INTO admin_activity_logs (log_id, admin_id, action_type, table_affected, record_id, action_description, created_at) VALUES
  (10001, 1001, 'CREATE', 'municipalities', 1001, 'Created Kabankalan City coverage record.', '2026-10-01 08:00:00'),
  (10002, 1001, 'CREATE', 'locations', 2001, 'Added Kabankalan City Government Center location.', '2026-10-02 09:00:00'),
  (10003, 1001, 'CREATE', 'routes', 3001, 'Added provisional Poblacion-Talubangi route for testing.', '2026-10-03 10:00:00'),
  (10004, 1001, 'UPDATE', 'route_fares', 5001, 'Updated provisional regular fare record for route 3001.', '2026-10-04 11:00:00'),
  (10005, 1001, 'UPDATE', 'routes', 3002, 'Updated route description; route remains provisional.', '2026-10-05 13:00:00'),
  (10006, 1001, 'DEACTIVATE', 'routes', 3007, 'Deactivated provisional airport route because airport is not operational.', '2026-10-06 14:00:00'),
  (10007, 1001, 'LOGIN', 'users', 1001, 'Demonstration administrator login log.', '2026-10-26 08:00:00');

COMMIT;

-- =====================================================================
-- BASIC VERIFICATION
-- =====================================================================
SELECT 'Database created' AS message, DATABASE() AS database_name;
SELECT COUNT(*) AS total_tables
FROM information_schema.tables
WHERE table_schema = DATABASE();
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
