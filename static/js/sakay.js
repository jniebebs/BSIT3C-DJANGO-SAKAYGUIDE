/* SakayGuide - Commuter route search frontend */
(function () {
  'use strict';

  var API_BASE = '/api';
  var originInput = document.getElementById('originInput');
  var originId = document.getElementById('originId');
  var destinationInput = document.getElementById('destinationInput');
  var destinationId = document.getElementById('destinationId');
  var findRouteBtn = document.getElementById('findRouteBtn');
  var routeResults = document.getElementById('routeResults');
  var hideResultsBtn = document.getElementById('hideResultsBtn');
  var journeyList = document.getElementById('journeyList');
  var journeyNotFound = document.getElementById('journeyNotFound');
  var resultOrigin = document.getElementById('resultOrigin');
  var resultDestination = document.getElementById('resultDestination');
  var saveRouteBtn = document.getElementById('saveRouteBtn');
  var savedRouteBtn = document.getElementById('savedRouteBtn');
  var popularRoutesContainer = document.getElementById('popularRoutes');
  var recentSearchesContainer = document.getElementById('recentSearches');

  var currentJourney = null;
  var isSaved = false;

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------
  function getCsrfToken() {
    var match = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    return match ? match[1] : '';
  }

  function formatMoney(value) {
    return '₱' + parseFloat(value).toFixed(2);
  }

  function formatMinutes(value) {
    return value.toFixed(0) + ' min';
  }

  function show(el) {
    if (el) el.style.display = '';
  }

  function hide(el) {
    if (el) el.style.display = 'none';
  }

  function setInputSelect(input, hidden, terminal) {
    input.value = terminal.name;
    hidden.value = terminal.id;
    input.dataset.terminalId = terminal.id;
    input.dataset.terminalName = terminal.name;
  }

  function clearInput(input, hidden) {
    input.value = '';
    hidden.value = '';
    delete input.dataset.terminalId;
    delete input.dataset.terminalName;
  }

  // ------------------------------------------------------------------
  // Terminal autocomplete
  // ------------------------------------------------------------------
  function setupAutocomplete(input, hiddenId) {
    var dropdown = document.createElement('div');
    dropdown.className = 'autocomplete-dropdown';
    dropdown.style.display = 'none';
    input.parentNode.appendChild(dropdown);

    var timeoutId;
    var selectedIndex = -1;
    var items = [];

    function render() {
      dropdown.innerHTML = '';
      if (items.length === 0) {
        hide(dropdown);
        selectedIndex = -1;
        return;
      }
      items.forEach(function (item, index) {
        var div = document.createElement('div');
        div.className = 'autocomplete-item' + (index === selectedIndex ? ' active' : '');
        div.textContent = item.name + (item.municipality ? ', ' + item.municipality : '');
        div.dataset.id = item.id;
        div.addEventListener('mousedown', function (e) {
          e.preventDefault();
          setInputSelect(input, hiddenId, item);
          hide(dropdown);
          selectedIndex = -1;
          items = [];
        });
        dropdown.appendChild(div);
      });
      show(dropdown);
    }

    input.addEventListener('input', function () {
      var q = input.value.trim();
      clearTimeout(timeoutId);
      if (q.length < 2) {
        hide(dropdown);
        items = [];
        selectedIndex = -1;
        hiddenId.value = '';
        delete input.dataset.terminalId;
        delete input.dataset.terminalName;
        return;
      }
      timeoutId = setTimeout(function () {
        fetch(API_BASE + '/terminals/search/?q=' + encodeURIComponent(q) + '&limit=10')
          .then(function (r) { return r.json(); })
          .then(function (data) {
            items = data.results || [];
            selectedIndex = -1;
            if (items.length > 0) render();
            else hide(dropdown);
          })
          .catch(function () {
            hide(dropdown);
          });
      }, 250);
    });

    input.addEventListener('keydown', function (e) {
      if (items.length === 0) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
        render();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedIndex = Math.max(selectedIndex - 1, 0);
        render();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (selectedIndex >= 0 && items[selectedIndex]) {
          setInputSelect(input, hiddenId, items[selectedIndex]);
          hide(dropdown);
          selectedIndex = -1;
          items = [];
        }
      } else if (e.key === 'Escape') {
        hide(dropdown);
        selectedIndex = -1;
        items = [];
      }
    });

    document.addEventListener('click', function (e) {
      if (!input.contains(e.target) && !dropdown.contains(e.target)) {
        hide(dropdown);
      }
    });
  }

  // ------------------------------------------------------------------
  // Popular routes
  // ------------------------------------------------------------------
  function loadPopularRoutes() {
    if (!popularRoutesContainer) return;
    fetch(API_BASE + '/routes/?limit=8')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var routes = data.routes || [];
        popularRoutesContainer.innerHTML = '';
        routes.slice(0, 6).forEach(function (route) {
          var col = document.createElement('div');
          col.className = 'col';
          col.innerHTML =
            '<div class="card h-100 popular-route-card" style="cursor: pointer;">' +
            '  <div class="card-body d-flex flex-column">' +
            '    <div class="d-flex align-items-center mb-2">' +
            '      <span class="badge bg-route-mode me-2" style="background:' + route.transport_mode.color + '; color: #fff;">' +
            route.transport_mode.name +
            '      </span>' +
            '      <span class="fw-semibold small text-truncate" style="max-width: 120px;">' + route.code + '</span>' +
            '    </div>' +
            '    <div class="flex-grow-1"><div class="route-name fw-bold text-dark">' + route.name + '</div></div>' +
            '    <div class="mt-auto small text-muted">' +
            route.origin_terminal.name +
            ' &rarr; ' +
            route.destination_terminal.name +
            '    </div>' +
            '    <div class="mt-2 small">Base fare: <strong>' + formatMoney(route.base_fare) + '</strong></div>' +
            '  </div>' +
            '</div>';
          col.querySelector('.popular-route-card').addEventListener('click', function () {
            originInput.value = route.origin_terminal.name;
            originId.value = route.origin_terminal.id;
            destinationInput.value = route.destination_terminal.name;
            destinationId.value = route.destination_terminal.id;
            findRouteBtn.click();
          });
          popularRoutesContainer.appendChild(col);
        });
      })
      .catch(function () {
        // Silently ignore; popular routes are optional
      });
  }

  // ------------------------------------------------------------------
  // Recent searches
  // ------------------------------------------------------------------
  function loadRecentSearches() {
    if (!recentSearchesContainer) return;
    // Recent searches are loaded server-side in the template.
    // This is a placeholder for future enhancement.
  }

  // ------------------------------------------------------------------
  // Route planning
  // ------------------------------------------------------------------
  function planRoute() {
    var oid = originId.value;
    var did = destinationId.value;

    if (!oid || !did) {
      alert('Please select both a starting point and a destination.');
      return;
    }

    if (oid === did) {
      alert('Origin and destination cannot be the same terminal.');
      return;
    }

    var btnText = findRouteBtn.innerHTML;
    findRouteBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Searching...';
    findRouteBtn.disabled = true;

    hide(routeResults);
    hide(journeyNotFound);
    hide(saveRouteBtn);
    hide(savedRouteBtn);

    fetch(
      API_BASE + '/route-plan/?origin=' + oid + '&destination=' + did + '&optimize=fastest'
    )
      .then(function (r) { return r.json(); })
      .then(function (data) {
        findRouteBtn.innerHTML = btnText;
        findRouteBtn.disabled = false;

        if (!data.found) {
          show(journeyNotFound);
          show(routeResults);
          resultOrigin.textContent = data.origin ? data.origin.name : '';
          resultDestination.textContent = data.destination ? data.destination.name : '';
          return;
        }

        currentJourney = data;
        renderJourney(data);

        // Record search history
        fetch(API_BASE.replace('/api', '') + '/sakay/record-search/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({
            origin_terminal_id: oid,
            destination_terminal_id: did,
          }),
        }).catch(function () {
          // Silently ignore; recording history is non-critical
        });

        // Check if already saved
        checkSavedStatus(oid, did);

        show(routeResults);
      })
      .catch(function () {
        findRouteBtn.innerHTML = btnText;
        findRouteBtn.disabled = false;
        alert('Unable to plan route. Please try again.');
      });
  }

  function checkSavedStatus(oid, did) {
    // We check saved status by looking at the saved routes page data.
    // For simplicity, we attempt to save and handle "already exists" via
    // the server response. The save button toggles based on response.
  }

  function renderJourney(journey) {
    journeyList.innerHTML = '';
    resultOrigin.textContent = journey.origin ? journey.origin.name : '';
    resultDestination.textContent = journey.destination ? journey.destination.name : '';

    // Summary bar
    var summary = document.createElement('div');
    summary.className = 'row mb-3';
    summary.innerHTML =
      '<div class="col-md-4"><div class="card bg-light"><div class="card-body text-center">' +
      '<div class="small text-muted">Total Fare</div><div class="fw-bold h5">' +
      formatMoney(journey.total_fare) + '</div></div></div></div>' +
      '<div class="col-md-4"><div class="card bg-light"><div class="card-body text-center">' +
      '<div class="small text-muted">Travel Time</div><div class="fw-bold h5">' +
      formatMinutes(journey.total_time_minutes) + '</div></div></div></div>' +
      '<div class="col-md-4"><div class="card bg-light"><div class="card-body text-center">' +
      '<div class="small text-muted">Transfers</div><div class="fw-bold h5">' +
      journey.transfers + '</div></div></div></div>';
    journeyList.appendChild(summary);

    // Steps
    if (journey.steps && journey.steps.length) {
      var stepsCard = document.createElement('div');
      stepsCard.className = 'card mb-3';
      var stepsBody = document.createElement('div');
      stepsBody.className = 'card-body';
      var stepsTitle = document.createElement('h6');
      stepsTitle.className = 'card-title mb-3';
      stepsTitle.textContent = 'Step-by-Step Instructions';
      stepsBody.appendChild(stepsTitle);
      var stepsList = document.createElement('ul');
      stepsList.className = 'list-unstyled journey-steps';
      journey.steps.forEach(function (step) {
        var li = document.createElement('li');
        li.className = 'mb-2 d-flex align-items-start';
        var iconClass = step.type === 'transfer' ? 'fa-exchange-alt text-warning' :
                        step.type === 'board' ? 'fa-sign-in text-success' :
                        step.type === 'ride' ? 'fa-bus text-info' :
                        step.type === 'alight' ? 'fa-sign-out text-secondary' :
                        'fa-info text-muted';
        li.innerHTML =
          '<i class="fa-solid ' + iconClass + ' me-2 mt-1"></i>' +
          '<div>' + step.text + '</div>';
        stepsList.appendChild(li);
      });
      stepsBody.appendChild(stepsList);
      stepsCard.appendChild(stepsBody);
      journeyList.appendChild(stepsCard);
    }

    // Leg details
    if (journey.legs && journey.legs.length) {
      journey.legs.forEach(function (leg, index) {
        var legCard = document.createElement('div');
        legCard.className = 'card mb-3';
        var legBody = document.createElement('div');
        legBody.className = 'card-body';
        var legTitle = document.createElement('h6');
        legTitle.className = 'card-title mb-2 d-flex align-items-center';
        var modeColor = leg.mode && leg.mode.color ? leg.mode.color : '#6366f1';
        legTitle.innerHTML =
          '<span class="badge" style="background:' + modeColor + '; color: #fff; width: 28px; height: 28px; display: inline-flex; align-items: center; justify-content: center; font-size: 0.75rem;">' +
          (index + 1) +
          '</span>' +
          ' <span class="fw-semibold">' + leg.route.name + '</span>' +
          ' <span class="badge bg-light text-dark ms-2">' + leg.mode.name + '</span>';
        legBody.appendChild(legTitle);

        var details = document.createElement('div');
        details.className = 'row g-3 small text-muted';
        details.innerHTML =
          '<div class="col-md-6"><div class="fw-bold">Board at</div><div>' + leg.stops[0].name + '</div></div>' +
          '<div class="col-md-6"><div class="fw-bold">Alight at</div><div>' + leg.stops[leg.stops.length - 1].name + '</div></div>' +
          '<div class="col-md-4"><div class="fw-bold">Fare</div><div>' + formatMoney(leg.fare) + '</div></div>' +
          '<div class="col-md-4"><div class="fw-bold">Time</div><div>' + formatMinutes(leg.time_minutes) + '</div></div>' +
          '<div class="col-md-4"><div class="fw-bold">Distance</div><div>' + leg.distance_km.toFixed(1) + ' km</div></div>';
        legBody.appendChild(details);

        // Intermediate stops
        if (leg.stops.length > 2) {
          var stopsList = document.createElement('div');
          stopsList.className = 'mt-2';
          var stopsLabel = document.createElement('div');
          stopsLabel.className = 'fw-bold small mb-1 text-muted';
          stopsLabel.textContent = 'Stops along the way:';
          stopsList.appendChild(stopsLabel);
          var stopsHtml = leg.stops.slice(1, -1).map(function (s) { return s.name; }).join(' &rarr; ');
          var stopsText = document.createElement('div');
          stopsText.className = 'small text-dark';
          stopsText.textContent = stopsHtml;
          stopsList.appendChild(stopsText);
          legBody.appendChild(stopsList);
        }

        legCard.appendChild(legBody);
        journeyList.appendChild(legCard);
      });
    }

    show(saveRouteBtn);
  }

  // ------------------------------------------------------------------
  // Save / unsave route
  // ------------------------------------------------------------------
  function toggleSave() {
    if (!currentJourney) return;

    var oid = originId.value;
    var did = destinationId.value;
    if (!oid || !did) return;

    var name = prompt('Give this route a name (optional):', '');
    if (name === null) return; // user cancelled

    fetch('/sakay/save-route/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify({
        origin_terminal_id: parseInt(oid),
        destination_terminal_id: parseInt(did),
        name: name || '',
      }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        isSaved = true;
        hide(saveRouteBtn);
        show(savedRouteBtn);
      })
      .catch(function () {
        alert('Failed to save route. Please try again.');
      });
  }

  // ------------------------------------------------------------------
  // Initialization
  // ------------------------------------------------------------------
  function init() {
    if (originInput && destinationInput) {
      setupAutocomplete(originInput, originId);
      setupAutocomplete(destinationInput, destinationId);
    }

    if (findRouteBtn) {
      findRouteBtn.addEventListener('click', planRoute);
    }

    if (hideResultsBtn) {
      hideResultsBtn.addEventListener('click', function () {
        hide(routeResults);
        currentJourney = null;
        isSaved = false;
        hide(saveRouteBtn);
        hide(savedRouteBtn);
      });
    }

    if (saveRouteBtn) {
      saveRouteBtn.addEventListener('click', toggleSave);
    }

    loadPopularRoutes();
    loadRecentSearches();
  }

  // Allow pressing Enter on inputs to search
  document.addEventListener('keydown', function (e) {
    if ((e.target === originInput || e.target === destinationInput) && e.key === 'Enter') {
      e.preventDefault();
      planRoute();
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();