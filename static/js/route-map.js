/* SakayGuide interactive journey map (Find My Route).

   Renders ONE map under the journey results and redraws it whenever the
   commuter selects another route card:

   - green pin  = starting point          (payload.origin)
   - red pin    = destination             (payload.destination)
   - blue pins  = intermediate stops      (payload.legs[n].stops)
   - orange pins= transfer locations      (payload.transfer_points)
   - small violet dots = landmarks        (payload.landmarks)
   - solid coloured line per ride       = OpenStreetMap road geometry
     fetched from the keyless OSRM demo server (router.project-osrm.org)
   - dashed grey line (fallback) = clearly-labelled APPROXIMATE connection
     between the recorded stops - never presented as the real road path.

   P R O G R E S S I V E   R E N D E R I N G :
   markers and a dashed stop-to-stop preview are drawn IMMEDIATELY from
   database coordinates, so the map is never blank while the network is
   busy. When the OSRM road geometry arrives the dashed preview is
   upgraded to the solid road path. If the network blocks OSRM the map
   simply keeps the labelled approximate lines.

   The basemap uses free keyless tile services (Esri World Street Map,
   with OpenStreetMap's volunteer tiles as the automatic fallback). If
   both fail, an explanatory note is shown while the markers, popups and
   route lines keep working from the database.

   If Leaflet cannot load (offline demo), the map degrades to a text note
   while the journey details stay visible.
*/
(function () {
  'use strict';

  /* Kabankalan City (OpenStreetMap, Oct 2026): poblacion centre and a
     generous clamp boundary so the view can never drift to other towns. */
  var CITY_CENTER = [9.9926, 122.8135];
  var CITY_BOUNDS = [[9.70, 122.66], [10.12, 122.99]];

  /* Free basemap providers, tried in order; both keyless, no API key.
     Esri World Street Map is the default: the OpenStreetMap volunteer
     tile servers block networks their usage policy flags (they answer
     with a 403 "Access blocked" IMAGE, which Leaflet cannot detect as a
     tile error), and the CARTO public endpoint now watermarks keyless
     tiles with "API KEY REQUIRED". Esri needs no key and its required
     attribution credits OpenStreetMap contributors too.
     tile.openstreetmap.org stays as the automatic fallback. */
  var TILE_PROVIDERS = [
    {
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
      attribution:
        'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; ' +
        '<a href="https://www.openstreetmap.org/copyright">' +
        'OpenStreetMap</a> contributors &middot; ' +
        'Ride paths via <a href="https://router.project-osrm.org/">OSRM</a>',
    },
    {
      url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">' +
        'OpenStreetMap</a> contributors &middot; ' +
        'Ride paths via <a href="https://router.project-osrm.org/">OSRM</a>',
    },
  ];

  /* Free public OSRM instance on OpenStreetMap data; no API key. */
  var OSRM_BASE = 'https://router.project-osrm.org/route/v1/driving/';
  var OSRM_TIMEOUT_MS = 8000;

  /* Consecutive tile errors before the next basemap provider is tried. */
  var TILE_ERROR_LIMIT = 6;

  var journeyData = [];
  var mapLocations = [];
  var mapLocationCoords = [];
  var locationMarkers = {};
  var map = null;
  var lineLayer = null;   /* route lines (upgraded in background)      */
  var markerLayer = null; /* green/red/blue/orange pins + landmark dots */
  var tileLayer = null;
  var currentIndex = -1;
  var drewStreetGeometry = false;
  var drewApproximate = false;
  var roadPending = false;  /* OSRM answer still on the way            */
  var tilesFailed = false;
  var tileErrors = 0;
  var tileProviderIndex = 0;

  /* ------------------------------------------------------------------ */
  /* Helpers                                                             */
  /* ------------------------------------------------------------------ */
  function readEmbeddedData() {
    var dataEl = document.getElementById('journey-maps');
    try {
      journeyData = JSON.parse((dataEl && dataEl.textContent) || '[]');
    } catch (error) {
      journeyData = [];
    }

    var locationsEl = document.getElementById('kabankalan-locations');
    try {
      mapLocations = JSON.parse((locationsEl && locationsEl.textContent) || '[]');
    } catch (error) {
      mapLocations = [];
    }
  }

  /* SVG pin shaped like a teardrop marker with a built-in white dot. */
  function pinIcon(color) {
    return L.divIcon({
      className: 'sg-pin-wrap',
      html:
        '<svg class="sg-pin" viewBox="0 0 26 36" width="26" height="36" ' +
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
        '<path d="M13 0C5.8 0 0 5.8 0 13c0 7.6 9.6 17.6 12.3 23.4a.8.8 0 0 0 1.4 0C16.4 30.6 26 20.6 26 13 26 5.8 20.2 0 13 0z" fill="' + color + '" stroke="#ffffff" stroke-width="1.5"/>' +
        '<circle cx="13" cy="13" r="4.6" fill="#ffffff"/></svg>',
      iconSize: [26, 36],
      iconAnchor: [13, 35],
      popupAnchor: [0, -30],
    });
  }

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text === null || text === undefined ? '' : String(text);
    return div.innerHTML;
  }

  function popupTitle(label, color) {
    return (
      '<div class="sg-popup">' +
      '<span class="sg-popup-dot" style="background:' + color + '"></span>' +
      '<strong>' + escapeHtml(label) + '</strong>'
    );
  }

  function markerKey(name, lat, lng) {
    return name + '|' + lat.toFixed(6) + '|' + lng.toFixed(6);
  }

  /* Every recorded Kabankalan City location, drawn as a small dot under
     the journey-specific pins. */
  function addAllLocationMarkers() {
    mapLocationCoords = [];
    locationMarkers = {};

    mapLocations.forEach(function (location) {
      if (location.latitude === null || location.latitude === undefined ||
          location.longitude === null || location.longitude === undefined) {
        return;
      }
      var active = !location.status || location.status === 'active';
      var isBarangay = location.location_type === 'barangay';
      var markerColor = active
        ? (isBarangay ? '#7c3aed' : '#64748b')
        : '#adb5bd';
      var latlng = [Number(location.latitude), Number(location.longitude)];
      mapLocationCoords.push(latlng);

      var marker = L.circleMarker(latlng, {
        radius: isBarangay ? 6 : 5,
        color: '#ffffff',
        weight: 2,
        fillColor: markerColor,
        fillOpacity: 0.9,
      });
      marker
        .bindPopup(
          popupTitle(location.location_name, markerColor) +
          '<div class="sg-popup-sub">' +
          escapeHtml(location.location_type) + ' &middot; ' +
          escapeHtml(location.barangay__barangay_name || '') + '</div>' +
          (location.address
            ? '<div class="sg-popup-line">' +
              escapeHtml(location.address) + '</div>'
            : '') +
          (active ? '' :
            '<div class="sg-popup-line">Inactive location</div>') +
          '</div>'
        )
        .bindTooltip(location.location_name, {
          direction: 'top',
          offset: [0, -6],
        })
        .addTo(markerLayer);
      locationMarkers[String(location.location_id)] = marker;
    });
  }

  /* ------------------------------------------------------------------ */
  /* Road path from the keyless OSRM demo server                          */
  /* ------------------------------------------------------------------ */
  function roadPathFor(orderedStops) {
    var points = [];
    orderedStops.forEach(function (stop) {
      if (stop.lat === null || stop.lat === undefined ||
          stop.lng === null || stop.lng === undefined) {
        return;
      }
      points.push([stop.lat, stop.lng]);
    });
    /* Need at least two distinct coordinates for a road path. */
    if (points.length < 2) {
      return Promise.resolve(null);
    }
    if (
      points.length === 2 &&
      points[0][0] === points[1][0] &&
      points[0][1] === points[1][1]
    ) {
      return Promise.resolve(null);
    }

    var coordsParam = points
      .map(function (p) { return p[1].toFixed(6) + ',' + p[0].toFixed(6); })
      .join(';');
    var url =
      OSRM_BASE + coordsParam +
      '?overview=full&geometries=geojson&alternatives=false&steps=false';

    var controller = typeof AbortController === 'function'
      ? new AbortController() : null;
    var timer = controller
      ? window.setTimeout(function () { controller.abort(); }, OSRM_TIMEOUT_MS)
      : null;

    return fetch(url, { signal: controller ? controller.signal : undefined })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('OSRM HTTP ' + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        if (timer) { window.clearTimeout(timer); }
        if (!data || data.code !== 'Ok' || !data.routes || !data.routes.length ||
            !data.routes[0].geometry || !data.routes[0].geometry.coordinates) {
          return null;
        }
        return data.routes[0].geometry.coordinates.map(function (c) {
          return [c[1], c[0]]; /* GeoJSON [lng, lat] -> Leaflet [lat, lng] */
        });
      })
      .catch(function () {
        if (timer) { window.clearTimeout(timer); }
        return null; /* offline / blocked / bad response -> fallback */
      });
  }

  function drawLegs(cfg) {
    var pending = [];
    cfg.legs.forEach(function (leg) {
      pending.push(roadPathFor(leg.stops).then(function (roadLatLngs) {
        return { leg: leg, road: roadLatLngs };
      }));
    });
    return Promise.all(pending);
  }

  /* ------------------------------------------------------------------ */
  /* Drawing helpers (all coordinates come from the database)             */
  /* ------------------------------------------------------------------ */
  function addRoadPathLine(coords, color) {
    /* solid road path with a light casing line for readability */
    L.polyline(coords, {
      color: '#ffffff',
      weight: 8,
      opacity: 0.55,
      lineCap: 'round',
      lineJoin: 'round',
    }).addTo(lineLayer);
    L.polyline(coords, {
      color: color,
      weight: 5,
      opacity: 0.95,
      lineCap: 'round',
      lineJoin: 'round',
    }).addTo(lineLayer);
    drewStreetGeometry = true;
  }

  function addApproximateLine(stops, color) {
    var coords = [];
    stops.forEach(function (stop) {
      if (stop.lat !== null && stop.lat !== undefined &&
          stop.lng !== null && stop.lng !== undefined) {
        coords.push([stop.lat, stop.lng]);
      }
    });
    if (coords.length < 2) {
      return;
    }
    L.polyline(coords, {
      color: color,
      weight: 4,
      opacity: 0.85,
      dashArray: '2 8',
      lineCap: 'round',
    }).addTo(lineLayer);
    drewApproximate = true;
  }

  function addMarkers(cfg) {
    var seen = {};

    /* Intermediate stops first (blue), then transfers (orange), so the
       orange transfer markers sit on top at shared locations. */
    cfg.legs.forEach(function (leg) {
      leg.stops.forEach(function (stop) {
        if (stop.lat === null || stop.lat === undefined) { return; }
        var key = 'stop' + markerKey(stop.name, stop.lat, stop.lng);
        if (seen[key]) { return; }
        if (stop.role !== 'intermediate') { return; }
        seen[key] = true;
        L.marker([stop.lat, stop.lng], { icon: pinIcon('#1a7fd4') })
          .bindPopup(
            popupTitle(stop.name, '#1a7fd4') +
            '<div class="sg-popup-sub">Stop on ride ' + (leg.leg_index + 1) +
            ' (' + escapeHtml(leg.route_code) + ')</div>' +
            '<div class="sg-popup-line">About ' + stop.time +
            ' min from the route start</div></div>'
          )
          .addTo(markerLayer);
      });
    });

    (cfg.transfer_points || []).forEach(function (transfer) {
      if (transfer.lat === null || transfer.lat === undefined) { return; }
      var key = 'tr' + markerKey(transfer.name, transfer.lat, transfer.lng);
      if (seen[key]) { return; }
      seen[key] = true;
      L.marker([transfer.lat, transfer.lng], { icon: pinIcon('#f0932b') })
        .bindPopup(
          popupTitle(transfer.name, '#f0932b') +
          '<div class="sg-popup-sub">Transfer point (' +
          escapeHtml(transfer.from_code) + ' &rarr; ' +
          escapeHtml(transfer.to_code) + ')</div>' +
          '<div class="sg-popup-line">' +
          escapeHtml(transfer.instructions) + '</div>' +
          (transfer.fare
            ? '<div class="sg-popup-line">Additional fare: PHP ' +
              transfer.fare + '</div>'
            : '') +
          '</div>'
        )
        .addTo(markerLayer);
    });

    (cfg.landmarks || []).forEach(function (landmark) {
      if (landmark.lat === null || landmark.lat === undefined) { return; }
      var key = 'lm' + markerKey(landmark.name, landmark.lat, landmark.lng);
      if (seen[key]) { return; }
      seen[key] = true;
      L.circleMarker([landmark.lat, landmark.lng], {
        radius: 6,
        color: '#ffffff',
        weight: 2,
        fillColor: '#8b5cf6',
        fillOpacity: 0.9,
      })
        .bindPopup(
          popupTitle(landmark.name, '#8b5cf6') +
          '<div class="sg-popup-sub">Landmark on ' +
          escapeHtml(landmark.route_code) + '</div>' +
          (landmark.description
            ? '<div class="sg-popup-line">' +
              escapeHtml(landmark.description) + '</div>'
            : '') +
          (landmark.distance
            ? '<div class="sg-popup-line">~' + landmark.distance +
              ' km from the route origin</div>'
            : '') +
          '</div>'
        )
        .addTo(markerLayer);
    });

    /* Starting point (green) and destination (red) added last so they are
       never hidden underneath other markers that share the same place. */
    if (cfg.origin && cfg.origin.verified) {
      L.marker([cfg.origin.lat, cfg.origin.lng], { icon: pinIcon('#2e8540') })
        .bindPopup(
          popupTitle(cfg.origin.name, '#2e8540') +
          '<div class="sg-popup-sub">Your starting point</div>' +
          (cfg.origin.address
            ? '<div class="sg-popup-line">' +
              escapeHtml(cfg.origin.address) + '</div>'
            : '') +
          '</div>'
        )
        .addTo(markerLayer);
    }
    if (cfg.destination && cfg.destination.verified) {
      L.marker(
        [cfg.destination.lat, cfg.destination.lng],
        { icon: pinIcon('#d63939') },
      )
        .bindPopup(
          popupTitle(cfg.destination.name, '#d63939') +
          '<div class="sg-popup-sub">Your destination</div>' +
          (cfg.destination.address
            ? '<div class="sg-popup-line">' +
              escapeHtml(cfg.destination.address) + '</div>'
            : '') +
          '</div>'
        )
        .addTo(markerLayer);
    }
  }

  /* ------------------------------------------------------------------ */
  /* Drawing one journey: instant preview, then the road upgrade          */
  /* ------------------------------------------------------------------ */
  function drawInstantPreview(cfg) {
    /* First pass - purely local, no network: all Kabankalan City
       locations, then the dashed stop-to-stop preview and every
       journey marker. The map is populated right away. */
    addAllLocationMarkers();
    cfg.legs.forEach(function (leg) {
      addApproximateLine(leg.stops, leg.color);
    });
    addMarkers(cfg);
    roadPending = true;
    renderNotes(cfg);
  }

  function upgradeToRoadPaths(index, cfg) {
    drawLegs(cfg).then(function (results) {
      if (index !== currentIndex) {
        return; /* a newer selection superseded this slow response */
      }
      roadPending = false;
      var anyRoad = results.some(function (item) {
        return item.road && item.road.length > 1;
      });
      if (anyRoad) {
        lineLayer.clearLayers();
        drewStreetGeometry = false;
        drewApproximate = false;
        results.forEach(function (item) {
          if (item.road && item.road.length > 1) {
            addRoadPathLine(item.road, item.leg.color);
          } else {
            addApproximateLine(item.leg.stops, item.leg.color);
          }
        });
      }
      renderNotes(cfg);
    });
  }

  function focusMap(cfg) {
    if (!cfg.journey_available && mapLocationCoords.length > 1) {
      /* No journey: show every recorded Kabankalan City location. */
      map.fitBounds(L.latLngBounds(mapLocationCoords), {
        padding: [28, 28],
        maxZoom: 13,
      });
    } else if (cfg.bounds) {
      map.fitBounds(L.latLngBounds(cfg.bounds), {
        padding: [28, 28],
        maxZoom: 15,
      });
    } else if (cfg.has_markers && cfg.center) {
      map.setView([cfg.center.lat, cfg.center.lng], 14);
    } else {
      map.setView(CITY_CENTER, 12);
    }
    map.invalidateSize();
  }

  function renderNotes(cfg) {
    var notes = document.getElementById('sg-map-notes');
    var label = document.getElementById('sg-map-route-label');
    if (label) {
      var timeText = '';
      if (
        cfg.journey_available &&
        cfg.total_time !== null &&
        cfg.total_time !== undefined
      ) {
        timeText = ' \u00b7 est. ' + cfg.total_time + ' min';
      }
      label.textContent = cfg.journey_available
        ? cfg.label + ' \u00b7 ' + cfg.rides +
          ' ride' + (cfg.rides === 1 ? '' : 's') + timeText
        : cfg.label + ' \u00b7 no journey found';
    }
    if (!notes) { return; }

    var html = '';
    if (cfg.journey_available) {
      if (drewStreetGeometry) {
        html += '<div><i class="ti ti-road me-1"></i>Solid coloured lines ' +
          'follow OpenStreetMap road geometry via the free OSRM routing ' +
          'service (no API key).</div>';
      }
      if (drewApproximate && !roadPending) {
        html += '<div><i class="ti ti-alert-circle me-1"></i>The dashed ' +
          'line is an <strong>approximate connection</strong> between the ' +
          'recorded database stops - the road path service was ' +
          'unreachable, so this is not presented as a verified road ' +
          'route.</div>';
      }
      if (roadPending) {
        html += '<div><i class="ti ti-loader-2 me-1"></i>The dashed ' +
          'preview lines are <strong>approximate</strong> connections of ' +
          'the recorded stops; the exact OpenStreetMap road paths are ' +
          'being fetched in the background and will replace them.</div>';
      }
    } else {
      html +=
        '<div><i class="ti ti-map-pin me-1"></i>All ' +
        mapLocationCoords.length + ' recorded Kabankalan City locations are ' +
        'pinned. The starting point and destination are highlighted - no ' +
        'connecting line is drawn, and none is invented.</div>';
    }
    if (cfg.unverified_names && cfg.unverified_names.length) {
      html += '<div class="mt-1"><i class="ti ti-map-pin-off me-1"></i>' +
        'Map position not yet verified for: <strong>' +
        cfg.unverified_names.map(escapeHtml).join(', ') + '</strong>. ' +
        'They still appear in the journey instructions above.</div>';
    }
    if (tilesFailed) {
      html += '<div class="mt-1 sg-map-fetch-error">' +
        '<i class="ti ti-wifi-off me-1"></i>Neither free basemap could ' +
        'load right now (Esri and the OpenStreetMap fallback). The ' +
        'markers, popups and route lines still show correctly from the ' +
        'database coordinates - only the street background is missing.</div>';
    }
    if (!cfg.journey_available && !cfg.has_markers) {
      html += '<div class="mt-1"><i class="ti ti-info-circle me-1"></i>' +
        'Neither location had verified coordinates, so the map shows ' +
        'Kabankalan City as a whole.</div>';
    }
    notes.innerHTML = html;
  }

  function selectJourney(index, options) {
    var cfg = journeyData[index];
    if (!cfg) { return; }

    /* Re-selecting the journey that is already on the map only needs to
       scroll (button clicks bubble up from the card); no redraw. */
    if (index === currentIndex && map && markerLayer.getLayers().length) {
      if (options && options.scroll) {
        scrollToMap();
      }
      return;
    }

    currentIndex = index;
    drewStreetGeometry = false;
    drewApproximate = false;
    roadPending = false;

    document.querySelectorAll('.journey-card').forEach(function (card) {
      card.classList.toggle('is-active', card.dataset.journeyIndex === String(index));
    });
    document.querySelectorAll('.sg-journey-panel').forEach(function (panel) {
      panel.hidden = panel.id !== 'journey-panel-' + index;
    });

    if (!map) { return; }
    lineLayer.clearLayers();
    markerLayer.clearLayers();

    if (typeof cfg !== 'object' || !cfg.origin) {
      map.setView(CITY_CENTER, 12);
      return;
    }

    drawInstantPreview(cfg);
    focusMap(cfg);
    if (options && options.scroll) {
      scrollToMap();
    }
    /* Quietly fetch the real road geometry and upgrade the lines. */
    upgradeToRoadPaths(index, cfg);
  }

  function scrollToMap() {
    var card = document.getElementById('sg-map-card');
    if (card && card.scrollIntoView) {
      card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  /* ------------------------------------------------------------------ */
  /* Map creation                                                         */
  /* ------------------------------------------------------------------ */
  function addTileLayer(providerIndex) {
    var provider = TILE_PROVIDERS[providerIndex];
    return L.tileLayer(provider.url, {
      maxZoom: 19,
      attribution: provider.attribution,
    }).addTo(map);
  }

  function createMap(container) {
    map = L.map(container, {
      scrollWheelZoom: false,
      attributionControl: true,
      maxBounds: L.latLngBounds(CITY_BOUNDS),
      maxBoundsViscosity: 0.9,
      minZoom: 9,
      maxZoom: 18,
    });

    /* Line layer first, marker layer second: Leaflet still stacks
       markers above vectors anyway, this just keeps the upgrade pass
       (which clears ONLY the lines) simple. */
    lineLayer = L.layerGroup().addTo(map);
    markerLayer = L.layerGroup().addTo(map);
    tileLayer = addTileLayer(0);

    /* If a basemap is unreachable (blocked network, offline demo),
       automatically try the next free provider before giving up.
       Markers, popups and route lines never depend on the basemap -
       they come from the database. */
    map.on('tileerror', function () {
      if (tilesFailed) { return; }
      tileErrors += 1;
      if (tileErrors < TILE_ERROR_LIMIT) { return; }
      if (tileProviderIndex < TILE_PROVIDERS.length - 1) {
        tileProviderIndex += 1;
        tileErrors = 0;
        map.removeLayer(tileLayer);
        tileLayer = addTileLayer(tileProviderIndex);
        return;
      }
      tilesFailed = true;
      if (journeyData && journeyData[currentIndex]) {
        renderNotes(journeyData[currentIndex]);
      }
    });

    /* Reset-view button so commuters can zoom the whole journey back in. */
    var ResetControl = L.Control.extend({
      options: { position: 'topleft' },
      onAdd: function () {
        var div = L.DomUtil.create(
          'div', 'leaflet-bar sg-map-reset-wrap',
        );
        var a = L.DomUtil.create('a', 'sg-map-reset', div);
        a.href = '#';
        a.title = 'Reset view to the whole journey';
        a.setAttribute('role', 'button');
        a.innerHTML = '&#9974; Reset view';
        L.DomEvent.on(a, 'click', function (event) {
          L.DomEvent.preventDefault(event);
          if (journeyData && journeyData[currentIndex]) {
            focusMap(journeyData[currentIndex]);
          } else {
            map.setView(CITY_CENTER, 12);
          }
        });
        return div;
      },
    });
    map.addControl(new ResetControl());

    map.setView(CITY_CENTER, 12);
    return map;
  }

  function bindSelection() {
    document.querySelectorAll('[data-journey-select]').forEach(function (el) {
      el.addEventListener('click', function (event) {
        event.preventDefault();
        selectJourney(parseInt(el.dataset.journeyIndex, 10), {
          scroll: el.classList.contains('sg-select-journey'),
        });
      });
      /* Keyboard activation for the card itself (role="button"). */
      if (el.tagName === 'ARTICLE') {
        el.addEventListener('keydown', function (event) {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            selectJourney(parseInt(el.dataset.journeyIndex, 10), {
              scroll: false,
            });
          }
        });
      }
    });
  }

  function bindLocationList() {
    var items = document.querySelectorAll('[data-map-location-id]');
    Array.prototype.forEach.call(items, function (item) {
      item.addEventListener('click', function () {
        var marker = locationMarkers[String(item.dataset.mapLocationId)];
        if (!marker || !map) { return; }

        Array.prototype.forEach.call(items, function (other) {
          other.classList.toggle('is-active', other === item);
        });
        map.setView(marker.getLatLng(), 16, { animate: true });
        marker.openPopup();
      });
    });
  }

  function init() {
    readEmbeddedData();
    var container = document.getElementById('sg-journey-map');
    if (!container) { return; }

    if (typeof L === 'undefined') {
      var gpsButton = document.querySelector('[data-gps-toggle]');
      var gpsStatus = document.querySelector('[data-gps-status]');
      if (gpsButton) {
        gpsButton.hidden = true;
      }
      if (gpsStatus) {
        gpsStatus.hidden = true;
      }
      container.classList.add('sg-map-offline');
      container.innerHTML =
        '<div class="sg-map-fallback">' +
        '<i class="ti ti-map-pin-off"></i> The interactive map needs an ' +
        'internet connection to load Leaflet and the OpenStreetMap tiles. ' +
        'The stops, fares, landmarks and travel times beside the map are ' +
        'still accurate for this search.</div>';
      bindSelection();
      bindLocationList();
      document.querySelectorAll('.sg-journey-panel').forEach(function (panel) {
        panel.hidden = panel.id !== 'journey-panel-0';
      });
      return;
    }

    createMap(container);
    if (window.SakayGuideGPS) {
      window.SakayGuideGPS.attach(map, {
        button: document.querySelector('[data-gps-toggle]'),
        status: document.querySelector('[data-gps-status]'),
      });
    }
    bindSelection();
    bindLocationList();

    /* Leaflet measures the container once it becomes visible. */
    window.setTimeout(function () {
      try {
        map.invalidateSize();
        selectJourney(0, { scroll: false });
      } catch (error) {
        console.error('SakayGuide journey map error:', error);
      }
    }, 60);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
