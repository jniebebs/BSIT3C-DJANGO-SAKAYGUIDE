/* SakayGuide admin dashboard behaviours. */
(function () {
  "use strict";

  function parseList(value) {
    return String(value || "")
      .split(",")
      .map(function (item) {
        return item.trim();
      })
      .filter(function (item) {
        return item.length > 0;
      });
  }

  function renderModeChart() {
    var dataNode = document.getElementById("dashboard-mode-data");
    var chartNode = document.getElementById("dashboard-mode-chart");
    if (!dataNode || !chartNode || typeof window.ApexCharts === "undefined") {
      return;
    }

    var labels = parseList(dataNode.getAttribute("data-labels"));
    var values = parseList(dataNode.getAttribute("data-values")).map(Number);
    if (!labels.length || !values.length) {
      chartNode.innerHTML =
        '<div class="dashboard-empty">' +
        '<div class="dashboard-empty-title">No data to display</div>' +
        "</div>";
      return;
    }

    new window.ApexCharts(chartNode, {
      chart: {
        type: "donut",
        fontFamily: "inherit",
        height: 320,
        toolbar: { show: false },
        animations: { enabled: true },
      },
      plotOptions: {
        pie: {
          donut: {
            size: "62%",
            labels: {
              show: true,
              name: { fontSize: "0.8rem", color: "#7a81a3" },
              value: { fontSize: "1rem", fontWeight: 700, color: "#232741" },
              total: {
                show: true,
                label: "Routes",
                fontSize: "0.85rem",
                color: "#7a81a3",
                formatter: function (w) {
                  return w.globals.seriesTotals.reduce(function (a, b) {
                    return a + b;
                  }, 0);
                },
              },
            },
          },
        },
      },
      stroke: { width: 2, lineCap: "round" },
      series: values,
      labels: labels,
      colors: ["#6366f1", "#06b6d4", "#22c55e", "#f59e0b", "#8b5cf6", "#ec4899"],
      legend: { position: "bottom", fontSize: "0.8rem" },
      tooltip: { theme: "dark" },
      dataLabels: { enabled: false },
    }).render();
  }

  function markActiveNav() {
    var anchor = window.location.hash;
    if (!anchor) {
      return;
    }
    var target = document.querySelector(anchor);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    renderModeChart();
    markActiveNav();
  });
})();
