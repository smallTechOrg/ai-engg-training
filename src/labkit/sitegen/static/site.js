/* Course site behaviour: theme, menu, tabs, copy, search, on-this-page. Vanilla JS, no dependencies. */
(function () {
  "use strict";
  var doc = document, root = doc.documentElement;
  var ROOT = root.getAttribute("data-root") || "";
  function $(s, c) { return (c || doc).querySelector(s); }
  function $$(s, c) { return Array.prototype.slice.call((c || doc).querySelectorAll(s)); }

  /* Theme toggle, remembered (storage can be blocked, so every access is guarded). */
  function currentTheme() {
    var t = root.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  var themeBtn = $("#theme-btn");
  if (themeBtn) themeBtn.addEventListener("click", function () {
    var next = currentTheme() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) { /* not remembered */ }
    doc.dispatchEvent(new Event("themechange"));
  });

  /* Mobile menu */
  var menuBtn = $("#menu-btn"), scrim = $("#scrim");
  function setMenu(open) {
    doc.body.classList.toggle("menu-open", open);
    if (menuBtn) { menuBtn.setAttribute("aria-expanded", String(open)); }
    if (scrim) scrim.hidden = !open;
  }
  if (menuBtn) menuBtn.addEventListener("click", function () { setMenu(!doc.body.classList.contains("menu-open")); });
  if (scrim) scrim.addEventListener("click", function () { setMenu(false); });
  doc.addEventListener("keydown", function (e) { if (e.key === "Escape" && doc.body.classList.contains("menu-open")) { setMenu(false); if (menuBtn) menuBtn.focus(); } });
  var current = $('.sidebar [aria-current="page"]');
  if (current && current.scrollIntoView) { try { current.scrollIntoView({ block: "center" }); } catch (e) { /* ignore */ } }

  /* Copy buttons (event delegation). Line numbers are CSS, so they are never copied. */
  doc.addEventListener("click", function (e) {
    var btn = e.target.closest && e.target.closest("button.copy");
    if (!btn) return;
    var box = btn.closest(".codeblock, .terminal, .cmd");
    var target = box && (box.querySelector("pre code") || box.querySelector("code"));
    if (!target) return;
    var text = target.textContent.replace(/\n$/, "");
    function done(ok) {
      btn.textContent = ok ? "Copied" : "Press Ctrl+C";
      btn.classList.toggle("is-done", ok);
      setTimeout(function () { btn.textContent = "Copy"; btn.classList.remove("is-done"); }, 1600);
    }
    function fallback() {
      var ta = doc.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      doc.body.appendChild(ta); ta.select();
      var ok = false;
      try { ok = doc.execCommand("copy"); } catch (err) { ok = false; }
      doc.body.removeChild(ta); done(ok);
    }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(function () { done(true); }, fallback);
    else fallback();
  });

  /* Tabs: Walkthrough | Full code | Output */
  $$("[data-tabs]").forEach(function (tabs) {
    var buttons = $$('[role="tab"]', tabs), panels = $$('[role="tabpanel"]', tabs), tools = $(".tabtools", tabs);
    function select(i, focus) {
      buttons.forEach(function (b, n) {
        var on = n === i;
        b.setAttribute("aria-selected", String(on)); b.tabIndex = on ? 0 : -1;
        panels[n].hidden = !on;
      });
      if (tools) tools.hidden = i !== 0;
      if (focus) buttons[i].focus();
    }
    buttons.forEach(function (b, i) {
      b.addEventListener("click", function () { select(i); });
      b.addEventListener("keydown", function (e) {
        var n = buttons.length, k = e.key;
        if (k === "ArrowRight") { e.preventDefault(); select((i + 1) % n, true); }
        else if (k === "ArrowLeft") { e.preventDefault(); select((i + n - 1) % n, true); }
        else if (k === "Home") { e.preventDefault(); select(0, true); }
        else if (k === "End") { e.preventDefault(); select(n - 1, true); }
      });
    });
    $$("[data-expand]", tabs).forEach(function (b) {
      b.addEventListener("click", function () {
        var open = b.getAttribute("data-expand") === "all";
        $$("details", panels[0]).forEach(function (d) { d.open = open; });
      });
    });
    select(0);
  });
  // Opening a link to a script or step inside a hidden tab: show the walkthrough.
  function revealHash() {
    var id = decodeURIComponent(location.hash.slice(1)), el = id && doc.getElementById(id);
    if (!el) return;
    var panel = el.closest && el.closest('[role="tabpanel"]');
    if (panel && panel.hidden) { var t = doc.getElementById(panel.getAttribute("aria-labelledby")); if (t) t.click(); }
  }
  window.addEventListener("hashchange", revealHash); revealHash();

  /* On this page: highlight the section being read */
  var tocLinks = $$(".toc .toc-list a");
  if (tocLinks.length && "IntersectionObserver" in window) {
    var map = {};
    tocLinks.forEach(function (a) { var el = doc.getElementById(a.getAttribute("href").slice(1)); if (el) map[el.id] = a; });
    var visible = {};
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { visible[en.target.id] = en.isIntersecting; });
      var first = Object.keys(map).filter(function (id) { return visible[id]; })[0];
      if (first) { tocLinks.forEach(function (a) { a.classList.remove("is-active"); }); map[first].classList.add("is-active"); }
    }, { rootMargin: "-70px 0px -65% 0px" });
    Object.keys(map).forEach(function (id) { io.observe(doc.getElementById(id)); });
  }

  /* Search: the index is a plain script (window.COURSE_INDEX) so it also works from file:// */
  var indexLoaded = null;
  function loadIndex(cb) {
    if (window.COURSE_INDEX) return cb();
    if (indexLoaded) { indexLoaded.push(cb); return; }
    indexLoaded = [cb];
    var s = doc.createElement("script");
    s.src = ROOT + "assets/search-index.js";
    s.onload = function () { var q = indexLoaded; indexLoaded = null; q.forEach(function (f) { f(); }); };
    s.onerror = function () { window.COURSE_INDEX = []; var q = indexLoaded; indexLoaded = null; q.forEach(function (f) { f(); }); };
    doc.head.appendChild(s);
  }
  var KIND = { lesson: "Lesson", module: "Module", heading: "Section", script: "Script", page: "Page" };
  var BOOST = { module: 30, lesson: 40, script: 14, heading: 6, page: 20 };
  function search(query) {
    var words = query.toLowerCase().split(/\s+/).filter(Boolean), out = [];
    if (!words.length) return out;
    (window.COURSE_INDEX || []).forEach(function (e) {
      var title = e[1].toLowerCase(), ctx = e[3].toLowerCase(), score = BOOST[e[0]] || 0;
      for (var i = 0; i < words.length; i++) {
        var w = words[i], t = title.indexOf(w), c = ctx.indexOf(w);
        if (t < 0 && c < 0) return;
        score += t >= 0 ? (t === 0 ? 30 : 18) : 4;
      }
      out.push([score - e[1].length / 40, e]);
    });
    out.sort(function (a, b) { return b[0] - a[0] || (a[1][1] < b[1][1] ? -1 : 1); });
    return out.slice(0, 30).map(function (x) { return x[1]; });
  }
  function esc(s) { return s.replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function mark(text, query) {
    var html = esc(text);
    query.toLowerCase().split(/\s+/).filter(Boolean).forEach(function (w) {
      var i = html.toLowerCase().indexOf(esc(w));
      if (i >= 0 && w.length > 1) html = html.slice(0, i) + "<mark>" + html.slice(i, i + esc(w).length) + "</mark>" + html.slice(i + esc(w).length);
    });
    return html;
  }
  function renderResults(list, results, query) {
    list.innerHTML = "";
    if (!query.trim()) return;
    if (!results.length) { list.innerHTML = '<li class="empty" style="padding:14px;color:var(--muted)">Nothing matches "' + esc(query) + '".</li>'; return; }
    results.forEach(function (e, i) {
      var li = doc.createElement("li"), a = doc.createElement("a");
      a.href = ROOT + e[2];
      a.innerHTML = '<span class="kind">' + (KIND[e[0]] || e[0]) + '</span><span class="rtitle">' + mark(e[1], query) + '</span>' + (e[3] ? '<span class="rctx">' + esc(e[3]) + "</span>" : "");
      if (i === 0) a.className = "is-active";
      li.appendChild(a); list.appendChild(li);
    });
  }
  function moveActive(list, step) {
    var links = $$("a", list); if (!links.length) return;
    var at = links.findIndex(function (a) { return a.classList.contains("is-active"); });
    links.forEach(function (a) { a.classList.remove("is-active"); });
    var next = links[(at + step + links.length) % links.length];
    next.classList.add("is-active"); next.scrollIntoView({ block: "nearest" });
  }
  function wire(input, list, onGo) {
    input.addEventListener("input", function () { loadIndex(function () { renderResults(list, search(input.value), input.value); }); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); moveActive(list, 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); moveActive(list, -1); }
      else if (e.key === "Enter") { var a = $("a.is-active", list); if (a) { e.preventDefault(); onGo(a.href); } }
    });
  }

  var pageInput = $("#search-page-input");
  if (pageInput) {
    var pageList = $("#search-page-results");
    wire(pageInput, pageList, function (href) { location.href = href; });
    var q = (/[?&]q=([^&]*)/.exec(location.search) || [])[1];
    if (q) { pageInput.value = decodeURIComponent(q.replace(/\+/g, " ")); pageInput.dispatchEvent(new Event("input")); }
  }

  var palette = null;
  function openPalette() {
    if (!palette) {
      if (typeof HTMLDialogElement === "undefined") { location.href = ROOT + "search.html"; return; }
      palette = doc.createElement("dialog");
      palette.className = "palette"; palette.setAttribute("aria-label", "Search the course");
      palette.innerHTML = '<input type="search" placeholder="Search lessons, sections and scripts" aria-label="Search the course" autocomplete="off"><ul class="results" role="listbox"></ul><p class="hint">Up and down to move, Enter to open, Esc to close</p>';
      doc.body.appendChild(palette);
      var input = $("input", palette), list = $(".results", palette);
      wire(input, list, function (href) { location.href = href; });
      palette.addEventListener("click", function (e) { if (e.target === palette) palette.close(); });
      list.addEventListener("click", function () { palette.close(); });
    }
    palette.showModal(); $("input", palette).focus(); $("input", palette).select();
    loadIndex(function () {});
  }
  var searchBtn = $("#search-btn");
  if (searchBtn && !pageInput) searchBtn.addEventListener("click", function (e) { e.preventDefault(); openPalette(); });
  var isMac = /Mac|iPhone|iPad/.test(navigator.platform || "");
  var kbd = $("#search-btn kbd"); if (kbd && isMac) kbd.textContent = "⌘K";
  doc.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
      e.preventDefault();
      if (pageInput) pageInput.focus(); else openPalette();
    }
  });
})();
