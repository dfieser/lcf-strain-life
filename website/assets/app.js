/* lcf-strain-life site behaviour: theme toggle, copy buttons, tabs.
   Vanilla JS, no dependencies. Kept deliberately small. */
(function () {
  "use strict";

  /* ---- Theme toggle ---------------------------------------------------- */
  var root = document.documentElement;
  var KEY = "lcf-theme";
  try {
    var saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);
  } catch (e) {}

  function currentTheme() {
    var set = root.getAttribute("data-theme");
    if (set) return set;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-theme-toggle]");
    if (!btn) return;
    var next = currentTheme() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem(KEY, next); } catch (e) {}
    btn.setAttribute("aria-label", "Switch to " + (next === "dark" ? "light" : "dark") + " theme");
  });

  /* ---- Copy buttons ---------------------------------------------------- */
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".copy-btn");
    if (!btn) return;
    var wrap = btn.closest(".code");
    var code = wrap && wrap.querySelector("code");
    if (!code) return;
    var text = code.innerText;
    var done = function () {
      var old = btn.textContent;
      btn.textContent = "Copied";
      btn.classList.add("copied");
      setTimeout(function () { btn.textContent = old; btn.classList.remove("copied"); }, 1600);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { fallback(text, done); });
    } else {
      fallback(text, done);
    }
  });
  function fallback(text, done) {
    var ta = document.createElement("textarea");
    ta.value = text; ta.setAttribute("readonly", "");
    ta.style.position = "absolute"; ta.style.left = "-9999px";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); done(); } catch (e) {}
    document.body.removeChild(ta);
  }

  /* ---- Tabs ------------------------------------------------------------ */
  var OS_KEY = "lcf-os";
  function selectTab(tab, remember) {
    var list = tab.closest(".tablist");
    var tabsWrap = tab.closest(".tabs");
    if (!list || !tabsWrap) return;
    list.querySelectorAll(".tab").forEach(function (t) {
      var on = t === tab;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.setAttribute("tabindex", on ? "0" : "-1");
      var panel = document.getElementById(t.getAttribute("aria-controls"));
      if (panel) panel.hidden = !on;
    });
    var group = tabsWrap.getAttribute("data-tabgroup");
    if (remember && group === "os") {
      try { localStorage.setItem(OS_KEY, tab.getAttribute("data-key") || ""); } catch (e) {}
      syncOsGroups(tab.getAttribute("data-key"));
    }
  }
  function syncOsGroups(key) {
    if (!key) return;
    document.querySelectorAll('.tabs[data-tabgroup="os"]').forEach(function (wrap) {
      var match = wrap.querySelector('.tab[data-key="' + key + '"]');
      if (match && match.getAttribute("aria-selected") !== "true") selectTab(match, false);
    });
  }
  document.querySelectorAll(".tabs").forEach(function (wrap) {
    wrap.querySelectorAll(".tab").forEach(function (tab) {
      tab.addEventListener("click", function () { selectTab(tab, true); });
      tab.addEventListener("keydown", function (ev) {
        var tabs = Array.prototype.slice.call(wrap.querySelectorAll(".tab"));
        var i = tabs.indexOf(tab);
        if (ev.key === "ArrowRight" || ev.key === "ArrowLeft") {
          ev.preventDefault();
          var n = ev.key === "ArrowRight" ? (i + 1) % tabs.length : (i - 1 + tabs.length) % tabs.length;
          tabs[n].focus(); selectTab(tabs[n], true);
        }
      });
    });
  });
  try {
    var os = localStorage.getItem(OS_KEY);
    if (os) syncOsGroups(os);
  } catch (e) {}
})();
