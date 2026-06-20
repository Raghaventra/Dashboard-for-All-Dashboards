// Reusable square-crop + upload, powered by Cropper.js.
//
// Wire up any file input like:
//   <input type="file" accept="image/*" data-crop="avatar"
//          data-target="#icon" data-preview="#preview">
// Flow: pick file -> validate (image, <= max MB) -> crop modal (square) ->
// upload to /media/upload -> on success set data-target's value + preview src.
(function () {
  var modal = document.getElementById("crop-modal");
  if (!modal || typeof Cropper === "undefined") return;

  var imgEl = document.getElementById("crop-image");
  var errEl = document.getElementById("crop-error");
  var saveBtn = document.getElementById("crop-save");
  var cancelBtn = document.getElementById("crop-cancel");
  var MAX_MB = window.UD_MAX_UPLOAD_MB || 5;

  var cropper = null;
  var ctx = null; // { kind, target, preview, objectUrl, onDone }

  function showError(msg) { errEl.textContent = msg; errEl.style.display = msg ? "block" : "none"; }

  function open() { modal.classList.add("open"); modal.setAttribute("aria-hidden", "false"); }
  function close() {
    modal.classList.remove("open"); modal.setAttribute("aria-hidden", "true");
    if (cropper) { cropper.destroy(); cropper = null; }
    if (ctx && ctx.objectUrl) { URL.revokeObjectURL(ctx.objectUrl); }
    ctx = null; showError(""); saveBtn.disabled = false; saveBtn.textContent = "Save";
  }

  function start(file, opts) {
    if (!file.type || file.type.indexOf("image/") !== 0) {
      alert("Please choose an image file."); return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      alert("That image is " + (file.size / 1048576).toFixed(1) + " MB — the limit is " + MAX_MB + " MB.");
      return;
    }
    showError("");
    var url = URL.createObjectURL(file);
    ctx = { objectUrl: url, kind: opts.kind, target: opts.target, preview: opts.preview, onDone: opts.onDone };
    imgEl.src = url;
    open();
    if (cropper) cropper.destroy();
    cropper = new Cropper(imgEl, {
      aspectRatio: 1,        // perfect square only
      viewMode: 1,
      autoCropArea: 1,
      background: false,
      responsive: true,
    });
  }

  saveBtn.addEventListener("click", function () {
    if (!cropper || !ctx) return;
    var canvas = cropper.getCroppedCanvas({ width: 512, height: 512, imageSmoothingQuality: "high" });
    if (!canvas) { showError("Could not read the crop. Try again."); return; }
    saveBtn.disabled = true; saveBtn.textContent = "Saving…";
    canvas.toBlob(function (blob) {
      var fd = new FormData();
      fd.append("image", blob, "upload.jpg");
      fd.append("kind", ctx.kind);
      fetch("/media/upload", { method: "POST", body: fd })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          if (!res.ok || !res.j.ok) { throw new Error((res.j && res.j.error) || "Upload failed."); }
          var url = res.j.url;
          if (ctx.target) { var t = document.querySelector(ctx.target); if (t) t.value = url; }
          if (ctx.preview) { var p = document.querySelector(ctx.preview); if (p) { p.src = url; p.style.display = ""; } }
          if (typeof ctx.onDone === "function") ctx.onDone(url);
          close();
        })
        .catch(function (e) { showError(e.message || "Upload failed."); saveBtn.disabled = false; saveBtn.textContent = "Save"; });
    }, "image/jpeg", 0.9);
  });

  cancelBtn.addEventListener("click", close);
  modal.addEventListener("click", function (e) { if (e.target === modal) close(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && modal.classList.contains("open")) close(); });

  // Auto-wire declarative inputs.
  document.querySelectorAll('input[type="file"][data-crop]').forEach(function (input) {
    input.addEventListener("change", function () {
      if (!input.files || !input.files[0]) return;
      var file = input.files[0];
      start(file, {
        kind: input.getAttribute("data-crop"),
        target: input.getAttribute("data-target"),
        preview: input.getAttribute("data-preview"),
        onDone: function () { input.value = ""; }, // allow re-picking the same file
      });
    });
  });
})();
