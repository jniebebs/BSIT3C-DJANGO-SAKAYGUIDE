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
    var value = getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
    return value || fallback;
  }

  function chartTheme() {
    return document.documentElement.getAttribute('data-bs-theme') === 'dark'
      ? 'dark'
      : 'light';
  }

  function renderSearchChart() {
    var container = document.getElementById('dashboard-search-chart');
    var activity = readJson('search-activity-data');
    if (!container || !activity || !window.ApexCharts) {
      return;
    }

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
          opacityFrom: 0.32,
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

    chart.render();
  }

  function renderModeChart() {
    var container = document.getElementById('dashboard-mode-chart');
    var breakdown = readJson('transport-breakdown-data');
    if (!container || !breakdown || !window.ApexCharts) {
      return;
    }

    var primary = cssColor('--tblr-primary', '#6366f1');
    var muted = cssColor('--tblr-muted', '#7a81a3');
    var bodyColor = cssColor('--tblr-body-color', '#232741');
    var palette = [
      primary, '#22c55e', '#f59e0b', '#06b6d4', '#ec4899', '#8b5cf6'
    ];

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

    chart.render();
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

  function init() {
    renderSearchChart();
    renderModeChart();

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
