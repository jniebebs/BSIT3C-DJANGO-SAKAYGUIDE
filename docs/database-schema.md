# SakayGuide Database Schema Design

**Total tables: 18** (minimum requirement: 14)
**Target database:** MySQL / MariaDB (InnoDB engine, UTF-8)

---

## Entity-Relationship Overview

The schema is organized into five logical groups:

1. **User Management** — users, roles, favorites, search_history, feedback
2. **Geography** — locations, landmarks, terminals
3. **Transport Network** — transport_types, operators, vehicles, routes, route_stops, route_segments
4. **Fare System** — fare_rules, fare_records
5. **User Engagement** — schedules, favorites, search_history, feedback

---

## Table Definitions

### 1. `users`

Stores registered user accounts.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| username | VARCHAR(50) | UNIQUE, NOT NULL |
| email | VARCHAR(100) | UNIQUE, NOT NULL |
| password_hash | VARCHAR(255) | NOT NULL |
| role_id | INT | FOREIGN KEY → roles(id) |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TIMESTAMP | ON UPDATE CURRENT_TIMESTAMP |

**Indexes:** `idx_users_role (role_id)`

---

### 2. `roles`

Stores user roles such as commuter and administrator.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| name | VARCHAR(30) | UNIQUE, NOT NULL |
| description | VARCHAR(255) | |

**Seed data:** commuter, administrator

---

### 3. `locations`

Stores places, pickup points, drop-off points, and destinations.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| name | VARCHAR(150) | NOT NULL |
| type | ENUM('pickup','dropoff','destination','terminal','landmark') | NOT NULL |
| latitude | DECIMAL(9,6) | NOT NULL, CHECK (-90 to 90) |
| longitude | DECIMAL(10,6) | NOT NULL, CHECK (-180 to 180) |
| description | TEXT | |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

**Indexes:** `idx_locations_type (type)`, `idx_locations_coords (latitude, longitude)`

---

### 4. `terminals`

Stores public transportation terminal information.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| name | VARCHAR(150) | UNIQUE, NOT NULL |
| location_id | INT | FOREIGN KEY → locations(id) |
| municipality | VARCHAR(100) | NOT NULL |
| province | VARCHAR(100) | |
| description | TEXT | |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

**Indexes:** `idx_terminals_location (location_id)`

---

### 5. `transport_types`

Stores vehicle types such as jeepney, bus, and tricycle.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| name | VARCHAR(50) | UNIQUE, NOT NULL |
| description | TEXT | |
| avg_speed_kmh | DECIMAL(5,2) | DEFAULT 20.00 |
| icon | VARCHAR(50) | |

**Seed data:** jeepney, bus, tricycle, UV express, train

---

### 6. `operators`

Stores transportation operators or service providers.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| name | VARCHAR(150) | UNIQUE, NOT NULL |
| contact_number | VARCHAR(20) | |
| contact_email | VARCHAR(100) | |
| description | TEXT | |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

---

### 7. `vehicles`

Stores vehicle information when applicable.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| plate_number | VARCHAR(20) | UNIQUE, NOT NULL |
| transport_type_id | INT | FOREIGN KEY → transport_types(id) |
| operator_id | INT | FOREIGN KEY → operators(id) |
| capacity | INT | DEFAULT 1 |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

**Indexes:** `idx_vehicles_operator (operator_id)`, `idx_vehicles_transport (transport_type_id)`

---

### 8. `routes`

Stores main transportation routes.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| code | VARCHAR(20) | UNIQUE, NOT NULL |
| name | VARCHAR(150) | NOT NULL |
| transport_type_id | INT | FOREIGN KEY → transport_types(id) |
| origin_terminal_id | INT | FOREIGN KEY → terminals(id) |
| destination_terminal_id | INT | FOREIGN KEY → terminals(id) |
| operator_id | INT | FOREIGN KEY → operators(id) |
| distance_km | DECIMAL(8,2) | DEFAULT 0.00 |
| estimated_duration_min | INT | DEFAULT 0 |
| base_fare | DECIMAL(8,2) | DEFAULT 0.00 |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TIMESTAMP | ON UPDATE CURRENT_TIMESTAMP |

**Indexes:** `idx_routes_transport (transport_type_id)`, `idx_routes_origin (origin_terminal_id)`, `idx_routes_destination (destination_terminal_id)`, `idx_routes_operator (operator_id)`

---

### 9. `route_stops`

Stores the ordered stops along each route.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| route_id | INT | FOREIGN KEY → routes(id) ON DELETE CASCADE |
| location_id | INT | FOREIGN KEY → locations(id) |
| sequence | INT | NOT NULL |
| distance_from_origin_km | DECIMAL(8,2) | DEFAULT 0.00 |
| dwell_time_seconds | INT | DEFAULT 30 |

**Constraints:**
- UNIQUE (route_id, sequence) — prevents duplicate sequence numbers
- UNIQUE (route_id, location_id) — prevents duplicate stops on same route
- CHECK (sequence > 0)

**Indexes:** `idx_route_stops_route (route_id, sequence)`

---

### 10. `route_segments`

Stores route segments and connections needed for transfers.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| from_location_id | INT | FOREIGN KEY → locations(id) |
| to_location_id | INT | FOREIGN KEY → locations(id) |
| route_id | INT | FOREIGN KEY → routes(id) ON DELETE CASCADE |
| segment_order | INT | NOT NULL |
| distance_km | DECIMAL(8,2) | DEFAULT 0.00 |
| estimated_time_min | INT | DEFAULT 0 |
| is_transfer_point | BOOLEAN | DEFAULT FALSE |
| transfer_description | VARCHAR(255) | |

**Constraints:**
- UNIQUE (route_id, segment_order)
- CHECK (from_location_id != to_location_id)

**Indexes:** `idx_segments_route (route_id, segment_order)`, `idx_segments_transfer (is_transfer_point)`

---

### 11. `fare_rules`

Stores fare calculation rules and applicable conditions.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| name | VARCHAR(100) | NOT NULL |
| transport_type_id | INT | FOREIGN KEY → transport_types(id) |
| base_fare | DECIMAL(8,2) | NOT NULL |
| fare_per_km | DECIMAL(8,2) | DEFAULT 0.00 |
| min_fare | DECIMAL(8,2) | DEFAULT 0.00 |
| max_fare | DECIMAL(8,2) | |
| discount_percent | DECIMAL(5,2) | DEFAULT 0.00 |
| condition_description | TEXT | |
| is_active | BOOLEAN | DEFAULT TRUE |
| effective_from | DATE | NOT NULL |
| effective_until | DATE | |

**Indexes:** `idx_fare_rules_transport (transport_type_id)`, `idx_fare_rules_effective (effective_from, effective_until)`

---

### 12. `fare_records`

Stores fare amounts associated with routes or segments.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| route_id | INT | FOREIGN KEY → routes(id) ON DELETE CASCADE |
| fare_rule_id | INT | FOREIGN KEY → fare_rules(id) |
| segment_id | INT | FOREIGN KEY → route_segments(id) |
| amount | DECIMAL(8,2) | NOT NULL |
| distance_km | DECIMAL(8,2) | DEFAULT 0.00 |
| passenger_type | ENUM('regular','student','senior','pwd') | DEFAULT 'regular' |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

**Constraints:**
- CHECK (amount >= 0)
- At least one of route_id or segment_id must be NOT NULL

**Indexes:** `idx_fare_records_route (route_id)`, `idx_fare_records_rule (fare_rule_id)`, `idx_fare_records_segment (segment_id)`

---

### 13. `landmarks`

Stores landmarks that help commuters identify places.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| name | VARCHAR(150) | UNIQUE, NOT NULL |
| category | VARCHAR(50) | |
| latitude | DECIMAL(9,6) | NOT NULL |
| longitude | DECIMAL(10,6) | NOT NULL |
| description | TEXT | |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

**Indexes:** `idx_landmarks_category (category)`, `idx_landmarks_coords (latitude, longitude)`

---

### 14. `route_landmarks`

Connects routes or stops with landmarks (junction table).

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| route_id | INT | FOREIGN KEY → routes(id) ON DELETE CASCADE |
| landmark_id | INT | FOREIGN KEY → landmarks(id) ON DELETE CASCADE |
| distance_m | INT | DEFAULT 0 |
| direction | ENUM('left','right','ahead','behind') | DEFAULT 'ahead' |
| description | VARCHAR(255) | |

**Constraints:**
- UNIQUE (route_id, landmark_id) — prevents duplicate associations

**Indexes:** `idx_route_landmarks_landmark (landmark_id)`

---

### 15. `schedules`

Stores published transportation schedules when available.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| route_id | INT | FOREIGN KEY → routes(id) ON DELETE CASCADE |
| day_type | ENUM('weekday','saturday','sunday','holiday') | NOT NULL |
| start_time | TIME | NOT NULL |
| end_time | TIME | NOT NULL |
| frequency_min | INT | DEFAULT 15 |
| is_active | BOOLEAN | DEFAULT TRUE |
| notes | TEXT | |

**Constraints:**
- CHECK (end_time > start_time)
- UNIQUE (route_id, day_type, start_time)

**Indexes:** `idx_schedules_route (route_id)`, `idx_schedules_day_type (day_type)`

---

### 16. `favorites`

Stores routes saved by users.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| user_id | INT | FOREIGN KEY → users(id) ON DELETE CASCADE |
| route_id | INT | FOREIGN KEY → routes(id) ON DELETE CASCADE |
| nickname | VARCHAR(100) | |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |

**Constraints:**
- UNIQUE (user_id, route_id) — prevents duplicate favorites

**Indexes:** `idx_favorites_route (route_id)`

---

### 17. `search_history`

Stores previous searches with appropriate privacy safeguards.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| user_id | INT | FOREIGN KEY → users(id) ON DELETE CASCADE |
| origin_location_id | INT | FOREIGN KEY → locations(id) |
| destination_location_id | INT | FOREIGN KEY → locations(id) |
| search_query | VARCHAR(255) | |
| searched_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| is_deleted | BOOLEAN | DEFAULT FALSE |

**Privacy safeguards:**
- `is_deleted` flag for soft-delete (user can "clear" without hard deletion)
- No exact GPS coordinates stored — only references to named locations
- user_id can be NULL for guest searches (auto-purged after 30 days via cron job)

**Indexes:** `idx_search_user (user_id)`, `idx_search_searched_at (searched_at)`, `idx_search_deleted (is_deleted)`

---

### 18. `feedback`

Stores user comments, route corrections, and reports.

| Column | Data Type | Constraints |
|---|---|---|
| id | INT | PRIMARY KEY, AUTO_INCREMENT |
| user_id | INT | FOREIGN KEY → users(id) ON DELETE SET NULL |
| route_id | INT | FOREIGN KEY → routes(id) ON DELETE CASCADE |
| type | ENUM('comment','correction','report','suggestion') | NOT NULL |
| subject | VARCHAR(150) | NOT NULL |
| message | TEXT | NOT NULL |
| status | ENUM('pending','reviewed','resolved','rejected') | DEFAULT 'pending' |
| admin_notes | TEXT | |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TIMESTAMP | ON UPDATE CURRENT_TIMESTAMP |

**Indexes:** `idx_feedback_user (user_id)`, `idx_feedback_route (route_id)`, `idx_feedback_status (status)`, `idx_feedback_type (type)`

---

## Relationships Summary

```
users ─────────────┬────< favorites >──── routes
                   │
                   ├────< search_history
                   │
                   └────< feedback >──── routes
                   │
roles ─────────────┘

locations ─┬────< terminals
           │
           ├────< route_stops
           │
           └────< route_segments (from/to)

transport_types ────< routes
                  │
                  ├────< fare_rules
                  │
                  └────< vehicles

operators ────┬──── vehicles
              │
              └──── routes

routes ────────┬────< route_stops
               ├────< route_segments
               ├────< route_landmarks >──── landmarks
               ├────< fare_records
               ├────< schedules
               ├────< favorites
               └────< feedback

fare_rules ────< fare_records

route_segments ────< fare_records (optional link)
```

### Relationship Descriptions

| Parent | Child | Type | Description |
|---|---|---|---|
| roles | users | 1:N | Each user has one role; each role has many users |
| users | favorites | 1:N | Each user can save many routes as favorites |
| users | search_history | 1:N | Each user has many search history entries |
| users | feedback | 1:N | Each user can submit many feedback items |
| routes | favorites | 1:N | Each route can be favorited by many users |
| routes | route_stops | 1:N | Each route has many ordered stops |
| routes | route_segments | 1:N | Each route has many segments |
| routes | route_landmarks | 1:N | Each route is associated with many landmarks |
| routes | fare_records | 1:N | Each route has many fare records |
| routes | schedules | 1:N | Each route has many schedule entries |
| routes | feedback | 1:N | Each route can receive many feedback items |
| locations | terminals | 1:N | Each location can host many terminals (e.g., multi-terminal complexes) |
| locations | route_stops | 1:N | Each location can appear as a stop on many routes |
| locations | route_segments | 1:N | Each location can be a segment endpoint on many routes |
| locations | search_history | 1:N | Each location can appear in many search history entries |
| transport_types | routes | 1:N | Each transport type has many routes |
| transport_types | fare_rules | 1:N | Each transport type has many fare rules |
| transport_types | vehicles | 1:N | Each transport type has many vehicles |
| operators | vehicles | 1:N | Each operator owns many vehicles |
| operators | routes | 1:N | Each operator runs many routes |
| landmarks | route_landmarks | 1:N | Each landmark is associated with many routes |
| fare_rules | fare_records | 1:N | Each fare rule generates many fare records |
| route_segments | fare_records | 1:N | Each segment can have many fare records |

---

## Constraints Summary

| Constraint Type | Tables | Purpose |
|---|---|---|
| PRIMARY KEY | All 18 tables | Uniquely identifies each row |
| FOREIGN KEY | 23 relationships | Enforces referential integrity |
| UNIQUE | 14 locations | Prevents duplicate data |
| CHECK | 8 locations | Validates data ranges (coordinates, sequence, time, amount) |
| NOT NULL | 45+ columns | Ensures required data is always present |
| ENUM | 6 columns | Restricts values to a predefined set |
| ON DELETE CASCADE | 12 FK relationships | Auto-deletes child records when parent is deleted |
| ON DELETE SET NULL | 1 FK relationship | Preserves feedback if user is deleted |
| ON UPDATE CURRENT_TIMESTAMP | 5 tables | Auto-updates modification timestamp |

---

## How Requirements Are Met

### Support for Direct Routes and Trips Requiring Transfers

- **Direct routes:** `routes` table stores origin and destination terminals; `route_stops` provides the ordered path; `fare_records` stores the fare for the complete journey.
- **Transfers:** `route_segments` marks transfer points with `is_transfer_point = TRUE` and `transfer_description`; commuters can chain multiple routes by matching `to_location_id` of one segment with `from_location_id` of another.

### Support for Ordered Route Stops

- `route_stops.sequence` (INT, CHECK > 0) defines the stop order.
- UNIQUE (route_id, sequence) prevents two stops from sharing the same position.
- UNIQUE (route_id, location_id) prevents the same location from appearing twice on one route.

### Support for Estimated Fares

- `routes.base_fare` stores the flag-down fare.
- `fare_rules` stores per-km rates, discounts, and conditions.
- `fare_records` stores the computed fare amount for each route or segment, linked to the applicable fare rule.

### Support for Landmarks

- `landmarks` stores notable places with coordinates and categories.
- `route_landmarks` associates landmarks with routes, including direction and distance to help commuters identify stops.

### Prevention of Unnecessary Duplicate Data

- UNIQUE constraints on usernames, emails, route codes, plate numbers, and terminal names.
- UNIQUE constraints on junction tables (favorites, route_landmarks) prevent duplicate associations.
- ENUM types restrict columns to valid values, eliminating free-text inconsistencies.
- Foreign keys ensure all references point to valid records.

### Privacy Safeguards for Search History

- Soft-delete via `is_deleted` flag.
- No raw GPS coordinates stored — only references to named `locations`.
- Guest searches (user_id NULL) can be auto-purged via scheduled cleanup.
- Users can clear their own search history without data loss to analytics.

---

## Notes for Beginners

1. **Start with seed data** — Populate `roles` (commuter, administrator) and `transport_types` (jeepney, bus, tricycle) first, as other tables depend on them.

2. **Cascading deletes** — When a route is deleted, all its stops, segments, fare records, schedules, and favorites are automatically removed. This keeps the database clean without manual cleanup.

3. **ENUM vs lookup tables** — Simple fixed lists (like day_type or passenger_type) use ENUM for simplicity. Lists that may grow (like transport types or roles) use separate tables for flexibility.

4. **Decimal for money** — All monetary values use DECIMAL(8,2) to avoid floating-point rounding errors. Never use FLOAT or DOUBLE for currency.

5. **Timestamps** — `created_at` and `updated_at` fields help with auditing and debugging. They are managed automatically by the database.
