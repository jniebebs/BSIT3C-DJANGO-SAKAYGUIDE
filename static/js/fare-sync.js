/* SakayGuide live fare synchronisation.
 *
 * The administrator saves fares in the management console (the shared
 * sakayguide_db.route_fares table). A commuter may already have a dashboard
 * or journey result on screen, so this script polls a small JSON endpoint
 * that fingerprints every currently effective fare. When the fingerprint
 * changes the commuter is told before using the old amount:
 *
 *   - on the commuter dashboard the page refreshes itself;
 *   - on search/results pages a banner offers a "Refresh now" action, so a
 *     half-typed search is never thrown away without warning.
 *
 * The page's own fare version is rendered by Django, so a change that
 * happened between rendering and the first poll is still detected.
 */
(function () {
  'use strict';

  var script = document.currentScript;
  if (!script) {
    var scripts = document.querySelectorAll('script[data-fare-version-url]');
    script = scripts.length ? scripts[scripts.length - 1] : null;
  }
  if (!script) {
    return;
  }

  var versionUrl = script.getAttribute('data-fare-version-url');
  if (!versionUrl) {
    return;
  }

  var knownVersion = script.getAttribute('data-fare-version') || '';
  var autoReload = script.getAttribute('data-fare-autoreload') === 'true';
  var reloadTimer = null;
  var banner = null;

  function bannerHost() {
    return document.querySelector('.page-body .container-xl')
      || document.querySelector('.page-body')
      || document.body;
  }

  function showBanner() {
    if (banner) {
      return;
    }
    banner = document.createElement('div');
    banner.className = 'alert alert-warning d-flex flex-wrap align-items-center gap-2 sg-fare-updated';
    banner.setAttribute('role', 'alert');
    banner.setAttribute('aria-live', 'assertive');
    /* Keep the notice visible even when the commuter has scrolled down the
       journey results before proceeding. */
    banner.style.position = 'sticky';
    banner.style.top = '0';
    banner.style.zIndex = '1050';

    var icon = document.createElement('i');
    icon.className = 'ti ti-refresh';

    var text = document.createElement('div');
    text.className = 'flex-grow-1';
    text.innerHTML =
      '<strong>Fares were updated by the administrator.</strong> ' +
      'Refresh to see the latest amounts before you continue.';

    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-warning btn-sm';
    button.innerHTML = '<i class="ti ti-refresh me-1"></i>Refresh now';
    button.addEventListener('click', function () {
      window.location.reload();
    });

    banner.appendChild(icon);
    banner.appendChild(text);
    banner.appendChild(button);

    var host = bannerHost();
    host.insertBefore(banner, host.firstChild);

    if (autoReload) {
      var seconds = 3;
      var note = document.createElement('span');
      note.className = 'small w-100';
      note.textContent = 'Refreshing automatically in ' + seconds + ' seconds...';
      banner.appendChild(note);
      reloadTimer = window.setInterval(function () {
        seconds -= 1;
        if (seconds <= 0) {
          window.clearInterval(reloadTimer);
          window.location.reload();
          return;
        }
        note.textContent = 'Refreshing automatically in ' + seconds + ' seconds...';
      }, 1000);
    }
  }

  function check() {
    if (document.hidden) {
      return;
    }
    var request;
    try {
      request = window.fetch(versionUrl, {
        cache: 'no-store',
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
    } catch (error) {
      return;
    }
    request.then(function (response) {
      if (!response.ok) {
        return null;
      }
      return response.json();
    }).then(function (data) {
      if (!data || !data.version) {
        return;
      }
      if (!knownVersion) {
        knownVersion = data.version;
        return;
      }
      if (data.version !== knownVersion) {
        showBanner();
      }
    }).catch(function () {
      /* Offline or endpoint unavailable: keep the page as it is. */
    });
  }

  check();
  window.setInterval(check, 15000);
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) {
      check();
    }
  });
})();
