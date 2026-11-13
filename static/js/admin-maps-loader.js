/* Shared Google Maps loader and small helpers for the admin dashboard.
   The API key is delivered by Django through a JSON script element; it is
   never hard-coded here. */
(function () {
  'use strict';

  var promise = null;

  function readJson(id, fallback) {
    var element = document.getElementById(id);
    if (!element) {
      return fallback;
    }
    try {
      return JSON.parse(element.textContent);
    } catch (error) {
      return fallback;
    }
  }

  function load(config) {
    if (window.google && window.google.maps) {
      return Promise.resolve(window.google.maps);
    }
    if (promise) {
      return promise;
    }
    if (!config || !config.api_key) {
      return Promise.reject(new Error('No Google Maps API key configured.'));
    }

    promise = new Promise(function (resolve, reject) {
      var callbackName = '__sakayAdminMapsReady';
      var settled = false;
      var timer = window.setTimeout(function () {
        if (!settled) {
          settled = true;
          reject(new Error('Google Maps took too long to load.'));
        }
      }, 15000);

      window[callbackName] = function () {
        if (settled) {
          return;
        }
        settled = true;
        window.clearTimeout(timer);
        resolve(window.google.maps);
      };

      var query = [
        'key=' + encodeURIComponent(config.api_key),
        'callback=' + callbackName,
        'loading=async',
        'language=' + encodeURIComponent(config.language || 'en'),
        'region=' + encodeURIComponent(config.region || 'PH')
      ].join('&');

      var script = document.createElement('script');
      script.src = 'https://maps.googleapis.com/maps/api/js?' + query;
      script.async = true;
      script.defer = true;
      script.onerror = function () {
        if (settled) {
          return;
        }
        settled = true;
        window.clearTimeout(timer);
        reject(new Error('Google Maps could not be loaded.'));
      };
      document.head.appendChild(script);
    });

    return promise;
  }

  function dotIcon(color) {
    return {
      path: window.google.maps.SymbolPath.CIRCLE,
      scale: 7,
      fillColor: color,
      fillOpacity: 1,
      strokeColor: '#ffffff',
      strokeWeight: 2
    };
  }

  function showError(container, message) {
    if (!container) {
      return;
    }
    container.innerHTML = '';
    var box = document.createElement('div');
    box.className = 'mgmt-map-placeholder';
    box.style.minHeight = '100%';
    box.innerHTML =
      '<i class="fa-solid fa-triangle-exclamation"></i>' +
      '<h4>Map unavailable</h4>' +
      '<p></p>';
    box.querySelector('p').textContent = message;
    container.appendChild(box);
  }

  window.SakayAdminMaps = {
    readJson: readJson,
    load: load,
    dotIcon: dotIcon,
    showError: showError
  };
})();
