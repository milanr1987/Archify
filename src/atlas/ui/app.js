(function () {
  "use strict";

  var PAGE = 300;
  var ORIGIN_KINDS = { skill: true, command: true, agent: true, hook: true };
  var KIND_ORDER = ["project", "skill", "plugin", "mcp", "document", "command", "agent", "hook"];
  var KIND_LABELS = { project: "Projekti", skill: "Skillovi", plugin: "Pluginovi", mcp: "MCP serveri", document: "Dokumenti", command: "Komande", agent: "Agenti", hook: "Hookovi" };
  var KIND_SINGULAR = { project: "projekat", skill: "skill", plugin: "plugin", mcp: "MCP server", document: "dokument", command: "komanda", agent: "agent", hook: "hook" };
  var META_LABELS = {
    projectType: "Tip projekta", scriptNames: "Komande", markers: "Markeri", marketplace: "Marketplace",
    version: "Verzija", scope: "Scope", projectPath: "Projekat", installedAt: "Instaliran",
    lastUpdated: "Ažuriran", transport: "Transport", executableName: "Izvršni fajl",
    envNames: "Env varijable (samo imena)", sourceFormat: "Format izvora", referenceStatus: "Vrsta reference",
    event: "Događaj", matcher: "Matcher", hookCount: "Broj hookova", hookTypes: "Tipovi hookova",
    lastCommitAt: "Zadnji commit", lastSessionAt: "Zadnja sesija (mtime)", dirtyCount: "Nekomitovano",
    branch: "Grana", sessionTimes: "Sesije po profilu"
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
  var notes = JSON.parse($("atlas-overlay").textContent).notes;
  var maps = JSON.parse($("atlas-maps").textContent);
  var checks = JSON.parse($("atlas-state").textContent);
  var skillChecks = Object.create(null);
  checks.skills.forEach(function (group) { group.itemIds.forEach(function (id) { skillChecks[id] = group; }); });
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
    if (notes[it.id]) parts.push(notes[it.id].text, notes[it.id].tags.join(" "));
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
  Object.keys(groups).forEach(function (key) {
    var union = new Set();
    groups[key].forEach(function (id) { byId[id]._profiles.forEach(function (p) { union.add(p); }); });
    var sorted = Array.from(union).sort();
    groups[key].forEach(function (id) { byId[id]._groupProfiles = sorted; });
  });
  data.relations.forEach(function (r) {
    (related[r.source] = related[r.source] || []).push({ id: r.target, key: r.type + ":out" });
    (related[r.target] = related[r.target] || []).push({ id: r.source, key: r.type + ":in" });
  });

  var state = { q: "", kinds: new Set(), profiles: new Set(), origin: "all", dup: false, link: false, drift: false, sort: "name", matrix: false, group: true, selected: null, limit: PAGE };
  var visible = [];

  function locationMatches(it, l) {
    if (state.profiles.size && !(l.profile && state.profiles.has(l.profile))) return false;
    if (state.origin !== "all") {
      if (!ORIGIN_KINDS[it.kind]) return false;
      var origin = l.origin || "";
      if (state.origin === "standalone" && origin !== "standalone") return false;
      if (state.origin === "plugin" && origin.indexOf("plugin:") !== 0) return false;
    }
    if (state.link && !l.via_link) return false;
    return true;
  }

  function matches(it, terms) {
    if (state.drift && (!skillChecks[it.id] || skillChecks[it.id].status !== "razlikuje se")) return false;
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
    if (state.sort === "activity") visible.sort(function (a, b) {
      function activity(it) {
        if (it.kind !== "project") return -Infinity;
        return Math.max.apply(null, ["lastCommitAt", "lastSessionAt"].map(function (k) {
          var n = Date.parse(it.metadata[k]); return Number.isFinite(n) ? n : -Infinity;
        }));
      }
      var aa = activity(a), bb = activity(b);
      return aa === bb ? a.name.localeCompare(b.name) || a.id.localeCompare(b.id) : aa > bb ? -1 : 1;
    });
    if (state.group) {
      var seen = Object.create(null);
      visible = visible.filter(function (it) {
        if (!it.duplicate_group) return true;
        if (seen[it.duplicate_group]) return false;
        seen[it.duplicate_group] = true;
        return true;
      });
    }
    renderList();
  }

  function refilter() {
    // Matrica pokriva listu; promjena filtera ili pretrage vraća listu da se vidi rezultat.
    if (state.matrix) { setMatrix(false); renderDetail(); }
    state.limit = PAGE; apply();
  }

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
      var grouped = state.group && it.duplicate_group;
      (grouped ? it._groupProfiles : it._profiles).forEach(function (p) { head.appendChild(el("span", "badge", p)); });
      if (grouped) head.appendChild(el("span", "badge dup", "×" + groups[it.duplicate_group].length));
      else if (it.duplicate_group) head.appendChild(el("span", "badge dup", "duplikat"));
      if (it.kind === "skill" && skillChecks[it.id] && skillChecks[it.id].multiple) head.appendChild(el("span", "badge", skillChecks[it.id].status));
      if (it.kind === "project" && it.metadata.dirtyCount && it.metadata.dirtyCount !== "unknown") head.appendChild(el("span", "badge", "nekomitovano: " + it.metadata.dirtyCount));
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
    var sel = state.selected ? byId[state.selected] : null;
    var group = sel && state.group && sel.duplicate_group ? groups[sel.duplicate_group] : [state.selected];
    document.querySelectorAll("#list li.row").forEach(function (row) {
      row.setAttribute("aria-selected", String(group.indexOf(row.dataset.id) !== -1));
    });
  }

  function instanceSummary(member) {
    var facts = member._profiles.length ? ["profil: " + member._profiles.join(", ")] : [];
    ["version", "scope", "matcher"].forEach(function (k) {
      if (member.metadata[k]) facts.push((META_LABELS[k] || k).toLowerCase() + ": " + member.metadata[k]);
    });
    var origins = new Set(member.locations.map(function (l) {
      return !l.origin ? "" : l.origin === "standalone" ? "samostalan" : "iz plugina " + pluginName(l.origin);
    }).filter(Boolean));
    origins.forEach(function (o) { facts.push(o); });
    return facts.join(" · ");
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
    if (state.matrix) {
      var head = el("div", "matrix-head");
      head.appendChild(el("h2", "matrix-title", "Matrica hookova"));
      var close = el("button", "matrix-close", "Zatvori matricu");
      close.type = "button"; close.id = "matrix-close";
      close.addEventListener("click", closeDetail);
      head.appendChild(close);
      body.appendChild(head);
      body.appendChild(el("p", "note", "Deklaracije u snimku; prazno nije dokaz odsustva ako izvor nije čitljiv. Pogledaj upozorenja izvora."));
      var wrap = el("div", "matrix-scroll");
      wrap.tabIndex = 0; wrap.setAttribute("role", "region"); wrap.setAttribute("aria-label", "Tabela hookova, horizontalno skrolovanje");
      var table = el("table", "hook-matrix"); table.id = "hook-matrix";
      var caption = el("caption", null, "Hookovi po profilu"); table.appendChild(caption);
      // Kolone samo za profile sa bar jednim hookom; ostali se navode ispod tabele.
      var shown = checks.profiles.filter(function (p) {
        return checks.hooks.some(function (row) { return (row.cells[p] || []).length; });
      });
      var empty = checks.profiles.filter(function (p) { return shown.indexOf(p) === -1; });
      var header = el("tr");
      var label = el("th", null, "Događaj / matcher"); label.scope = "col"; header.appendChild(label);
      shown.forEach(function (p) { var th = el("th", "mx-profile", p); th.scope = "col"; header.appendChild(th); });
      var thead = el("thead"); thead.appendChild(header); table.appendChild(thead);
      var tbody = el("tbody");
      checks.hooks.forEach(function (row) {
        var tr = el("tr"); var th = el("th"); th.scope = "row";
        th.appendChild(el("span", "mx-event", row.event));
        if (row.matcher) th.appendChild(el("span", "mx-matcher", row.matcher));
        tr.appendChild(th);
        shown.forEach(function (profile) {
          var entries = row.cells[profile] || [];
          var td = el("td", entries.length ? "mx-cell" : "mx-cell matrix-missing");
          if (!entries.length) {
            td.appendChild(el("span", "mx-dash", "—"));
            td.appendChild(el("span", "visually-hidden", "nema u ovom profilu"));
          }
          entries.forEach(function (e) {
            var cell = el("div", "mx-entry");
            cell.appendChild(el("span", "mx-count", String(e.hookCount)));
            cell.appendChild(el("span", "mx-type", e.hookTypes.join(", ")));
            cell.appendChild(el("span", "mx-origin", e.origin));
            td.appendChild(cell);
          });
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody); wrap.appendChild(table);
      if (checks.hooks.length) body.appendChild(wrap);
      else body.appendChild(el("p", "note", "Nema pronađenih deklaracija hookova."));
      if (empty.length) body.appendChild(el("p", "note mx-empty", "Profili bez ijednog hooka: " + empty.join(", ")));
      return;
    }
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
    body.appendChild(el("p", "", "ID za CLI bilješke:"));
    body.appendChild(el("code", "path item-id", it.id));
    if (it.kind === "skill" && skillChecks[it.id]) {
      var comparison = skillChecks[it.id];
      body.appendChild(el("p", "content-status", "Sadržaj: " + comparison.status));
      if (comparison.status !== "isti") {
        body.appendChild(el("h3", null, "Varijante sadržaja"));
        comparison.variants.forEach(function (cohort) {
          var cohortLabel = cohort.cohort[0] === "own" ? "Vlastiti skill" : cohort.cohort[0] === "plugin" ? "Plugin · " + cohort.cohort.slice(1).join(" · ") : "Nepoznato porijeklo";
          body.appendChild(el("p", "note", cohortLabel + ": " + cohort.status));
          var variants = el("ul", "content-variants");
          cohort.locations.forEach(function (v) {
            variants.appendChild(el("li", null, v.hash.slice(0, 12) + " · " + v.profile + " · " + v.path + " · " + v.origin + (v.plugin ? " " + v.plugin + " " + v.version : "")));
          });
          body.appendChild(variants);
        });
      }
    }
    if (it.kind === "project") maps.filter(function (map) { return map.projectId === it.id; }).forEach(function (map) {
      var labels = { current: "Aktuelna", stale: "Zastarjela", unverified: "Neprovjerena" };
      body.appendChild(el("p", "map-status status-" + map.status, "Mapa: " + labels[map.status]));
      var link = el("a", "map-link", map.title);
      if (/^maps\/[a-z0-9]+(?:-[a-z0-9]+)*\.html$/.test(map.htmlPath)) {
        link.setAttribute("href", map.htmlPath);
        body.appendChild(link);
      }
    });
    if (it.description) body.appendChild(el("p", "detail-desc", it.description));
    if (notes[it.id]) {
      body.appendChild(el("h3", "", "Bilješka"));
      body.appendChild(el("p", "detail-note", notes[it.id].text));
      if (notes[it.id].tags.length) body.appendChild(el("p", "note-tags", notes[it.id].tags.join(", ")));
    }
    body.appendChild(el("p", "evidence", it.evidence === "observed" ? "Pronađeno na disku" : "Dokumentovano; trenutno stanje nije potvrđeno"));
    if (it.kind === "mcp") body.appendChild(el("p", "note", "Deklarisan u konfiguraciji. Katalog ne provjerava da li server radi."));
    if (it.kind === "hook") body.appendChild(el("p", "note", "Deklarisan u konfiguraciji; katalog ne provjerava da li se izvršava. Sadržaj komande se ne prikazuje."));
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

    var keys = Object.keys(it.metadata).filter(function (k) { return k !== "ownDrift" && k !== "contentStatus"; }).sort();
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
      var all = groups[it.duplicate_group];
      body.appendChild(el("h3", null, "Sve instance (" + all.length + ")"));
      var inst = el("ul", "instances");
      all.forEach(function (id) {
        var member = byId[id];
        var li = el("li", id === it.id ? "current" : "");
        var label = (id === it.id ? "Prikazana: " : "") + member.locations[0].path;
        if (id === it.id) li.appendChild(el("span", "inst-path", label));
        else {
          var btn = el("button", "linkish", label);
          btn.type = "button";
          btn.addEventListener("click", function () { openItem(id); });
          li.appendChild(btn);
        }
        var summary = instanceSummary(member);
        if (summary) li.appendChild(el("div", "loc-facts", summary));
        inst.appendChild(li);
      });
      body.appendChild(inst);
    }
  }

  function openItem(id) {
    if (decodeURIComponent(location.hash.slice(1)) === id) fromHash();
    else location.hash = id;
  }

  function setMatrix(on) {
    state.matrix = on;
    document.body.classList.toggle("show-matrix", on);
    document.body.classList.toggle("show-detail", on);
  }

  function fromHash() {
    if (state.matrix) setMatrix(false);
    var id = decodeURIComponent(location.hash.slice(1));
    state.selected = id && byId[id] ? id : null;
    document.body.classList.toggle("show-detail", Boolean(state.selected));
    renderDetail();
    markSelected();
    if (state.selected && window.matchMedia("(max-width: 699px)").matches) $("detail-title").focus();
  }

  function closeDetail() {
    if (state.matrix) { setMatrix(false); renderDetail(); $("hook-matrix-toggle").focus(); return; }
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
    $("f-drift").addEventListener("change", function () { state.drift = this.checked; refilter(); });
    $("activity-sort").addEventListener("change", function () { state.sort = this.value; refilter(); });
    $("hook-matrix-toggle").addEventListener("click", function () {
      setMatrix(true); renderDetail();
      if (window.matchMedia("(max-width: 699px)").matches) { $("back").focus(); }
    });
    // Browser može vratiti staro stanje polja pri osvježavanju; stanje liste uvijek prati polje.
    state.group = $("f-group").checked;
    $("f-group").addEventListener("change", function () { state.group = this.checked; refilter(); markSelected(); });
    window.addEventListener("pageshow", function () {
      if (state.group !== $("f-group").checked) { state.group = $("f-group").checked; refilter(); markSelected(); }
    });
    $("clear-filters").addEventListener("click", function () {
      state.kinds.clear();
      state.profiles.clear();
      state.origin = "all";
      state.dup = false;
      state.link = false;
      state.drift = false;
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
        if (state.selected || state.matrix) { closeDetail(); return; }
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
