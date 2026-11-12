# Google Maps setup for SakayGuide

SakayGuide now uses **Google Maps as the primary map engine** on the route
pages. The existing Leaflet/OpenStreetMap map stays loaded as an automatic
fallback, so the site still works when the Google key is missing, rejected,
over quota, or the Google script cannot be reached.

Everything drawn on the map comes from the existing `sakayguide_db` MySQL
tables. No marker, fare, stop or route is hard-coded in JavaScript.

---

## 1. Create and restrict the API key

1. Open <https://console.cloud.google.com/> and create (or select) a project.
2. Go to **APIs & Services → Library** and enable both:
   - **Maps JavaScript API**
   - **Directions API**
3. Go to **APIs & Services → Credentials → Create credentials → API key**.
4. Click **Restrict key** and configure:

   **Application restrictions → HTTP referrers (web sites)**

   Add the origins that will load the map, for example:

   ```
   http://localhost:8000/*
   http://127.0.0.1:8000/*
   http://localhost/*
   https://your-production-domain.example/*
   ```

   **API restrictions → Restrict key**

   Select only:
   - Maps JavaScript API
   - Directions API

5. Make sure billing is enabled for the Google Cloud project. Google Maps
   Platform gives a recurring free usage allowance, but an active billing
   account is required.

> The browser key is intentionally delivered to the browser (all Google Maps
> JavaScript sites do this). The HTTP-referrer and API restrictions above are
> what keep it safe. Do **not** use an unrestricted key.

---

## 2. Add the key to the project

Copy `.env.example` to `.env` in the project root:

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```dotenv
GOOGLE_MAPS_API_KEY=AIza...your-restricted-browser-key...
GOOGLE_MAPS_LANGUAGE=en
GOOGLE_MAPS_REGION=PH
```

The project already loads `.env` from `mysite/settings.py` (real process
environment variables still win). Restart the Django server after changing it:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

`.env` is ignored by Git; `.env.example` is safe to commit.

If `GOOGLE_MAPS_API_KEY` is empty, the pages automatically use the original
Leaflet/OpenStreetMap implementation. Nothing else needs to be changed.

---

## 3. What the integration does

| Feature | Source |
| --- | --- |
| 50 city markers (barangays, terminals, stops, schools, markets, landmarks) | `routes.services.map_locations()` → `locations`, `route_stops`, `routes`, `transportation_types` |
| Marker transport badges and route codes | Joined from active `routes` / `transportation_types` |
| Journey markers: origin, destination, stops, transfers, landmarks | `journey['map']` payload built by `routes.services` |
| Route line geometry / turn-by-turn steps | Google `DirectionsService`, using the recorded stops as origin/waypoint/destination |
| Alternative routes | Google Directions alternatives, drawn as dashed grey lines |
| Boarding / alighting / transfer instructions | `route_stops`, `route_transfers`, `route_fares` |
| Fares, ride times, total distance | Existing SakayGuide services (regular fare type + Haversine stop distance) |
| Transportation options panel | `routes.services.transport_options()` |
| Live GPS | Browser Geolocation API, blue overlay marker + accuracy circle |
| Fallback map | Existing `city-map.js` / `route-map.js` + OSRM road paths |

### Progressive behaviour

1. The recorded stops and a dashed stop-to-stop preview are drawn immediately
   from database coordinates.
2. Each ride then asks Google Directions for the road path and steps.
3. If Google fails for a ride, the free OSRM service supplies the road path.
4. If OSRM also fails, the dashed line remains and is labelled as approximate.
5. If the Google Maps JavaScript API itself cannot load, the page hands the
   same container to the existing Leaflet map and keeps all other features.

---

## 4. Verify it works

1. Start the server and open <http://localhost:8000/plan/>.
2. Click **Show map preview** and confirm the Google basemap and 50 pins load.
3. Click **My Current Location**, allow the browser permission prompt, and
   confirm the blue marker/accuracy circle follow the device.
4. Search for a route (for example **Bantayan → Barangay 1**).
5. On the results page:
   - select journey cards and watch the map redraw;
   - confirm the coloured ride paths and the **Google Maps directions** panel;
   - check that alternative routes appear as dashed grey lines when Google
     returns them;
   - confirm fares, ride times, boarding/alighting points and transfers still
     match the database.

GPS requires a **secure context**: `http://localhost`, `http://127.0.0.1`, or
HTTPS. A plain HTTP deployment on a LAN IP will show a clear error message.

---

## 5. Troubleshooting

| Browser console / map message | Meaning / fix |
| --- | --- |
| `RefererNotAllowedMapError` | Add the exact origin (including port) to the key's HTTP referrer list. |
| `ApiNotActivatedMapError` | Enable **Maps JavaScript API** for the project. |
| `REQUEST_DENIED` in the directions panel | Enable **Directions API**; check the key's API restrictions. |
| `OVER_QUERY_LIMIT` | The key's quota/billing limit is exhausted. The map falls back to OSRM for road paths. |
| Google script blocked / offline | The page switches to Leaflet automatically and shows a note. |
| GPS permission denied | Allow location for the site in the browser's site settings, then retry. |

The backend configuration is exposed to the route templates only through
`routes.views._google_maps_config()`; the key is read from
`settings.GOOGLE_MAPS_API_KEY` (`.env` / environment), never hard-coded in a
template or JavaScript file.

---

## 6. Files involved

- `mysite/settings.py` – `.env` loader and `GOOGLE_MAPS_*` settings.
- `routes/views.py` – passes `google_maps` config and `transport_options`.
- `routes/services.py` – database-driven map payload, distances, transport
  options, expanded location choices.
- `templates/routes/_map_assets.html` – chooses Google vs Leaflet and loads
  the correct scripts.
- `static/js/google-maps.js` – Google map, markers, DirectionsService, OSRM
  fallback, GPS overlay, automatic Leaflet hand-off.
- `static/js/city-map.js`, `static/js/route-map.js` – existing Leaflet maps,
  now exposed as fallbacks.
- `templates/routes/route_search.html`, `route_results.html`,
  `_journey_card.html`, `_journey_panel.html`, `_search_form.html` – UI.
- `static/css/routes.css` – Google map, directions, transport card and GPS
  styles, using the existing Tabler design tokens.
