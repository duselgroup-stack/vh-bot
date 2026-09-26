// VOHA UYLARI — kichik interaktivlik: galereya, mobil filtr, komissiya kalkulyatori
(function () {
  "use strict";

  // Galereya
  var gallery = document.querySelector("[data-gallery]");
  if (gallery) {
    var main = document.getElementById("gallery-main");
    var thumbs = Array.prototype.slice.call(gallery.querySelectorAll(".thumb"));
    var counter = gallery.querySelector("[data-current]");
    var index = 0;
    var show = function (i) {
      if (!thumbs.length || !main) return;
      index = (i + thumbs.length) % thumbs.length;
      main.src = thumbs[index].getAttribute("data-src");
      thumbs.forEach(function (t, n) { t.classList.toggle("active", n === index); });
      if (counter) counter.textContent = String(index + 1);
      thumbs[index].scrollIntoView({ block: "nearest", inline: "nearest" });
    };
    thumbs.forEach(function (t, n) { t.addEventListener("click", function () { show(n); }); });
    var prev = gallery.querySelector(".gallery-nav.prev");
    var next = gallery.querySelector(".gallery-nav.next");
    if (prev) prev.addEventListener("click", function () { show(index - 1); });
    if (next) next.addEventListener("click", function () { show(index + 1); });
    var startX = null;
    var stage = gallery.querySelector(".gallery-stage");
    if (stage) {
      stage.addEventListener("touchstart", function (e) { startX = e.touches[0].clientX; }, { passive: true });
      stage.addEventListener("touchend", function (e) {
        if (startX === null) return;
        var dx = e.changedTouches[0].clientX - startX;
        if (Math.abs(dx) > 40) show(index + (dx < 0 ? 1 : -1));
        startX = null;
      });
    }
    document.addEventListener("keydown", function (e) {
      if (e.target.closest && e.target.closest("input, textarea, select")) return;
      if (e.key === "ArrowLeft") show(index - 1);
      if (e.key === "ArrowRight") show(index + 1);
    });
  }

  // Mobil qurilmada filtr paneli yopiq ochiladi
  var filters = document.querySelector("[data-collapse-mobile]");
  if (filters && window.matchMedia("(max-width: 900px)").matches) filters.removeAttribute("open");

  // Komissiya kalkulyatori
  var calc = document.getElementById("calc-results");
  var priceInput = document.getElementById("calc-price");
  if (calc && priceInput) {
    var models = JSON.parse(calc.getAttribute("data-models"));
    var short = function (v) { return String(Math.round(v * 100) / 100).replace(".", ","); };
    var fmt = function (n) {
      if (n >= 1e9) return short(n / 1e9) + " mlrd so‘m";
      if (n >= 1e6) return short(n / 1e6) + " mln so‘m";
      return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " so‘m";
    };
    var update = function () {
      var price = parseFloat(String(priceInput.value).replace(",", ".")) * 1e6 || 0;
      calc.querySelectorAll(".calc-row").forEach(function (row) {
        var m = models[row.getAttribute("data-model")];
        row.querySelector("[data-broker]").textContent = price ? fmt(price * m[2] / 100) : "—";
      });
    };
    priceInput.addEventListener("input", update);
    update();
  }
})();
