/* SakayGuide Live GPS
 *
 * Adds browser geolocation to the Leaflet maps and a "Use my location"
 * shortcut that selects the nearest recorded place as the starting point.
 *
 * The browser only reveals coordinates with the commuter's permission, and
 * positions are never sent to the server or stored in the database. The map
 * marker and accuracy circle live in a dedicated Leaflet layer so selecting
 * another journey does not remove the GPS position.
 */
(function () {
  'use strict';

  var lastPosition = null;
  var mapController = null;

  function readMapLocations() {
    var dataEl = document.getElementById('kabankalan-locations');
    try {
      return JSON.parse((dataEl && dataEl.textContent) || '[]');
    } catch (error) {
      return [];
    }
  }

  function toRadians(value) {
    return (value * Math.PI) / 180;
  }

  function distanceMeters(lat1, lng1, lat2, lng2) {
    var earthRadius = 6371000;
    var dLat = toRadians(lat2 - lat1);
    var dLng = toRadians(lng2 - lng1);
    var a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) *
      Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * earthRadius * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  function formatDistance(meters) {
    if (meters === null || meters === undefined || isNaN(meters)) {
      return '';
    }
    if (meters < 1000) {
      return Math.round(meters) + ' m';
    }
    return (meters / 1000).toFixed(meters < 10000 ? 1 : 0) + ' km';
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

  function setStatus(element, text, isError) {
    if (!element) {
      return;
    }
    element.textContent = text || '';
    element.hidden = !text;
    element.classList.toggle('is-error', Boolean(isError));
  }

  function setButtonState(button, active) {
    if (!button) {
      return;
    }
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
    button.classList.toggle('is-active', active);
    button.classList.toggle('btn-primary', active);
    button.classList.toggle('btn-outline-primary', !active);
    var label = button.querySelector('[data-gps-toggle-label]');
    if (label) {
      label.textContent = active ? 'Stop GPS' : 'Live GPS';
    }
  }

  function nearestRecordedLocation(lat, lng) {
    var best = null;
    var bestDistance = Infinity;

    readMapLocations().forEach(function (location) {
      if (location.status !== 'active' ||
          location.location_type === 'barangay' ||
          location.latitude === null || location.latitude === undefined ||
          location.longitude === null || location.longitude === undefined) {
        return;
      }
      var distance = distanceMeters(
        lat, lng, Number(location.latitude), Number(location.longitude)
      );
      if (distance < bestDistance) {
        bestDistance = distance;
        best = location;
      }
    });

    if (!best) {
      return null;
    }
    return { location: best, distance: bestDistance };
  }

  /* ------------------------------------------------------------------ */
  /* Live position marker on a Leaflet map                               */
  /* ------------------------------------------------------------------ */
  function attach(map, options) {
    if (!map || typeof L === 'undefined') {
      return null;
    }

    options = options || {};
    var button = options.button ||
      document.querySelector('[data-gps-toggle]');
    var statusElement = options.status ||
      document.querySelector('[data-gps-status]');
    var layer = L.layerGroup().addTo(map);
    var marker = null;
    var accuracyCircle = null;
    var watchId = null;
    var active = false;
    var seenFix = false;
    var savedMaxBounds = map.options.maxBounds ?
      L.latLngBounds(map.options.maxBounds) : null;
    var relaxedBounds = false;
    var worldBounds = [[-85, -180], [85, 180]];

    function relaxBounds(latlng) {
      if (!savedMaxBounds || relaxedBounds) {
        return;
      }
      if (!savedMaxBounds.contains(latlng)) {
        map.setMaxBounds(worldBounds);
        relaxedBounds = true;
      }
    }

    function restoreBounds() {
      if (relaxedBounds && savedMaxBounds) {
        map.setMaxBounds(savedMaxBounds);
        relaxedBounds = false;
      }
    }

    function clearLayers() {
      layer.clearLayers();
      marker = null;
      accuracyCircle = null;
    }

    function ensureLayers(latlng) {
      if (!marker) {
        marker = L.marker(latlng, {
          icon: L.divIcon({
            className: 'sg-gps-marker',
            html: '<span class="sg-gps-dot" aria-hidden="true"></span>',
            iconSize: [22, 22],
            iconAnchor: [11, 11],
          }),
          zIndexOffset: 1000,
          keyboard: false,
          title: 'Your live GPS position',
        }).addTo(layer);
        marker.bindTooltip('You are here', {
          direction: 'top',
          offset: [0, -12],
        });

        accuracyCircle = L.circle(latlng, {
          radius: 0,
          color: '#1c7ed6',
          weight: 1,
          fillColor: '#1c7ed6',
          fillOpacity: 0.12,
          interactive: false,
        }).addTo(layer);
      } else {
        marker.setLatLng(latlng);
        accuracyCircle.setLatLng(latlng);
      }
    }

    function onPosition(position) {
      if (!active) {
        return;
      }
      var coords = position.coords;
      var latlng = [coords.latitude, coords.longitude];
      var accuracy = Number(coords.accuracy) || 0;

      lastPosition = {
        lat: coords.latitude,
        lng: coords.longitude,
        accuracy: accuracy,
        timestamp: position.timestamp,
      };

      relaxBounds(latlng);
      ensureLayers(latlng);
      accuracyCircle.setRadius(accuracy);

      if (!seenFix) {
        seenFix = true;
        map.setView(latlng, Math.max(map.getZoom(), 16));
      } else if (!map.getBounds().contains(latlng)) {
        map.panTo(latlng, { animate: true });
      }

      setStatus(
        statusElement,
        'Live GPS on' +
          (accuracy ? ' \u00b7 accuracy \u00b1' + formatDistance(accuracy) : ''),
        false
      );
    }

    function stop(silent) {
      if (!active && watchId === null) {
        return;
      }
      if (watchId !== null && navigator.geolocation) {
        navigator.geolocation.clearWatch(watchId);
        watchId = null;
      }
      active = false;
      seenFix = false;
      clearLayers();
      restoreBounds();
      setButtonState(button, false);
      if (!silent) {
        setStatus(statusElement, 'Live GPS stopped.', false);
      }
    }

    function fail(error) {
      if (!active) {
        return;
      }
      stop(true);
      setStatus(statusElement, gpsErrorMessage(error), true);
    }

    function start() {
      if (active) {
        return;
      }
      var contextError = locationContextError();
      if (contextError) {
        setStatus(statusElement, contextError, true);
        return;
      }
      if (!navigator.geolocation) {
        setStatus(
          statusElement,
          'Live GPS is not supported by this browser.',
          true
        );
        return;
      }

      active = true;
      seenFix = false;
      setButtonState(button, true);
      setStatus(statusElement, 'Requesting your current location\u2026', false);

      try {
        watchId = navigator.geolocation.watchPosition(onPosition, fail, {
          enableHighAccuracy: true,
          maximumAge: 5000,
          timeout: 15000,
        });
      } catch (error) {
        active = false;
        setButtonState(button, false);
        setStatus(statusElement, gpsErrorMessage(error), true);
      }
    }

    function toggle() {
      if (active) {
        stop(false);
      } else {
        start();
      }
    }

    if (button) {
      button.addEventListener('click', toggle);
    }

    var controller = {
      map: map,
      start: start,
      stop: stop,
      toggle: toggle,
      isActive: function () {
        return active;
      },
    };

    mapController = controller;
    return controller;
  }

  /* ------------------------------------------------------------------ */
  /* "Use my location" in the route search form                          */
  /* ------------------------------------------------------------------ */
  function bindUseOrigin() {
    var button = document.getElementById('gps-use-origin');
    if (!button) {
      return;
    }
    var statusElement = document.getElementById('gps-origin-status');

    button.addEventListener('click', function () {
      var contextError = locationContextError();
      if (contextError) {
        setStatus(statusElement, contextError, true);
        return;
      }
      if (!navigator.geolocation) {
        setStatus(
          statusElement,
          'Live GPS is not supported by this browser.',
          true
        );
        return;
      }

      button.disabled = true;
      setStatus(statusElement, 'Finding your current location\u2026', false);

      function onSuccess(position) {
        button.disabled = false;
        var result = nearestRecordedLocation(
          position.coords.latitude, position.coords.longitude
        );
        if (!result) {
          setStatus(
            statusElement,
            'No recorded locations with map coordinates are available.',
            true
          );
          return;
        }

        lastPosition = {
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          accuracy: Number(position.coords.accuracy) || 0,
          timestamp: position.timestamp,
        };

        document.dispatchEvent(new CustomEvent('sg:gps-origin', {
          detail: {
            location_id: result.location.location_id,
            distance_m: result.distance,
          },
        }));
        setStatus(
          statusElement,
          'Using ' + result.location.location_name + ' \u00b7 about ' +
            formatDistance(result.distance) + ' from your GPS position.',
          false
        );
      }

      function onError(error) {
        button.disabled = false;
        setStatus(statusElement, gpsErrorMessage(error), true);
      }

      try {
        navigator.geolocation.getCurrentPosition(onSuccess, onError, {
          enableHighAccuracy: true,
          maximumAge: 0,
          timeout: 15000,
        });
      } catch (error) {
        button.disabled = false;
        setStatus(statusElement, gpsErrorMessage(error), true);
      }
    });
  }

  function init() {
    bindUseOrigin();
  }

  window.SakayGuideGPS = {
    attach: attach,
    nearestRecordedLocation: nearestRecordedLocation,
    getLastPosition: function () {
      return lastPosition;
    },
    getMapController: function () {
      return mapController;
    },
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
