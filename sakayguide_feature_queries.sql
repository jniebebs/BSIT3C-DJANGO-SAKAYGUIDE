USE sakayguide_db;

-- =====================================================================
-- SakayGuide - Feature Queries
-- Read-only examples run as-is. Write examples are included as comments
-- (or use the matching examples in SAKAYGUIDE_DATABASE.md).
-- In PHP, replace the @variables with ? placeholders and bind values.
-- =====================================================================

-- ---------------------------------------------------------------------
-- FEATURE 1: Search for a starting point and destination (direct ride)
-- Example: Butuan Central Terminal (2) -> Butuan City Hall (1)
-- ---------------------------------------------------------------------
SET @origin_id = 2;
SET @destination_id = 1;

SELECT
  r.route_id,
  r.route_code,
  r.route_name,
  tt.transport_name,
  o.location_name AS route_origin,
  d.location_name AS route_destination,
  r.estimated_travel_time AS estimated_minutes,
  os.stop_order AS boarding_stop_order,
  ds.stop_order AS alighting_stop_order,
  (ds.stop_order - os.stop_order) AS stops_travelled
FROM routes AS r
JOIN route_stops AS os
  ON os.route_id = r.route_id
 AND os.location_id = @origin_id
JOIN route_stops AS ds
  ON ds.route_id = r.route_id
 AND ds.location_id = @destination_id
JOIN transportation_types AS tt
  ON tt.transport_type_id = r.transport_type_id
JOIN locations AS o
  ON o.location_id = r.origin_id
JOIN locations AS d
  ON d.location_id = r.destination_id
WHERE r.status = 'active'
  AND tt.status = 'active'
  AND os.stop_order < ds.stop_order
ORDER BY r.estimated_travel_time, r.route_code;


-- ---------------------------------------------------------------------
-- FEATURE 2: Display available transportation routes
-- Lists every active route, its endpoints, transport type, stop count,
-- and current regular fare.
-- ---------------------------------------------------------------------
SELECT
  r.route_id,
  r.route_code,
  r.route_name,
  tt.transport_name,
  o.location_name AS origin,
  d.location_name AS destination,
  r.estimated_travel_time AS estimated_minutes,
  COUNT(DISTINCT rs.stop_id) AS stop_count,
  (
    SELECT rf.total_estimated_fare
    FROM route_fares AS rf
    WHERE rf.route_id = r.route_id
      AND rf.fare_type_id = 1
      AND rf.status = 'active'
      AND rf.effective_date <= CURDATE()
      AND (rf.expiry_date IS NULL OR rf.expiry_date >= CURDATE())
    ORDER BY rf.effective_date DESC
    LIMIT 1
  ) AS regular_fare
FROM routes AS r
JOIN transportation_types AS tt
  ON tt.transport_type_id = r.transport_type_id
JOIN locations AS o
  ON o.location_id = r.origin_id
JOIN locations AS d
  ON d.location_id = r.destination_id
LEFT JOIN route_stops AS rs
  ON rs.route_id = r.route_id
WHERE r.status = 'active'
  AND tt.status = 'active'
GROUP BY r.route_id, r.route_code, r.route_name, tt.transport_name,
         o.location_name, d.location_name, r.estimated_travel_time
ORDER BY r.route_code;


-- ---------------------------------------------------------------------
-- FEATURE 3: Show ordered stops and route landmarks
-- Example route: JEEP-LD-01 (route_id = 1)
-- ---------------------------------------------------------------------
SET @route_id = 1;

SELECT
  rs.stop_order,
  l.location_name,
  l.location_type,
  b.barangay_name,
  m.municipality_name,
  rs.is_transfer_point,
  rs.estimated_stop_time AS minutes_from_origin
FROM route_stops AS rs
JOIN locations AS l
  ON l.location_id = rs.location_id
JOIN barangays AS b
  ON b.barangay_id = l.barangay_id
JOIN municipalities AS m
  ON m.municipality_id = b.municipality_id
WHERE rs.route_id = @route_id
ORDER BY rs.stop_order;

SELECT
  rl.display_order,
  l.location_name AS landmark,
  b.barangay_name,
  rl.landmark_description,
  rl.distance_from_origin AS km_from_origin
FROM route_landmarks AS rl
JOIN locations AS l
  ON l.location_id = rl.location_id
JOIN barangays AS b
  ON b.barangay_id = l.barangay_id
WHERE rl.route_id = @route_id
ORDER BY rl.display_order;


-- ---------------------------------------------------------------------
-- FEATURE 4: Display estimated fares for regular and discounted riders
-- ---------------------------------------------------------------------
SELECT
  ft.fare_type_name,
  rf.minimum_fare,
  rf.fare_per_km,
  rf.total_estimated_fare AS estimated_fare,
  ft.discount_percentage,
  rf.effective_date,
  rf.expiry_date,
  rf.status
FROM route_fares AS rf
JOIN fare_types AS ft
  ON ft.fare_type_id = rf.fare_type_id
WHERE rf.route_id = @route_id
  AND rf.status = 'active'
  AND rf.effective_date <= CURDATE()
  AND (rf.expiry_date IS NULL OR rf.expiry_date >= CURDATE())
ORDER BY ft.fare_type_id;


-- ---------------------------------------------------------------------
-- FEATURE 5: Explain where passengers should transfer
-- Lists all active route-to-route transfers.
-- ---------------------------------------------------------------------
SELECT
  rt.transfer_id,
  fr.route_code AS from_route_code,
  fr.route_name AS from_route_name,
  tr.route_code AS to_route_code,
  tr.route_name AS to_route_name,
  l.location_name AS transfer_at,
  rt.transfer_instructions,
  rt.estimated_transfer_time AS transfer_minutes,
  rt.additional_estimated_fare
FROM route_transfers AS rt
JOIN routes AS fr
  ON fr.route_id = rt.from_route_id
JOIN routes AS tr
  ON tr.route_id = rt.to_route_id
JOIN locations AS l
  ON l.location_id = rt.transfer_location_id
WHERE fr.status = 'active'
  AND tr.status = 'active'
ORDER BY fr.route_code, tr.route_code;


-- ---------------------------------------------------------------------
-- FEATURE 6: Calculate the estimated total fare for a journey with a
-- transfer. Example: Bancasi Airport (9) -> Butuan City Hall (1),
-- Regular fare (1). Result: route 2 + transfer + route 1.
-- ---------------------------------------------------------------------
SET @journey_origin_id = 9;
SET @journey_destination_id = 1;
SET @fare_type_id = 1;

SELECT
  r1.route_code AS first_route_code,
  r1.route_name AS first_route_name,
  r2.route_code AS second_route_code,
  r2.route_name AS second_route_name,
  transfer_location.location_name AS transfer_at,
  rt.transfer_instructions,
  rt.estimated_transfer_time AS transfer_minutes,
  f1.total_estimated_fare AS first_ride_fare,
  rt.additional_estimated_fare AS transfer_fee,
  f2.total_estimated_fare AS second_ride_fare,
  ROUND(f1.total_estimated_fare + rt.additional_estimated_fare + f2.total_estimated_fare, 2)
    AS total_estimated_fare,
  (r1.estimated_travel_time + rt.estimated_transfer_time + r2.estimated_travel_time)
    AS total_estimated_minutes
FROM route_stops AS os
JOIN routes AS r1
  ON r1.route_id = os.route_id
 AND r1.status = 'active'
JOIN route_transfers AS rt
  ON rt.from_route_id = r1.route_id
JOIN routes AS r2
  ON r2.route_id = rt.to_route_id
 AND r2.status = 'active'
JOIN route_stops AS transfer_on_first
  ON transfer_on_first.route_id = r1.route_id
 AND transfer_on_first.location_id = rt.transfer_location_id
JOIN route_stops AS transfer_on_second
  ON transfer_on_second.route_id = r2.route_id
 AND transfer_on_second.location_id = rt.transfer_location_id
JOIN route_stops AS ds
  ON ds.route_id = r2.route_id
 AND ds.location_id = @journey_destination_id
JOIN locations AS transfer_location
  ON transfer_location.location_id = rt.transfer_location_id
JOIN route_fares AS f1
  ON f1.route_id = r1.route_id
 AND f1.fare_type_id = @fare_type_id
 AND f1.status = 'active'
 AND f1.effective_date <= CURDATE()
 AND (f1.expiry_date IS NULL OR f1.expiry_date >= CURDATE())
JOIN route_fares AS f2
  ON f2.route_id = r2.route_id
 AND f2.fare_type_id = @fare_type_id
 AND f2.status = 'active'
 AND f2.effective_date <= CURDATE()
 AND (f2.expiry_date IS NULL OR f2.expiry_date >= CURDATE())
WHERE os.location_id = @journey_origin_id
  AND os.stop_order < transfer_on_first.stop_order
  AND transfer_on_second.stop_order < ds.stop_order
ORDER BY total_estimated_fare, total_estimated_minutes
LIMIT 5;


-- ---------------------------------------------------------------------
-- FEATURE 7: Save a frequently searched route
-- PHP prepared statement equivalent is shown in the documentation.
-- ---------------------------------------------------------------------
-- SET @user_id = 2;
-- SET @save_origin_id = 2;
-- SET @save_destination_id = 1;
-- INSERT INTO saved_routes (user_id, origin_id, destination_id, nickname)
-- VALUES (@user_id, @save_origin_id, @save_destination_id, 'Daily commute')
-- ON DUPLICATE KEY UPDATE
--   nickname = VALUES(nickname),
--   saved_at = CURRENT_TIMESTAMP;

-- View a commuter's saved routes:
SET @user_id = 2;
SELECT
  sr.saved_route_id,
  o.location_name AS origin,
  d.location_name AS destination,
  sr.nickname,
  sr.saved_at
FROM saved_routes AS sr
JOIN locations AS o ON o.location_id = sr.origin_id
JOIN locations AS d ON d.location_id = sr.destination_id
WHERE sr.user_id = @user_id
ORDER BY sr.saved_at DESC;


-- ---------------------------------------------------------------------
-- FEATURE 8: View search history
-- ---------------------------------------------------------------------
SET @history_user_id = 2;
SELECT
  sh.search_id,
  o.location_name AS origin,
  d.location_name AS destination,
  sh.search_date
FROM search_history AS sh
JOIN locations AS o ON o.location_id = sh.origin_id
JOIN locations AS d ON d.location_id = sh.destination_id
WHERE sh.user_id = @history_user_id
ORDER BY sh.search_date DESC
LIMIT 50;


-- ---------------------------------------------------------------------
-- FEATURE 9: Administrator - add, edit, and deactivate a route
-- ---------------------------------------------------------------------
-- Add:
-- INSERT INTO routes
--   (route_name, route_code, origin_id, destination_id,
--    transport_type_id, estimated_travel_time, route_description, status)
-- VALUES
--   ('Sample New Route', 'JEEP-NEW-07', 2, 4, 1, 22,
--    'Sample route description.', 'active');

-- Edit:
-- UPDATE routes
-- SET route_name = 'Sample Updated Route',
--     estimated_travel_time = 24,
--     route_description = 'Updated sample description.'
-- WHERE route_id = 7;

-- Deactivate (do not hard-delete routes that have fare history):
-- UPDATE routes
-- SET status = 'inactive'
-- WHERE route_id = 7;


-- ---------------------------------------------------------------------
-- FEATURE 10: Administrator - manage municipalities, barangays, and
-- locations
-- ---------------------------------------------------------------------
-- Add a municipality:
-- INSERT INTO municipalities (municipality_name, province, description, status)
-- VALUES ('Sample Municipality', 'Agusan del Norte', 'Sample record.', 'active');

-- Add a barangay:
-- INSERT INTO barangays (municipality_id, barangay_name, description)
-- VALUES (2, 'Sample Barangay', 'Sample record.');

-- Add a location:
-- INSERT INTO locations
--   (barangay_id, location_name, location_type, address, description, status)
-- VALUES
--   (11, 'Sample Terminal', 'terminal', 'Sample Address',
--    'Sample record.', 'active');

-- Edit a location:
-- UPDATE locations
-- SET address = 'Updated sample address',
--     description = 'Updated sample description.'
-- WHERE location_id = 19;

-- Deactivate a location instead of deleting a referenced record:
-- UPDATE locations SET status = 'inactive' WHERE location_id = 19;


-- ---------------------------------------------------------------------
-- FEATURE 11: Administrator - update a fare while preserving history
-- This transaction closes the old active fare and inserts a new one.
-- ---------------------------------------------------------------------
-- START TRANSACTION;
-- SET @fare_route_id = 1;
-- SET @fare_type_id = 1;
-- SET @new_effective_date = '2027-01-01';
-- SET @new_minimum_fare = 14.00;
-- SET @new_fare_per_km = 1.60;
-- SET @new_total_fare = 16.00;
--
-- UPDATE route_fares
-- SET expiry_date = DATE_SUB(@new_effective_date, INTERVAL 1 DAY),
--     status = 'expired'
-- WHERE route_id = @fare_route_id
--   AND fare_type_id = @fare_type_id
--   AND status = 'active';
--
-- INSERT INTO route_fares
--   (route_id, fare_type_id, minimum_fare, fare_per_km,
--    total_estimated_fare, effective_date, expiry_date, status)
-- VALUES
--   (@fare_route_id, @fare_type_id, @new_minimum_fare, @new_fare_per_km,
--    @new_total_fare, @new_effective_date, NULL, 'active');
-- COMMIT;

-- Current and historical fare records for route 1:
SELECT
  rf.fare_id,
  ft.fare_type_name,
  rf.total_estimated_fare,
  rf.effective_date,
  rf.expiry_date,
  rf.status
FROM route_fares AS rf
JOIN fare_types AS ft ON ft.fare_type_id = rf.fare_type_id
WHERE rf.route_id = 1
ORDER BY rf.effective_date DESC, ft.fare_type_id;


-- ---------------------------------------------------------------------
-- FEATURE 12: Administrator - manage transport types and fare categories
-- ---------------------------------------------------------------------
-- INSERT INTO transportation_types (transport_name, description, status)
-- VALUES ('Van', 'Sample van service.', 'active');

-- UPDATE transportation_types
-- SET description = 'Updated sample description.'
-- WHERE transport_type_id = 1;

-- UPDATE transportation_types SET status = 'inactive' WHERE transport_type_id = 5;

-- INSERT INTO fare_types
--   (fare_type_name, description, discount_percentage, status)
-- VALUES
--   ('Sample Category', 'Sample fare category.', 10.00, 'active');

-- UPDATE fare_types
-- SET discount_percentage = 20.00
-- WHERE fare_type_id = 2;

-- UPDATE fare_types SET status = 'inactive' WHERE fare_type_id = 5;


-- ---------------------------------------------------------------------
-- FEATURE 13: Record an administrator activity
-- In PHP, use the logged-in administrator's user_id.
-- ---------------------------------------------------------------------
-- INSERT INTO admin_activity_logs
--   (admin_id, action_type, table_affected, record_id, action_description)
-- VALUES
--   (1, 'UPDATE', 'routes', 1, 'Updated route JEEP-LD-01.');

SELECT
  al.log_id,
  u.full_name AS administrator,
  al.action_type,
  al.table_affected,
  al.record_id,
  al.action_description,
  al.created_at
FROM admin_activity_logs AS al
JOIN users AS u ON u.user_id = al.admin_id
ORDER BY al.created_at DESC
LIMIT 20;


-- ---------------------------------------------------------------------
-- FEATURE 14: Dashboard statistics
-- ---------------------------------------------------------------------
SELECT
  (SELECT COUNT(*) FROM users WHERE role = 'commuter' AND status = 'active') AS active_commuters,
  (SELECT COUNT(*) FROM routes WHERE status = 'active') AS active_routes,
  (SELECT COUNT(*) FROM locations WHERE status = 'active') AS active_locations,
  (SELECT COUNT(*) FROM transportation_types WHERE status = 'active') AS active_transport_types,
  (SELECT COUNT(*) FROM route_transfers) AS transfer_connections,
  (SELECT COUNT(*) FROM route_fares WHERE status = 'active') AS active_fare_records,
  (SELECT COUNT(*) FROM saved_routes) AS saved_routes,
  (SELECT COUNT(*) FROM search_history) AS total_searches,
  (SELECT COUNT(*) FROM search_history WHERE search_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)) AS searches_last_7_days;

-- Most searched origin-destination pairs:
SELECT
  o.location_name AS origin,
  d.location_name AS destination,
  COUNT(*) AS search_count
FROM search_history AS sh
JOIN locations AS o ON o.location_id = sh.origin_id
JOIN locations AS d ON d.location_id = sh.destination_id
GROUP BY o.location_name, d.location_name
ORDER BY search_count DESC, origin, destination
LIMIT 5;

-- Recent administrator actions:
SELECT
  u.full_name AS administrator,
  al.action_type,
  al.table_affected,
  al.record_id,
  al.created_at
FROM admin_activity_logs AS al
JOIN users AS u ON u.user_id = al.admin_id
ORDER BY al.created_at DESC
LIMIT 5;
