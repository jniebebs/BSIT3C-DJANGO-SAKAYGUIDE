/* Google Maps renderer for the administrator map pages and route detail. */
(function () {
  'use strict';

  var maps = window.SakayAdminMaps;
  if (!maps) {
    return;
  }

  var config = maps.readJson('google-maps-config', null);
  var routeContainer = document.getElementById('route-detail-map');
  var managementContainer = document.getElementById('management-map');
  if (!config || (!routeContainer && !managementContainer)) {
    return;
  }

  function buildMap(container) {
    return new google.maps.Map(container, {
      center: config.center || { lat: 9.9926, lng: 122.8135 },
      zoom: 13,
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: true,
      clickableIcons: false,
      gestureHandling: 'greedy',
      restriction: config.bounds ? { latLngBounds: config.bounds, strictBounds: false } : undefined
    });
  }

  function infoContent(payload) {
    var wrapper = document.createElement('div');
    wrapper.className = 'mgmt-map-info';

    var title = document.createElement('strong');
    title.textContent = payload.name || 'Unnamed location';
    wrapper.appendChild(title);

    if (payload.roleLabel) {
      var role = document.createElement('div');
      role.textContent = payload.roleLabel;
      wrapper.appendChild(role);
    }
    if (payload.detail) {
      var detail = document.createElement('div');
      detail.className = 'text-muted';
      detail.textContent = payload.detail;
      wrapper.appendChild(detail);
    }
    if (payload.coords) {
      var coords = document.createElement('div');
      coords.className = 'text-muted';
      coords.textContent =
        payload.coords.lat.toFixed(6) + ', ' + payload.coords.lng.toFixed(6);
      wrapper.appendChild(coords);
    }
    if (payload.editUrl) {
      var link = document.createElement('a');
      link.href = payload.editUrl;
      link.textContent = 'Edit location';
      wrapper.appendChild(link);
    }
    return wrapper;
  }

  function addMarker(map, infoWindow, payload) {
    var marker = new google.maps.Marker({
      map: map,
      position: payload.coords,
      title: payload.name,
      icon: maps.dotIcon(payload.color),
      zIndex: payload.zIndex || 1
    });
    marker.addListener('click', function () {
      infoWindow.setContent(infoContent(payload));
      infoWindow.open({ map: map, anchor: marker });
    });
    return marker;
  }

  function fitTo(map, points) {
    if (!points.length) {
      return;
    }
    if (points.length === 1) {
      map.setCenter(points[0]);
      map.setZoom(16);
      return;
    }
    var bounds = new google.maps.LatLngBounds();
    points.forEach(function (point) {
      bounds.extend(point);
    });
    map.fitBounds(bounds, { top: 40, right: 40, bottom: 40, left: 40 });
  }

  function drawRoute(map, data) {
    var points = (data.points || []).filter(function (point) {
      return point && typeof point.lat === 'number' && typeof point.lng === 'number';
    });
    if (points.length < 2) {
      return;
    }

    new google.maps.Polyline({
      map: map,
      path: points,
      strokeColor: '#ffffff',
      strokeOpacity: 0.9,
      strokeWeight: 9,
      zIndex: 1
    });
    new google.maps.Polyline({
      map: map,
      path: points,
      strokeColor: '#6366f1',
      strokeOpacity: 0.95,
      strokeWeight: 5,
      zIndex: 2
    });
  }

  function renderRouteMap(map, data) {
    var infoWindow = new google.maps.InfoWindow();
    var points = [];
    var colors = {
      origin: '#22c55e',
      stop: '#6366f1',
      transfer: '#f59e0b',
      destination: '#ef4444'
    };
    var labels = {
      origin: 'Origin / boarding point',
      stop: 'Route stop',
      transfer: 'Transfer point',
      destination: 'Destination / drop-off point'
    };

    (data.markers || []).forEach(function (marker) {
      if (!marker.coords) {
        return;
      }
      points.push(marker.coords);
      addMarker(map, infoWindow, {
        name: marker.name,
        coords: marker.coords,
        color: colors[marker.role] || colors.stop,
        roleLabel: labels[marker.role] || labels.stop,
        detail: marker.order ? 'Stop order #' + marker.order : '',
        zIndex: marker.role === 'origin' || marker.role === 'destination' ? 4 : 2
      });
    });

    drawRoute(map, data);
    fitTo(map, points);
  }

  function renderManagementMap(map, data) {
    var infoWindow = new google.maps.InfoWindow();
    var points = [];

    data.forEach(function (marker) {
      if (!marker.has_coords || !marker.coords) {
        return;
      }
      points.push(marker.coords);
      addMarker(map, infoWindow, {
        name: marker.name,
        coords: marker.coords,
        color: marker.status === 'active' ? '#14b8a6' : '#94a3b8',
        roleLabel: (marker.type || 'location') + ' · ' + (marker.barangay || ''),
        detail: marker.status === 'active' ? 'Active location' : 'Inactive location',
        editUrl: marker.edit_url
      });
    });

    var selectedRoute = maps.readJson('route-map-data', null);
    if (selectedRoute) {
      drawRoute(map, selectedRoute);
      (selectedRoute.points || []).forEach(function (point) {
        points.push(point);
      });
    }

    fitTo(map, points);
  }

  maps.load(config).then(function () {
    if (routeContainer) {
      var routeData = maps.readJson('route-map-data', null);
      if (routeData) {
        renderRouteMap(buildMap(routeContainer), routeData);
      }
    }

    if (managementContainer) {
      var markerData = maps.readJson('management-markers', []);
      var map = buildMap(managementContainer);
      renderManagementMap(map, markerData || []);
    }
  }).catch(function (error) {
    var message = error && error.message
      ? error.message
      : 'The map could not be loaded.';
    maps.showError(routeContainer, message);
    maps.showError(managementContainer, message);
  });
})();
