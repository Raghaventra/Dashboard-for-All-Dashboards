// User dropdown menu: click the username chip to open Account / Admin / Log out.
(function () {
  var menu = document.getElementById("user-menu");
  var trigger = document.getElementById("user-trigger");
  if (!menu || !trigger) return;

  function close() {
    menu.classList.remove("open");
    trigger.setAttribute("aria-expanded", "false");
  }
  function toggle(e) {
    e.stopPropagation();
    var open = menu.classList.toggle("open");
    trigger.setAttribute("aria-expanded", open ? "true" : "false");
  }

  trigger.addEventListener("click", toggle);
  document.addEventListener("click", function (e) {
    if (!menu.contains(e.target)) close();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") close();
  });
})();
