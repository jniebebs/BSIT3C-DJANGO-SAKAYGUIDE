/* SakayGuide "Where do you want to go?" search controls:
   searchable From/To comboboxes, swap, clear, popular-destination chips. */
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

    function closeMenu() {
      menu.hidden = true;
      textInput.setAttribute('aria-expanded', 'false');
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
          meta.textContent =
            loc.location_type +
            ' \u00b7 ' +
            String(loc.barangay__barangay_name || '');

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
      selectLocation: selectLocation
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
