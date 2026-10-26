/* Kabankalan City map for the Find My Route page: Leaflet on keyless
   Esri streets tiles, clamped to the Kabankalan City area. The map only
   ever shows Kabankalan City - no From/To pins are drawn on it.
   If Leaflet is unavailable the map degrades to a text note. */
(function () {
  'use strict';

  /* Rough Kabankalan City boundary [southwest, northeast] - the map cannot
     pan or zoom out beyond it. */
  var CITY_BOUNDS = [[10.17, 122.75], [10.32, 122.91]];

  /* Kabankalan City proper, so the map always opens on the city. */
  var CITY_CENTER = [10.2435, 122.8183];

  function init() {
    var container = document.getElementById('sg-search-map');
    if (!container) {
      return;
    }

    if (typeof L === 'undefined') {
      container.classList.add('sg-map-offline');
      container.innerHTML =
        '<div class="sg-map-fallback">' +
        '<i class="ti ti-map-pin-off"></i> Map unavailable offline. ' +
        'Pick your From and To above to search routes.</div>';
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

    /* Kabankalan City only: the view never follows the From/To picks. */
    map.setView(CITY_CENTER, 12);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
