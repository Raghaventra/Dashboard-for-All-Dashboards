// Theme toggle: applies the choice to <html>, remembers it in localStorage,
// and — for logged-in users — persists it to their account so it carries over
// to the next login on any device.
(function () {
  var KEY = "ud-theme";
  var root = document.documentElement;

  function persistToServer(theme) {
    if (!window.__LOGGED_IN__) return; // anonymous: localStorage only
    try {
      var body = new URLSearchParams();
      body.set("theme", theme);
      fetch("/account/theme", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body.toString(),
      }).catch(function () { /* preference save is best-effort */ });
    } catch (e) {}
  }

  function apply(theme, persist) {
    root.setAttribute("data-theme", theme);
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
})();
