(function () {
  "use strict";

  var PAGE = 300;
  var KIND_ORDER = ["project", "skill", "plugin", "mcp", "document"];
  var KIND_LABELS = { project: "Projekti", skill: "Skillovi", plugin: "Pluginovi", mcp: "MCP serveri", document: "Dokumenti" };
  var KIND_SINGULAR = { project: "projekat", skill: "skill", plugin: "plugin", mcp: "MCP server", document: "dokument" };
  var META_LABELS = {
    projectType: "Tip projekta", scriptNames: "Komande", markers: "Markeri", marketplace: "Marketplace",
    version: "Verzija", scope: "Scope", projectPath: "Projekat", installedAt: "Instaliran",
    lastUpdated: "Ažuriran", transport: "Transport", executableName: "Izvršni fajl",
    envNames: "Env varijable (samo imena)", sourceFormat: "Format izvora", referenceStatus: "Vrsta reference"
  };
  var RELATION_LABELS = {
    "contains:out": "Sadrži", "contains:in": "Dio plugina",
    "documented-by:out": "Dokumentacija", "documented-by:in": "Dokumentuje projekat",
    "configured-for:out": "Konfigurisan za projekat", "configured-for:in": "MCP server projekta"
  };

  function $(id) { return document.getElementById(id); }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function fold(value) {
    return String(value).toLowerCase().replace(/đ/g, "dj").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  }

  function plural(n, one, few, many) {
    var m10 = n % 10, m100 = n % 100;
    if (m10 === 1 && m100 !== 11) return one;
    if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
    return many;
  }

  function isTyping(target) {
    if (!target) return false;
    if (target.isContentEditable) return true;
    var tag = target.tagName;
    if (tag === "TEXTAREA" || tag === "SELECT") return true;
    return tag === "INPUT" && ["checkbox", "radio", "button", "submit", "reset"].indexOf(target.type) === -1;
  }

  var data = JSON.parse($("atlas-data").textContent);
  var items = data.items;
  var byId = Object.create(null);
  var related = Object.create(null);
  var groups = Object.create(null);
  var profileSet = new Set();
  var counts = {};

  items.forEach(function (it) {
    byId[it.id] = it;
    counts[it.kind] = (counts[it.kind] || 0) + 1;
    var parts = [it.name, it.description];
    var profiles = new Set();
    it.locations.forEach(function (l) {
      parts.push(l.path);
      if (l.link_target) parts.push(l.link_target);
      if (l.root_label) parts.push(l.root_label);
      if (l.profile) { profiles.add(l.profile); profileSet.add(l.profile); }
    });
    Object.keys(it.metadata).forEach(function (k) {
      var v = it.metadata[k];
      parts.push(Array.isArray(v) ? v.join(" ") : v);
    });
    it._hay = fold(parts.join("\n"));
    it._profiles = Array.from(profiles).sort();
    if (it.duplicate_group) (groups[it.duplicate_group] = groups[it.duplicate_group] || []).push(it.id);
  });
  data.relations.forEach(function (r) {
    (related[r.source] = related[r.source] || []).push({ id: r.target, key: r.type + ":out" });
    (related[r.target] = related[r.target] || []).push({ id: r.source, key: r.type + ":in" });
  });

  var state = { q: "", kinds: new Set(), profiles: new Set(), origin: "all", dup: false, link: false, selected: null, limit: PAGE };
  var visible = [];

  function locationMatches(it, l) {
    if (state.profiles.size && !(l.profile && state.profiles.has(l.profile))) return false;
    if (state.origin !== "all") {
      if (it.kind !== "skill") return false;
      var origin = l.origin || "";
      if (state.origin === "standalone" && origin !== "standalone") return false;
      if (state.origin === "plugin" && origin.indexOf("plugin:") !== 0) return false;
    }
    if (state.link && !l.via_link) return false;
    return true;
  }

  function matches(it, terms) {
    if (state.kinds.size && !state.kinds.has(it.kind)) return false;
    if (state.dup && !it.duplicate_group) return false;
    if (state.profiles.size || state.origin !== "all" || state.link) {
      if (!it.locations.some(function (l) { return locationMatches(it, l); })) return false;
    }
    for (var i = 0; i < terms.length; i++) {
      if (it._hay.indexOf(terms[i]) === -1) return false;
    }
    return true;
  }

  function apply() {
    var terms = fold(state.q).split(/\s+/).filter(Boolean);
    visible = items.filter(function (it) { return matches(it, terms); });
    renderList();
  }

  function refilter() { state.limit = PAGE; apply(); }

  function renderList() {
    var list = $("list");
    list.textContent = "";
    var frag = document.createDocumentFragment();
    visible.slice(0, state.limit).forEach(function (it) {
      var li = el("li", "row");
      li.id = "opt-" + it.id;
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", String(it.id === state.selected));
      li.tabIndex = -1;
      li.dataset.id = it.id;
      var head = el("div", "row-head");
      head.appendChild(el("span", "row-name", it.name));
      head.appendChild(el("span", "badge", KIND_SINGULAR[it.kind]));
      it._profiles.forEach(function (p) { head.appendChild(el("span", "badge", p)); });
      if (it.duplicate_group) head.appendChild(el("span", "badge dup", "duplikat"));
      li.appendChild(head);
      li.appendChild(el("div", "row-desc", (it.description || it.locations[0].path).split("\n")[0]));
      frag.appendChild(li);
    });
    list.appendChild(frag);
    list.tabIndex = visible.length ? 0 : -1;
    var n = visible.length;
    $("count").textContent = n + " " + plural(n, "stavka", "stavke", "stavki");
    $("empty").hidden = n !== 0;
    var rest = n - state.limit;
    $("more").hidden = rest <= 0;
    if (rest > 0) $("more").textContent = "Prikaži još (" + rest + ")";
  }

  function markSelected() {
    document.querySelectorAll("#list li.row").forEach(function (row) {
      row.setAttribute("aria-selected", String(row.dataset.id === state.selected));
    });
  }

  function pluginName(origin) {
    var plugin = byId[origin.slice("plugin:".length)];
    return plugin ? plugin.name : "nepoznat plugin";
  }

  function copyPath(text, code, status) {
    function fallback() {
      var range = document.createRange();
      range.selectNodeContents(code);
      var sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      status.textContent = "Putanja je označena. Kopiraj sa Ctrl+C.";
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { status.textContent = "Putanja kopirana."; }, fallback);
    } else {
      fallback();
    }
  }

  function linkList(entries) {
    var ul = el("ul", "links");
    entries.forEach(function (entry) {
      var target = byId[entry.id];
      if (!target) return;
      var li = el("li");
      if (entry.label) li.appendChild(document.createTextNode(entry.label + ": "));
      var btn = el("button", "linkish", target.name + " (" + KIND_SINGULAR[target.kind] + ")");
      btn.type = "button";
      btn.addEventListener("click", function () { openItem(target.id); });
      li.appendChild(btn);
      ul.appendChild(li);
    });
    return ul;
  }

  function renderDetail() {
    var body = $("detail-body");
    body.textContent = "";
    var it = state.selected ? byId[state.selected] : null;
    if (!it) {
      body.appendChild(el("p", "placeholder", "Izaberi stavku sa liste da vidiš detalje."));
      return;
    }
    var title = el("h2", null, it.name);
    title.id = "detail-title";
    title.tabIndex = -1;
    body.appendChild(title);
    body.appendChild(el("p", "detail-kind", KIND_SINGULAR[it.kind]));
    if (it.description) body.appendChild(el("p", "detail-desc", it.description));
    body.appendChild(el("p", "evidence", it.evidence === "observed" ? "Pronađeno na disku" : "Dokumentovano; trenutno stanje nije potvrđeno"));
    if (it.kind === "mcp") body.appendChild(el("p", "note", "Deklarisan u konfiguraciji. Katalog ne provjerava da li server radi."));
    if (it.kind === "document") body.appendChild(el("p", "note", "Sadržaj dokumenta opisuje stanje u vrijeme pisanja; skener ga ne potvrđuje."));

    body.appendChild(el("h3", null, it.locations.length === 1 ? "Lokacija" : "Lokacije (" + it.locations.length + ")"));
    var ul = el("ul", "locations");
    it.locations.forEach(function (l) {
      var li = el("li", "loc");
      var code = el("code", "path", l.path);
      li.appendChild(code);
      var facts = [];
      if (l.profile) facts.push("profil: " + l.profile);
      if (l.root_label) facts.push("izvor: " + l.root_label);
      if (l.origin) facts.push(l.origin === "standalone" ? "samostalan" : "iz plugina: " + pluginName(l.origin));
      if (facts.length) li.appendChild(el("div", "loc-facts", facts.join(" · ")));
      if (l.via_link) li.appendChild(el("div", "loc-link", "preko linka → " + (l.link_target || "nepoznat cilj")));
      var btn = el("button", "copy", "Kopiraj putanju");
      btn.type = "button";
      var status = el("span", "copy-status");
      status.setAttribute("aria-live", "polite");
      btn.addEventListener("click", function () { copyPath(l.path, code, status); });
      li.appendChild(btn);
      li.appendChild(status);
      ul.appendChild(li);
    });
    body.appendChild(ul);

    var keys = Object.keys(it.metadata).sort();
    if (keys.length) {
      body.appendChild(el("h3", null, "Podaci"));
      var dl = el("dl", "meta");
      keys.forEach(function (k) {
        var v = it.metadata[k];
        dl.appendChild(el("dt", null, META_LABELS[k] || k));
        dl.appendChild(el("dd", null, Array.isArray(v) ? v.join(", ") : v));
      });
      body.appendChild(dl);
    }

    var rel = (related[it.id] || []).map(function (r) {
      return { id: r.id, label: RELATION_LABELS[r.key] || r.key };
    }).sort(function (a, b) {
      return (a.label + byId[a.id].name).localeCompare(b.label + byId[b.id].name);
    });
    if (rel.length) {
      body.appendChild(el("h3", null, "Povezano"));
      body.appendChild(linkList(rel));
    }
    if (it.duplicate_group) {
      var others = groups[it.duplicate_group].filter(function (id) { return id !== it.id; });
      if (others.length) {
        body.appendChild(el("h3", null, "Isto ime, druga stavka"));
        body.appendChild(linkList(others.map(function (id) { return { id: id, label: "" }; })));
      }
    }
  }

  function openItem(id) {
    if (decodeURIComponent(location.hash.slice(1)) === id) fromHash();
    else location.hash = id;
  }

  function fromHash() {
    var id = decodeURIComponent(location.hash.slice(1));
    state.selected = id && byId[id] ? id : null;
    document.body.classList.toggle("show-detail", Boolean(state.selected));
    renderDetail();
    markSelected();
    if (state.selected && window.matchMedia("(max-width: 699px)").matches) $("detail-title").focus();
  }

  function closeDetail() {
    var id = state.selected;
    location.hash = "";
    var row = id ? document.getElementById("opt-" + id) : null;
    if (row) row.focus(); else $("search").focus();
  }

  function syncKinds() {
    document.querySelectorAll("#counters .counter").forEach(function (b) {
      b.setAttribute("aria-pressed", String(state.kinds.has(b.dataset.kind)));
    });
    document.querySelectorAll("#f-kind input").forEach(function (c) { c.checked = state.kinds.has(c.value); });
  }

  function toggleKind(kind, on) {
    if (on) state.kinds.add(kind); else state.kinds.delete(kind);
    syncKinds();
    refilter();
  }

  function buildChecks(container, values, labelFn, onChange) {
    values.forEach(function (value) {
      var label = el("label");
      var input = el("input");
      input.type = "checkbox";
      input.value = value;
      input.addEventListener("change", function () { onChange(value, input.checked); });
      label.appendChild(input);
      label.appendChild(document.createTextNode(" " + labelFn(value)));
      container.appendChild(label);
    });
  }

  function init() {
    $("scanned").textContent = "Skenirano: " + data.scanned_at.replace("T", " ");

    KIND_ORDER.forEach(function (k) {
      var b = el("button", "counter");
      b.type = "button";
      b.dataset.kind = k;
      b.setAttribute("aria-pressed", "false");
      b.appendChild(el("b", null, String(counts[k] || 0)));
      b.appendChild(document.createTextNode(" " + KIND_LABELS[k]));
      b.addEventListener("click", function () { toggleKind(k, !state.kinds.has(k)); });
      $("counters").appendChild(b);
    });
    buildChecks($("f-kind"), KIND_ORDER, function (k) { return KIND_LABELS[k] + " (" + (counts[k] || 0) + ")"; }, toggleKind);
    buildChecks($("f-profile"), Array.from(profileSet).sort(), function (p) { return p; }, function (p, on) {
      if (on) state.profiles.add(p); else state.profiles.delete(p);
      refilter();
    });
    document.querySelectorAll("input[name=origin]").forEach(function (radio) {
      radio.addEventListener("change", function () { if (radio.checked) { state.origin = radio.value; refilter(); } });
    });
    $("f-dup").addEventListener("change", function () { state.dup = this.checked; refilter(); });
    $("f-link").addEventListener("change", function () { state.link = this.checked; refilter(); });
    $("clear-filters").addEventListener("click", function () {
      state.kinds.clear();
      state.profiles.clear();
      state.origin = "all";
      state.dup = false;
      state.link = false;
      document.querySelectorAll("#filters input[type=checkbox]").forEach(function (c) { c.checked = false; });
      document.querySelector("input[name=origin][value=all]").checked = true;
      syncKinds();
      refilter();
    });

    var warnCount = data.warnings.filter(function (w) { return w.severity === "warn"; }).length;
    if (data.partial) {
      $("partial").hidden = false;
      var toggle = $("partial-toggle");
      toggle.textContent = "Djelimičan pregled: " + warnCount + " " + plural(warnCount, "upozorenje", "upozorenja", "upozorenja");
      data.warnings.forEach(function (w) {
        $("warning-list").appendChild(el("li", null, "[" + w.severity + " " + w.code + "] " + w.source + ": " + w.message));
      });
      toggle.addEventListener("click", function () {
        var open = $("warning-list").hidden;
        $("warning-list").hidden = !open;
        toggle.setAttribute("aria-expanded", String(open));
      });
    }

    $("search").addEventListener("input", function () { state.q = this.value; refilter(); });
    $("more").addEventListener("click", function () { state.limit += PAGE; renderList(); });
    $("filters-toggle").addEventListener("click", function () {
      var open = document.body.classList.toggle("show-filters");
      this.setAttribute("aria-expanded", String(open));
    });
    $("back").addEventListener("click", closeDetail);

    $("list").addEventListener("click", function (e) {
      var row = e.target.closest("li.row");
      if (row) { row.focus(); openItem(row.dataset.id); }
    });
    $("list").addEventListener("keydown", function (e) {
      var rows = $("list").querySelectorAll("li.row");
      if (!rows.length) return;
      var current = Array.prototype.indexOf.call(rows, document.activeElement);
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        var step = e.key === "ArrowDown" ? 1 : -1;
        var next = current === -1 ? 0 : Math.min(rows.length - 1, Math.max(0, current + step));
        rows[next].focus();
      } else if (e.key === "Enter" && current !== -1) {
        e.preventDefault();
        openItem(rows[current].dataset.id);
      }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "/" && !isTyping(e.target) && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        $("search").focus();
        $("search").select();
        return;
      }
      if (e.key === "Escape") {
        if (state.selected) { closeDetail(); return; }
        if (e.target === $("search") && $("search").value) {
          $("search").value = "";
          state.q = "";
          refilter();
        }
      }
    });
    window.addEventListener("hashchange", fromHash);

    apply();
    fromHash();
  }

  init();
})();
