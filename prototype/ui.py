"""Pages for the web interface: layout, styling and the guided tour.

Pure functions that turn data into HTML strings; no HTTP and no file access here (webapp.py does that).
Rules this module keeps:
  * every value that comes from data, a user or a file goes through esc();
  * the only script is the guided tour, served with a per-response nonce, and NO data is ever placed inside it
    (the tour text below is a constant), so a hostile officer name or note cannot reach script context;
  * risk is never shown by colour alone: each class also has a text label.
"""
from __future__ import annotations

import html
import json

SITE_NAMES = {"QEUH": "Queen Elizabeth University Hospital", "GRI": "Glasgow Royal Infirmary",
              "RHC": "Royal Hospital for Children"}
RISK_TEXT = {"low": "Low", "medium": "Medium", "high": "High"}
RISK_HELP = {"low": "within the normal range", "medium": "busier than usual: watch only",
             "high": "unusually busy: needs an officer's decision"}


def nice_time(iso: str) -> str:
    """'2026-11-15T03:14:20+00:00' -> '15 Nov 2026, 03:14 UTC' (falls back to the raw text if it cannot be parsed)."""
    import datetime as dt
    try:
        return dt.datetime.fromisoformat(iso).strftime("%-d %b %Y, %H:%M UTC")
    except (ValueError, TypeError):
        return str(iso)


def esc(x) -> str:
    return html.escape(str(x), quote=True)


# ------------------------------------------------------------------ guided tour (constant text, single source for the tests)
# target = data-tour names tried in order; the first one present on the page is highlighted, otherwise the step is centred.
TOUR_STEPS = [
    {"target": [], "title": "Welcome",
     "body": "This tool forecasts next week's A&E attendance at three Glasgow hospitals and flags weeks that may be unusually "
             "busy. It is decision support only: nothing is released until a named officer approves it. This tour takes about a minute."},
    {"target": ["run"], "title": "1. Get a forecast",
     "body": "Press this to compute next week's forecast. Tick \"pull the latest data first\" to download new attendance and weather "
             "figures (about a minute). In demo mode it replays a past week offline."},
    {"target": ["cards", "run"], "title": "2. One card per hospital",
     "body": "The coloured label is the risk class: Low, Medium or High. The big number is the forecast attendance for the week, and the "
             "arrow compares it with last week."},
    {"target": ["chart", "cards"], "title": "3. How unusual is it?",
     "body": "The line shows the last 52 weeks and the dot is the forecast. The shaded bands mark the 75th and 90th percentile of those "
             "weeks: above the 75th is Medium, above the 90th is High."},
    {"target": ["drivers", "cards"], "title": "4. Why this forecast?",
     "body": "The bars show what pushes the forecast above or below a typical week: recent attendance, time of year, bank holidays, "
             "temperature. These are patterns in past data, not proven causes."},
    {"target": ["alerts"], "title": "5. Your decision",
     "body": "Only a High forecast creates an alert; Medium is watch-only. Approve it, or reject it with a reason (a rejection is final for "
             "that hospital and week). Your name comes from your login and is recorded. After approving, press Release to publish the message."},
    {"target": ["audit"], "title": "6. Everything is logged",
     "body": "Every action is written to a tamper-evident log with the officer's name and the time. If the integrity check ever fails, "
             "decisions are blocked until someone investigates."},
    {"target": ["limits"], "title": "Know the limits",
     "body": "In testing, high-pressure weeks were caught about a third to a half of the time. Treat an alert as a prompt to check, and no "
             "alert as no guarantee. This is not clinically validated. You can replay this tour any time with the Take the tour button."},
]

TOUR_JS = r"""
(function () {
  var STEPS = __STEPS__;
  var KEY = "ae_tour_done_v1";
  var root, spot, card, titleEl, bodyEl, countEl, backBtn, nextBtn, skipBtn, idx = 0, active = false, opener = null;

  function seen() { try { return localStorage.getItem(KEY) === "1"; } catch (e) { return false; } }
  function remember() { try { localStorage.setItem(KEY, "1"); } catch (e) {} }
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; }

  function build() {
    root = el("div", "tour-root"); root.id = "tour-root"; root.hidden = true;
    spot = el("div", "tour-spot");
    card = el("div", "tour-card"); card.setAttribute("role", "dialog"); card.setAttribute("aria-modal", "true");
    card.setAttribute("aria-labelledby", "tour-title"); card.tabIndex = -1;
    countEl = el("p", "tour-count"); titleEl = el("h2", "tour-title"); titleEl.id = "tour-title"; bodyEl = el("p", "tour-body");
    var row = el("div", "tour-row");
    skipBtn = el("button", "btn ghost", "Skip tour"); skipBtn.type = "button";
    backBtn = el("button", "btn", "Back"); backBtn.type = "button";
    nextBtn = el("button", "btn primary", "Next"); nextBtn.type = "button";
    row.appendChild(skipBtn); row.appendChild(backBtn); row.appendChild(nextBtn);
    card.appendChild(countEl); card.appendChild(titleEl); card.appendChild(bodyEl); card.appendChild(row);
    root.appendChild(spot); root.appendChild(card); document.body.appendChild(root);
    skipBtn.addEventListener("click", function () { stop(true); });
    backBtn.addEventListener("click", function () { go(idx - 1); });
    nextBtn.addEventListener("click", function () { if (idx >= STEPS.length - 1) stop(true); else go(idx + 1); });
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
  }

  function findTarget(step) {
    for (var i = 0; i < step.target.length; i++) {
      var n = document.querySelector('[data-tour="' + step.target[i] + '"]');
      if (n && n.getClientRects().length) return n;
    }
    return null;
  }

  function place() {
    if (!active) return;
    var t = findTarget(STEPS[idx]), pad = 8, vw = window.innerWidth, vh = window.innerHeight, cw = card.offsetWidth, ch = card.offsetHeight;
    root.classList.toggle("dim", !t);
    if (!t) {
      spot.style.display = "none";
      card.style.left = Math.max(12, (vw - cw) / 2) + "px"; card.style.top = Math.max(12, (vh - ch) / 2) + "px";
      return;
    }
    var r = t.getBoundingClientRect();
    spot.style.display = "block";
    spot.style.left = (r.left - pad) + "px"; spot.style.top = (r.top - pad) + "px";
    spot.style.width = (r.width + 2 * pad) + "px"; spot.style.height = (r.height + 2 * pad) + "px";
    var below = vh - r.bottom, above = r.top, top;
    if (below >= ch + 24) top = r.bottom + pad + 10;
    else if (above >= ch + 24) top = r.top - pad - 10 - ch;
    else top = Math.max(12, vh - ch - 12);                      // no room either side: dock to the bottom edge
    var left = Math.min(Math.max(12, r.left), Math.max(12, vw - cw - 12));
    card.style.top = Math.max(12, top) + "px"; card.style.left = left + "px";
  }

  function go(i) {
    idx = Math.max(0, Math.min(STEPS.length - 1, i));
    var s = STEPS[idx];
    countEl.textContent = "Step " + (idx + 1) + " of " + STEPS.length;
    titleEl.textContent = s.title; bodyEl.textContent = s.body;
    backBtn.disabled = idx === 0;
    nextBtn.textContent = idx === STEPS.length - 1 ? "Finish" : "Next";
    var t = findTarget(s);
    if (t) { var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
             t.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" }); }
    place(); setTimeout(place, 350);
    nextBtn.focus();
  }

  function start() {
    if (!root) build();
    opener = document.activeElement; active = true; root.hidden = false; document.body.classList.add("touring"); go(0);
  }

  function stop(finished) {
    if (!active) return;
    active = false; root.hidden = true; document.body.classList.remove("touring");
    if (finished) remember();
    if (opener && opener.focus) opener.focus();
  }

  function onKey(e) {
    if (!active) return;
    if (e.key === "Escape") { stop(true); }
    else if (e.key === "ArrowRight") { if (idx < STEPS.length - 1) go(idx + 1); }
    else if (e.key === "ArrowLeft") { go(idx - 1); }
    else if (e.key === "Tab") {                                  // keep focus inside the dialog
      var f = [skipBtn, backBtn, nextBtn].filter(function (b) { return !b.disabled; });
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      else if (!card.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var b = document.getElementById("tour-start");
    if (b) b.addEventListener("click", start);
    var run = document.getElementById("run-form");                // feedback while a forecast is computed
    if (run) {
      var runBtn = run.querySelector("button"), runLabel = runBtn.textContent;
      run.addEventListener("submit", function () { runBtn.disabled = true; runBtn.textContent = "Running (this can take a minute)..."; });
      window.addEventListener("pageshow", function () { runBtn.disabled = false; runBtn.textContent = runLabel; });   // Back button
    }
    if (document.body.hasAttribute("data-autotour") && !seen()) setTimeout(start, 400);
  });
})();
"""


def tour_script(nonce: str) -> str:
    steps = json.dumps(TOUR_STEPS).replace("</", "<\\/")           # constant data; never contains user input
    return f"<script nonce=\"{esc(nonce)}\">{TOUR_JS.replace('__STEPS__', steps)}</script>"


# ------------------------------------------------------------------ styling
CSS = """
:root{--bg:#f5f7fa;--panel:#fff;--ink:#17202a;--muted:#5b6672;--line:#dde3ea;--brand:#0b5cad;--brand-ink:#fff;
--low:#009E73;--medium:#B77900;--high:#C4430A;--low-bg:#e5f5ef;--medium-bg:#fdf1d8;--high-bg:#fbe5da;--ok-bg:#e8f5ee;--err-bg:#fdeee8;
--demo-bg:#fff6dd;--shadow:0 1px 2px rgba(16,24,40,.06),0 1px 3px rgba(16,24,40,.08)}
@media (prefers-color-scheme:dark){:root{--bg:#10151b;--panel:#18202a;--ink:#e8edf2;--muted:#9aa7b4;--line:#2a3542;--brand:#5aa2f0;--brand-ink:#08121d;
--low:#35c79b;--medium:#f0b445;--high:#ff8a56;--low-bg:#14342b;--medium-bg:#3a2f14;--high-bg:#3d2316;--ok-bg:#14342b;--err-bg:#3d2316;--demo-bg:#3a2f14;--shadow:none}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--brand)}
.wrap{max-width:1100px;margin:0 auto;padding:0 16px 48px}
header.top{background:var(--panel);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}
header.top .in{max-width:1100px;margin:0 auto;padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.brand{display:flex;gap:10px;align-items:center;font-weight:650;font-size:1.05rem;margin-right:auto}
.brand svg{width:28px;height:28px;color:var(--brand)}
.chip{font-size:.78rem;padding:2px 8px;border-radius:999px;border:1px solid var(--line);color:var(--muted);white-space:nowrap}
.chip.demo{background:var(--demo-bg);border-color:transparent;color:var(--ink);font-weight:600}
.btn{font:inherit;padding:.45rem .9rem;border-radius:8px;border:1px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer}
.btn:hover{border-color:var(--brand)}
.btn.primary{background:var(--brand);color:var(--brand-ink);border-color:var(--brand);font-weight:600}
.btn.ghost{border-color:transparent;color:var(--muted)}
.btn.danger{color:var(--high);border-color:var(--high)}
.btn[disabled]{opacity:.55;cursor:default}
:focus-visible{outline:3px solid var(--brand);outline-offset:2px}
h1{font-size:1.35rem;margin:1.2rem 0 .2rem}
h2{font-size:1.1rem;margin:1.8rem 0 .6rem}
.sub{color:var(--muted);margin:0 0 .8rem;font-size:.9rem}
.banner{padding:.6rem .9rem;border-radius:8px;margin:.7rem 0;border-left:4px solid}
.banner.ok{background:var(--ok-bg);border-color:var(--low)}
.banner.err{background:var(--err-bg);border-color:var(--high)}
.banner.demo{background:var(--demo-bg);border-color:var(--medium)}
.toolbar{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:.6rem 0}
.toolbar label{font-size:.9rem;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;box-shadow:var(--shadow)}
.card h3{margin:0;font-size:1rem;line-height:1.3}
.card.r-high{border-top:4px solid var(--high)}.card.r-medium{border-top:4px solid var(--medium)}.card.r-low{border-top:4px solid var(--low)}
.cardhead{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.cardhead .risk{flex:none}
.pagehead{display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:8px 16px}
.pagehead .toolbar{margin:0}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:.8rem 0 1.1rem}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px 14px;box-shadow:var(--shadow)}
.tile b{display:block;font-size:1.7rem;line-height:1.1}
.tile span{font-size:.8rem;color:var(--muted)}
.tile.t-high b{color:var(--high)}.tile.t-medium b{color:var(--medium)}.tile.t-low b{color:var(--low)}
.tile.t-act{border-color:var(--high);background:var(--high-bg)}
.tile a{font-weight:600;font-size:.85rem}
.axis{display:flex;justify-content:space-between;font-size:.72rem;color:var(--muted);margin:-2px 2px 4px}
.card .abbr{color:var(--muted);font-weight:500}
.risk{display:inline-flex;align-items:center;gap:6px;font-weight:650;font-size:.82rem;padding:2px 10px;border-radius:999px}
.risk::before{content:"";width:9px;height:9px;border-radius:50%;background:currentColor}
.risk.low{color:var(--low);background:var(--low-bg)}.risk.medium{color:var(--medium);background:var(--medium-bg)}.risk.high{color:var(--high);background:var(--high-bg)}
.big{font-size:2.3rem;font-weight:700;line-height:1.1;margin:.5rem 0 0}
.delta{color:var(--muted);font-size:.9rem;margin:0 0 .4rem}
.hint{font-size:.82rem;color:var(--muted)}
svg.chart{width:100%;height:auto;display:block;margin:.4rem 0}
.drv{margin-top:.4rem}
.drow{display:grid;grid-template-columns:minmax(0,2.1fr) minmax(0,.85fr) 2.6rem;gap:8px;align-items:center;font-size:.84rem;padding:2px 0}
.dbar{display:block;position:relative;height:10px;background:var(--bg);border-radius:5px}
.dbar::after{content:"";position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:var(--muted)}
.dbar i{position:absolute;top:0;height:10px;border-radius:5px}
.dbar i.pos{background:var(--high)}.dbar i.neg{background:var(--brand)}
.dval{text-align:right;font-variant-numeric:tabular-nums}
.legend{font-size:.76rem;color:var(--muted);margin:.2rem 0 0}
.status{margin-top:.6rem;font-size:.88rem;border-top:1px solid var(--line);padding-top:.5rem}
.empty{border:2px dashed var(--line);border-radius:12px;padding:28px;text-align:center;color:var(--muted)}
table{border-collapse:collapse;width:100%;font-size:.88rem}
th,td{padding:.4rem .6rem;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:.78rem;text-transform:uppercase;letter-spacing:.03em}
.tablewrap{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:4px 8px}
.alert{display:flex;gap:16px;justify-content:space-between;flex-wrap:wrap;align-items:flex-start}
.alert form{display:flex;gap:8px;flex-wrap:wrap;margin:.3rem 0;align-items:center}
.alert .acts{flex:1;min-width:280px;max-width:480px}
.alert .acts small{display:block;color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;margin-top:.5rem}
.alert input[type=text]{padding:.4rem .6rem;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);min-width:200px;font:inherit}
.st{font-weight:600}.st.pending{color:var(--medium)}.st.approved,.st.released{color:var(--low)}.st.rejected{color:var(--high)}
p.credits{margin:1rem 0 0;color:var(--muted);font-size:.78rem;line-height:1.5}p.credits a{color:inherit}
footer.note{margin-top:2rem;padding:.8rem 1rem;border:1px solid var(--line);border-radius:12px;background:var(--panel);color:var(--muted);font-size:.86rem}
form.login{max-width:380px;margin:3rem auto}
form.login label{display:block;margin:.8rem 0 .2rem;font-weight:600}
form.login input{width:100%;padding:.55rem .7rem;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--ink);font:inherit}
form.login button{margin-top:1.2rem;width:100%}
/* guided tour */
.tour-root[hidden]{display:none}
.tour-root{position:fixed;inset:0;z-index:100}
.tour-root::before{content:"";position:absolute;inset:0}
.tour-root.dim::before{background:rgba(8,15,25,.62)}
.tour-spot{position:fixed;border-radius:12px;box-shadow:0 0 0 9999px rgba(8,15,25,.62);pointer-events:none;transition:all .25s ease;display:none;outline:3px solid var(--brand)}
.tour-card{position:fixed;max-height:calc(100vh - 24px);overflow:auto;width:min(360px,calc(100vw - 24px));background:var(--panel);color:var(--ink);border-radius:12px;padding:16px;box-shadow:0 12px 40px rgba(0,0,0,.35);border:1px solid var(--line)}
.tour-count{margin:0;font-size:.76rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.tour-title{margin:.2rem 0 .4rem;font-size:1.1rem}
.tour-body{margin:0 0 .9rem;font-size:.92rem}
.tour-row{display:flex;gap:8px;justify-content:flex-end}
.tour-row .ghost{margin-right:auto}
body.touring{overflow:auto}
@media (prefers-reduced-motion:reduce){.tour-spot{transition:none}}
@media (max-width:560px){.big{font-size:2rem}.drow{grid-template-columns:1.6fr 1fr 2.6rem}.pagehead{align-items:flex-start}}
"""

LOGO = ("<svg viewBox='0 0 28 28' fill='none' stroke='currentColor' stroke-width='2.4' stroke-linecap='round' "
        "stroke-linejoin='round' aria-hidden='true'><rect x='2' y='2' width='24' height='24' rx='6'/>"
        "<path d='M5 15h4l2.5-6 4 11 2.5-5H23'/></svg>")
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 28 28'%3E%3Crect width='28' height='28' rx='6' "
           "fill='%230b5cad'/%3E%3Cpath d='M5 15h4l2.5-6 4 11 2.5-5H23' fill='none' stroke='white' stroke-width='2.4' "
           "stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")


def page(title: str, body: str, nonce: str, tour: bool = False, autotour: bool = False) -> str:
    script = tour_script(nonce) if tour else ""
    auto = " data-autotour='1'" if autotour else ""
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)}</title><link rel='icon' href=\"{FAVICON}\"><style>{CSS}</style></head>"
            f"<body{auto}>{body}{script}</body></html>")


# ------------------------------------------------------------------ pieces
def chart_svg(hist, forecast: float, p75: float, p90: float) -> str:
    """Last weeks as a line, the forecast as a dot, and the risk bands (below 75th / 75th-90th / above 90th)."""
    h = [float(v) for v in hist]
    if len(h) < 2:
        return ""
    w, ht, padl, padr, padt, padb = 320, 130, 6, 46, 8, 8
    lo, hi = min(min(h), forecast, p75) * 0.985, max(max(h), forecast, p90) * 1.015
    if hi - lo < 1e-9:                                         # flat data: avoid dividing by zero
        hi = lo + 1.0
    n = len(h)

    def x(i):
        return padl + (w - padl - padr) * i / n                  # i = n is the forecast week

    def y(v):
        return padt + (ht - padt - padb) * (1 - (v - lo) / (hi - lo))
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(h))
    bands = (f"<rect x='{padl}' y='{y(p75):.1f}' width='{w - padl - padr}' height='{ht - padb - y(p75):.1f}' fill='var(--low-bg)'/>"
             f"<rect x='{padl}' y='{y(p90):.1f}' width='{w - padl - padr}' height='{y(p75) - y(p90):.1f}' fill='var(--medium-bg)'/>"
             f"<rect x='{padl}' y='{padt}' width='{w - padl - padr}' height='{y(p90) - padt:.1f}' fill='var(--high-bg)'/>")
    labels = (f"<text x='{w - padr + 6}' y='{y(p90) + 4:.1f}' font-size='11' fill='var(--muted)'>90th</text>"
              f"<text x='{w - padr + 6}' y='{y(p75) + 4:.1f}' font-size='11' fill='var(--muted)'>75th</text>")
    cl = "high" if forecast > p90 else "medium" if forecast > p75 else "low"
    desc = (f"Weekly attendance for the last {n} weeks with the forecast of {forecast:.0f} for next week. "
            f"The 75th percentile is {p75:.0f} and the 90th is {p90:.0f}; the forecast is in the {cl} band.")
    return (f"<svg class='chart' viewBox='0 0 {w} {ht}' role='img' aria-label=\"{esc(desc)}\">{bands}{labels}"
            f"<polyline points='{pts}' fill='none' stroke='var(--brand)' stroke-width='1.6'/>"
            f"<line x1='{x(n - 1):.1f}' y1='{y(h[-1]):.1f}' x2='{x(n):.1f}' y2='{y(forecast):.1f}' stroke='var(--ink)' "
            f"stroke-width='1.4' stroke-dasharray='3 3'/>"
            f"<circle cx='{x(n):.1f}' cy='{y(forecast):.1f}' r='5' fill='var(--ink)' stroke='var(--panel)' stroke-width='2'/></svg>")


def drivers_html(drivers) -> str:
    if not drivers:
        return ""
    m = max(abs(v) for _, v in drivers) or 1.0
    rows = []
    for name, v in drivers:
        wpc = abs(v) / m * 50
        bar = (f"<i class='pos' style='left:50%;width:{wpc:.1f}%'></i>" if v >= 0
               else f"<i class='neg' style='left:{50 - wpc:.1f}%;width:{wpc:.1f}%'></i>")
        rows.append(f"<div class='drow'><span>{esc(name)}</span><span class='dbar'>{bar}</span><span class='dval'>{v:+.0f}</span></div>")
    return ("<div class='drv' data-tour='drivers'><div class='hint'>Why this forecast (attendances above or below a typical week)</div>"
            + "".join(rows) + "<div class='legend'>Red pushes the forecast up, blue pushes it down. Patterns in past data, not proven causes.</div></div>")


def site_card(r: dict, alert) -> str:
    risk = r["risk"]
    d = r["forecast"] - r["last_week"]
    arrow = "▲" if d > 0 else "▼" if d < 0 else "■"
    pct = 100 * d / r["last_week"] if r["last_week"] else 0.0
    if alert:
        status = f"Alert <b>{esc(alert.id)}</b>: <span class='st {esc(alert.status)}'>{esc(alert.status)}</span>"
    elif risk == "medium":
        status = "Watch only: no alert is raised for this tier."
    elif risk == "high":
        status = "High forecast: an alert should exist; see below."
    else:
        status = "No alert."
    return (f"<article class='card r-{risk}' aria-label=\"{esc(SITE_NAMES.get(r['site'], r['site']))}\">"
            f"<div class='cardhead'><h3>{esc(SITE_NAMES.get(r['site'], r['site']))} <span class='abbr'>({esc(r['site'])})</span></h3>"
            f"<span class='risk {risk}'>{RISK_TEXT[risk]}</span></div>"
            f"<div class='hint'>{RISK_HELP[risk]}</div>"
            f"<p class='big'>{r['forecast']:.0f}</p>"
            f"<p class='delta'>forecast attendances: {arrow} {abs(d):.0f} ({pct:+.1f}%) vs last week ({r['last_week']:.0f})</p>"
            f"<div data-tour='chart'>{chart_svg(r['history'], r['forecast'], r['p75'], r['p90'])}"
            f"<div class='axis'><span>&larr; last 52 weeks</span><span>forecast &bull;</span></div></div>"
            f"{drivers_html(r['drivers'])}<div class='status'>{status}</div></article>")


def summary_html(res, alerts) -> str:
    """At-a-glance strip: how many hospitals are high / medium / low and how many alerts wait for a decision."""
    n = {k: sum(1 for r in res if r["risk"] == k) for k in ("high", "medium", "low")}
    pend = sum(1 for a in alerts.values() if a.status == "pending")
    act = (f"<div class='tile t-act'><b>{pend}</b><span>alert{'s' if pend != 1 else ''} waiting</span><br><a href='#alerts'>Review now</a></div>"
           if pend else "<div class='tile'><b>0</b><span>alerts waiting</span></div>")
    return ("<div class='summary' role='group' aria-label='Summary'>"
            f"<div class='tile t-high'><b>{n['high']}</b><span>high</span></div>"
            f"<div class='tile t-medium'><b>{n['medium']}</b><span>medium</span></div>"
            f"<div class='tile t-low'><b>{n['low']}</b><span>low</span></div>{act}</div>")


def flash_html(flashes) -> str:
    return "".join(f"<div class='banner {'ok' if k == 'ok' else 'err'}' role='status'>{esc(m)}</div>" for k, m in flashes)


def alerts_html(alerts: dict, csrf: str) -> str:
    c = esc(csrf)
    pending = [a for a in alerts.values() if a.status == "pending"]
    out = [f"<section id='alerts' data-tour='alerts' aria-labelledby='h-alerts'><h2 id='h-alerts'>Needs your decision ({len(pending)})</h2>"]
    if not pending:
        out.append("<div class='empty'>No alerts are waiting. An alert appears here when a forecast is High.</div>")
    for a in pending:
        top = ", ".join(f"{n} ({v:+.0f})" for n, v in a.drivers[:3]) or "n/a"
        hid = f"<input type='hidden' name='csrf' value='{c}'><input type='hidden' name='id' value='{esc(a.id)}'>"
        out.append(
            f"<div class='card alert' style='margin-bottom:12px'><div><b>{esc(SITE_NAMES.get(a.site, a.site))}</b> "
            f"<span class='risk high'>High</span><br>Week ending {esc(a.target_week)}: forecast {a.forecast:.0f} attendances.<br>"
            f"<span class='hint'>Main drivers: {esc(top)}. Alert {esc(a.id)}</span></div><div class='acts'>"
            f"<small>Approve (releases nothing yet)</small><form method='post' action='/decide'>{hid}<input type='hidden' name='action' value='approve'>"
            f"<input type='text' name='note' placeholder='note (optional)' maxlength='500' aria-label='Approval note'>"
            f"<button class='btn primary'>Approve</button></form>"
            f"<small>Reject (final for this week)</small><form method='post' action='/decide'>{hid}<input type='hidden' name='action' value='reject'>"
            f"<input type='text' name='note' placeholder='reason (required)' maxlength='500' required aria-label='Rejection reason'>"
            f"<button class='btn danger'>Reject</button></form></div></div>")
    done = [a for a in alerts.values() if a.status != "pending"]
    if done:
        out.append("<h2>Decided alerts</h2><div class='tablewrap'><table><thead><tr><th>Alert</th><th>Hospital</th><th>Week ending</th>"
                   "<th>Status</th><th>By</th><th></th></tr></thead><tbody>")
        for a in done:
            btn = (f"<form method='post' action='/decide'><input type='hidden' name='csrf' value='{c}'>"
                   f"<input type='hidden' name='id' value='{esc(a.id)}'><input type='hidden' name='action' value='release'>"
                   f"<button class='btn'>Release message</button></form>") if a.status == "approved" else ""
            out.append(f"<tr><td>{esc(a.id)}</td><td>{esc(a.site)}</td><td>{esc(a.target_week)}</td>"
                       f"<td><span class='st {esc(a.status)}'>{esc(a.status)}</span></td><td>{esc(a.decided_by or '')}</td><td>{btn}</td></tr>")
        out.append("</tbody></table></div>")
    out.append("</section>")
    return "".join(out)


def audit_html(events, intact: bool, error: str) -> str:
    if not intact:
        status = (f"<div class='banner err'><b>Audit log integrity check FAILED:</b> {esc(error)}. Decisions are disabled until "
                  "this is investigated.</div>")
    else:
        status = "<div class='banner ok'>Audit log integrity check: passed.</div>"
    out = [f"<section data-tour='audit' aria-labelledby='h-audit'><h2 id='h-audit'>Audit log</h2>{status}"]
    if intact and events:
        out.append("<div class='tablewrap'><table><thead><tr><th>Time (UTC)</th><th>Event</th><th>Alert</th><th>Officer</th>"
                   "<th>Note</th></tr></thead><tbody>")
        for e in reversed(events[-30:]):
            who = e.get("released_by") or e.get("officer") or ""
            out.append(f"<tr><td>{esc(e['ts'])}</td><td>{esc(e['event'])}</td>"
                       f"<td>{esc(e.get('alert', {}).get('id') or e.get('alert_id') or '')}</td><td>{esc(who)}</td>"
                       f"<td>{esc(e.get('note') or '')}</td></tr>")
        out.append("</tbody></table></div><p class='hint'>Latest 30 events, newest first.</p>")
    elif intact:
        out.append("<div class='empty'>No events yet.</div>")
    out.append("</section>")
    return "".join(out)


# ------------------------------------------------------------------ pages
CREDITS = ("<p class='credits'>Attendance data: Public Health Scotland, "
           "<a href='https://www.opendata.nhs.scot/dataset/weekly-accident-and-emergency-activity-and-waiting-times' rel='noopener noreferrer'>"
           "Weekly A&amp;E Activity and Waiting Times</a>. Contains public sector information licensed under the "
           "<a href='https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/' rel='noopener noreferrer'>Open Government Licence v3.0</a>. "
           "<a href='https://open-meteo.com/' rel='noopener noreferrer'>Weather data by Open-Meteo.com</a> "
           "(<a href='https://creativecommons.org/licenses/by/4.0/' rel='noopener noreferrer'>CC BY 4.0</a>). "
           "A student research prototype, not endorsed by Public Health Scotland or the NHS.</p>")


def login_page(nonce: str, demo: bool, any_users: bool, error: str = "") -> str:
    msg = f"<div class='banner err' role='alert'>{esc(error)}</div>" if error else ""
    if not any_users:
        msg += ("<div class='banner err'>No officer accounts exist yet. Create one in a terminal: "
                "<code>python alert_tool.py adduser \"Your Name\"</code></div>")
    demo_b = "<div class='banner demo'>DEMO MODE: demo log and demo forecast only.</div>" if demo else ""
    body = (f"<main class='wrap'><form class='login' method='post' action='/login'>"
            f"<div class='brand' style='margin-bottom:1rem'>{LOGO}<span>A&amp;E Pressure Early Warning</span></div>"
            f"<h1>Sign in</h1>{demo_b}{msg}"
            "<label for='name'>Officer name</label><input id='name' type='text' name='name' autocomplete='username' required maxlength='40'>"
            "<label for='pw'>Password</label><input id='pw' type='password' name='password' autocomplete='current-password' "
            "required maxlength='200'><button class='btn primary' type='submit'>Sign in</button>"
            "<p class='hint' style='margin-top:1rem'>Decision support only. Every approval is recorded in the audit log under the "
            "name you sign in with.</p></form>" + CREDITS + "</main>")
    return page("Sign in", body, nonce)


def dashboard(*, nonce: str, user: str, csrf: str, flashes, demo: bool, latest: dict | None, alerts: dict, events,
              intact: bool, error: str, site_alerts_lookup=None) -> str:
    c = esc(csrf)
    top = (f"<header class='top'><div class='in'><div class='brand'>{LOGO}<span>A&amp;E Pressure Early Warning</span></div>"
           + ("<span class='chip demo'>DEMO MODE</span>" if demo else "")
           + "<button type='button' id='tour-start' class='btn'>Take the tour</button>"
           f"<span class='chip'>signed in as <b>{esc(user)}</b></span>"
           f"<form method='post' action='/logout'><input type='hidden' name='csrf' value='{c}'><button class='btn ghost'>Sign out</button></form>"
           "</div></header>")
    refresh = "" if demo else ("<label><input type='checkbox' name='refresh' value='1'> pull the latest data first "
                               "(about a minute)</label>")
    run = (f"<form id='run-form' method='post' action='/run' class='toolbar' data-tour='run'><input type='hidden' name='csrf' value='{c}'>"
           f"<button class='btn primary'>{'Run the demo forecast' if demo else 'Run forecast now'}</button>{refresh}</form>")
    if latest:
        res = latest["results"]
        cards = "".join(site_card(r, next((a for a in alerts.values() if a.site == r["site"] and a.target_week == r["target_week"]), None))
                        for r in res)
        head = (f"<div class='pagehead'><div><h1>Forecast: week ending {esc(res[0]['target_week'])}</h1>"
                f"<p class='sub'>Computed {esc(nice_time(latest['saved_at']))}. Decision support only: predictive, not causal.</p></div>{run}</div>")
        body_f = f"{head}{summary_html(res, alerts)}<div class='grid' data-tour='cards'>{cards}</div>"
    else:
        body_f = (f"<div class='pagehead'><h1>Forecast</h1>{run}</div><div class='empty' data-tour='cards'><b>No forecast yet.</b><br>Press the blue button above to compute "
                  "next week's forecast for the three hospitals.</div>")
    demo_b = ("<div class='banner demo'>DEMO MODE: this uses the demo log and a past week as if it were the forecast.</div>" if demo else "")
    limits = ("<footer class='note' data-tour='limits'><b>Know the limits.</b> This is decision support, not clinical advice. Alerts "
              "caught only about a third to a half of high-pressure weeks in testing, so treat an alert as a prompt to check and no alert "
              "as no guarantee. Forecasts are patterns in past data, not causes. Not clinically validated.</footer>" + CREDITS)
    main = (f"<main class='wrap'>{flash_html(flashes)}{demo_b}{body_f}{alerts_html(alerts, csrf)}"
            f"{audit_html(events, intact, error)}{limits}</main>")
    return page("A&E Pressure Early Warning", top + main, nonce, tour=True, autotour=not flashes)
