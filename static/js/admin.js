/* Small enhancements for the SakayGuide management dashboard. */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    /* Confirmation prompts for destructive POST forms. */
    document.querySelectorAll('form[data-confirm]').forEach(function (form) {
      form.addEventListener('submit', function (event) {
        var message = form.getAttribute('data-confirm') || 'Continue?';
        if (!window.confirm(message)) {
          event.preventDefault();
        }
      });
    });

    /* Show/hide password buttons on account forms. */
    document.querySelectorAll('.mgmt-reveal').forEach(function (button) {
      button.addEventListener('click', function () {
        var targetId = button.getAttribute('data-target');
        var input = targetId ? document.getElementById(targetId) : null;
        if (!input) {
          return;
        }
        var reveal = input.type === 'password';
        input.type = reveal ? 'text' : 'password';
        button.setAttribute('aria-label', reveal ? 'Hide password' : 'Show password');
        var icon = button.querySelector('i');
        if (icon) {
          icon.className = reveal ? 'fa-regular fa-eye-slash' : 'fa-regular fa-eye';
        }
      });
    });

    /* Auto-dismiss success messages so they do not cover the table actions. */
    document.querySelectorAll('.mgmt-messages .alert-success').forEach(function (alert) {
      window.setTimeout(function () {
        if (window.bootstrap && bootstrap.Alert) {
          bootstrap.Alert.getOrCreateInstance(alert).close();
        } else {
          alert.remove();
        }
      }, 6500);
    });
  });
})();
