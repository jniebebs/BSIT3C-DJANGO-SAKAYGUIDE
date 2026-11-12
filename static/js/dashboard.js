/* SakayGuide dashboard enhancements. */
(function () {
  'use strict';

  function readJson(id) {
    var el = document.getElementById(id);
    if (!el) {
      return null;
    }
    try {
      return JSON.parse(el.textContent);
    } catch (error) {
      return null;
    }
  }

  function cssColor(name, fallback) {
    // Dashboard tokens live on the .dh-dashboard wrapper, while Tabler
    // tokens are declared on :root. Look in the dashboard first, then
    // fall back to the document root.
    var scope = document.querySelector('.dh-dashboard') || document.documentElement;
    var value = getComputedStyle(scope).getPropertyValue(name).trim();
    if (!value) {
      value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    }
    return value || fallback;
  }

  /* The palette mirrors the --dh-accent-* dashboard tokens so charts and
     legends always agree on colour. */
  function accentPalette() {
    return [
      cssColor('--dh-accent-1', '#6366f1'),
      cssColor('--dh-accent-2', '#22c55e'),
      cssColor('--dh-accent-3', '#f59e0b'),
      cssColor('--dh-accent-4', '#06b6d4'),
      cssColor('--dh-accent-5', '#ec4899'),
      cssColor('--dh-accent-6', '#8b5cf6'),
    ];
  }

  function chartTheme() {
    return document.documentElement.getAttribute('data-bs-theme') === 'dark'
      ? 'dark'
      : 'light';
  }

  var charts = {
    search: null,
    mode: null
  };

  function destroyChart(key) {
    if (charts[key] && typeof charts[key].destroy === 'function') {
      charts[key].destroy();
    }
    charts[key] = null;
  }

  function renderSearchChart() {
    var container = document.getElementById('dashboard-search-chart');
    var activity = readJson('search-activity-data');
    if (!container || !activity || !window.ApexCharts) {
      return;
    }

    destroyChart('search');

    var primary = cssColor('--tblr-primary', '#6366f1');
    var muted = cssColor('--tblr-muted', '#7a81a3');
    var border = cssColor('--tblr-border-color', '#e8eaf4');

    var chart = new ApexCharts(container, {
      chart: {
        type: 'area',
        height: 268,
        fontFamily: 'inherit',
        toolbar: { show: false },
        animations: { enabled: true, speed: 450 },
        parentHeightOffset: 0
      },
      series: [{
        name: 'Searches',
        data: activity.map(function (item) { return item.count; })
      }],
      colors: [primary],
      stroke: { curve: 'smooth', width: 3 },
      fill: {
        type: 'gradient',
        gradient: {
          shadeIntensity: 1,
          opacityFrom: 0.36,
          opacityTo: 0.02,
          stops: [0, 90, 100]
        }
      },
      markers: {
        size: 4,
        colors: [primary],
        strokeWidth: 0,
        hover: { size: 6 }
      },
      dataLabels: { enabled: false },
      grid: {
        borderColor: border,
        strokeDashArray: 4,
        padding: { top: 0, right: 8, bottom: 0, left: 8 }
      },
      xaxis: {
        categories: activity.map(function (item) { return item.label; }),
        axisBorder: { show: false },
        axisTicks: { show: false },
        labels: {
          style: { colors: muted, fontSize: '11px', fontWeight: 600 }
        },
        tooltip: { enabled: false }
      },
      yaxis: {
        min: 0,
        forceNiceScale: true,
        labels: {
          formatter: function (value) { return Math.round(value); },
          style: { colors: muted, fontSize: '11px' }
        }
      },
      tooltip: {
        theme: chartTheme(),
        y: {
          formatter: function (value) {
            return value + (value === 1 ? ' search' : ' searches');
          }
        }
      },
      noData: { text: 'No searches recorded in the last 7 days' }
    });

    charts.search = chart;
    chart.render();
  }

  function renderModeChart() {
    var container = document.getElementById('dashboard-mode-chart');
    var breakdown = readJson('transport-breakdown-data');
    if (!container || !breakdown || !window.ApexCharts) {
      return;
    }

    destroyChart('mode');

    var primary = cssColor('--tblr-primary', '#6366f1');
    var muted = cssColor('--tblr-muted', '#7a81a3');
    var palette = accentPalette();

    var total = breakdown.reduce(function (sum, item) {
      return sum + item.count;
    }, 0);

    var chart = new ApexCharts(container, {
      chart: {
        type: 'donut',
        height: 238,
        fontFamily: 'inherit',
        animations: { enabled: true, speed: 450 }
      },
      series: breakdown.map(function (item) { return item.count; }),
      labels: breakdown.map(function (item) { return item.name; }),
      colors: palette,
      stroke: { width: 0 },
      dataLabels: { enabled: false },
      legend: { show: false },
      plotOptions: {
        pie: {
          expandOnClick: false,
          donut: {
            size: '74%',
            labels: {
              show: true,
              name: { show: false },
              value: { show: false },
              total: {
                show: true,
                label: 'Active routes',
                fontSize: '12px',
                fontWeight: 600,
                color: muted,
                formatter: function () { return String(total); }
              }
            }
          }
        }
      },
      tooltip: {
        theme: chartTheme(),
        y: {
          formatter: function (value) {
            return value + (value === 1 ? ' route' : ' routes');
          }
        }
      }
    });

    charts.mode = chart;
    chart.render();
  }

  /* Re-render the charts when the user switches colour mode or primary
     colour so the canvas follows the active theme. */
  function setupThemeWatcher() {
    if (!window.MutationObserver) {
      return;
    }

    var pending = null;
    var observer = new MutationObserver(function () {
      window.clearTimeout(pending);
      pending = window.setTimeout(function () {
        renderSearchChart();
        renderModeChart();
      }, 120);
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-bs-theme', 'data-bs-theme-primary']
    });
  }

  function setupTableFilter(inputId, rowSelector, countSelector, emptyId) {
    var input = document.getElementById(inputId);
    if (!input) {
      return;
    }

    var rows = Array.prototype.slice.call(document.querySelectorAll(rowSelector));
    var counter = countSelector ? document.querySelector(countSelector) : null;
    var empty = emptyId ? document.getElementById(emptyId) : null;

    function apply() {
      var query = input.value.trim().toLowerCase();
      var visible = 0;

      rows.forEach(function (row) {
        var haystack = (row.getAttribute('data-search') || row.textContent)
          .toLowerCase();
        var match = !query || haystack.indexOf(query) !== -1;
        row.hidden = !match;
        if (match) {
          visible += 1;
        }
      });

      if (counter) {
        counter.textContent = String(visible);
      }
      if (empty) {
        empty.hidden = visible !== 0 || rows.length === 0;
      }
    }

    input.addEventListener('input', apply);
    input.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        input.value = '';
        apply();
      }
    });
    apply();
  }

  /* ------------------------------------------------------------------
     Live dashboard: auto refresh, relative timestamps and count-ups
     ------------------------------------------------------------------ */

  var REFRESH_KEY = 'sakayguide-auto-refresh';
  var REFRESH_INTERVAL = 60000;

  function relativeTime(date) {
    var seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
    if (seconds < 10) {
      return 'just now';
    }
    if (seconds < 60) {
      return seconds + ' second' + (seconds === 1 ? '' : 's') + ' ago';
    }
    var minutes = Math.round(seconds / 60);
    if (minutes < 60) {
      return minutes + ' minute' + (minutes === 1 ? '' : 's') + ' ago';
    }
    var hours = Math.round(minutes / 60);
    if (hours < 24) {
      return hours + ' hour' + (hours === 1 ? '' : 's') + ' ago';
    }
    var days = Math.round(hours / 24);
    return days + ' day' + (days === 1 ? '' : 's') + ' ago';
  }

  function setupUpdatedTicker() {
    var holder = document.getElementById('dh-updated-at');
    if (!holder) {
      return;
    }

    var text = holder.querySelector('.dh-updated-text');
    var stamp = holder.getAttribute('data-generated-at');
    var parsed = stamp ? new Date(stamp) : null;
    if (!text || !parsed || isNaN(parsed.getTime())) {
      return;
    }

    function paint() {
      text.textContent = 'Updated ' + relativeTime(parsed);
    }

    paint();
    window.setInterval(paint, 15000);
  }

  function setupCountUp() {
    var targets = document.querySelectorAll('[data-count-to]');
    if (!targets.length) {
      return;
    }

    var reduceMotion = window.matchMedia
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    Array.prototype.forEach.call(targets, function (el) {
      var end = parseFloat(el.getAttribute('data-count-to'));
      if (isNaN(end)) {
        return;
      }

      if (reduceMotion || end === 0) {
        el.textContent = String(end);
        return;
      }

      var start = null;
      var duration = 650;

      function step(timestamp) {
        if (start === null) {
          start = timestamp;
        }
        var progress = Math.min((timestamp - start) / duration, 1);
        var eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = String(Math.round(end * eased));
        if (progress < 1) {
          window.requestAnimationFrame(step);
        } else {
          el.textContent = String(end);
        }
      }

      window.requestAnimationFrame(step);
    });
  }

  function setupBars() {
    var bars = document.querySelectorAll(
      '.dh-health-fill, .dh-rank-bar > span'
    );
    if (!bars.length) {
      return;
    }

    Array.prototype.forEach.call(bars, function (el) {
      var width = el.style.width;
      if (!width) {
        return;
      }
      el.style.width = '0%';
      // Force a reflow so the transition animates from the new width.
      void el.offsetWidth;
      el.style.width = width;
    });
  }

  function setupDemandTabs() {
    var tabs = Array.prototype.slice.call(
      document.querySelectorAll('.dh-demand-tab')
    );
    if (!tabs.length) {
      return;
    }

    function activate(tab) {
      tabs.forEach(function (candidate) {
        var selected = candidate === tab;
        candidate.classList.toggle('is-active', selected);
        candidate.setAttribute('aria-selected', selected ? 'true' : 'false');

        var panel = document.getElementById(
          candidate.getAttribute('aria-controls')
        );
        if (panel) {
          panel.hidden = !selected;
        }
      });
    }

    tabs.forEach(function (tab, index) {
      tab.addEventListener('click', function () {
        activate(tab);
      });

      tab.addEventListener('keydown', function (event) {
        var next = null;
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
          next = tabs[(index + 1) % tabs.length];
        } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
          next = tabs[(index - 1 + tabs.length) % tabs.length];
        }
        if (next) {
          event.preventDefault();
          next.focus();
          activate(next);
        }
      });
    });
  }

  function setupAutoRefresh() {
    var toggle = document.getElementById('dh-refresh-toggle');
    var now = document.getElementById('dh-refresh-now');
    var pill = document.getElementById('dh-live-pill');

    if (!toggle) {
      return;
    }

    var timer = null;

    function start() {
      stop();
      timer = window.setInterval(function () {
        window.location.reload();
      }, REFRESH_INTERVAL);
    }

    function stop() {
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
    }

    function setState(enabled) {
      toggle.setAttribute('aria-pressed', enabled ? 'true' : 'false');
      var label = toggle.querySelector('.dh-refresh-label');
      if (label) {
        label.textContent = enabled ? 'Auto refresh on' : 'Auto refresh';
      }
      if (pill) {
        pill.hidden = !enabled;
      }
      if (enabled) {
        start();
      } else {
        stop();
      }
    }

    toggle.addEventListener('click', function () {
      var enabled = toggle.getAttribute('aria-pressed') !== 'true';
      try {
        window.localStorage.setItem(REFRESH_KEY, enabled ? '1' : '0');
      } catch (error) {
        /* Storage may be unavailable in private mode; the toggle still works. */
      }
      setState(enabled);
    });

    if (now) {
      now.addEventListener('click', function () {
        window.location.reload();
      });
    }

    var stored = null;
    try {
      stored = window.localStorage.getItem(REFRESH_KEY);
    } catch (error) {
      stored = null;
    }
    setState(stored === '1');
  }

  function init() {
    renderSearchChart();
    renderModeChart();
    setupThemeWatcher();

    setupCountUp();
    setupBars();
    setupDemandTabs();
    setupUpdatedTicker();
    setupAutoRefresh();

    setupTableFilter(
      'route-filter',
      '#routes-table tbody tr[data-filter-row]',
      '[data-filter-count="routes"]',
      'routes-empty'
    );

    setupTableFilter(
      'location-filter',
      '#locations-table tbody tr[data-filter-row]',
      '[data-filter-count="locations"]',
      'locations-empty'
    );

    setupTableFilter(
      'commuter-filter',
      '#commuters-table tbody tr[data-filter-row]',
      '[data-filter-count="commuters"]',
      'commuters-empty'
    );
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
