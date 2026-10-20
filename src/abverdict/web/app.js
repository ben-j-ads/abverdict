(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var NS = "http://www.w3.org/2000/svg";

  // ---------- helpers ----------
  function el(tag, props, kids) {
    var n = document.createElement(tag);
    Object.keys(props || {}).forEach(function (k) {
      if (k === "text") n.textContent = props[k];
      else if (k === "class") n.className = props[k];
      else n.setAttribute(k, props[k]);
    });
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  function svg(tag, attrs, text) {
    var n = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (text != null) n.textContent = text;
    return n;
  }
  function num(id) { var v = $(id).value.trim(); return v === "" ? null : Number(v); }
  function fmtInt(n) { return Number(n).toLocaleString("en-US"); }
  function fmtP(p) { return p < 1e-4 ? "<0.0001" : Number(p.toPrecision(3)).toString(); }
  function post(url, body) {
    return fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || "something went wrong"); return j; }); });
  }
  function showError(id, msg) { var e = $(id); e.textContent = msg || ""; e.hidden = !msg; }

  // ---------- theme + tabs ----------
  function setTheme(t) {
    document.documentElement.dataset.theme = t;
    $("theme").setAttribute("aria-pressed", String(t === "dark"));
    try { localStorage.setItem("abverdict-theme", t); } catch (e) {}
  }
  $("theme").addEventListener("click", function () { setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"); });
  setTheme(document.documentElement.dataset.theme === "dark" ? "dark" : "light");

  function showTab(name) {
    ["test", "plan"].forEach(function (t) {
      $("tab-" + t).setAttribute("aria-selected", String(t === name));
      $("panel-" + t).hidden = t !== name;
    });
  }
  $("tab-test").addEventListener("click", function () { showTab("test"); });
  $("tab-plan").addEventListener("click", function () { showTab("plan"); });

  // ---------- variant rows ----------
  var rowsEl = $("rows");
  function addRow(name, conv, n) {
    var row = el("div", { class: "row" }, [
      el("input", { class: "name", type: "text", "aria-label": "variant name", placeholder: "name", value: name || "" }),
      el("input", { class: "conv", type: "number", min: "0", inputmode: "numeric", "aria-label": "conversions", value: conv == null ? "" : conv }),
      el("input", { class: "vis", type: "number", min: "1", inputmode: "numeric", "aria-label": "visitors", value: n == null ? "" : n }),
      el("button", { class: "rm", type: "button", "aria-label": "remove variant", text: "×" })
    ]);
    row.querySelector(".rm").addEventListener("click", function () { row.remove(); syncRemove(); });
    rowsEl.appendChild(row);
    syncRemove();
  }
  function syncRemove() {
    var rows = rowsEl.children;
    for (var i = 0; i < rows.length; i++) rows[i].querySelector(".rm").disabled = rows.length <= 2;
  }
  function setRows(list) { rowsEl.innerHTML = ""; list.forEach(function (r) { addRow(r[0], r[1], r[2]); }); }
  $("add-row").addEventListener("click", function () {
    addRow(String.fromCharCode(65 + rowsEl.children.length), null, null);
    rowsEl.lastChild.querySelector(".conv").focus();
  });
  setRows([["control", null, null], ["new", null, null]]);

  var EXAMPLES = {
    early: { rows: [["control", 500, 10000], ["new", 580, 10000]], planned_n: 31234, days: 5, looks: 1 },
    clear: { rows: [["control", 5000, 100000], ["new", 5400, 100000]], planned_n: 100000, days: 14, looks: 1 }
  };
  document.querySelectorAll("[data-example]").forEach(function (b) {
    b.addEventListener("click", function () {
      var ex = EXAMPLES[b.dataset.example];
      setRows(ex.rows);
      $("csv").value = ""; $("planned_n").value = ex.planned_n; $("days").value = ex.days; $("looks").value = ex.looks;
      $("mde").value = ""; $("split").value = "";
      $("test-form").requestSubmit();
    });
  });

  // ---------- test ----------
  var lastReport = null;
  $("test-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    showError("form-error", "");
    var body = {
      planned_n: num("planned_n"), days: num("days"), looks: num("looks") || 1, mde: $("mde").value.trim() === "" ? null : num("mde") / 100,
      split: $("split").value.trim() || null, alpha: num("alpha") || 0.05
    };
    var csv = $("csv").value.trim();
    if (csv) { body.csv = csv; body.control = $("control").value.trim(); }
    else {
      body.arms = Array.prototype.map.call(rowsEl.children, function (r) {
        return { name: r.querySelector(".name").value.trim(), conversions: r.querySelector(".conv").value, n: r.querySelector(".vis").value };
      });
      for (var i = 0; i < body.arms.length; i++) {
        var a = body.arms[i];
        if (a.conversions === "" || a.n === "") { showError("form-error", "Fill in conversions and visitors for every variant, or paste a csv."); return; }
      }
    }
    post("/api/test", body).then(renderResult).catch(function (e) { showError("form-error", e.message); });
  });

  var VERDICT_WORD = { "WINNER": "winner", "LOSER": "loser", "KEEP RUNNING": "keep running", "NO MEANINGFUL DIFFERENCE": "no difference", "INCONCLUSIVE": "inconclusive", "INVALID": "invalid" };

  function renderResult(r) {
    lastReport = r;
    var box = $("result");
    box.innerHTML = "";
    var word = VERDICT_WORD[r.overall] || r.overall.toLowerCase();
    var sub = r.headline.indexOf(": ") > -1 ? r.headline.slice(r.headline.indexOf(": ") + 2) : r.headline;

    box.appendChild(el("p", { class: "label kicker" + (r.overall === "INVALID" ? " invalid" : ""), text: "verdict" }));
    box.appendChild(el("h2", { class: "verdict" }, [el("mark", { class: "hl", text: word + "." })]));
    box.appendChild(el("p", { class: "lead", text: sub }));

    box.appendChild(section("the evidence", [intervalFigure(r), armsTable(r)]));
    box.appendChild(section("each comparison", r.comparisons.map(comparison.bind(null, r))));
    box.appendChild(section("the checks", [checksList(r)].concat(r.warnings.length ? [warnList(r.warnings)] : [])));

    var copy = el("button", { class: "link", type: "button", text: "copy this as text" });
    copy.addEventListener("click", function () {
      if (navigator.clipboard) navigator.clipboard.writeText(summaryText(r)).then(function () { copy.textContent = "copied"; setTimeout(function () { copy.textContent = "copy this as text"; }, 1500); });
    });
    box.appendChild(el("div", { class: "copy-row" }, [copy]));
    box.hidden = false;
    box.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  }

  function section(title, kids) { return el("div", { class: "section" }, [el("h3", { text: title })].concat(kids)); }

  function armsTable(r) {
    var conv = r.metric === "conversion";
    var head = conv ? ["variant", "conversions", "visitors", "rate"] : ["variant", "n", "mean", "sd"];
    var t = el("table", {}, [
      el("thead", {}, [el("tr", {}, head.map(function (h, i) { return el("th", { class: i ? "num" : "", text: h }); }))]),
      el("tbody", {}, r.arms.map(function (a) {
        var cells = conv
          ? [a.name, fmtInt(a.conversions), fmtInt(a.n), (100 * a.conversions / a.n).toFixed(2) + "%"]
          : [a.name, fmtInt(a.n), a.mean.toFixed(3), a.sd.toFixed(3)];
        return el("tr", {}, cells.map(function (c, i) { return el("td", { class: i ? "num" : "", text: c }); }));
      }))
    ]);
    t.style.marginTop = "16px";
    return t;
  }

  // Interval figure: each variant's effect with its confidence interval. Lime squares carry an ink outline.
  function intervalFigure(r) {
    var conv = r.metric === "conversion", k = conv ? 100 : 1, unit = conv ? " pts" : "";
    var narrow = window.innerWidth < 720, cs = r.comparisons, W = narrow ? Math.max(280, window.innerWidth - 76) : 720, left = narrow ? 70 : 150, right = 16, rowH = 56, top = 20, H = top + cs.length * rowH + 36;
    var ext = 0.0001;
    cs.forEach(function (c) { ext = Math.max(ext, Math.abs(c.ci[0]), Math.abs(c.ci[1]), Math.abs(c.effect)); });
    if (r.mde) ext = Math.max(ext, r.mde);
    ext *= 1.15 * k;
    var x = function (v) { return left + (v * k + ext) / (2 * ext) * (W - left - right); };
    var s = svg("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "effect and confidence interval for each variant versus control" });
    if (r.mde) {
      s.appendChild(svg("rect", { x: x(-r.mde), y: top - 6, width: x(r.mde) - x(-r.mde), height: cs.length * rowH, fill: "var(--rule)", opacity: "0.55" }));
      s.appendChild(svg("text", { x: x(r.mde) + 6, y: top + 6 }, "smallest lift worth acting on"));
    }
    var zero = x(0);
    s.appendChild(svg("line", { x1: zero, x2: zero, y1: top - 6, y2: top + cs.length * rowH - 6, stroke: "var(--ink)", "stroke-width": 1.5 }));
    s.appendChild(svg("text", { x: zero, y: H - 12, "text-anchor": "middle" }, "no change"));
    var ticks = [-ext, ext];
    ticks.forEach(function (t) {
      s.appendChild(svg("text", { x: x(t / k), y: H - 12, "text-anchor": t < 0 ? "start" : "end" }, (t > 0 ? "+" : "") + t.toFixed(conv ? 1 : 2) + unit));
    });
    cs.forEach(function (c, i) {
      var y = top + i * rowH + 20;
      s.appendChild(svg("text", { class: "name", x: 0, y: y + 5 }, c.variant));
      s.appendChild(svg("line", { x1: x(c.ci[0]), x2: x(c.ci[1]), y1: y, y2: y, stroke: "var(--ink)", "stroke-width": 2.5 }));
      [c.ci[0], c.ci[1]].forEach(function (e) {
        s.appendChild(svg("line", { x1: x(e), x2: x(e), y1: y - 8, y2: y + 8, stroke: "var(--ink)", "stroke-width": 2.5 }));
      });
      s.appendChild(svg("rect", { x: x(c.effect) - 8, y: y - 8, width: 16, height: 16, fill: "var(--lime)", stroke: "var(--ink)", "stroke-width": 1.5 }));
      s.appendChild(svg("text", { x: x(c.effect), y: y + 28, "text-anchor": "middle" }, (c.effect > 0 ? "+" : "") + (c.effect * k).toFixed(conv ? 2 : 3) + unit));
    });
    var fig = el("div", { class: "fig" }, [s, el("p", { class: "caption cap", text: "Square = observed effect vs control. Bar = " + (r.ci_level * 100).toFixed(1) + "% confidence interval. If the bar crosses no change, the data can't separate this from nothing." })]);
    return fig;
  }

  function comparison(r, c) {
    var cls = c.verdict === "WINNER" ? "win" : (c.verdict === "LOSER" || c.verdict === "INVALID" ? "bad" : "");
    var conv = r.metric === "conversion", k = conv ? 100 : 1, unit = conv ? " pts" : "";
    var f = function (v) { return (v > 0 ? "+" : "") + (v * k).toFixed(conv ? 2 : 3) + unit; };
    var rel = c.relative_effect != null ? " (" + (c.relative_effect > 0 ? "+" : "") + (c.relative_effect * 100).toFixed(1) + "% relative)" : "";
    return el("div", { class: "cmp" }, [
      el("div", { class: "cmp-head" }, [el("strong", { text: c.variant + " vs " + c.control }), el("span", { class: "pill " + cls, text: c.verdict.toLowerCase() })]),
      el("p", { text: "Effect " + f(c.effect) + rel + ". Interval " + f(c.ci[0]) + " to " + f(c.ci[1]) + "." }),
      el("p", { class: "caption", text: "p = " + fmtP(c.p_value) + ", adjusted " + fmtP(c.p_adjusted) + ", needs to beat " + Number(r.alpha_effective.toPrecision(3)) + "." }),
      el("ul", {}, c.reasons.map(function (t) { return el("li", { text: t }); }))
    ]);
  }

  function checksList(r) {
    return el("ul", { class: "checks" }, r.checks.map(function (c) {
      return el("li", {}, [el("span", { class: "state " + c.status, text: c.status }), el("span", { class: "cname", text: c.name }), el("span", { class: "cdetail", text: c.detail })]);
    }));
  }
  function warnList(ws) {
    return el("ul", { class: "warn-list" }, ws.map(function (w) { return el("li", { text: w }); }));
  }

  function summaryText(r) {
    var out = [r.headline, ""];
    r.arms.forEach(function (a) { out.push("  " + a.name + ": " + (r.metric === "conversion" ? a.conversions + " / " + a.n + " = " + (100 * a.conversions / a.n).toFixed(2) + "%" : "n=" + a.n + ", mean " + a.mean.toFixed(3))); });
    out.push("");
    r.comparisons.forEach(function (c) { out.push(c.variant + " vs " + c.control + ": " + c.verdict); c.reasons.forEach(function (t) { out.push("  - " + t); }); });
    out.push("");
    r.checks.forEach(function (c) { out.push(c.status + "  " + c.name + ": " + c.detail); });
    r.warnings.forEach(function (w) { out.push("! " + w); });
    out.push("", "Checked with abverdict (ben.j.ads).");
    return out.join("\n");
  }

  // ---------- plan ----------
  function metric() { return document.querySelector('input[name="metric"]:checked').value; }
  document.querySelectorAll('input[name="metric"]').forEach(function (r) {
    r.addEventListener("change", function () {
      var conv = metric() === "conversion";
      document.querySelector('[data-for="conversion"]').hidden = !conv;
      document.querySelector('[data-for="continuous"]').hidden = conv;
      $("p-mde-label").textContent = conv ? "smallest lift worth detecting (relative, %)" : "smallest difference worth detecting (same units as the metric)";
      $("p-mde").value = conv ? 10 : "";
    });
  });

  $("plan-form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    showError("plan-error", "");
    var conv = metric() === "conversion";
    var body = { metric: metric(), arms: num("p-arms") || 2, power: (num("p-power") || 80) / 100, daily_traffic: num("p-traffic") };
    if (conv) { body.baseline = (num("p-baseline") || 0) / 100; body.mde = (num("p-mde") || 0) / 100; }
    else { body.sd = num("p-sd"); body.mde = num("p-mde"); }
    post("/api/plan", body).then(renderPlan).catch(function (e) { showError("plan-error", e.message); });
  });

  function renderPlan(p) {
    var box = $("plan-result");
    box.innerHTML = "";
    box.appendChild(el("p", { class: "label kicker", text: "the plan" }));
    box.appendChild(el("h2", { class: "verdict" }, [el("mark", { class: "hl", text: fmtInt(p.n_per_arm) })]));
    box.appendChild(el("p", { class: "lead", text: "visitors per variant. Decide this now, and do not call the test before you get there." }));
    var stats = [["total visitors", fmtInt(p.total)], ["variants", String(p.arms)]];
    if (p.days) stats.push(["run for", p.days + " days"]);
    box.appendChild(el("div", { class: "plan-stats" }, stats.map(function (s) {
      return el("div", {}, [el("p", { class: "label", text: s[0] }), el("p", { class: "n", text: s[1] })]);
    })));
    if (p.days && p.raw_days && p.days !== p.raw_days) box.appendChild(el("p", { class: "caption", text: "Traffic alone needs " + p.raw_days + " days. Rounded up to whole weeks so every weekday is covered equally." }));
    box.appendChild(el("p", { class: "caption", text: "alpha " + p.alpha + " (" + Number(p.alpha_per_comparison.toPrecision(3)) + " per comparison), power " + Math.round(p.power * 100) + "%." }));
    var use = el("button", { class: "primary", type: "button", text: "use this in the test →" });
    use.style.marginTop = "24px";
    use.addEventListener("click", function () { $("planned_n").value = p.n_per_arm; if (p.days) $("days").placeholder = "at least " + p.days; showTab("test"); $("planned_n").scrollIntoView({ block: "center" }); });
    box.appendChild(use);
    box.hidden = false;
  }
})();
