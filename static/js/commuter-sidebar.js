/* SakayGuide commuter sidebar - desktop expand/collapse toggle.
 *
 * The sidebar starts collapsed (icons only, default on desktop). Clicking
 * the rail toggle expands it smoothly to the full 15rem sidebar with
 * labels and the commuter's profile. Clicking again collapses it. On
 * screens below the lg breakpoint the Bootstrap hamburger handles
 * expansion instead; this toggle is hidden there by CSS.
 */
(function () {
  'use strict';

  function init() {
    var aside = document.getElementById('commuterSidebar');
    var toggle = document.getElementById('commuterSidebarToggle');
    if (!aside || !toggle) {
      return;
    }

    var setState = function (expanded) {
      aside.classList.toggle('is-expanded', expanded);
      toggle.setAttribute('aria-expanded', String(expanded));
      var label = expanded ? 'Collapse sidebar' : 'Expand sidebar';
      toggle.setAttribute('aria-label', label);
      toggle.setAttribute('title', label);
    };

    /* Always start collapsed on page load. */
    setState(false);

    toggle.addEventListener('click', function () {
      setState(!aside.classList.contains('is-expanded'));
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
