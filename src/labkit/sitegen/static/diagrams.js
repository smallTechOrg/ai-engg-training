/* Renders ```mermaid diagrams from a pinned CDN build. If anything fails, the source text stays visible. */
(function () {
  "use strict";
  var URL = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs";
  var nodes = Array.prototype.slice.call(document.querySelectorAll("pre.mermaid"));
  if (!nodes.length) return;
  nodes.forEach(function (n) { n.setAttribute("data-src", n.textContent); });
  function isDark() {
    var t = document.documentElement.getAttribute("data-theme");
    if (t) return t === "dark";
    return !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  }
  var lib = null;
  function draw() {
    if (!lib) return;
    nodes.forEach(function (n) { n.removeAttribute("data-processed"); n.textContent = n.getAttribute("data-src"); });
    try {
      lib.initialize({ startOnLoad: false, securityLevel: "strict", theme: isDark() ? "dark" : "neutral", suppressErrorRendering: true });
      var done = lib.run({ nodes: nodes, suppressErrors: true });
      if (done && done.catch) done.catch(function () {});
    } catch (e) { /* the source text remains */ }
  }
  try {
    import(URL).then(function (mod) { lib = mod.default; draw(); }).catch(function () {});
  } catch (e) { /* old browser: leave the source */ }
  document.addEventListener("themechange", draw);
})();
