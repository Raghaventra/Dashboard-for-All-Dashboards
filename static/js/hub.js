// Hub interactions: double-click a card to open the dashboard in a NEW TAB,
// and tell the server to log the launch. We open the tab synchronously inside
// the user-gesture handler so popup blockers don't interfere; logging is a
// separate fire-and-forget request.
(function () {
  function toast(message) {
    var el = document.createElement("div");
    el.className = "toast";
    el.textContent = message;
    document.body.appendChild(el);
    // Force reflow so the transition runs, then show.
    void el.offsetWidth;
    el.classList.add("show");
    setTimeout(function () {
      el.classList.remove("show");
      setTimeout(function () { el.remove(); }, 250);
    }, 1800);
  }

  function launch(card) {
    var id = card.getAttribute("data-id");
    var url = card.getAttribute("data-url");
    var name = card.getAttribute("data-name");
    if (!url) return;

    // Open immediately (synchronous → not blocked by popup blockers).
    window.open(url, "_blank", "noopener");

    card.classList.add("launching");
    setTimeout(function () { card.classList.remove("launching"); }, 600);
    toast("Opening " + name + " in a new tab…");

    // Log the launch for the activity log (best-effort).
    fetch("/launch/" + id, { method: "POST", headers: { "X-Requested-With": "fetch" } })
      .catch(function () { /* logging failure must not break the launch */ });
  }

  document.querySelectorAll(".dashboard-card").forEach(function (card) {
    card.addEventListener("dblclick", function () { launch(card); });
    // Keyboard accessibility: Enter / Space activates the focused card.
    card.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        launch(card);
      }
    });
  });
})();
