/* SakayGuide Google Maps engine.

   This is the PRIMARY map implementation for the two route pages:

     - search page : #sg-search-map (created lazily when "Show map preview"
                     is pressed, exactly like the existing Leaflet map)
     - results page: #sg-journey-map (created immediately and redrawn when
                     the commuter selects another journey card)

   Everything shown on the map comes from the SakayGuide MySQL database:
   the 50 recorded locations are embedded by Django as JSON, and the journey
   payload contains every recorded stop, transfer point and landmark. No
   marker or route is hard-coded here.

   Road geometry / turn-by-turn instructions:
     1. Google Maps DirectionsService (primary), using the recorded stops of
        each ride as origin, waypoints and destination. Alternative routes
        returned by Google are drawn as dashed grey lines and listed in the
        directions panel.
     2. If Directions is unavailable (API not enabled, quota, ZERO_RESULTS,
        offline), the free OSRM demo server is used for the road geometry.
     3. If both fail, the dashed stop-to-stop preview stays on the map and is
        explicitly labelled as approximate.

   Live GPS:
     The browser Geolocation API is watched while the "My Current Location"
     button is on. A pulsing blue marker and accuracy circle follow the
     device in real time. Coordinates are never sent to or stored on the
     server. Permission, unsupported-browser and timeout errors are shown in
     the status line next to the button.

   Fallback:
     If the Google Maps JavaScript API cannot load (missing/invalid key,
     network failure, blocked script), the page automatically hands the same
     container to the existing Leaflet/OpenStreetMap implementation exposed
     by city-map.js / route-map.js. The rest of the SakayGuide page (fares,
     stops, steps, save-route form, auth) is untouched.
*/
(function () {
  'use strict';

  var CONFIG = readJson('google-maps-config', null);

  var OSRM_BASE = 'https://router.project-osrm.org/route/v1/driving/';
  var OSRM_TIMEOUT_MS = 8000;
  var GOOGLE_LOAD_TIMEOUT_MS = 15000;

  var page = null;               /* 'search' | 'journey' */
  var engine = 'google';
  var fallbackDone = false;
  var googleLoadTimer = null;

  var map = null;
  var infoWindow = null;
  var gpsController = null;

  var mapLocations = [];
  var journeyData = [];

  var baseMarkers = [];
  var baseCoords = [];
  var baseMarkerById = {};

  var journeyLines = [];
  var alternativeLines = [];
  var journeyMarkers = [];
  var previewLinesByLeg = {};

  var activeJourneyIndex = -1;
  var journeySequence = 0;
  var directionsState = emptyDirectionsState();

  var searchToggleHandler = null;

  /* ------------------------------------------------------------------ */
  /* Small helpers                                                       */
  /* ------------------------------------------------------------------ */
  function readJson(id, fallback) {
    var element = document.getElementById(id);
    if (!element) {
      return fallback;
    }
    try {
      return JSON.parse(element.textContent || '');
    } catch (error) {
      return fallback;
    }
  }

  function emptyDirectionsState() {
    return {
      pending: false,
      googleLegs: 0,
      osrmLegs: 0,
      approximateLegs: 0,
      reason: ''
    };
  }

  function escapeHtml(value) {
    var div = document.createElement('div');
    div.textContent = value === null || value === undefined ? '' : String(value);
    return div.innerHTML;
  }

  function plainText(html) {
    var div = document.createElement('div');
    div.innerHTML = html || '';
    return (div.textContent || div.innerText || '').replace(/\s+/g, ' ').trim();
  }

  function hasCoord(item) {
    return Boolean(
      item &&
      item.lat !== null && item.lat !== undefined &&
      item.lng !== null && item.lng !== undefined &&
      !isNaN(Number(item.lat)) && !isNaN(Number(item.lng))
    );
  }

  function toLatLng(item) {
    return new google.maps.LatLng(Number(item.lat), Number(item.lng));
  }

  function modeClass(name) {
    var key = String(name || '').toLowerCase();
    if (key.indexOf('jeep') !== -1) { return 'jeepney'; }
    if (key.indexOf('bus') !== -1) { return 'bus'; }
    if (key.indexOf('van') !== -1) { return 'van'; }
    if (key.indexOf('tric') !== -1) { return 'tricycle'; }
    return 'other';
  }

  function modeBadges(modes) {
    if (!modes || !modes.length) {
      return '';
    }
    return '<div class="sg-gm-modes">' + modes.map(function (mode) {
      return '<span class="sg-gm-mode sg-mode-' + modeClass(mode) + '">' +
        escapeHtml(mode) + '</span>';
    }).join('') + '</div>';
  }

  function formatDistanceMeters(meters) {
    if (meters === null || meters === undefined || isNaN(meters)) {
      return '';
    }
    if (meters < 1000) {
      return Math.round(meters) + ' m';
    }
    return (meters / 1000).toFixed(meters < 10000 ? 1 : 0) + ' km';
  }

  function formatDurationSeconds(seconds) {
    if (seconds === null || seconds === undefined || isNaN(seconds)) {
      return '';
    }
    var minutes = Math.max(1, Math.round(Number(seconds) / 60));
    if (minutes < 60) {
      return minutes + ' min';
    }
    var hours = Math.floor(minutes / 60);
    var rest = minutes % 60;
    return hours + ' hr' + (rest ? ' ' + rest + ' min' : '');
  }

  function closestElement(element, selector) {
    var node = element;
    while (node && node !== document) {
      if (node.matches && node.matches(selector)) {
        return node;
      }
      node = node.parentNode;
    }
    return null;
  }

  function removeFromMap(items) {
    items.forEach(function (item) {
      if (item && item.setMap) {
        item.setMap(null);
      }
    });
    items.length = 0;
  }

  function setText(element, text) {
    if (element) {
      element.textContent = text;
    }
  }

  function setEngineNote(text, isWarning) {
    var element = document.getElementById('sg-map-engine-note');
    if (!element) {
      return;
    }
    element.textContent = text || '';
    element.hidden = !text;
    element.classList.toggle('is-error', Boolean(isWarning));
  }

  function setSearchAttribution(engineName) {
    var element = document.getElementById('sg-map-attribution');
    if (!element) {
      return;
    }
    if (engineName === 'google') {
      element.innerHTML =
        'All ' + mapLocations.length + ' recorded locations in Kabankalan ' +
        'City are pinned - click a pin for its name, type, barangay and the ' +
        'jeepney, bus, van or tricycle routes recorded there. Base map ' +
        '&copy; Google.';
    } else {
      element.innerHTML =
        'All ' + mapLocations.length + ' recorded locations in Kabankalan ' +
        'City are pinned - click a pin for its name, type, barangay and the ' +
        'routes recorded there. Base map &copy; OpenStreetMap contributors ' +
        '(automatic fallback).';
    }
  }

  /* ------------------------------------------------------------------ */
  /* Marker icons                                                        */
  /* ------------------------------------------------------------------ */
  function pinIcon(color) {
    var svg =
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 26 36" ' +
      'width="26" height="36">' +
      '<path d="M13 0C5.8 0 0 5.8 0 13c0 7.6 9.6 17.6 12.3 23.4a.8.8 0 0 0 ' +
      '1.4 0C16.4 30.6 26 20.6 26 13 26 5.8 20.2 0 13 0z" fill="' + color +
      '" stroke="#ffffff" stroke-width="1.5"/>' +
      '<circle cx="13" cy="13" r="4.6" fill="#ffffff"/></svg>';
    return {
      url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
      scaledSize: new google.maps.Size(26, 36),
      anchor: new google.maps.Point(13, 35)
    };
  }

  function dotIcon(color) {
    var svg =
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18" ' +
      'width="18" height="18">' +
      '<circle cx="9" cy="9" r="7" fill="' + color + '" stroke="#ffffff" ' +
      'stroke-width="2"/></svg>';
    return {
      url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
      scaledSize: new google.maps.Size(18, 18),
      anchor: new google.maps.Point(9, 9)
    };
  }

  /* ------------------------------------------------------------------ */
  /* Map creation                                                        */
  /* ------------------------------------------------------------------ */
  function cityBounds() {
    if (!CONFIG || !CONFIG.bounds) {
      return null;
    }
    return new google.maps.LatLngBounds(
      new google.maps.LatLng(CONFIG.bounds.south, CONFIG.bounds.west),
      new google.maps.LatLng(CONFIG.bounds.north, CONFIG.bounds.east)
    );
  }

  function createMap(container) {
    var options = {
      center: new google.maps.LatLng(CONFIG.center.lat, CONFIG.center.lng),
      zoom: 12,
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: true,
      clickableIcons: false,
      gestureHandling: 'cooperative',
      minZoom: 9,
      maxZoom: 19,
      backgroundColor: '#e9edf2'
    };
    var bounds = cityBounds();
    if (bounds) {
      options.restriction = { latLngBounds: bounds, strictBounds: false };
    }
    map = new google.maps.Map(container, options);
    infoWindow = new google.maps.InfoWindow({ maxWidth: 300 });
    return map;
  }

  function addResetControl(callback) {
    if (!map || !map.controls) {
      return;
    }
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'sg-gmaps-ctrl';
    button.title = 'Reset view to the whole journey';
    button.innerHTML = '<i class="ti ti-zoom-reset me-1"></i>Reset view';
    button.addEventListener('click', callback);
    map.controls[google.maps.ControlPosition.TOP_LEFT].push(button);
  }

  function fitPoints(points, maxZoom) {
    if (!map) {
      return;
    }
    if (points.length > 1) {
      var bounds = new google.maps.LatLngBounds();
      points.forEach(function (point) { bounds.extend(point); });
      google.maps.event.addListenerOnce(map, 'bounds_changed', function () {
        if (maxZoom && map.getZoom() > maxZoom) {
          map.setZoom(maxZoom);
        }
      });
      map.fitBounds(bounds, { top: 34, right: 34, bottom: 34, left: 34 });
    } else if (points.length === 1) {
      map.setCenter(points[0]);
      map.setZoom(14);
    } else {
      map.setCenter(
        new google.maps.LatLng(CONFIG.center.lat, CONFIG.center.lng)
      );
      map.setZoom(12);
    }
  }

  function fitAllLocations() {
    fitPoints(baseCoords, 13);
  }

  function openInfo(marker, html) {
    if (!infoWindow || !map) {
      return;
    }
    infoWindow.setContent(html);
    infoWindow.open(map, marker);
  }

  /* ------------------------------------------------------------------ */
  /* Database-driven location markers                                    */
  /* ------------------------------------------------------------------ */
  function locationInfoHtml(location) {
    var html =
      '<div class="sg-gm-info">' +
      '<strong>' + escapeHtml(location.location_name) + '</strong>' +
      '<div class="sg-gm-sub">' +
      escapeHtml(location.location_type) + ' &middot; ' +
      escapeHtml(location.barangay__barangay_name || 'Kabankalan City') +
      '</div>';

    if (location.address) {
      html += '<div class="sg-gm-line">' + escapeHtml(location.address) +
        '</div>';
    }
    html += modeBadges(location.transport_types);

    if (location.route_codes && location.route_codes.length) {
      html += '<div class="sg-gm-line"><strong>Routes:</strong> ' +
        escapeHtml(location.route_codes.join(', ')) + '</div>';
    }
    if (location.status && location.status !== 'active') {
      html += '<div class="sg-gm-line text-muted">Inactive location</div>';
    }
    return html + '</div>';
  }

  function addBaseLocationMarkers(useSlate) {
    baseMarkers.length = 0;
    baseCoords.length = 0;
    baseMarkerById = {};

    mapLocations.forEach(function (location) {
      if (location.latitude === null || location.latitude === undefined ||
          location.longitude === null || location.longitude === undefined) {
        return;
      }
      var active = !location.status || location.status === 'active';
      var isBarangay = location.location_type === 'barangay';
      var color = active
        ? (isBarangay ? '#7c3aed' : (useSlate ? '#64748b' : '#5c7cfa'))
        : '#adb5bd';
      var position = new google.maps.LatLng(
        Number(location.latitude), Number(location.longitude)
      );
      baseCoords.push(position);

      var marker = new google.maps.Marker({
        map: map,
        position: position,
        icon: dotIcon(color),
        title: location.location_name,
        zIndex: 5
      });
      marker.addListener('click', function () {
        openInfo(marker, locationInfoHtml(location));
      });
      baseMarkers.push(marker);
      baseMarkerById[String(location.location_id)] = marker;
    });
  }

  /* ------------------------------------------------------------------ */
  /* Google landmark/stop/journey markers                                */
  /* ------------------------------------------------------------------ */
  function addJourneyMarker(position, icon, html, zIndex) {
    var marker = new google.maps.Marker({
      map: map,
      position: position,
      icon: icon,
      zIndex: zIndex || 20
    });
    marker.addListener('click', function () {
      openInfo(marker, html);
    });
    journeyMarkers.push(marker);
    return marker;
  }

  function stopInfoHtml(entry) {
    var stop = entry.stop;
    var html =
      '<div class="sg-gm-info"><strong>' + escapeHtml(stop.name) +
      '</strong><div class="sg-gm-sub">Recorded stop on the SakayGuide ' +
      'network</div>';

    entry.boards.forEach(function (label) {
      html += '<div class="sg-gm-line"><i class="ti ti-log-in me-1"></i>' +
        'Board ' + escapeHtml(label) + ' here</div>';
    });
    entry.alights.forEach(function (label) {
      html += '<div class="sg-gm-line"><i class="ti ti-log-out me-1"></i>' +
        'Alight ' + escapeHtml(label) + ' here</div>';
    });
    html += '<div class="sg-gm-line">About ' + escapeHtml(stop.time) +
      ' min from that ride\'s origin</div></div>';
    return html;
  }

  function transferInfoHtml(transfer) {
    return '<div class="sg-gm-info">' +
      '<strong>' + escapeHtml(transfer.name) + '</strong>' +
      '<div class="sg-gm-sub">Transfer point (' +
      escapeHtml(transfer.from_code) + ' &rarr; ' +
      escapeHtml(transfer.to_code) + ')</div>' +
      '<div class="sg-gm-line">' + escapeHtml(transfer.instructions) +
      '</div>' +
      (transfer.fare
        ? '<div class="sg-gm-line">Additional fare: PHP ' +
          escapeHtml(transfer.fare) + '</div>'
        : '') +
      (transfer.time
        ? '<div class="sg-gm-line">Allow about ' + escapeHtml(transfer.time) +
          ' minutes to transfer</div>'
        : '') +
      '</div>';
  }

  function landmarkInfoHtml(landmark) {
    return '<div class="sg-gm-info">' +
      '<strong>' + escapeHtml(landmark.name) + '</strong>' +
      '<div class="sg-gm-sub">Landmark on ' +
      escapeHtml(landmark.route_code) + '</div>' +
      (landmark.description
        ? '<div class="sg-gm-line">' + escapeHtml(landmark.description) +
          '</div>'
        : '') +
      (landmark.distance
        ? '<div class="sg-gm-line">~' + escapeHtml(landmark.distance) +
          ' km from the route origin</div>'
        : '') +
      '</div>';
  }

  function drawJourneyMarkers(cfg) {
    var stopEntries = {};
    var order = [];

    cfg.legs.forEach(function (leg) {
      var lastIndex = leg.stops.length - 1;
      leg.stops.forEach(function (stop, index) {
        if (!hasCoord(stop)) {
          return;
        }
        var key = stop.location_id
          ? 'id:' + stop.location_id
          : 'c:' + Number(stop.lat).toFixed(5) + ',' +
            Number(stop.lng).toFixed(5);
        var entry = stopEntries[key];
        if (!entry) {
          entry = { stop: stop, boards: [], alights: [] };
          stopEntries[key] = entry;
          order.push(key);
        }
        var label = 'ride ' + (leg.leg_index + 1) + ' (' +
          leg.route_code + ')';
        if (index === 0) {
          entry.boards.push(label);
        }
        if (index === lastIndex) {
          entry.alights.push(label);
        }
      });
    });

    order.forEach(function (key) {
      var entry = stopEntries[key];
      if (entry.stop.role !== 'intermediate') {
        return;
      }
      addJourneyMarker(
        toLatLng(entry.stop),
        dotIcon('#1a7fd4'),
        stopInfoHtml(entry),
        20
      );
    });

    (cfg.transfer_points || []).forEach(function (transfer) {
      if (!hasCoord(transfer)) {
        return;
      }
      addJourneyMarker(
        toLatLng(transfer),
        pinIcon('#f0932b'),
        transferInfoHtml(transfer),
        40
      );
    });

    (cfg.landmarks || []).forEach(function (landmark) {
      if (!hasCoord(landmark)) {
        return;
      }
      addJourneyMarker(
        toLatLng(landmark),
        dotIcon('#8b5cf6'),
        landmarkInfoHtml(landmark),
        18
      );
    });

    if (cfg.origin && cfg.origin.verified) {
      addJourneyMarker(
        toLatLng(cfg.origin),
        pinIcon('#2e8540'),
        '<div class="sg-gm-info"><strong>' +
          escapeHtml(cfg.origin.name) + '</strong>' +
          '<div class="sg-gm-sub">Your starting point</div>' +
          (cfg.origin.address
            ? '<div class="sg-gm-line">' + escapeHtml(cfg.origin.address) +
              '</div>'
            : '') +
          '</div>',
        60
      );
    }
    if (cfg.destination && cfg.destination.verified) {
      addJourneyMarker(
        toLatLng(cfg.destination),
        pinIcon('#d63939'),
        '<div class="sg-gm-info"><strong>' +
          escapeHtml(cfg.destination.name) + '</strong>' +
          '<div class="sg-gm-sub">Your destination</div>' +
          (cfg.destination.address
            ? '<div class="sg-gm-line">' + escapeHtml(cfg.destination.address) +
              '</div>'
            : '') +
          '</div>',
        60
      );
    }
  }

  /* ------------------------------------------------------------------ */
  /* Polyline helpers                                                    */
  /* ------------------------------------------------------------------ */
  function makePolyline(path, color, dashed) {
    var options = {
      map: map,
      path: path,
      strokeColor: color,
      strokeOpacity: dashed ? 0 : 0.95,
      strokeWeight: dashed ? 4 : 5,
      clickable: false,
      zIndex: 10
    };
    if (dashed) {
      options.icons = [{
        icon: {
          path: 'M 0,-1 0,1',
          strokeOpacity: 1,
          strokeColor: color,
          scale: 3
        },
        offset: '0',
        repeat: '14px'
      }];
    }
    return new google.maps.Polyline(options);
  }

  function addSolidRoad(path, color, target) {
    var casing = new google.maps.Polyline({
      map: map,
      path: path,
      strokeColor: '#ffffff',
      strokeOpacity: 0.55,
      strokeWeight: 9,
      clickable: false,
      zIndex: 9
    });
    target.push(casing);
    var line = makePolyline(path, color, false);
    target.push(line);
    return line;
  }

  function stopPath(stops) {
    var path = [];
    (stops || []).forEach(function (stop) {
      if (hasCoord(stop)) {
        path.push(toLatLng(stop));
      }
    });
    return path;
  }

  function removePreviewLines(legIndex) {
    var lines = previewLinesByLeg[legIndex] || [];
    lines.forEach(function (line) { line.setMap(null); });
    previewLinesByLeg[legIndex] = [];
  }

  function drawApproximateLeg(leg, legIndex) {
    var path = stopPath(leg.stops);
    if (path.length < 2) {
      return;
    }
    var line = makePolyline(path, leg.color, true);
    journeyLines.push(line);
    previewLinesByLeg[legIndex] = (previewLinesByLeg[legIndex] || []);
    previewLinesByLeg[legIndex].push(line);
  }

  function clearJourneyLayers() {
    removeFromMap(journeyLines);
    removeFromMap(alternativeLines);
    removeFromMap(journeyMarkers);
    previewLinesByLeg = {};
    if (infoWindow) {
      infoWindow.close();
    }
  }

  /* ------------------------------------------------------------------ */
  /* Map notes / label                                                   */
  /* ------------------------------------------------------------------ */
  function noteLine(icon, text) {
    return '<div><i class="ti ' + icon + ' me-1"></i>' + text + '</div>';
  }

  function renderMapNotes(cfg) {
    var notes = document.getElementById('sg-map-notes');
    var label = document.getElementById('sg-map-route-label');

    if (label) {
      if (cfg.journey_available) {
        var bits = [
          cfg.label,
          cfg.rides + ' ride' + (cfg.rides === 1 ? '' : 's')
        ];
        if (cfg.total_time !== null && cfg.total_time !== undefined) {
          bits.push('est. ' + cfg.total_time + ' min');
        }
        if (cfg.total_distance_km) {
          bits.push(Number(cfg.total_distance_km).toFixed(2) + ' km');
        }
        label.textContent = bits.join(' \u00b7 ');
      } else {
        label.textContent = cfg.label + ' \u00b7 no journey found';
      }
    }

    if (!notes) {
      return;
    }
    var html = '';

    if (cfg.journey_available) {
      if (directionsState.pending) {
        html += noteLine(
          'ti-loader-2',
          'Turn-by-turn directions are loading. The dashed preview follows ' +
          'the recorded stops until the road paths arrive.'
        );
      }
      if (directionsState.googleLegs) {
        html += noteLine(
          'ti-brand-google',
          'Road geometry for ' + directionsState.googleLegs + ' ride' +
          (directionsState.googleLegs === 1 ? '' : 's') +
          ' comes from Google Maps Directions. Alternative routes, when ' +
          'available, are the dashed grey lines.'
        );
      }
      if (directionsState.osrmLegs) {
        html += noteLine(
          'ti-route',
          'Google Directions was unavailable for ' +
          directionsState.osrmLegs + ' ride' +
          (directionsState.osrmLegs === 1 ? '' : 's') +
          ', so the free OSRM road path is shown there instead.'
        );
      }
      if (directionsState.approximateLegs) {
        html += noteLine(
          'ti-alert-circle',
          'The dashed line for ' + directionsState.approximateLegs + ' ride' +
          (directionsState.approximateLegs === 1 ? '' : 's') +
          ' is only an <strong>approximate</strong> stop-to-stop connection; ' +
          'no road path service could be reached.'
        );
      }
    } else {
      html += noteLine(
        'ti-map-pin',
        'All ' + baseCoords.length + ' recorded Kabankalan City locations ' +
        'are pinned. The starting point and destination are highlighted - ' +
        'no connecting line is drawn, and none is invented.'
      );
    }

    if (cfg.unverified_names && cfg.unverified_names.length) {
      html += '<div class="mt-1">' + noteLine(
        'ti-map-pin-off',
        'Map position not yet verified for: <strong>' +
        cfg.unverified_names.map(escapeHtml).join(', ') +
        '</strong>. They still appear in the journey instructions above.'
      ) + '</div>';
    }

    notes.innerHTML = html;
  }

  /* ------------------------------------------------------------------ */
  /* Directions panel                                                    */
  /* ------------------------------------------------------------------ */
  function routeTotals(route) {
    var meters = 0;
    var seconds = 0;
    (route.legs || []).forEach(function (leg) {
      if (leg.distance && leg.distance.value) {
        meters += leg.distance.value;
      }
      if (leg.duration && leg.duration.value) {
        seconds += leg.duration.value;
      }
    });
    return {
      distance: formatDistanceMeters(meters),
      duration: formatDurationSeconds(seconds)
    };
  }

  function directionsStatusMessage(status) {
    switch (status) {
      case 'ZERO_RESULTS':
        return 'Google found no driving route between these recorded stops.';
      case 'OVER_QUERY_LIMIT':
        return 'The Google Maps quota for this key is exhausted right now.';
      case 'REQUEST_DENIED':
        return 'Google Directions rejected the request. Check that the ' +
          'Directions API is enabled and allowed for this browser key.';
      case 'INVALID_REQUEST':
        return 'Google Directions could not understand the recorded stops ' +
          'for this ride.';
      case 'NOT_FOUND':
        return 'One of the recorded stops was not found by Google Directions.';
      case 'TIMEOUT':
        return 'Google Directions took too long to answer.';
      case 'NO_COORDS':
        return 'Not enough recorded stops have verified coordinates for ' +
          'road directions.';
      default:
        return 'Google Directions is unavailable (' + status + ').';
    }
  }

  function maneuverIcon(maneuver) {
    var icons = {
      'turn-left': 'ti-arrow-left',
      'turn-right': 'ti-arrow-right',
      'turn-slight-left': 'ti-arrow-left',
      'turn-slight-right': 'ti-arrow-right',
      'turn-sharp-left': 'ti-arrow-left',
      'turn-sharp-right': 'ti-arrow-right',
      'uturn-left': 'ti-rotate-clockwise',
      'uturn-right': 'ti-rotate-clockwise',
      'merge': 'ti-arrows-join',
      'fork-left': 'ti-arrow-left',
      'fork-right': 'ti-arrow-right',
      'roundabout-left': 'ti-refresh',
      'roundabout-right': 'ti-refresh',
      'ramp-left': 'ti-arrow-left',
      'ramp-right': 'ti-arrow-right',
      'ferry': 'ti-ship',
      'ferry-train': 'ti-train'
    };
    return icons[maneuver] || 'ti-arrow-up';
  }

  function stepListHtml(route) {
    var steps = [];
    (route.legs || []).forEach(function (leg) {
      (leg.steps || []).forEach(function (step) {
        steps.push(step);
      });
    });
    if (!steps.length) {
      return '';
    }
    return '<ol class="sg-gdir-steps">' + steps.map(function (step) {
      var instruction = plainText(step.instructions) || 'Continue';
      var distance = step.distance ? step.distance.text : '';
      var duration = step.duration ? step.duration.text : '';
      var meta = [distance, duration].filter(Boolean).join(' \u00b7 ');
      return '<li><i class="ti ' + maneuverIcon(step.maneuver) +
        ' me-1"></i>' + escapeHtml(instruction) +
        (meta
          ? '<span class="sg-gdir-meta">' + escapeHtml(meta) + '</span>'
          : '') +
        '</li>';
    }).join('') + '</ol>';
  }

  function setDirectionsLoading(cfg) {
    var container = document.getElementById('sg-google-directions');
    if (!container) {
      return;
    }
    if (!cfg.journey_available || !cfg.legs.length) {
      container.innerHTML = '';
      return;
    }
    container.innerHTML =
      '<div class="sg-gdir-head"><span><i class="ti ti-signpost me-1"></i>' +
      'Google Maps directions</span><span class="sg-gdir-note">' +
      'Loading turn-by-turn guidance&hellip;</span></div>';
  }

  function renderDirectionsPanel(cfg, results) {
    var container = document.getElementById('sg-google-directions');
    if (!container) {
      return;
    }
    if (!cfg.journey_available || !cfg.legs.length) {
      container.innerHTML = '';
      return;
    }

    var html =
      '<div class="sg-gdir-head"><span><i class="ti ti-signpost me-1"></i>' +
      'Google Maps directions</span><span class="sg-gdir-note">' +
      'Road guidance follows the recorded stops. Fares and ride times ' +
      'remain SakayGuide database estimates.</span></div>';

    var allFailed = true;
    results.forEach(function (result, index) {
      if (!result) {
        return;
      }
      var leg = cfg.legs[index];
      html += '<div class="sg-gdir-leg">';
      html += '<div class="sg-gdir-leg-head"><div>' +
        '<span class="sg-gdir-swatch" style="background:' +
        escapeHtml(leg.color) + '"></span>' +
        '<strong>Ride ' + (index + 1) + ' &middot; ' +
        escapeHtml(leg.route_code) + '</strong> ' +
        '<span class="text-muted">' + escapeHtml(leg.mode) + '</span>' +
        '<div class="text-muted small">Board at <strong>' +
        escapeHtml(leg.board_at) + '</strong> &rarr; alight at <strong>' +
        escapeHtml(leg.alight_at) + '</strong></div></div>';

      if (result.kind === 'google' && result.route) {
        allFailed = false;
        var totals = routeTotals(result.route);
        html += '<div class="text-end small"><strong>' +
          escapeHtml(totals.distance) + '</strong><br>' +
          escapeHtml(totals.duration) + '</div>';
        html += '</div>'; /* leg head */
        html += stepListHtml(result.route);

        if (result.alternatives && result.alternatives.length) {
          html += '<div class="sg-gdir-alt-title">Alternative routes ' +
            '(dashed grey on the map)</div><ul class="sg-gdir-alts">';
          result.alternatives.forEach(function (alternative) {
            var altTotals = routeTotals(alternative);
            html += '<li>' +
              (alternative.summary
                ? 'via ' + escapeHtml(alternative.summary) + ' &middot; '
                : '') +
              escapeHtml(altTotals.distance) + ' &middot; ' +
              escapeHtml(altTotals.duration) +
              '</li>';
          });
          html += '</ul>';
        }
      } else if (result.kind === 'osrm') {
        allFailed = false;
        html += '</div>'; /* leg head */
        html += '<div class="sg-gdir-error">' +
          escapeHtml(result.reason) +
          ' The free OSRM road path is drawn on the map instead, so the ' +
          'line still follows public roads; only Google\'s turn-by-turn ' +
          'steps are missing for this ride.</div>';
      } else {
        html += '</div>'; /* leg head */
        html += '<div class="sg-gdir-error">' +
          escapeHtml(result.reason) +
          ' The map keeps the dashed approximate stop-to-stop line for this ' +
          'ride; it is not presented as a verified road route.</div>';
      }
      html += '</div>'; /* .sg-gdir-leg */
    });

    if (allFailed) {
      html += '<div class="sg-gdir-error mt-2"><i class="ti ' +
        'ti-alert-triangle me-1"></i>Google Directions could not be used ' +
        'for this journey. Enable the <strong>Directions API</strong> for ' +
        'the browser key and check its API restrictions. The map falls back ' +
        'to free road paths or the labelled approximate dashed line.</div>';
    }

    container.innerHTML = html;
  }

  /* ------------------------------------------------------------------ */
  /* OSRM fallback (free, no key)                                        */
  /* ------------------------------------------------------------------ */
  function osrmPath(stops) {
    var points = [];
    (stops || []).forEach(function (stop) {
      if (hasCoord(stop)) {
        points.push([Number(stop.lat), Number(stop.lng)]);
      }
    });
    if (points.length < 2) {
      return Promise.resolve(null);
    }
    if (points.length === 2 &&
        points[0][0] === points[1][0] &&
        points[0][1] === points[1][1]) {
      return Promise.resolve(null);
    }

    var coords = points.map(function (point) {
      return point[1].toFixed(6) + ',' + point[0].toFixed(6);
    }).join(';');
    var url = OSRM_BASE + coords +
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
        if (!data || data.code !== 'Ok' || !data.routes ||
            !data.routes.length || !data.routes[0].geometry ||
            !data.routes[0].geometry.coordinates) {
          return null;
        }
        return data.routes[0].geometry.coordinates.map(function (coordinate) {
          return new google.maps.LatLng(coordinate[1], coordinate[0]);
        });
      })
      .catch(function () {
        if (timer) { window.clearTimeout(timer); }
        return null;
      });
  }

  /* ------------------------------------------------------------------ */
  /* DirectionsService                                                   */
  /* ------------------------------------------------------------------ */
  function drawGoogleLeg(route, leg, legIndex) {
    var path = route.overview_path;
    if (!path || path.length < 2) {
      return;
    }
    removePreviewLines(legIndex);
    addSolidRoad(path, leg.color, journeyLines);
  }

  function drawAlternativeRoutes(routes) {
    routes.slice(1).forEach(function (alternative) {
      var path = alternative.overview_path;
      if (!path || path.length < 2) {
        return;
      }
      var line = new google.maps.Polyline({
        map: map,
        path: path,
        strokeColor: '#8a94a6',
        strokeOpacity: 0,
        strokeWeight: 3,
        clickable: false,
        zIndex: 4,
        icons: [{
          icon: {
            path: 'M 0,-1 0,1',
            strokeOpacity: 0.8,
            strokeColor: '#8a94a6',
            scale: 2
          },
          offset: '0',
          repeat: '12px'
        }]
      });
      alternativeLines.push(line);
    });
  }

  function fallbackLegToOsrm(cfg, leg, legIndex, sequence, reason, callback) {
    if (sequence !== journeySequence) {
      return; /* a newer journey selection superseded this request */
    }
    if (typeof fetch !== 'function') {
      directionsState.approximateLegs += 1;
      callback({ kind: 'approximate', reason: reason });
      renderMapNotes(cfg);
      return;
    }
    osrmPath(leg.stops).then(function (path) {
      if (sequence !== journeySequence) {
        return;
      }
      if (path && path.length > 1) {
        removePreviewLines(legIndex);
        addSolidRoad(path, leg.color, journeyLines);
        directionsState.osrmLegs += 1;
        callback({
          kind: 'osrm',
          reason: reason
        });
      } else {
        directionsState.approximateLegs += 1;
        callback({
          kind: 'approximate',
          reason: reason
        });
      }
      renderMapNotes(cfg);
    });
  }

  function requestLegDirections(cfg, leg, legIndex, sequence, callback) {
    if (sequence !== journeySequence) {
      return;
    }
    var path = stopPath(leg.stops);
    if (path.length < 2) {
      directionsState.approximateLegs += 1;
      callback({
        kind: 'approximate',
        reason: directionsStatusMessage('NO_COORDS')
      });
      return;
    }

    /* Google Directions accepts at most 25 waypoints in total; keep one
       slot each for the recorded origin and destination. */
    var waypoints = path.slice(1, path.length - 1).slice(0, 23)
      .map(function (point) {
        return { location: point, stopover: true };
      });

    var request = {
      origin: path[0],
      destination: path[path.length - 1],
      waypoints: waypoints,
      travelMode: google.maps.TravelMode.DRIVING,
      provideRouteAlternatives: true,
      optimizeWaypoints: false,
      region: (CONFIG.region || 'PH')
    };

    var service = new google.maps.DirectionsService();
    var answered = false;
    var timer = null;

    function respond(status, response) {
      if (answered || sequence !== journeySequence) {
        return;
      }
      answered = true;
      if (timer) {
        window.clearTimeout(timer);
        timer = null;
      }

      if (status === 'OK' && response && response.routes &&
          response.routes.length) {
        drawGoogleLeg(response.routes[0], leg, legIndex);
        drawAlternativeRoutes(response.routes);
        directionsState.googleLegs += 1;
        renderMapNotes(cfg);
        callback({
          kind: 'google',
          route: response.routes[0],
          alternatives: response.routes.slice(1)
        });
        return;
      }

      var reason = directionsStatusMessage(status || 'UNKNOWN_ERROR');
      fallbackLegToOsrm(cfg, leg, legIndex, sequence, reason, callback);
    }

    timer = window.setTimeout(function () {
      respond('TIMEOUT', null);
    }, 12000);

    try {
      service.route(request, function (response, status) {
        if (sequence !== journeySequence) {
          return;
        }
        respond(status, response);
      });
    } catch (error) {
      respond('UNKNOWN_ERROR', null);
    }
  }

  function loadDirections(cfg, sequence) {
    directionsState = emptyDirectionsState();
    directionsState.pending = cfg.legs.length > 0;
    setDirectionsLoading(cfg);
    renderMapNotes(cfg);

    var results = new Array(cfg.legs.length);
    var index = 0;

    function next() {
      if (sequence !== journeySequence) {
        return;
      }
      if (index >= cfg.legs.length) {
        directionsState.pending = false;
        renderDirectionsPanel(cfg, results);
        renderMapNotes(cfg);
        return;
      }

      var current = index;
      var leg = cfg.legs[current];
      requestLegDirections(cfg, leg, current, sequence, function (result) {
        if (sequence !== journeySequence) {
          return;
        }
        results[current] = result;
        index += 1;
        next();
      });
    }

    next();
  }

  /* ------------------------------------------------------------------ */
  /* Journey selection                                                   */
  /* ------------------------------------------------------------------ */
  function focusJourney(cfg) {
    if (!cfg) {
      fitAllLocations();
      return;
    }
    if (!cfg.journey_available && baseCoords.length > 1) {
      fitAllLocations();
      return;
    }
    if (cfg.bounds && cfg.bounds.length === 2) {
      var bounds = new google.maps.LatLngBounds(
        new google.maps.LatLng(cfg.bounds[0][0], cfg.bounds[0][1]),
        new google.maps.LatLng(cfg.bounds[1][0], cfg.bounds[1][1])
      );
      google.maps.event.addListenerOnce(map, 'bounds_changed', function () {
        if (map.getZoom() > 15) {
          map.setZoom(15);
        }
      });
      map.fitBounds(bounds, { top: 36, right: 36, bottom: 36, left: 36 });
      return;
    }
    if (cfg.center) {
      map.setCenter(new google.maps.LatLng(cfg.center.lat, cfg.center.lng));
      map.setZoom(14);
      return;
    }
    fitAllLocations();
  }

  function scrollToMap() {
    var card = document.getElementById('sg-map-card');
    if (card && card.scrollIntoView) {
      card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  function markSelection(index) {
    document.querySelectorAll('.journey-card').forEach(function (card) {
      card.classList.toggle(
        'is-active',
        card.dataset.journeyIndex === String(index)
      );
      card.setAttribute(
        'aria-pressed',
        card.dataset.journeyIndex === String(index) ? 'true' : 'false'
      );
    });
    document.querySelectorAll('.sg-journey-panel').forEach(function (panel) {
      panel.hidden = panel.id !== 'journey-panel-' + index;
    });
  }

  function selectJourney(index, options) {
    var cfg = journeyData[index];
    if (!cfg) {
      return;
    }
    if (index === activeJourneyIndex && journeyMarkers.length) {
      if (options && options.scroll) {
        scrollToMap();
      }
      return;
    }

    activeJourneyIndex = index;
    journeySequence += 1;
    var sequence = journeySequence;

    markSelection(index);
    clearJourneyLayers();

    if (!map) {
      return;
    }

    if (!cfg.journey_available) {
      drawJourneyMarkers(cfg);
      focusJourney(cfg);
      renderMapNotes(cfg);
      var emptyDirections = document.getElementById('sg-google-directions');
      if (emptyDirections) {
        emptyDirections.innerHTML = '';
      }
      if (options && options.scroll) {
        scrollToMap();
      }
      return;
    }

    cfg.legs.forEach(function (leg, legIndex) {
      drawApproximateLeg(leg, legIndex);
    });
    drawJourneyMarkers(cfg);
    focusJourney(cfg);
    renderMapNotes(cfg);

    if (options && options.scroll) {
      scrollToMap();
    }

    /* Progressive upgrade: Google Directions first, then OSRM. */
    loadDirections(cfg, sequence);
  }

  function bindJourneySelection() {
    document.addEventListener('click', function (event) {
      if (engine !== 'google') {
        return;
      }
      var target = closestElement(event.target, '[data-journey-select]');
      if (!target) {
        return;
      }
      event.preventDefault();
      var index = parseInt(
        target.getAttribute('data-journey-index') ||
        target.getAttribute('data-journey-select'),
        10
      );
      if (isNaN(index)) {
        return;
      }
      selectJourney(index, {
        scroll: target.classList.contains('sg-select-journey')
      });
    });

    document.addEventListener('keydown', function (event) {
      if (engine !== 'google') {
        return;
      }
      if (event.key !== 'Enter' && event.key !== ' ') {
        return;
      }
      var card = closestElement(event.target, '.journey-card');
      if (!card) {
        return;
      }
      event.preventDefault();
      var index = parseInt(card.getAttribute('data-journey-index'), 10);
      if (!isNaN(index)) {
        selectJourney(index, { scroll: false });
      }
    });
  }

  function bindLocationList() {
    var items = document.querySelectorAll('[data-map-location-id]');
    Array.prototype.forEach.call(items, function (item) {
      item.addEventListener('click', function () {
        if (engine !== 'google' || !map) {
          return;
        }
        var marker = baseMarkerById[String(item.dataset.mapLocationId)];
        if (!marker || !marker.getPosition()) {
          return;
        }

        Array.prototype.forEach.call(items, function (other) {
          other.classList.toggle('is-active', other === item);
        });

        map.panTo(marker.getPosition());
        map.setZoom(16);
        google.maps.event.trigger(marker, 'click');
      });
    });
  }

  /* ------------------------------------------------------------------ */
  /* Live GPS (Google Maps overlay)                                      */
  /* ------------------------------------------------------------------ */
  var gpsOverlayClassCache = null;

  function gpsOverlayClass() {
    /* This must run only after the Google Maps JS API has loaded, so the
       base class (google.maps.OverlayView) exists. */
    if (gpsOverlayClassCache) {
      return gpsOverlayClassCache;
    }

    function GpsOverlay() {
      this.position_ = null;
      this.div_ = null;
    }

    GpsOverlay.prototype = new google.maps.OverlayView();

    GpsOverlay.prototype.onAdd = function () {
      var div = document.createElement('div');
      div.className = 'sg-gmaps-gps';
      div.setAttribute('aria-hidden', 'true');
      div.innerHTML = '<span class="sg-gps-dot"></span>';
      this.div_ = div;
      var panes = this.getPanes();
      if (panes && panes.overlayMouseTarget) {
        panes.overlayMouseTarget.appendChild(div);
      }
    };

    GpsOverlay.prototype.draw = function () {
      if (!this.div_ || !this.position_) {
        return;
      }
      var projection = this.getProjection();
      if (!projection) {
        return;
      }
      var point = projection.fromLatLngToDivPixel(this.position_);
      if (!point) {
        return;
      }
      this.div_.style.left = point.x + 'px';
      this.div_.style.top = point.y + 'px';
    };

    GpsOverlay.prototype.onRemove = function () {
      if (this.div_ && this.div_.parentNode) {
        this.div_.parentNode.removeChild(this.div_);
      }
      this.div_ = null;
    };

    GpsOverlay.prototype.setPosition = function (latLng) {
      this.position_ = latLng;
      this.draw();
    };

    gpsOverlayClassCache = GpsOverlay;
    return gpsOverlayClassCache;
  }

  function locationContextError() {
    if (window.isSecureContext === false) {
      return 'Live GPS needs a secure connection (HTTPS or localhost). ' +
        'Open this site securely to share your position.';
    }
    return '';
  }

  function gpsErrorMessage(error) {
    var contextError = locationContextError();
    if (contextError) {
      return contextError;
    }
    if (!error) {
      return 'Could not read your GPS position.';
    }
    if (error.code === 1) {
      return 'Location permission was denied. Allow location access for ' +
        'this site in your browser settings and try again.';
    }
    if (error.code === 2) {
      return 'Your position is unavailable. Check that device location or ' +
        'GPS is turned on.';
    }
    if (error.code === 3) {
      return 'GPS timed out. Move to an open area and try again.';
    }
    return 'Could not read your GPS position.';
  }

  function createGps(mapInstance) {
    var button = document.querySelector('[data-gps-toggle]');
    var status = document.querySelector('[data-gps-status]');
    var overlay = null;
    var accuracyCircle = null;
    var watchId = null;
    var active = false;
    var seenFix = false;
    var relaxedRestriction = false;
    var savedRestriction = mapInstance.get('restriction') || null;
    var GpsOverlay = gpsOverlayClass();

    function setStatus(text, isError) {
      if (!status) {
        return;
      }
      status.textContent = text || '';
      status.hidden = !text;
      status.classList.toggle('is-error', Boolean(isError));
    }

    function setButtonState(isActive) {
      if (!button) {
        return;
      }
      button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      button.classList.toggle('is-active', isActive);
      button.classList.toggle('btn-primary', isActive);
      button.classList.toggle('btn-outline-primary', !isActive);
      var label = button.querySelector('[data-gps-toggle-label]');
      if (label) {
        label.textContent = isActive ? 'Stop GPS' : 'My Current Location';
      }
    }

    function relaxRestriction(latLng) {
      if (!savedRestriction || relaxedRestriction) {
        return;
      }
      var bounds = savedRestriction.latLngBounds;
      if (bounds && !bounds.contains(latLng)) {
        mapInstance.setOptions({ restriction: null });
        relaxedRestriction = true;
      }
    }

    function restoreRestriction() {
      if (relaxedRestriction && savedRestriction) {
        mapInstance.setOptions({ restriction: savedRestriction });
        relaxedRestriction = false;
      }
    }

    function ensureLayers(latLng, accuracy) {
      if (!overlay) {
        overlay = new GpsOverlay();
        overlay.setMap(mapInstance);
        accuracyCircle = new google.maps.Circle({
          map: mapInstance,
          center: latLng,
          radius: accuracy,
          strokeColor: '#1a73e8',
          strokeOpacity: 0.6,
          strokeWeight: 1,
          fillColor: '#1a73e8',
          fillOpacity: 0.12,
          clickable: false,
          zIndex: 3
        });
      }
      overlay.setPosition(latLng);
      accuracyCircle.setCenter(latLng);
      accuracyCircle.setRadius(accuracy);
    }

    function onPosition(position) {
      if (!active) {
        return;
      }
      var coords = position.coords;
      var latLng = new google.maps.LatLng(
        coords.latitude, coords.longitude
      );
      var accuracy = Number(coords.accuracy) || 0;

      relaxRestriction(latLng);
      ensureLayers(latLng, accuracy);

      if (!seenFix) {
        seenFix = true;
        mapInstance.setCenter(latLng);
        mapInstance.setZoom(Math.max(mapInstance.getZoom(), 16));
      } else if (!mapInstance.getBounds() ||
                 !mapInstance.getBounds().contains(latLng)) {
        mapInstance.panTo(latLng);
      }

      setStatus(
        'Live GPS on' +
        (accuracy ? ' \u00b7 accuracy \u00b1' + formatDistanceMeters(accuracy) : ''),
        false
      );
    }

    function stop(silent) {
      if (watchId !== null && navigator.geolocation) {
        navigator.geolocation.clearWatch(watchId);
        watchId = null;
      }
      active = false;
      seenFix = false;
      if (overlay) {
        overlay.setMap(null);
        overlay = null;
      }
      if (accuracyCircle) {
        accuracyCircle.setMap(null);
        accuracyCircle = null;
      }
      restoreRestriction();
      setButtonState(false);
      if (!silent) {
        setStatus('Live GPS stopped.', false);
      }
    }

    function fail(error) {
      if (!active) {
        return;
      }
      stop(true);
      setStatus(gpsErrorMessage(error), true);
    }

    function start() {
      if (active) {
        return;
      }
      var contextError = locationContextError();
      if (contextError) {
        setStatus(contextError, true);
        return;
      }
      if (!navigator.geolocation) {
        setStatus('Live GPS is not supported by this browser.', true);
        return;
      }

      active = true;
      seenFix = false;
      setButtonState(true);
      setStatus('Requesting your current location\u2026', false);

      try {
        watchId = navigator.geolocation.watchPosition(
          onPosition,
          fail,
          {
            enableHighAccuracy: true,
            maximumAge: 5000,
            timeout: 15000
          }
        );
      } catch (error) {
        active = false;
        setButtonState(false);
        setStatus(gpsErrorMessage(error), true);
      }
    }

    function toggle() {
      if (active) {
        stop(false);
      } else {
        start();
      }
    }

    function destroy() {
      stop(true);
      if (button) {
        button.removeEventListener('click', toggle);
      }
    }

    if (button) {
      button.addEventListener('click', toggle);
    }

    return {
      start: start,
      stop: stop,
      toggle: toggle,
      destroy: destroy,
      isActive: function () { return active; }
    };
  }

  /* ------------------------------------------------------------------ */
  /* Search page                                                         */
  /* ------------------------------------------------------------------ */
  function buildSearchMap() {
    var container = document.getElementById('sg-search-map');
    if (!container || map) {
      return;
    }

    createMap(container);
    addBaseLocationMarkers(false);
    fitAllLocations();
    addResetControl(fitAllLocations);

    gpsController = createGps(map);
    setSearchAttribution('google');
    setEngineNote(
      'Map engine: Google Maps JavaScript API. All pins, routes and fares ' +
      'come from the SakayGuide database.'
    );
  }

  function bindSearchToggle() {
    if (searchToggleHandler) {
      return;
    }
    var container = document.getElementById('sg-search-map');
    var body = document.getElementById('sg-city-map-body');
    var toggle = document.getElementById('sg-city-map-toggle');
    var label = document.getElementById('sg-city-map-toggle-label');
    if (!container) {
      return;
    }

    searchToggleHandler = function () {
      if (engine !== 'google' || !body) {
        return;
      }
      var willShow = body.hidden;
      body.hidden = !willShow;
      if (toggle) {
        toggle.setAttribute('aria-expanded', String(willShow));
      }
      if (label) {
        label.textContent = willShow ? 'Hide map preview' : 'Show map preview';
      }

      if (!willShow) {
        if (gpsController) {
          gpsController.stop(false);
        }
        return;
      }

      if (!map) {
        if (!window.google || !window.google.maps) {
          setEngineNote(
            'Map engine: Google Maps JavaScript API is still loading. The ' +
            'preview will open as soon as it is ready.',
            false
          );
          return;
        }
        try {
          buildSearchMap();
        } catch (error) {
          console.error('SakayGuide Google search map error:', error);
          fallbackToLeaflet('map-error');
        }
        return;
      }

      window.setTimeout(function () {
        google.maps.event.trigger(map, 'resize');
        fitAllLocations();
      }, 60);
    };

    if (toggle) {
      toggle.addEventListener('click', searchToggleHandler);
    }
  }

  function initSearchPage() {
    var container = document.getElementById('sg-search-map');
    var body = document.getElementById('sg-city-map-body');
    if (!container) {
      return;
    }

    bindSearchToggle();
    setEngineNote(
      'Map engine: Google Maps JavaScript API. Open the preview to load the ' +
      'city map.'
    );

    if (!body || !body.hidden) {
      buildSearchMap();
    }
  }

  /* ------------------------------------------------------------------ */
  /* Results page                                                        */
  /* ------------------------------------------------------------------ */
  function initResultsPage() {
    var container = document.getElementById('sg-journey-map');
    if (!container) {
      return;
    }

    journeyData = readJson('journey-maps', []);
    mapLocations = readJson('kabankalan-locations', []);
    if (!Array.isArray(journeyData)) {
      journeyData = [];
    }
    if (!Array.isArray(mapLocations)) {
      mapLocations = [];
    }

    createMap(container);
    addBaseLocationMarkers(true);
    addResetControl(function () {
      if (journeyData[activeJourneyIndex]) {
        focusJourney(journeyData[activeJourneyIndex]);
      } else {
        fitAllLocations();
      }
    });

    gpsController = createGps(map);
    bindJourneySelection();
    bindLocationList();

    setEngineNote(
      'Map engine: Google Maps JavaScript API. Turn-by-turn directions ' +
      'come from Google; fares and ride times come from SakayGuide.'
    );

    window.setTimeout(function () {
      try {
        if (journeyData.length && activeJourneyIndex === -1) {
          selectJourney(0, { scroll: false });
        } else if (!journeyData.length) {
          fitAllLocations();
        }
      } catch (error) {
        console.error('SakayGuide Google journey map error:', error);
        fallbackToLeaflet('map-error');
      }
    }, 80);
  }

  /* ------------------------------------------------------------------ */
  /* Google Maps loader + Leaflet fallback                               */
  /* ------------------------------------------------------------------ */
  function fallbackReasonText(reason) {
    if (reason === 'auth') {
      return 'Google Maps rejected the API key. ';
    }
    if (reason === 'timeout') {
      return 'Google Maps took too long to load. ';
    }
    if (reason === 'network') {
      return 'Google Maps could not be reached (offline or blocked script). ';
    }
    return 'Google Maps could not start. ';
  }

  function fallbackToLeaflet(reason) {
    if (fallbackDone) {
      return;
    }
    fallbackDone = true;
    engine = 'leaflet';
    journeySequence += 1;

    if (googleLoadTimer) {
      window.clearTimeout(googleLoadTimer);
      googleLoadTimer = null;
    }
    if (gpsController) {
      gpsController.destroy();
      gpsController = null;
    }

    if (searchToggleHandler) {
      var toggle = document.getElementById('sg-city-map-toggle');
      if (toggle) {
        toggle.removeEventListener('click', searchToggleHandler);
      }
      searchToggleHandler = null;
    }

    var container = document.getElementById(
      page === 'search' ? 'sg-search-map' : 'sg-journey-map'
    );
    if (container) {
      container.innerHTML = '';
      container.removeAttribute('style');
      container.classList.remove('sg-map-offline');
    }

    var directions = document.getElementById('sg-google-directions');
    if (directions) {
      directions.innerHTML = '';
    }

    if (map && typeof google !== 'undefined' &&
        google.maps && google.maps.event) {
      try {
        google.maps.event.clearInstanceListeners(map);
      } catch (error) {
        /* The map may already be unusable after an auth failure. */
      }
    }
    map = null;
    infoWindow = null;

    setSearchAttribution('leaflet');
    setEngineNote(
      fallbackReasonText(reason) +
      'Using the built-in Leaflet/OpenStreetMap map instead. Fares, stops, ' +
      'directions and all other SakayGuide features are unchanged.',
      true
    );

    if (page === 'search' && window.SakayLeafletCityMap) {
      window.SakayLeafletCityMap.init();
    } else if (page === 'journey' && window.SakayLeafletJourneyMap) {
      window.SakayLeafletJourneyMap.init();
    }
  }

  function loadGoogleMaps(onReady, onFailure) {
    if (window.google && window.google.maps) {
      onReady();
      return;
    }
    if (!CONFIG || !CONFIG.enabled || !CONFIG.api_key) {
      onFailure('auth');
      return;
    }

    var callbackName = '__sakayGoogleMapsReady';
    var settled = false;

    function settle(ok, reason) {
      if (settled) {
        return;
      }
      settled = true;
      if (googleLoadTimer) {
        window.clearTimeout(googleLoadTimer);
        googleLoadTimer = null;
      }
      if (ok) {
        onReady();
      } else {
        onFailure(reason);
      }
    }

    window[callbackName] = function () {
      settle(true);
    };

    window.gm_authFailure = function () {
      settle(false, 'auth');
      fallbackToLeaflet('auth');
    };

    var params = [
      'key=' + encodeURIComponent(CONFIG.api_key),
      'callback=' + callbackName,
      'loading=async',
      'v=weekly',
      'language=' + encodeURIComponent(CONFIG.language || 'en'),
      'region=' + encodeURIComponent(CONFIG.region || 'PH')
    ];

    var script = document.createElement('script');
    script.id = 'sg-google-maps-script';
    script.async = true;
    script.defer = true;
    script.src = 'https://maps.googleapis.com/maps/api/js?' + params.join('&');
    script.onerror = function () {
      settle(false, 'network');
    };

    googleLoadTimer = window.setTimeout(function () {
      settle(false, 'timeout');
    }, GOOGLE_LOAD_TIMEOUT_MS);

    document.head.appendChild(script);
  }

  /* ------------------------------------------------------------------ */
  /* Boot                                                                */
  /* ------------------------------------------------------------------ */
  function boot() {
    if (!document.getElementById('sg-search-map') &&
        !document.getElementById('sg-journey-map')) {
      return; /* not a route page */
    }
    if (!CONFIG || !CONFIG.enabled) {
      return; /* _map_assets.html already chose Leaflet */
    }

    page = document.getElementById('sg-search-map') ? 'search' : 'journey';

    if (page === 'search') {
      mapLocations = readJson('kabankalan-locations', []);
      /* Bind the preview toggle immediately so an early click opens the
         container (and shows a loading message) while Google loads. */
      bindSearchToggle();
    }

    loadGoogleMaps(function () {
      if (fallbackDone) {
        return;
      }
      try {
        if (page === 'search') {
          initSearchPage();
        } else {
          initResultsPage();
        }
      } catch (error) {
        console.error('SakayGuide Google Maps initialisation error:', error);
        fallbackToLeaflet('map-error');
      }
    }, fallbackToLeaflet);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
