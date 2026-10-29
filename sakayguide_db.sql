-- =====================================================================
-- SakayGuide: A Web-Based Public Transportation Route and Fare
-- Information System for Local Commuters
-- ---------------------------------------------------------------------
-- Database : sakayguide_db
-- Engine   : InnoDB
-- Charset  : utf8mb4 / utf8mb4_unicode_ci
-- Target   : MySQL 8.x or MariaDB 10.4+ (XAMPP)
-- ---------------------------------------------------------------------
-- IMPORTANT:
--   All routes, fares, landmarks, and travel times below are SAMPLE TEST
--   DATA for one Philippine city. They are NOT official LTFRB/local
--   government route or fare information. Replace them with verified
--   data before using the system for real commuters.
--
--   This script drops existing SakayGuide tables before recreating them.
--   Back up any existing data before importing.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS sakayguide_db
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE sakayguide_db;

SET NAMES utf8mb4;

-- Disable FK checks only while dropping old tables. They are re-enabled
-- before the CREATE TABLE statements so the schema is still validated.
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS admin_activity_logs;
DROP TABLE IF EXISTS route_landmarks;
DROP TABLE IF EXISTS search_history;
DROP TABLE IF EXISTS saved_routes;
DROP TABLE IF EXISTS route_transfers;
DROP TABLE IF EXISTS route_fares;
DROP TABLE IF EXISTS route_stops;
DROP TABLE IF EXISTS routes;
DROP TABLE IF EXISTS fare_types;
DROP TABLE IF EXISTS transportation_types;
DROP TABLE IF EXISTS locations;
DROP TABLE IF EXISTS barangays;
DROP TABLE IF EXISTS municipalities;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;


-- =====================================================================
-- TABLE 1: users
-- Commuter and administrator accounts.
-- Passwords must always be generated with PHP password_hash().
-- =====================================================================
CREATE TABLE users (
  user_id     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  full_name   VARCHAR(100) NOT NULL,
  email       VARCHAR(150) NOT NULL,
  password    VARCHAR(255) NOT NULL COMMENT 'password_hash() output; never plain text',
  role        ENUM('admin', 'commuter') NOT NULL DEFAULT 'commuter',
  status      ENUM('active', 'inactive') NOT NULL DEFAULT 'active',
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  UNIQUE KEY uq_users_email (email),
  KEY idx_users_role_status (role, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Commuter and administrator accounts';


-- =====================================================================
-- TABLE 2: municipalities
-- Municipalities or cities covered by SakayGuide.
-- =====================================================================
CREATE TABLE municipalities (
  municipality_id   INT UNSIGNED NOT NULL AUTO_INCREMENT,
  municipality_name VARCHAR(100) NOT NULL,
  province          VARCHAR(100) NOT NULL,
  description       TEXT NULL,
  status            ENUM('active', 'inactive') NOT NULL DEFAULT 'active',
  PRIMARY KEY (municipality_id),
  UNIQUE KEY uq_municipalities_name_province (municipality_name, province),
  KEY idx_municipalities_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Municipalities and cities covered by the system';


-- =====================================================================
-- TABLE 3: barangays
-- Barangays belonging to a municipality.
-- =====================================================================
CREATE TABLE barangays (
  barangay_id     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  municipality_id INT UNSIGNED NOT NULL,
  barangay_name   VARCHAR(100) NOT NULL,
  description     TEXT NULL,
  PRIMARY KEY (barangay_id),
  UNIQUE KEY uq_barangays_municipality_name (municipality_id, barangay_name),
  KEY idx_barangays_municipality (municipality_id),
  CONSTRAINT fk_barangays_municipality
    FOREIGN KEY (municipality_id) REFERENCES municipalities (municipality_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Barangays within each municipality';


-- =====================================================================
-- TABLE 4: locations
-- Terminals, landmarks, establishments, and other important places.
-- =====================================================================
CREATE TABLE locations (
  location_id   INT UNSIGNED NOT NULL AUTO_INCREMENT,
  barangay_id   INT UNSIGNED NOT NULL,
  location_name VARCHAR(150) NOT NULL,
  location_type VARCHAR(50) NOT NULL
                COMMENT 'Recommended: terminal, landmark, establishment, hospital, school, government, market, health_center, other',
  address       VARCHAR(255) NULL,
  description   TEXT NULL,
  status        ENUM('active', 'inactive') NOT NULL DEFAULT 'active',
  latitude      DECIMAL(10,7) NULL
                COMMENT 'Verified WGS 84 latitude from OpenStreetMap; NULL = not yet verified (sakayguide_locations_coordinates.sql)',
  longitude     DECIMAL(10,7) NULL
                COMMENT 'Verified WGS 84 longitude from OpenStreetMap; NULL = not yet verified (sakayguide_locations_coordinates.sql)',
  PRIMARY KEY (location_id),
  UNIQUE KEY uq_locations_barangay_name_type (barangay_id, location_name, location_type),
  KEY idx_locations_name (location_name),
  KEY idx_locations_type_status (location_type, status),
  KEY idx_locations_barangay (barangay_id),
  CONSTRAINT fk_locations_barangay
    FOREIGN KEY (barangay_id) REFERENCES barangays (barangay_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Terminals, landmarks, establishments, and important places';


-- =====================================================================
-- TABLE 5: transportation_types
-- Jeepney, bus, tricycle, multicab, and other transport types.
-- =====================================================================
CREATE TABLE transportation_types (
  transport_type_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  transport_name    VARCHAR(50) NOT NULL,
  description       TEXT NULL,
  status            ENUM('active', 'inactive') NOT NULL DEFAULT 'active',
  PRIMARY KEY (transport_type_id),
  UNIQUE KEY uq_transportation_types_name (transport_name),
  KEY idx_transportation_types_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Available public transportation types';


-- =====================================================================
-- TABLE 6: routes
-- Public transportation routes between two locations.
-- estimated_travel_time is stored in minutes.
-- =====================================================================
CREATE TABLE routes (
  route_id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  route_name            VARCHAR(150) NOT NULL,
  route_code            VARCHAR(30) NOT NULL,
  origin_id             INT UNSIGNED NOT NULL,
  destination_id        INT UNSIGNED NOT NULL,
  transport_type_id     INT UNSIGNED NOT NULL,
  estimated_travel_time INT UNSIGNED NOT NULL COMMENT 'Estimated one-way travel time in minutes',
  route_description     TEXT NULL,
  status                ENUM('active', 'inactive') NOT NULL DEFAULT 'active',
  created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (route_id),
  UNIQUE KEY uq_routes_code (route_code),
  KEY idx_routes_origin_destination (origin_id, destination_id),
  KEY idx_routes_destination (destination_id),
  KEY idx_routes_transport (transport_type_id),
  KEY idx_routes_status (status),
  KEY idx_routes_name (route_name),
  CONSTRAINT chk_routes_distinct_ends CHECK (origin_id <> destination_id),
  CONSTRAINT chk_routes_travel_time CHECK (estimated_travel_time > 0),
  CONSTRAINT fk_routes_origin
    FOREIGN KEY (origin_id) REFERENCES locations (location_id)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_routes_destination
    FOREIGN KEY (destination_id) REFERENCES locations (location_id)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_routes_transport_type
    FOREIGN KEY (transport_type_id) REFERENCES transportation_types (transport_type_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Public transportation routes';


-- =====================================================================
-- TABLE 7: route_stops
-- Ordered stops along each route. estimated_stop_time is the estimated
-- elapsed time in minutes from the route origin.
-- =====================================================================
CREATE TABLE route_stops (
  stop_id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
  route_id            INT UNSIGNED NOT NULL,
  location_id         INT UNSIGNED NOT NULL,
  stop_order          SMALLINT UNSIGNED NOT NULL,
  is_transfer_point   TINYINT(1) NOT NULL DEFAULT 0,
  estimated_stop_time SMALLINT UNSIGNED NOT NULL DEFAULT 0
                      COMMENT 'Estimated elapsed minutes from the route origin',
  PRIMARY KEY (stop_id),
  UNIQUE KEY uq_route_stops_order (route_id, stop_order),
  UNIQUE KEY uq_route_stops_location (route_id, location_id),
  KEY idx_route_stops_location_route (location_id, route_id),
  KEY idx_route_stops_transfer (is_transfer_point),
  CONSTRAINT chk_route_stops_order CHECK (stop_order > 0),
  CONSTRAINT chk_route_stops_transfer CHECK (is_transfer_point IN (0, 1)),
  CONSTRAINT fk_route_stops_route
    FOREIGN KEY (route_id) REFERENCES routes (route_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_route_stops_location
    FOREIGN KEY (location_id) REFERENCES locations (location_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Stops and landmarks along each route, in travel order';


-- =====================================================================
-- TABLE 8: fare_types
-- Regular, Student, Senior Citizen, Person with Disability, etc.
-- =====================================================================
CREATE TABLE fare_types (
  fare_type_id       INT UNSIGNED NOT NULL AUTO_INCREMENT,
  fare_type_name     VARCHAR(50) NOT NULL,
  description        TEXT NULL,
  discount_percentage DECIMAL(5,2) NOT NULL DEFAULT 0.00,
  status             ENUM('active', 'inactive') NOT NULL DEFAULT 'active',
  PRIMARY KEY (fare_type_id),
  UNIQUE KEY uq_fare_types_name (fare_type_name),
  KEY idx_fare_types_status (status),
  CONSTRAINT chk_fare_types_discount CHECK (discount_percentage BETWEEN 0 AND 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Fare categories and discount percentages';


-- =====================================================================
-- TABLE 9: route_fares
-- Fare records per route and fare category. Historical rows are kept by
-- setting status to 'expired'; they must not be deleted.
-- =====================================================================
CREATE TABLE route_fares (
  fare_id               INT UNSIGNED NOT NULL AUTO_INCREMENT,
  route_id              INT UNSIGNED NOT NULL,
  fare_type_id          INT UNSIGNED NOT NULL,
  minimum_fare          DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  fare_per_km           DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  total_estimated_fare  DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  effective_date        DATE NOT NULL,
  expiry_date           DATE NULL,
  status                ENUM('active', 'inactive', 'expired') NOT NULL DEFAULT 'active',
  created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (fare_id),
  UNIQUE KEY uq_route_fares_route_type_date (route_id, fare_type_id, effective_date),
  KEY idx_route_fares_lookup (route_id, fare_type_id, status, effective_date),
  KEY idx_route_fares_effective (effective_date, expiry_date),
  KEY idx_route_fares_status (status),
  CONSTRAINT chk_route_fares_minimum CHECK (minimum_fare >= 0),
  CONSTRAINT chk_route_fares_per_km CHECK (fare_per_km >= 0),
  CONSTRAINT chk_route_fares_total CHECK (total_estimated_fare >= 0),
  CONSTRAINT chk_route_fares_dates CHECK (expiry_date IS NULL OR expiry_date >= effective_date),
  CONSTRAINT fk_route_fares_route
    FOREIGN KEY (route_id) REFERENCES routes (route_id)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_route_fares_fare_type
    FOREIGN KEY (fare_type_id) REFERENCES fare_types (fare_type_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Route fare amounts by fare category, with fare history';


-- =====================================================================
-- TABLE 10: route_transfers
-- Valid connections between two routes at a shared transfer location.
-- The triggers below verify that transfer_location_id is a stop on BOTH
-- routes. Application logic must also verify the requested direction.
-- =====================================================================
CREATE TABLE route_transfers (
  transfer_id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  from_route_id            INT UNSIGNED NOT NULL,
  to_route_id              INT UNSIGNED NOT NULL,
  transfer_location_id     INT UNSIGNED NOT NULL,
  transfer_instructions     TEXT NOT NULL,
  estimated_transfer_time  SMALLINT UNSIGNED NOT NULL DEFAULT 0
                           COMMENT 'Estimated walking/waiting time in minutes',
  additional_estimated_fare DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  PRIMARY KEY (transfer_id),
  UNIQUE KEY uq_route_transfers_connection
    (from_route_id, to_route_id, transfer_location_id),
  KEY idx_route_transfers_to_route (to_route_id),
  KEY idx_route_transfers_location (transfer_location_id),
  CONSTRAINT chk_route_transfers_distinct_routes CHECK (from_route_id <> to_route_id),
  CONSTRAINT chk_route_transfers_fare CHECK (additional_estimated_fare >= 0),
  CONSTRAINT fk_route_transfers_from_route
    FOREIGN KEY (from_route_id) REFERENCES routes (route_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_route_transfers_to_route
    FOREIGN KEY (to_route_id) REFERENCES routes (route_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_route_transfers_location
    FOREIGN KEY (transfer_location_id) REFERENCES locations (location_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Connections between routes through a transfer location';

-- Transfer validation triggers (they do not create extra tables).
-- A transfer location must be an existing stop on BOTH routes.
DELIMITER $$

CREATE TRIGGER trg_route_transfers_validate_insert
BEFORE INSERT ON route_transfers
FOR EACH ROW
BEGIN
  IF NOT EXISTS (
       SELECT 1 FROM route_stops
       WHERE route_id = NEW.from_route_id
         AND location_id = NEW.transfer_location_id
     )
     OR NOT EXISTS (
       SELECT 1 FROM route_stops
       WHERE route_id = NEW.to_route_id
         AND location_id = NEW.transfer_location_id
     ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Invalid transfer: the transfer location must be a stop on both routes.';
  END IF;
END$$

CREATE TRIGGER trg_route_transfers_validate_update
BEFORE UPDATE ON route_transfers
FOR EACH ROW
BEGIN
  IF NOT EXISTS (
       SELECT 1 FROM route_stops
       WHERE route_id = NEW.from_route_id
         AND location_id = NEW.transfer_location_id
     )
     OR NOT EXISTS (
       SELECT 1 FROM route_stops
       WHERE route_id = NEW.to_route_id
         AND location_id = NEW.transfer_location_id
     ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Invalid transfer: the transfer location must be a stop on both routes.';
  END IF;
END$$

DELIMITER ;


-- =====================================================================
-- TABLE 11: saved_routes
-- Frequently searched origin-destination pairs saved by commuters.
-- =====================================================================
CREATE TABLE saved_routes (
  saved_route_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id        INT UNSIGNED NOT NULL,
  origin_id      INT UNSIGNED NOT NULL,
  destination_id INT UNSIGNED NOT NULL,
  nickname       VARCHAR(100) NULL,
  saved_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (saved_route_id),
  UNIQUE KEY uq_saved_routes_user_pair (user_id, origin_id, destination_id),
  KEY idx_saved_routes_origin_destination (origin_id, destination_id),
  KEY idx_saved_routes_user_date (user_id, saved_at),
  CONSTRAINT chk_saved_routes_distinct_ends CHECK (origin_id <> destination_id),
  CONSTRAINT fk_saved_routes_user
    FOREIGN KEY (user_id) REFERENCES users (user_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_saved_routes_origin
    FOREIGN KEY (origin_id) REFERENCES locations (location_id)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_saved_routes_destination
    FOREIGN KEY (destination_id) REFERENCES locations (location_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Routes or origin-destination pairs saved by commuters';


-- =====================================================================
-- TABLE 12: search_history
-- Previous commuter searches. user_id is NULL for guest searches.
-- =====================================================================
CREATE TABLE search_history (
  search_id      INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id        INT UNSIGNED NULL,
  origin_id      INT UNSIGNED NOT NULL,
  destination_id INT UNSIGNED NOT NULL,
  search_date    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (search_id),
  KEY idx_search_history_user_date (user_id, search_date),
  KEY idx_search_history_origin_destination (origin_id, destination_id),
  KEY idx_search_history_date (search_date),
  CONSTRAINT chk_search_history_distinct_ends CHECK (origin_id <> destination_id),
  CONSTRAINT fk_search_history_user
    FOREIGN KEY (user_id) REFERENCES users (user_id)
    ON UPDATE CASCADE ON DELETE SET NULL,
  CONSTRAINT fk_search_history_origin
    FOREIGN KEY (origin_id) REFERENCES locations (location_id)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_search_history_destination
    FOREIGN KEY (destination_id) REFERENCES locations (location_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Commuter and guest search history';


-- =====================================================================
-- TABLE 13: route_landmarks
-- Important landmarks associated with a route. distance_from_origin is
-- stored in kilometres.
-- =====================================================================
CREATE TABLE route_landmarks (
  route_landmark_id    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  route_id             INT UNSIGNED NOT NULL,
  location_id          INT UNSIGNED NOT NULL,
  landmark_description TEXT NULL,
  distance_from_origin DECIMAL(8,2) NOT NULL DEFAULT 0.00
                       COMMENT 'Approximate distance from route origin in kilometres',
  display_order        SMALLINT UNSIGNED NOT NULL,
  PRIMARY KEY (route_landmark_id),
  UNIQUE KEY uq_route_landmarks_route_location (route_id, location_id),
  UNIQUE KEY uq_route_landmarks_route_order (route_id, display_order),
  KEY idx_route_landmarks_location (location_id),
  CONSTRAINT chk_route_landmarks_distance CHECK (distance_from_origin >= 0),
  CONSTRAINT chk_route_landmarks_order CHECK (display_order > 0),
  CONSTRAINT fk_route_landmarks_route
    FOREIGN KEY (route_id) REFERENCES routes (route_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_route_landmarks_location
    FOREIGN KEY (location_id) REFERENCES locations (location_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Important landmarks along each route';


-- =====================================================================
-- TABLE 14: admin_activity_logs
-- Audit trail of administrative actions.
-- =====================================================================
CREATE TABLE admin_activity_logs (
  log_id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
  admin_id           INT UNSIGNED NOT NULL,
  action_type        VARCHAR(50) NOT NULL
                     COMMENT 'Example: CREATE, UPDATE, DEACTIVATE, ACTIVATE, LOGIN, LOGOUT',
  table_affected     VARCHAR(64) NOT NULL,
  record_id          INT UNSIGNED NULL,
  action_description TEXT NULL,
  created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (log_id),
  KEY idx_admin_logs_admin_date (admin_id, created_at),
  KEY idx_admin_logs_table_record (table_affected, record_id),
  KEY idx_admin_logs_action (action_type),
  CONSTRAINT fk_admin_logs_admin
    FOREIGN KEY (admin_id) REFERENCES users (user_id)
    ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Audit trail of administrator actions';


-- =====================================================================
-- SAMPLE TEST DATA
-- One municipality: Butuan City, Agusan del Norte.
-- All route, fare, and landmark values are illustrative only.
-- =====================================================================

-- Passwords:
--   admin@sakayguide.test  -> Admin@123
--   juan@example.com       -> Commuter@123
--   ana@example.com        -> Commuter@123
-- These are bcrypt hashes generated with PHP password_hash().
INSERT INTO users
  (user_id, full_name, email, password, role, status, created_at, updated_at)
VALUES
  (1, 'Maria Santos', 'admin@sakayguide.test',
   '$2y$10$uhcLJG5RsRH7Gj1EoV5F2eoclh2BRo/qe78TlNy6eup46wu8TWn6W',
   'admin', 'active', '2026-01-02 08:00:00', '2026-01-02 08:00:00'),
  (2, 'Juan Dela Cruz', 'juan@example.com',
   '$2y$10$S8uupghLrqLOhY49LQI13.BbSH99soL7kSuYYk8lnwF11FYYKMzsa',
   'commuter', 'active', '2026-01-03 09:15:00', '2026-01-03 09:15:00'),
  (3, 'Ana Reyes', 'ana@example.com',
   '$2y$10$S8uupghLrqLOhY49LQI13.BbSH99soL7kSuYYk8lnwF11FYYKMzsa',
   'commuter', 'active', '2026-01-04 10:30:00', '2026-01-04 10:30:00');

INSERT INTO municipalities
  (municipality_id, municipality_name, province, description, status)
VALUES
  (1, 'Butuan City', 'Agusan del Norte',
   'Sample coverage area for the SakayGuide student project. Route and fare data are illustrative, not official.',
   'active');

INSERT INTO barangays
  (barangay_id, municipality_id, barangay_name, description)
VALUES
  (1, 1, 'Agusan Pequeno', 'Sample barangay record.'),
  (2, 1, 'Ambago', 'Sample barangay record.'),
  (3, 1, 'Baan', 'Sample barangay record.'),
  (4, 1, 'Bancasi', 'Sample barangay record; sample location of the airport.'),
  (5, 1, 'Doongan', 'Sample barangay record for the city proper.'),
  (6, 1, 'Libertad', 'Sample barangay record for the commercial area.'),
  (7, 1, 'Limaha', 'Sample barangay record.'),
  (8, 1, 'San Vicente', 'Sample barangay record.'),
  (9, 1, 'Ampayon', 'Sample barangay record; sample location of the state university.'),
  (10, 1, 'Villa Kananga', 'Sample barangay record.');

INSERT INTO locations
  (location_id, barangay_id, location_name, location_type, address, description, status)
VALUES
  (1, 5, 'Butuan City Hall', 'government',
   'J. Rosales Avenue, Doongan, Butuan City',
   'Sample city government landmark and route endpoint.', 'active'),
  (2, 6, 'Butuan Central Terminal', 'terminal',
   'J.C. Aquino Avenue, Libertad, Butuan City',
   'Sample central terminal used as a transfer point.', 'active'),
  (3, 6, 'Robinsons Place Butuan', 'establishment',
   'J.C. Aquino Avenue, Libertad, Butuan City',
   'Sample shopping mall and landmark.', 'active'),
  (4, 10, 'SM City Butuan', 'establishment',
   'J.C. Aquino Avenue, Villa Kananga, Butuan City',
   'Sample shopping mall and landmark.', 'active'),
  (5, 5, 'Saint Joseph Cathedral', 'landmark',
   'Montilla Boulevard, Doongan, Butuan City',
   'Sample heritage and religious landmark.', 'active'),
  (6, 7, 'Butuan Medical Center', 'hospital',
   'Limaha, Butuan City',
   'Sample hospital landmark.', 'active'),
  (7, 5, 'Father Saturnino Urios University', 'school',
   'San Francisco Street, Doongan, Butuan City',
   'Sample university landmark.', 'active'),
  (8, 6, 'Libertad Public Market', 'market',
   'Libertad, Butuan City',
   'Sample public market and jeepney stop.', 'active'),
  (9, 4, 'Bancasi Airport', 'terminal',
   'Bancasi, Butuan City',
   'Sample airport terminal and route endpoint.', 'active'),
  (10, 5, 'Butuan Doctors Hospital', 'hospital',
   'Doongan, Butuan City',
   'Sample hospital landmark.', 'active'),
  (11, 9, 'Caraga State University', 'school',
   'Ampayon, Butuan City',
   'Sample state university and route endpoint.', 'active'),
  (12, 2, 'Barangay Ambago Hall', 'government',
   'Ambago, Butuan City',
   'Sample barangay hall and stop.', 'active'),
  (13, 3, 'Barangay Baan Terminal', 'terminal',
   'Baan, Butuan City',
   'Sample barangay terminal and stop.', 'active'),
  (14, 8, 'Barangay San Vicente Plaza', 'landmark',
   'San Vicente, Butuan City',
   'Sample plaza and tricycle terminal.', 'active'),
  (15, 6, 'Agusan del Norte Provincial Capitol', 'government',
   'Libertad, Butuan City',
   'Sample provincial government landmark.', 'active'),
  (16, 5, 'Butuan City Sports Complex', 'landmark',
   'Doongan, Butuan City',
   'Sample sports and events landmark.', 'active'),
  (17, 1, 'Agusan Pequeno Health Center', 'health_center',
   'Agusan Pequeno, Butuan City',
   'Sample barangay health center.', 'active'),
  (18, 5, 'Gaisano Mall Butuan', 'establishment',
   'Montilla Boulevard, Doongan, Butuan City',
   'Sample shopping center and landmark.', 'active');

INSERT INTO transportation_types
  (transport_type_id, transport_name, description, status)
VALUES
  (1, 'Jeepney', 'Sample public jeepney service.', 'active'),
  (2, 'Bus', 'Sample city or provincial bus service.', 'active'),
  (3, 'Tricycle', 'Sample short-distance tricycle service.', 'active'),
  (4, 'Multicab', 'Sample multicab service.', 'active');

INSERT INTO routes
  (route_id, route_name, route_code, origin_id, destination_id,
   transport_type_id, estimated_travel_time, route_description, status,
   created_at, updated_at)
VALUES
  (1, 'Libertad - Doongan Jeepney', 'JEEP-LD-01', 2, 1, 1, 20,
   'Sample route from Butuan Central Terminal to Butuan City Hall via Libertad and Doongan. Not an official route.',
   'active', '2026-01-05 08:00:00', '2026-01-05 08:00:00'),
  (2, 'Bancasi Airport - City Proper Jeepney', 'JEEP-BC-02', 9, 2, 1, 35,
   'Sample route from Bancasi Airport to Butuan Central Terminal via Baan and Robinsons Place. Not an official route.',
   'active', '2026-01-05 08:10:00', '2026-01-05 08:10:00'),
  (3, 'Ampayon - Libertad Multicab', 'MC-AM-03', 11, 8, 4, 30,
   'Sample route from Caraga State University to Libertad Public Market via Ambago and SM City. Not an official route.',
   'active', '2026-01-05 08:20:00', '2026-01-05 08:20:00'),
  (4, 'Doongan - SM City Jeepney', 'JEEP-DS-04', 1, 4, 1, 25,
   'Sample route from Butuan City Hall to SM City Butuan via the cathedral and Robinsons Place. Not an official route.',
   'active', '2026-01-05 08:30:00', '2026-01-05 08:30:00'),
  (5, 'Central Terminal - Ampayon Bus', 'BUS-AM-05', 2, 11, 2, 40,
   'Sample bus route from Butuan Central Terminal to Caraga State University via SM City and Ambago. Not an official route.',
   'active', '2026-01-05 08:40:00', '2026-01-05 08:40:00'),
  (6, 'San Vicente - Doongan Tricycle', 'TRI-SV-06', 14, 1, 3, 15,
   'Sample tricycle route from San Vicente Plaza to Butuan City Hall via Butuan Doctors Hospital. Not an official route.',
   'active', '2026-01-05 08:50:00', '2026-01-05 08:50:00');

INSERT INTO route_stops
  (stop_id, route_id, location_id, stop_order, is_transfer_point, estimated_stop_time)
VALUES
  -- Route 1: Central Terminal -> City Hall
  (1, 1, 2, 1, 1, 0),
  (2, 1, 8, 2, 0, 5),
  (3, 1, 3, 3, 0, 10),
  (4, 1, 5, 4, 0, 15),
  (5, 1, 1, 5, 1, 20),

  -- Route 2: Airport -> Central Terminal
  (6, 2, 9, 1, 1, 0),
  (7, 2, 13, 2, 0, 10),
  (8, 2, 3, 3, 0, 28),
  (9, 2, 2, 4, 1, 35),

  -- Route 3: CSU -> Libertad Market
  (10, 3, 11, 1, 0, 0),
  (11, 3, 12, 2, 0, 10),
  (12, 3, 4, 3, 1, 20),
  (13, 3, 8, 4, 1, 30),

  -- Route 4: City Hall -> SM City
  (14, 4, 1, 1, 1, 0),
  (15, 4, 5, 2, 0, 5),
  (16, 4, 3, 3, 0, 12),
  (17, 4, 4, 4, 1, 25),

  -- Route 5: Central Terminal -> CSU
  (18, 5, 2, 1, 1, 0),
  (19, 5, 4, 2, 1, 15),
  (20, 5, 12, 3, 0, 25),
  (21, 5, 11, 4, 0, 40),

  -- Route 6: San Vicente Plaza -> City Hall
  (22, 6, 14, 1, 0, 0),
  (23, 6, 10, 2, 0, 7),
  (24, 6, 1, 3, 1, 15);

INSERT INTO fare_types
  (fare_type_id, fare_type_name, description, discount_percentage, status)
VALUES
  (1, 'Regular', 'Standard fare for regular passengers.', 0.00, 'active'),
  (2, 'Student', 'Sample discounted fare for students.', 20.00, 'active'),
  (3, 'Senior Citizen', 'Sample discounted fare for senior citizens.', 20.00, 'active'),
  (4, 'Person with Disability', 'Sample discounted fare for persons with disability.', 20.00, 'active');

-- Current fares effective 2026-01-01. Amounts are illustrative only.
-- Fare IDs 1-4: route 1 current; fare ID 5: route 1 historical record.
INSERT INTO route_fares
  (fare_id, route_id, fare_type_id, minimum_fare, fare_per_km,
   total_estimated_fare, effective_date, expiry_date, status, created_at)
VALUES
  (1, 1, 1, 13.00, 1.50, 15.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (2, 1, 2, 10.40, 1.20, 12.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (3, 1, 3, 10.40, 1.20, 12.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (4, 1, 4, 10.40, 1.20, 12.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (5, 1, 1, 12.00, 1.40, 14.00, '2025-06-01', '2025-12-31', 'expired', '2025-06-01 00:00:00'),

  (6, 2, 1, 13.00, 1.50, 18.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (7, 2, 2, 10.40, 1.20, 14.40, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (8, 2, 3, 10.40, 1.20, 14.40, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (9, 2, 4, 10.40, 1.20, 14.40, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),

  (10, 3, 1, 13.00, 1.50, 15.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (11, 3, 2, 10.40, 1.20, 12.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (12, 3, 3, 10.40, 1.20, 12.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (13, 3, 4, 10.40, 1.20, 12.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),

  (14, 4, 1, 13.00, 1.50, 13.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (15, 4, 2, 10.40, 1.20, 10.40, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (16, 4, 3, 10.40, 1.20, 10.40, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (17, 4, 4, 10.40, 1.20, 10.40, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),

  (18, 5, 1, 25.00, 2.00, 30.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (19, 5, 2, 20.00, 1.60, 24.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (20, 5, 3, 20.00, 1.60, 24.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (21, 5, 4, 20.00, 1.60, 24.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),

  (22, 6, 1, 8.00, 1.50, 10.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (23, 6, 2, 6.40, 1.20, 8.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (24, 6, 3, 6.40, 1.20, 8.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00'),
  (25, 6, 4, 6.40, 1.20, 8.00, '2026-01-01', NULL, 'active', '2026-01-01 00:00:00');

INSERT INTO route_transfers
  (transfer_id, from_route_id, to_route_id, transfer_location_id,
   transfer_instructions, estimated_transfer_time, additional_estimated_fare)
VALUES
  (1, 2, 1, 2,
   'Alight at Butuan Central Terminal. Walk to the jeepney bay and board the JEEP-LD-01 jeepney heading to Doongan and City Hall.',
   5, 0.00),
  (2, 3, 1, 8,
   'Alight at Libertad Public Market. Cross to the designated jeepney stop and board JEEP-LD-01 heading to Doongan and City Hall.',
   5, 0.00),
  (3, 6, 4, 1,
   'Alight at Butuan City Hall. Walk to the jeepney stop in front of the city hall and board JEEP-DS-04 heading to SM City Butuan.',
   3, 0.00),
  (4, 5, 3, 4,
   'Alight at SM City Butuan. Move to the multicab stop and board MC-AM-03 heading to Libertad Public Market.',
   5, 0.00);

INSERT INTO saved_routes
  (saved_route_id, user_id, origin_id, destination_id, nickname, saved_at)
VALUES
  (1, 2, 2, 1, 'Daily commute to City Hall', '2026-10-21 07:35:00'),
  (2, 2, 9, 1, 'Airport to City Hall', '2026-10-20 08:20:00'),
  (3, 3, 11, 8, 'School to market', '2026-10-22 17:00:00');

INSERT INTO search_history
  (search_id, user_id, origin_id, destination_id, search_date)
VALUES
  (1, 2, 9, 1, '2026-10-20 08:15:00'),
  (2, 2, 2, 1, '2026-10-21 07:30:00'),
  (3, 3, 11, 8, '2026-10-22 16:45:00'),
  (4, 3, 11, 8, '2026-10-23 07:10:00'),
  (5, NULL, 2, 4, '2026-10-24 12:00:00'),
  (6, 2, 9, 8, '2026-10-25 09:00:00');

INSERT INTO route_landmarks
  (route_landmark_id, route_id, location_id, landmark_description,
   distance_from_origin, display_order)
VALUES
  (1, 1, 8, 'Libertad Public Market, a recognizable stop near the route origin.', 0.40, 1),
  (2, 1, 3, 'Robinsons Place Butuan along J.C. Aquino Avenue.', 1.10, 2),
  (3, 1, 5, 'Saint Joseph Cathedral near the city proper.', 1.80, 3),
  (4, 1, 1, 'Butuan City Hall, the route destination.', 2.40, 4),

  (5, 2, 9, 'Bancasi Airport, the route origin.', 0.00, 1),
  (6, 2, 13, 'Barangay Baan Terminal along the route.', 3.20, 2),
  (7, 2, 2, 'Butuan Central Terminal, the route destination.', 8.50, 3),

  (8, 3, 11, 'Caraga State University, the route origin.', 0.00, 1),
  (9, 3, 12, 'Barangay Ambago Hall along the route.', 2.50, 2),
  (10, 3, 4, 'SM City Butuan near the midpoint.', 5.00, 3),
  (11, 3, 8, 'Libertad Public Market, the route destination.', 6.80, 4),

  (12, 4, 1, 'Butuan City Hall, the route origin.', 0.00, 1),
  (13, 4, 5, 'Saint Joseph Cathedral along the city proper segment.', 0.80, 2),
  (14, 4, 3, 'Robinsons Place Butuan along the route.', 1.70, 3),
  (15, 4, 4, 'SM City Butuan, the route destination.', 3.50, 4),

  (16, 5, 2, 'Butuan Central Terminal, the route origin.', 0.00, 1),
  (17, 5, 4, 'SM City Butuan along the route.', 4.20, 2),
  (18, 5, 12, 'Barangay Ambago Hall along the route.', 6.00, 3),
  (19, 5, 11, 'Caraga State University, the route destination.', 9.50, 4),

  (20, 6, 14, 'Barangay San Vicente Plaza, the route origin.', 0.00, 1),
  (21, 6, 10, 'Butuan Doctors Hospital along the route.', 0.80, 2),
  (22, 6, 1, 'Butuan City Hall, the route destination.', 1.60, 3);

INSERT INTO admin_activity_logs
  (log_id, admin_id, action_type, table_affected, record_id, action_description, created_at)
VALUES
  (1, 1, 'CREATE', 'routes', 1,
   'Created sample jeepney route JEEP-LD-01.', '2026-01-05 08:00:00'),
  (2, 1, 'UPDATE', 'route_fares', 1,
   'Updated the regular fare for JEEP-LD-01 effective 2026-01-01; previous record retained as expired.', '2026-01-10 10:15:00'),
  (3, 1, 'CREATE', 'route_transfers', 1,
   'Added transfer connection from JEEP-BC-02 to JEEP-LD-01 at Butuan Central Terminal.', '2026-01-12 14:20:00'),
  (4, 1, 'LOGIN', 'users', 1,
   'Administrator logged in to the management dashboard.', '2026-10-25 08:00:00');


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
