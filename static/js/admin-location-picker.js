/* Map picker for the location create/edit form. */
(function () {
  'use strict';

  var maps = window.SakayAdminMaps;
  if (!maps) {
    return;
  }

  var container = document.getElementById('location-picker-map');
  if (!container) {
    return;
  }

  var config = maps.readJson('google-maps-config', null);
  if (!config) {
    return;
  }

  var latInput = document.getElementById(container.getAttribute('data-lat-field'));
  var lngInput = document.getElementById(container.getAttribute('data-lng-field'));
  var latOutput = document.getElementById('location-picker-lat');
  var lngOutput = document.getElementById('location-picker-lng');
  var statusBox = document.getElementById('location-picker-status');
  var searchInput = document.getElementById('location-picker-search');
  var searchButton = document.getElementById('location-picker-search-btn');

  var defaultCenter = config.center || { lat: 9.9926, lng: 122.8135 };
  var map = null;
  var marker = null;

  function setStatus(message, tone) {
    if (!statusBox) {
      return;
    }
    statusBox.className = 'mgmt-picker-status' + (tone ? ' is-' + tone : '');
    var icon = statusBox.querySelector('i');
    if (icon) {
      icon.className = 'fa-solid ' + (tone === 'error'
        ? 'fa-triangle-exclamation'
        : tone === 'success'
          ? 'fa-circle-check'
          : 'fa-location-crosshairs');
    }
    var text = statusBox.querySelector('span');
    if (text) {
      text.textContent = message;
    }
  }

  function readInputs() {
    var lat = parseFloat(latInput ? latInput.value : '');
    var lng = parseFloat(lngInput ? lngInput.value : '');
    if (isNaN(lat) || isNaN(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 180) {
      return null;
    }
    return { lat: lat, lng: lng };
  }

  function updateOutputs(position) {
    if (latOutput) {
      latOutput.textContent = position ? position.lat.toFixed(7) : 'Not set';
    }
    if (lngOutput) {
      lngOutput.textContent = position ? position.lng.toFixed(7) : 'Not set';
    }
  }

  function applyPosition(position, centerMap) {
    if (!position) {
      return;
    }
    if (latInput) {
      latInput.value = position.lat.toFixed(7);
    }
    if (lngInput) {
      lngInput.value = position.lng.toFixed(7);
    }
    updateOutputs(position);

    if (map && marker) {
      marker.setPosition(position);
      if (centerMap) {
        map.panTo(position);
        map.setZoom(16);
      }
    }
    setStatus('Pin set at ' + position.lat.toFixed(6) + ', ' + position.lng.toFixed(6), 'success');
  }

  function placeMarker(position, centerMap) {
    if (!map) {
      return;
    }
    if (!marker) {
      marker = new google.maps.Marker({
        map: map,
        position: position,
        draggable: true,
        icon: maps.dotIcon('#6366f1')
      });
      marker.addListener('dragend', function () {
        applyPosition({
          lat: marker.getPosition().lat(),
          lng: marker.getPosition().lng()
        }, false);
      });
    } else {
      marker.setPosition(position);
    }
    applyPosition(position, centerMap);
  }

  function manualInputChanged() {
    var position = readInputs();
    if (position) {
      placeMarker(position, true);
    } else {
      updateOutputs(null);
      setStatus('Enter both latitude and longitude, or click the map to set the pin.', '');
    }
  }

  function searchPlace() {
    if (!searchInput || !searchInput.value.trim()) {
      setStatus('Type a place or address to search.', 'error');
      return;
    }
    var geocoder = new google.maps.Geocoder();
    setStatus('Searching…', '');
    geocoder.geocode({
      address: searchInput.value.trim(),
      bounds: config.bounds,
      componentRestrictions: { country: 'PH' }
    }, function (results, status) {
      if (status === 'OK' && results && results.length) {
        var result = results[0];
        var position = {
          lat: result.geometry.location.lat(),
          lng: result.geometry.location.lng()
        };
        placeMarker(position, true);
        setStatus('Found: ' + result.formatted_address, 'success');
      } else if (status === 'ZERO_RESULTS') {
        setStatus('No matching place was found. Try a nearby landmark or barangay.', 'error');
      } else {
        setStatus('The place search failed (' + status + '). You can still click the map.', 'error');
      }
    });
  }

  maps.load(config).then(function () {
    var initial = readInputs();
    map = new google.maps.Map(container, {
      center: initial || defaultCenter,
      zoom: initial ? 16 : 13,
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: true,
      clickableIcons: false,
      gestureHandling: 'greedy',
      restriction: config.bounds ? { latLngBounds: config.bounds, strictBounds: false } : undefined
    });

    if (initial) {
      marker = new google.maps.Marker({
        map: map,
        position: initial,
        draggable: true,
        icon: maps.dotIcon('#6366f1')
      });
      marker.addListener('dragend', function () {
        applyPosition({
          lat: marker.getPosition().lat(),
          lng: marker.getPosition().lng()
        }, false);
      });
      setStatus('Existing coordinates loaded. Click or drag the pin to adjust.', 'success');
    }

    map.addListener('click', function (event) {
      placeMarker({
        lat: event.latLng.lat(),
        lng: event.latLng.lng()
      }, false);
    });

    if (searchButton) {
      searchButton.addEventListener('click', searchPlace);
    }
    if (searchInput) {
      searchInput.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          event.preventDefault();
          searchPlace();
        }
      });
    }
    [latInput, lngInput].forEach(function (input) {
      if (input) {
        input.addEventListener('change', manualInputChanged);
      }
    });
    updateOutputs(initial);
  }).catch(function (error) {
    maps.showError(container, error && error.message
      ? error.message
      : 'The map picker could not be loaded.');
    setStatus('The map picker is unavailable. Enter coordinates manually.', 'error');
  });
})();
