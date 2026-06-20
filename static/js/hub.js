// Hub interactions:
//  - single-click a card to open the dashboard in the SAME TAB + log the launch
//  - live search/filter
//  - subtle pointer-tracked glow on cards
(function () {
  function toast(message) {
    var el = document.createElement("div");
    el.className = "toast";
    el.textContent = message;
    document.body.appendChild(el);
    void el.offsetWidth;
    el.classList.add("show");
    setTimeout(function () {
      el.classList.remove("show");
      setTimeout(function () { el.remove(); }, 280);
    }, 1800);
  }

  function launch(card) {
    var id = card.getAttribute("data-id");
    var url = card.getAttribute("data-url");
    var name = card.getAttribute("data-name");

    // Placeholder / not-yet-ready link: don't open a broken tab.
    if (!url || url === "#") {
      toast(name + " is still under construction 🚧");
      return;
    }

    card.classList.add("launching");
    toast("Opening " + name + "…");

    // Log the launch BEFORE navigating away — the page is about to unload, so a
    // normal fetch may be cancelled. sendBeacon survives the unload; fall back to
    // a keepalive fetch if it's unavailable.
    var logged = false;
    if (navigator.sendBeacon) {
      logged = navigator.sendBeacon("/launch/" + id);
    }
    if (!logged) {
      fetch("/launch/" + id, { method: "POST", keepalive: true, headers: { "X-Requested-With": "fetch" } })
        .catch(function () { /* logging failure must not break the launch */ });
    }

    // Navigate the same tab to the tool (proxied path or external URL).
    window.location.href = url;
  }

  var cards = Array.prototype.slice.call(document.querySelectorAll(".dashboard-card"));

  // When returning via the browser Back button the page is restored from the
  // back-forward cache with the clicked tile still marked ".launching" (faded).
  // Clear it on every show so tiles never look stuck/faded.
  window.addEventListener("pageshow", function () {
    cards.forEach(function (card) { card.classList.remove("launching"); });
  });
  cards.forEach(function (card) {
    card.addEventListener("click", function () { launch(card); });
    card.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); launch(card); }
    });
    // Pointer-tracked glow.
    card.addEventListener("pointermove", function (e) {
      var r = card.getBoundingClientRect();
      card.style.setProperty("--mx", (e.clientX - r.left) + "px");
      card.style.setProperty("--my", (e.clientY - r.top) + "px");
    });
  });

  // Live search filter.
  var input = document.getElementById("dashboard-search");
  var noResults = document.getElementById("no-results");
  if (input) {
    input.addEventListener("input", function () {
      var q = input.value.trim().toLowerCase();
      var anyVisible = false;
      cards.forEach(function (card) {
        var hay = card.getAttribute("data-search") || "";
        var show = !q || hay.indexOf(q) !== -1;
        card.style.display = show ? "" : "none";
        if (show) anyVisible = true;
      });
      // Hide category sections that have no visible cards.
      document.querySelectorAll("[data-category]").forEach(function (sec) {
        var visible = sec.querySelectorAll('.dashboard-card:not([style*="display: none"])').length;
        sec.style.display = visible ? "" : "none";
      });
      if (noResults) noResults.style.display = anyVisible ? "none" : "block";
    });
  }
})();
