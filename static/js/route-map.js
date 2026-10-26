/* Renders the journey maps with Leaflet on keyless Esri streets tiles,
   clamped to the Kabankalan City area so the view never drifts to other
   towns or open sea. The map shows Kabankalan City only - no trip pins are
   drawn on it. If Leaflet is unavailable the map degrades to a text note
   (journey details stay visible). */
(function () {
  'use strict';

  /* Rough Kabankalan City boundary [southwest, northeast] - the map cannot
     pan or zoom out beyond it. */
  var CITY_BOUNDS = [[10.17, 122.75], [10.32, 122.91]];

  /* Kabankalan City proper, so every map opens on the city. */
  var CITY_CENTER = [10.2435, 122.8183];

  function init() {
    var dataEl = document.getElementById('journey-maps');
    var containers = document.querySelectorAll('.sg-map[data-map-index]');
    if (!containers.length) {
      return;
    }

    var maps = [];
    try {
      maps = JSON.parse((dataEl && dataEl.textContent) || '[]');
    } catch (error) {
      maps = [];
    }

    Array.prototype.forEach.call(containers, function (container) {
      var index = parseInt(container.getAttribute('data-map-index'), 10);
      var cfg = maps[index];

      if (!cfg || !cfg.points || !cfg.points.length) {
        container.classList.add('d-none');
        return;
      }

      if (typeof L === 'undefined') {
        container.classList.add('sg-map-offline');
        container.innerHTML =
          '<div class="sg-map-fallback">' +
          '<i class="ti ti-map-pin-off"></i> Map unavailable offline. ' +
          'The stops, fare and travel time above are still accurate ' +
          'for this search.</div>';
        return;
      }

      var map = L.map(container, {
        scrollWheelZoom: false,
        attributionControl: true,
        maxBounds: L.latLngBounds(CITY_BOUNDS),
        maxBoundsViscosity: 1.0,
        minZoom: 11,
        maxZoom: 18
      });

      /* Keyless Esri streets tiles: no API key and no usage-policy blocks. */
      L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/' +
          'World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        {
          maxZoom: 18,
          maxNativeZoom: 19,
          attribution:
            'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, ' +
            'Intermap, iPC, NRCAN, Esri Japan, METI, Esri China (Hong Kong), ' +
            'Esri (Thailand), TomTom'
        }
      ).addTo(map);

      /* Kabankalan City only: maxBounds keeps the view inside the city. */
      map.setView(CITY_CENTER, 12);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
