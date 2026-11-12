/* SakayGuide "Where do you want to go?" search controls:
   searchable From/To comboboxes, swap, clear, popular-destination chips,
   and destination fare/time summaries. */
(function () {
  'use strict';

  var dataEl = document.getElementById('location-data');
  var form = document.getElementById('route-search-form');
  if (!dataEl || !form) {
    return;
  }

  var LOCATIONS = [];
  try {
    LOCATIONS = JSON.parse(dataEl.textContent || '[]');
  } catch (error) {
    LOCATIONS = [];
  }

  var summaryUrl = form.getAttribute('data-summary-url') || '';
  var summaries = { originId: null, status: 'idle', data: {} };
  var summaryRequest = 0;

  function formatFare(value) {
    return Number(value).toFixed(2);
  }

  function findByLocationId(id) {
    var wanted = String(id);
    for (var i = 0; i < LOCATIONS.length; i += 1) {
      if (String(LOCATIONS[i].location_id) === wanted) {
        return LOCATIONS[i];
      }
    }
    return null;
  }

  /* Announce the confirmed From/To pair. Nothing on the page listens for
     this any more - the map always shows Kabankalan City only - but the
     event is kept so page scripts can react to a From/To change. Reads the
     hidden inputs directly so it also works inside the combobox closures. */
  function notifySelection() {
    var originInput = form.querySelector('input[name="origin"]');
    var destinationInput = form.querySelector('input[name="destination"]');
    document.dispatchEvent(
      new CustomEvent('sg:selection', {
        detail: {
          origin: originInput ? originInput.value : '',
          destination: destinationInput ? destinationInput.value : ''
        }
      })
    );
  }

  function setupCombobox(root) {
    var textInput = root.querySelector('input[type="text"]');
    var hiddenInput = root.querySelector('input[type="hidden"]');
    var menu = root.querySelector('.sg-combobox-menu');
    if (!textInput || !hiddenInput || !menu) {
      return null;
    }
    var isDestination = hiddenInput.name === 'destination';

    function closeMenu() {
      menu.hidden = true;
      textInput.setAttribute('aria-expanded', 'false');
    }

    function refresh() {
      if (!menu.hidden) {
        renderList(textInput.value);
      }
    }

    /* Fare/time line shown for the destination dropdown once a starting
       location has been chosen. Falls back to the address until the
       summary arrives. */
    function destinationMeta(loc) {
      if (!isDestination || !summaries.originId) {
        return '';
      }
      if (summaries.status === 'loading') {
        return 'Checking fare and time\u2026';
      }
      if (summaries.status === 'error') {
        return '';
      }
      var summary = summaries.data[String(loc.location_id)];
      if (!summary) {
        if (String(loc.location_id) === String(summaries.originId)) {
          return 'Same as starting point';
        }
        return 'Fare and time unavailable';
      }
      if (!summary.has_route) {
        return 'No recorded route from this starting point';
      }
      return (
        'from \u20b1' + formatFare(summary.fare) +
        ' \u00b7 ~' + summary.minutes + ' min'
      );
    }

    function selectLocation(location) {
      hiddenInput.value = String(location.location_id);
      textInput.value = location.location_name;
      closeMenu();
      notifySelection();
    }

    function renderList(query) {
      var q = query.trim().toLowerCase();
      var matches = LOCATIONS.filter(function (loc) {
        if (!q) {
          return true;
        }
        return (
          loc.location_name.toLowerCase().indexOf(q) !== -1 ||
          String(loc.barangay__barangay_name || '').toLowerCase().indexOf(q) !== -1 ||
          String(loc.location_type || '').toLowerCase().indexOf(q) !== -1
        );
      }).slice(0, 8);

      menu.innerHTML = '';
      if (!matches.length) {
        var empty = document.createElement('div');
        empty.className = 'sg-combobox-empty';
        empty.textContent = 'No matching location';
        menu.appendChild(empty);
      } else {
        matches.forEach(function (loc) {
          var item = document.createElement('button');
          item.type = 'button';
          item.className = 'sg-combobox-item';

          var name = document.createElement('span');
          name.className = 'sg-combobox-name';
          name.textContent = loc.location_name;

          var meta = document.createElement('small');
          meta.className = 'sg-combobox-meta';
          var metaText = destinationMeta(loc);
          if (!metaText) {
            metaText =
              loc.address ||
              loc.location_type +
                ' \u00b7 ' +
                String(loc.barangay__barangay_name || '');
          }
          meta.textContent = metaText;

          item.appendChild(name);
          item.appendChild(meta);
          item.addEventListener('mousedown', function (event) {
            event.preventDefault();
            selectLocation(loc);
          });
          menu.appendChild(item);
        });
      }
      menu.hidden = false;
      textInput.setAttribute('aria-expanded', 'true');
    }

    textInput.addEventListener('input', function () {
      if (hiddenInput.value) {
        hiddenInput.value = ''; // edited text = no confirmed selection yet
      }
      renderList(textInput.value);
    });
    textInput.addEventListener('focus', function () {
      renderList(textInput.value);
    });
    textInput.addEventListener('blur', function () {
      window.setTimeout(closeMenu, 120);
    });

    return {
      textInput: textInput,
      hiddenInput: hiddenInput,
      selectLocation: selectLocation,
      refresh: refresh
    };
  }

  var boxes = Array.prototype.map
    .call(document.querySelectorAll('[data-combobox]'), setupCombobox)
    .filter(Boolean);

  if (boxes.length < 2) {
    return;
  }
  var fromBox = boxes[0];
  var toBox = boxes[1];

  /* ---- Destination fare/time summaries -------------------------------
     Once a starting location is chosen, fetch the cheapest fare and its
     estimated time for every other active location. The destination dropdown
     annotates each suggestion and the trip preview under the form shows
     the selected pair's fare/time before Find My Route is submitted. */
  var preview = document.getElementById('sg-trip-preview');
  var previewText = document.getElementById('sg-trip-preview-text');

  function selectedLocation(box) {
    return box.hiddenInput.value
      ? findByLocationId(box.hiddenInput.value)
      : null;
  }

  function renderPreview() {
    if (!preview || !previewText) {
      return;
    }
    var origin = selectedLocation(fromBox);
    var destination = selectedLocation(toBox);
    if (!origin || !destination || !summaries.originId) {
      preview.hidden = true;
      previewText.textContent = '';
      return;
    }

    if (summaries.status === 'loading') {
      previewText.textContent =
        'Checking fare and travel time to ' + destination.location_name +
        '\u2026';
      preview.hidden = false;
      return;
    }
    if (summaries.status === 'error') {
      preview.hidden = true;
      previewText.textContent = '';
      return;
    }

    var summary = summaries.data[String(destination.location_id)];
    if (!summary) {
      preview.hidden = true;
      previewText.textContent = '';
      return;
    }

    if (summary.has_route) {
      previewText.textContent =
        origin.location_name + ' \u2192 ' + destination.location_name +
        ': from \u20b1' + formatFare(summary.fare) +
        ' \u00b7 about ' + summary.minutes + ' min';
    } else {
      previewText.textContent =
        origin.location_name + ' \u2192 ' + destination.location_name +
        ': no recorded route yet';
    }
    preview.hidden = false;
  }

  function updateSummaries(originId) {
    if (!summaryUrl || !originId) {
      summaries.originId = null;
      summaries.status = 'idle';
      summaries.data = {};
      toBox.refresh();
      renderPreview();
      return;
    }

    var wanted = String(originId);
    if (summaries.originId === wanted) {
      toBox.refresh();
      renderPreview();
      return;
    }

    var requestId = summaryRequest + 1;
    summaryRequest = requestId;
    summaries.originId = wanted;
    summaries.status = 'loading';
    summaries.data = {};
    toBox.refresh();
    renderPreview();

    var query =
      summaryUrl + (summaryUrl.indexOf('?') === -1 ? '?' : '&') +
      'origin=' + encodeURIComponent(wanted);
    fetch(query, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
      cache: 'no-store'
    }).then(function (response) {
      if (!response.ok) {
        throw new Error('Destination summary request failed');
      }
      return response.json();
    }).then(function (payload) {
      if (requestId !== summaryRequest) {
        return;
      }
      var next = {};
      (payload.destinations || []).forEach(function (item) {
        next[String(item.location_id)] = item;
      });
      summaries.data = next;
      summaries.status = 'ready';
      toBox.refresh();
      renderPreview();
    }).catch(function () {
      if (requestId !== summaryRequest) {
        return;
      }
      summaries.data = {};
      summaries.status = 'error';
      toBox.refresh();
      renderPreview();
    });
  }

  document.addEventListener('sg:selection', function (event) {
    updateSummaries(event.detail && event.detail.origin);
  });

  /* Live GPS shortcut: live-gps.js finds the nearest recorded place and
     announces it here so the existing combobox state stays authoritative. */
  document.addEventListener('sg:gps-origin', function (event) {
    var location = findByLocationId(
      event.detail && event.detail.location_id
    );
    if (!location) {
      return;
    }
    fromBox.selectLocation(location);
  });

  var swapButton = document.getElementById('swap-button');
  if (swapButton) {
    swapButton.addEventListener('click', function () {
      var fromId = fromBox.hiddenInput.value;
      var fromText = fromBox.textInput.value;
      fromBox.hiddenInput.value = toBox.hiddenInput.value;
      fromBox.textInput.value = toBox.textInput.value;
      toBox.hiddenInput.value = fromId;
      toBox.textInput.value = fromText;
      notifySelection();
    });
  }

  var clearButton = document.getElementById('clear-button');
  if (clearButton) {
    clearButton.addEventListener('click', function () {
      form.reset();
      boxes.forEach(function (box) {
        box.hiddenInput.value = '';
        box.textInput.value = '';
      });
      notifySelection();
      fromBox.textInput.focus();
    });
  }

  Array.prototype.forEach.call(
    document.querySelectorAll('.popular-chip'),
    function (chip) {
      chip.addEventListener('click', function () {
        var location = findByLocationId(chip.getAttribute('data-location-id'));
        if (location) {
          toBox.selectLocation(location);
          fromBox.textInput.focus();
        }
      });
    }
  );

  /* ---- While searching: loading indicator -------------------------------
     Find My Route loads a fresh results page, so the server render always
     hides the indicator again afterwards; restore state only when the
     browser restores the old page from the back-forward cache. */
  var loading = document.getElementById('sg-search-loading');
  var submitButton = form.querySelector('button[type="submit"]');
  form.addEventListener('submit', function () {
    if (loading) {
      loading.hidden = false;
    }
    if (submitButton) {
      submitButton.disabled = true;
    }
  });
  window.addEventListener('pageshow', function (event) {
    if (event.persisted) {
      if (loading) {
        loading.hidden = true;
      }
      if (submitButton) {
        submitButton.disabled = false;
      }
    }
  });

  /* ---- Changed From/To: hide the previous map until a new search --------
     The results page renders #sg-map-card for the pair that was submitted.
     The moment the commuter edits the origin, destination, swaps or clears
     them, the map no longer matches their inputs, so it is hidden (and a
     hint appears) until Find My Route is submitted again. Returning the
     selection back to the searched pair restores the map. */
  var mapCard = document.getElementById('sg-map-card');
  var staleAlert = document.getElementById('sg-stale-results');
  if (mapCard && staleAlert) {
    var initialOrigin = String(form.querySelector('input[name="origin"]').value);
    var initialDestination =
      String(form.querySelector('input[name="destination"]').value);

    document.addEventListener('sg:selection', function (event) {
      var changed =
        String(event.detail.origin) !== initialOrigin ||
        String(event.detail.destination) !== initialDestination;
      mapCard.hidden = changed;
      staleAlert.hidden = !changed;
    });
  }

  /* Publish the current state once at load (e.g. a form redisplayed after
     a validation error already has From/To filled in). This fires the
     sg:selection listener above with the searched pair, which is a
     no-op - the map stays exactly as the server rendered it. */
  notifySelection();
})();
