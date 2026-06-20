// Theme handling.
//
// localStorage is the instant, per-device source of truth (set in the <head>
// bootstrap before paint). This file handles the toggle and keeps the server
// copy in sync so the preference carries to the next login on a new device.
(function () {
  var KEY = "ud-theme";
  var root = document.documentElement;

  function persistToServer(theme) {
    if (!window.__LOGGED_IN__) return; // anonymous: localStorage only
    try {
      // keepalive lets the request survive an immediate page navigation, so the
      // save isn't lost when the user toggles and clicks a link right away.
      fetch("/account/theme", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "theme=" + encodeURIComponent(theme),
        keepalive: true,
      }).catch(function () { /* best-effort */ });
    } catch (e) {}
  }

  function apply(theme, persist) {
    root.setAttribute("data-theme", theme);
    root.style.colorScheme = theme;
    try { localStorage.setItem(KEY, theme); } catch (e) {}
    if (persist) persistToServer(theme);
  }

  var btn = document.getElementById("theme-toggle");
  if (btn) {
    btn.addEventListener("click", function () {
      var current = root.getAttribute("data-theme") === "dark" ? "dark" : "light";
      apply(current === "dark" ? "light" : "dark", true);
    });
  }

  // Reconcile: if this device's saved theme differs from what the server has,
  // push it up once so the account record matches (best-effort, no UI change).
  if (window.__LOGGED_IN__) {
    var current = root.getAttribute("data-theme");
    if (current && current !== window.__SERVER_THEME__) {
      persistToServer(current);
    }
  }
})();
