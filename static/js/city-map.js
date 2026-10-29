/* Kabankalan City map for the Find My Route page: Leaflet with
   OpenStreetMap tiles (free, no API key), clamped to the Kabankalan City
   area so the view cannot drift to other towns.

   Every recorded Kabankalan City location is pinned so commuters can see
   the whole city at a glance. The city map is HIDDEN until the commuter
   clicks "Show map preview" (requirement: no map is visible before a
   search). Leaflet is built on the first reveal, and invalidateSize()
   keeps the tiles aligned after the container becomes visible. If
   Leaflet is unavailable the map degrades to a text note. */
(function () {
  'use strict';

  /* Kabankalan City poblacion (OpenStreetMap, Oct 2026). */
  var CITY_CENTER = [9.9926, 122.8135];

  /* Generous clamp around the Kabankalan City - Himamaylan - Ilog road
     corridor [southwest, northeast]; the view cannot pan beyond it. */
  var CITY_BOUNDS = [[9.70, 122.66], [10.12, 122.99]];

  var mapInstance = null;
  var allLocationCoords = [];
  var gpsController = null;

  function readLocations() {
    var dataEl = document.getElementById('kabankalan-locations');
    try {
      return JSON.parse((dataEl && dataEl.textContent) || '[]');
    } catch (error) {
      return [];
    }
  }

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text === null || text === undefined ? '' : String(text);
    return div.innerHTML;
  }

  function locationPopup(location) {
    var html =
      '<div class="sg-popup">' +
      '<strong>' + escapeHtml(location.location_name) + '</strong>' +
      '<div class="sg-popup-sub">' +
      escapeHtml(location.location_type) +
      ' &middot; ' + escapeHtml(location.barangay__barangay_name || '') +
      '</div>';
    if (location.address) {
      html += '<div class="sg-popup-line">' +
        escapeHtml(location.address) + '</div>';
    }
    if (location.status && location.status !== 'active') {
      html += '<div class="sg-popup-line text-muted">Inactive location' +
        '</div>';
    }
    return html + '</div>';
  }

  function addAllLocationMarkers(map) {
    var locations = readLocations();
    var coords = [];

    locations.forEach(function (location) {
      if (location.latitude === null || location.latitude === undefined ||
          location.longitude === null || location.longitude === undefined) {
        return;
      }
      var active = !location.status || location.status === 'active';
      var isBarangay = location.location_type === 'barangay';
      var latlng = [Number(location.latitude), Number(location.longitude)];
      coords.push(latlng);

      L.circleMarker(latlng, {
        radius: isBarangay ? 7 : 6,
        color: '#ffffff',
        weight: 2,
        fillColor: active
          ? (isBarangay ? '#7c3aed' : '#5c7cfa')
          : '#adb5bd',
        fillOpacity: 0.95,
      })
        .bindPopup(locationPopup(location))
        .bindTooltip(location.location_name, {
          direction: 'top',
          offset: [0, -6],
        })
        .addTo(map);
    });

    return coords;
  }

  function fitAllLocations() {
    if (!mapInstance) {
      return;
    }
    if (allLocationCoords.length > 1) {
      mapInstance.fitBounds(L.latLngBounds(allLocationCoords), {
        padding: [24, 24],
        maxZoom: 13,
      });
    } else if (allLocationCoords.length === 1) {
      mapInstance.setView(allLocationCoords[0], 13);
    } else {
      mapInstance.setView(CITY_CENTER, 12);
    }
    mapInstance.invalidateSize();
  }

  function build(container) {
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
        '<i class="ti ti-map-pin-off"></i> Map unavailable offline. ' +
        'Pick your From and To above to search routes.</div>';
      return;
    }

    mapInstance = L.map(container, {
      scrollWheelZoom: false,
      attributionControl: true,
      maxBounds: L.latLngBounds(CITY_BOUNDS),
      maxBoundsViscosity: 0.9,
      minZoom: 9,
      maxZoom: 18,
    });

    /* Esri World Street Map basemap: free, keyless, no watermark.
       OSM's volunteer tiles block some networks and the CARTO public
       endpoint now requires a key, so Esri is the reliable default. */
    L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
      {
        maxZoom: 19,
        attribution:
          'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; ' +
          '<a href="https://www.openstreetmap.org/copyright">' +
          'OpenStreetMap</a> contributors',
      }
    ).addTo(mapInstance);

    allLocationCoords = addAllLocationMarkers(mapInstance);
    fitAllLocations();

    if (window.SakayGuideGPS) {
      gpsController = window.SakayGuideGPS.attach(mapInstance, {
        button: document.querySelector('[data-gps-toggle]'),
        status: document.querySelector('[data-gps-status]'),
      });
    }
  }

  function init() {
    var container = document.getElementById('sg-search-map');
    if (!container) {
      return;
    }

    var body = document.getElementById('sg-city-map-body');
    var toggle = document.getElementById('sg-city-map-toggle');
    var label = document.getElementById('sg-city-map-toggle-label');

    if (toggle && body) {
      toggle.addEventListener('click', function () {
        var willShow = body.hidden;
        body.hidden = !willShow;
        toggle.setAttribute('aria-expanded', String(willShow));
        if (label) {
          label.textContent = willShow ? 'Hide map preview' : 'Show map preview';
        }
        if (!willShow) {
          if (gpsController) {
            gpsController.stop(false);
          }
          return;
        }
        if (!mapInstance) {
          build(container);
        } else {
          /* Leaflet last measured the box while it was display:none. */
          window.setTimeout(fitAllLocations, 60);
        }
      });
    }

    if (!body || !body.hidden) {
      /* Map container is visible from the start - build immediately. */
      build(container);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
