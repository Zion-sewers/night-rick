#!/usr/bin/env python3
"""Real-browser flow audit: drive every route and every control, at phone size.

WHY THIS EXISTS

An agent shipped a web app, said it worked, and it did not work. The specific
failure was not a wrong algorithm. It was that nobody opened the thing on a
phone-sized screen and pressed the buttons. Nothing in this setup could have
caught that, because every quality artifact here was prose: a testing-pyramid
skill that plans layers, a ui-ux skill that recommends palettes, a completion
gate that greps the assistant's own sentence for the word "tested". None of them
load a page. A model asked "does the app work" answers from the source it wrote,
which is the one witness that cannot be trusted.

So this is the instrument. It opens the real Chrome on this machine through
tools/browser/cdp.py, emulates a phone, walks the routes, and for each route it
presses every control it can find and watches what happens. Its output is a list
of findings with severities and a non-zero exit code, which means it can sit in
front of a done-claim and refuse it. That is the whole point: the judgement has
to come from something other than the agent's opinion of its own work.

WHAT IT CHECKS, AND WHY EACH ONE EARNED ITS PLACE

Per route, statically:
  render        a route that paints almost nothing is the most common silent
                failure of a client-rendered app; a router that matched nothing
                still returns HTTP 200
  overflow      horizontal scroll at 390px is the signature of desktop-first
                CSS, and it is invisible on the developer's monitor
  tap targets   WCAG 2.5.8 puts the AA floor at 24x24 CSS px and Apple's
                guidance is 44x44, so under 24 fails and under 44 warns
  names         a control with no text, no aria-label and no title is operable
                by nobody, including the person who wrote it
  labels        an input with no associated label is the same defect for forms
  contrast      computed against the nearest painted ancestor background, since
                4.5:1 is the AA floor for body text and getting this wrong is
                the most common accessibility failure on any page
  text size     under 12px is unreadable on a phone, and a form control under
                16px makes iOS Safari zoom the whole viewport on focus
  images        naturalWidth of 0 means the asset 404ed even though the layout
                looks intact
  head          title, html lang, and a device-width viewport meta; the last
                one absent means the phone renders at 980px and scales down,
                which makes every other measurement here meaningless
  ids           duplicates break label-for and anchor navigation

Per route, dynamically, which is the part that answers "every flow works":
  every visible control is clicked, one per fresh page load so state cannot
  leak between them, and the click is judged on whether anything happened at
  all (url, DOM, dialog, new request) and on whether it threw. A control that
  does nothing is reported as dead. This is the check that would have caught
  the original complaint.

Live, from the browser rather than the DOM:
  uncaught exceptions, console errors, failed requests, and any response at or
  above 400 on the app's own origin.

EXIT CODES
  0  no fail-level findings
  1  at least one fail-level finding
  2  the audit could not run (no browser, host unreachable, no routes)
Warnings never change the exit code unless --strict is passed, so that a
warning backlog cannot be used as a reason to disable the gate.

Stdlib only, same as the rest of tools/.

USAGE
  python tools/e2e/flow.py audit http://localhost:3000
  python tools/e2e/flow.py audit http://localhost:3000 --route /login --route /app
  python tools/e2e/flow.py audit http://localhost:3000 --viewport both --strict
  python tools/e2e/flow.py audit http://localhost:3000 --out state/e2e/report.json
  python tools/e2e/flow.py selftest
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "browser"))
import cdp  # noqa: E402

# Two viewports, both real devices rather than round numbers, because the
# interesting failures are at the narrow end and 390x844 is the most common
# phone in use. The desktop arm exists only to prove a finding is
# mobile-specific rather than universal.
VIEWPORTS = {
    "mobile": {
        "width": 390, "height": 844, "deviceScaleFactor": 3, "mobile": True,
        "ua": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"),
    },
    "desktop": {
        "width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False,
        "ua": None,
    },
}

FAIL = "fail"
WARN = "warn"
INFO = "info"

MAX_ROUTES_DEFAULT = 25
MAX_CONTROLS_PER_ROUTE = 40


# --------------------------------------------------------------- browser probes

# One probe, run once per route, returning structured findings rather than a
# verdict. Keeping the judgement in Python means the thresholds are reviewable
# in one place instead of buried in a page script.
PROBE_JS = r"""
(() => {
  const out = { checks: [], meta: {} };
  const add = (kind, sev, msg, extra) => out.checks.push(
    Object.assign({ kind, sev, msg }, extra || {}));

  // Deliberately clientWidth and not innerWidth. Under mobile emulation with no
  // viewport meta, Chrome scales the page out to fit its content, so innerWidth
  // reports the *content* width (1200 on a 390px device) while clientWidth
  // reports the layout viewport (980). Comparing scrollWidth to innerWidth then
  // reads 1200 > 1200 and declares the worst possible page overflow-free, which
  // is how the first version of this probe missed its own planted defect.
  // scrollWidth > clientWidth is also the exact condition under which a browser
  // shows a horizontal scrollbar, and it is in the same CSS space as every
  // getBoundingClientRect below.
  const vw = document.documentElement.clientWidth || window.innerWidth;
  const vh = document.documentElement.clientHeight || window.innerHeight;
  const deviceW = __TARGET_W__;
  out.meta.viewport = [vw, vh];
  out.meta.device_width = deviceW;
  if (vw > deviceW + 2)
    add("head", "fail", "layout viewport is " + vw + "px on a " + deviceW +
        "px device, so the phone renders wide and scales down; every size below " +
        "is measured in that scaled space");
  out.meta.url = location.href;
  out.meta.title = document.title || "";

  // ---- head
  if (!document.title || !document.title.trim())
    add("head", "warn", "document has no title");
  if (!document.documentElement.getAttribute("lang"))
    add("head", "warn", "<html> has no lang attribute, so screen readers guess the language");
  const vp = document.querySelector('meta[name="viewport"]');
  if (!vp) {
    add("head", "fail", "no viewport meta tag, so a phone renders this at 980px and scales down");
  } else if (!/width\s*=\s*device-width/i.test(vp.getAttribute("content") || "")) {
    add("head", "fail", "viewport meta does not set width=device-width: " +
        (vp.getAttribute("content") || ""));
  } else if (/user-scalable\s*=\s*no|maximum-scale\s*=\s*1(\.0)?\b/i.test(vp.getAttribute("content") || "")) {
    add("head", "warn", "viewport blocks pinch zoom, which fails WCAG 1.4.4");
  }

  // ---- did anything render
  const visibleText = (document.body ? document.body.innerText || "" : "").replace(/\s+/g, " ").trim();
  const imgs = Array.from(document.images || []);
  const canvases = document.querySelectorAll("canvas, svg").length;
  out.meta.text_len = visibleText.length;
  if (visibleText.length < 20 && imgs.length === 0 && canvases === 0)
    add("render", "fail", "route painted almost nothing: " + visibleText.length +
        " chars of visible text, no images, no canvas or svg");
  else if (visibleText.length < 80 && imgs.length === 0 && canvases === 0)
    add("render", "warn", "route painted very little: " + visibleText.length + " chars");

  // ---- horizontal overflow, and who is causing it
  const de = document.documentElement;
  const slack = 2;
  if (de.scrollWidth > vw + slack) {
    const culprits = [];
    const all = document.querySelectorAll("body *");
    for (const el of all) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      const cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden") continue;
      if (cs.position === "fixed") continue;
      if (r.right > vw + slack || r.left < -slack) {
        // Only report the outermost offender in each subtree; a wide child
        // inside a wide parent is one bug, not two.
        if (!culprits.some(c => c.el.contains(el))) culprits.push({ el, r });
      }
      if (culprits.length > 12) break;
    }
    add("overflow", "fail",
        "page scrolls horizontally at " + vw + "px: content is " + de.scrollWidth + "px wide",
        { offenders: culprits.slice(0, 8).map(c => ({
            sel: sel(c.el), right: Math.round(c.r.right), width: Math.round(c.r.width) })) });
  }

  // ---- selectors, stable enough to click again on a fresh load
  function sel(el) {
    if (!el || el.nodeType !== 1) return "";
    if (el.id && document.querySelectorAll("#" + CSS.escape(el.id)).length === 1)
      return "#" + CSS.escape(el.id);
    for (const a of ["data-testid", "data-test", "data-cy", "name", "aria-label"]) {
      const v = el.getAttribute && el.getAttribute(a);
      if (v) {
        const s = el.tagName.toLowerCase() + "[" + a + '="' + v.replace(/"/g, '\\"') + '"]';
        try { if (document.querySelectorAll(s).length === 1) return s; } catch (e) {}
      }
    }
    const parts = [];
    let n = el;
    while (n && n.nodeType === 1 && parts.length < 6) {
      let p = n.tagName.toLowerCase();
      const parent = n.parentElement;
      if (parent) {
        const sibs = Array.from(parent.children).filter(c => c.tagName === n.tagName);
        if (sibs.length > 1) p += ":nth-of-type(" + (sibs.indexOf(n) + 1) + ")";
      }
      parts.unshift(p);
      if (n.id && document.querySelectorAll("#" + CSS.escape(n.id)).length === 1) {
        parts[0] = "#" + CSS.escape(n.id);
        break;
      }
      n = parent;
      if (!n || n.tagName === "HTML") break;
    }
    return parts.join(" > ");
  }

  const INTERACTIVE = 'a[href], button, [role="button"], [role="link"], [role="tab"], ' +
    '[role="menuitem"], [role="switch"], [role="checkbox"], input, select, textarea, ' +
    'summary, [onclick], [tabindex]:not([tabindex="-1"])';

  function accName(el) {
    const al = (el.getAttribute("aria-label") || "").trim();
    if (al) return al;
    const lb = el.getAttribute("aria-labelledby");
    if (lb) {
      const t = lb.split(/\s+/).map(id => {
        const n = document.getElementById(id);
        return n ? (n.innerText || "").trim() : "";
      }).join(" ").trim();
      if (t) return t;
    }
    const txt = (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
    if (txt) return txt;
    const ttl = (el.getAttribute("title") || "").trim();
    if (ttl) return ttl;
    const ph = (el.getAttribute("placeholder") || "").trim();
    if (ph) return ph;
    const v = (el.getAttribute("value") || "").trim();
    if (v && /^(input)$/i.test(el.tagName)) return v;
    const img = el.querySelector && el.querySelector("img[alt], svg title, [aria-label]");
    if (img) {
      const a = (img.getAttribute && (img.getAttribute("alt") || img.getAttribute("aria-label"))) ||
                (img.textContent || "");
      if (a && a.trim()) return a.trim();
    }
    if (el.labels && el.labels.length) {
      const t = Array.from(el.labels).map(l => (l.innerText || "").trim()).join(" ").trim();
      if (t) return t;
    }
    return "";
  }

  function visible(el) {
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity || "1") < 0.05)
      return false;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    if (r.bottom < -vh * 3 || r.top > vh * 6) return false;   // far offscreen
    return true;
  }

  // ---- controls: size, name, and the clickable inventory the driver uses
  const controls = [];
  const seenSel = new Set();
  for (const el of document.querySelectorAll(INTERACTIVE)) {
    if (!visible(el)) continue;
    if (el.disabled) continue;
    const r = el.getBoundingClientRect();
    const name = accName(el);
    const s = sel(el);
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute("type") || "").toLowerCase();
    const min = Math.min(r.width, r.height);

    if (!name && !(tag === "input" && /^(hidden)$/.test(type)))
      add("name", "fail", "control has no accessible name: <" + tag +
          (type ? " type=" + type : "") + ">", { sel: s });

    if (min < 24)
      add("target", "fail", "tap target " + Math.round(r.width) + "x" + Math.round(r.height) +
          " is under the 24x24 WCAG minimum: " + (name || tag), { sel: s });
    else if (min < 44)
      add("target", "warn", "tap target " + Math.round(r.width) + "x" + Math.round(r.height) +
          " is under the 44x44 comfortable size: " + (name || tag), { sel: s });

    const cs = getComputedStyle(el);
    const fs = parseFloat(cs.fontSize || "16");
    if (/^(input|select|textarea)$/.test(tag) && fs < 16 && !/^(checkbox|radio|range|color|file|submit|button|hidden)$/.test(type))
      add("text", "warn", "form control font-size " + fs +
          "px is under 16px, so iOS Safari zooms the viewport on focus", { sel: s });

    if (tag === "a") {
      const href = (el.getAttribute("href") || "").trim();
      if (!href || href === "#" || /^javascript:\s*(void\(0\)|;)?\s*$/i.test(href))
        add("link", "warn", "anchor with no destination (" + JSON.stringify(href) +
            "), which is a button wearing a link costume: " + (name || "unnamed"), { sel: s });
    }

    if (s && !seenSel.has(s) && controls.length < 200) {
      seenSel.add(s);
      controls.push({
        sel: s, tag, type, name: name.slice(0, 60),
        x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2),
        w: Math.round(r.width), h: Math.round(r.height),
        in_view: r.top >= 0 && r.bottom <= vh,
      });
    }
  }
  out.controls = controls;

  // ---- form fields without labels
  for (const el of document.querySelectorAll("input, select, textarea")) {
    if (!visible(el)) continue;
    const type = (el.getAttribute("type") || "").toLowerCase();
    if (/^(hidden|submit|button|image|reset)$/.test(type)) continue;
    const hasLabel = (el.labels && el.labels.length > 0) ||
      el.getAttribute("aria-label") || el.getAttribute("aria-labelledby");
    if (!hasLabel) {
      const ph = el.getAttribute("placeholder");
      add("label", ph ? "warn" : "fail",
          ph ? "field is labelled only by a placeholder, which disappears on focus: " + ph
             : "form field has no label at all: <" + el.tagName.toLowerCase() +
               (type ? " type=" + type : "") + ">",
          { sel: sel(el) });
    }
  }

  // ---- images
  for (const im of imgs) {
    if (!visible(im)) continue;
    if (im.complete && im.naturalWidth === 0)
      add("image", "fail", "image failed to load: " + (im.currentSrc || im.src || "?").slice(0, 160),
          { sel: sel(im) });
    if (!im.hasAttribute("alt"))
      add("image", "warn", "image has no alt attribute: " + (im.currentSrc || im.src || "?").slice(0, 120),
          { sel: sel(im) });
  }

  // ---- duplicate ids
  const ids = {};
  for (const el of document.querySelectorAll("[id]")) {
    const i = el.id;
    if (!i) continue;
    ids[i] = (ids[i] || 0) + 1;
  }
  const dupes = Object.keys(ids).filter(k => ids[k] > 1);
  if (dupes.length)
    add("dom", "warn", "duplicate element ids break label-for and anchors: " +
        dupes.slice(0, 8).join(", "));

  // ---- contrast, against the nearest painted ancestor
  function parseColor(c) {
    const m = /rgba?\(([^)]+)\)/.exec(c || "");
    if (!m) return null;
    const p = m[1].split(",").map(s => parseFloat(s));
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  }
  function lum(c) {
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  }
  function bgOf(el) {
    let n = el;
    while (n && n.nodeType === 1) {
      const c = parseColor(getComputedStyle(n).backgroundColor);
      if (c && c.a > 0.5) return c;
      n = n.parentElement;
    }
    return { r: 255, g: 255, b: 255, a: 1 };
  }
  const contrastSeen = new Set();
  let contrastChecked = 0;
  const walker = document.createTreeWalker(document.body || document.documentElement,
    NodeFilter.SHOW_TEXT, null);
  let node;
  while ((node = walker.nextNode()) && contrastChecked < 400) {
    const t = (node.nodeValue || "").replace(/\s+/g, " ").trim();
    if (t.length < 3) continue;
    const el = node.parentElement;
    if (!el || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|TITLE)$/.test(el.tagName)) continue;
    if (!visible(el)) continue;
    const cs = getComputedStyle(el);
    const fg = parseColor(cs.color);
    if (!fg || fg.a < 0.5) continue;
    const fs = parseFloat(cs.fontSize || "16");
    const bold = (parseInt(cs.fontWeight, 10) || 400) >= 700;
    if (fs < 12)
      add("text", "warn", "text at " + fs + "px is too small to read on a phone: " +
          t.slice(0, 50), { sel: sel(el) });
    const bg = bgOf(el);
    const L1 = lum(fg), L2 = lum(bg);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    contrastChecked++;
    // 3:1 is the AA floor for large text (>=24px, or >=18.66px bold), 4.5:1 otherwise.
    const large = fs >= 24 || (bold && fs >= 18.66);
    const floor = large ? 3 : 4.5;
    if (ratio < floor) {
      const key = cs.color + "|" + bg.r + "," + bg.g + "," + bg.b + "|" + Math.round(fs);
      if (!contrastSeen.has(key)) {
        contrastSeen.add(key);
        add("contrast", ratio < floor * 0.67 ? "fail" : "warn",
            "contrast " + ratio.toFixed(2) + ":1 is below the " + floor + ":1 floor for " +
            fs + "px text: " + JSON.stringify(t.slice(0, 40)),
            { sel: sel(el), fg: cs.color, bg: "rgb(" + bg.r + "," + bg.g + "," + bg.b + ")" });
      }
    }
  }

  // ---- an overlay that eats the screen
  for (const el of document.querySelectorAll("body *")) {
    const cs = getComputedStyle(el);
    if (cs.position !== "fixed") continue;
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.height > vh * 0.55 && r.width > vw * 0.8) {
      add("layout", "warn", "a fixed element covers " + Math.round(r.height / vh * 100) +
          "% of the viewport height, which on a phone leaves nothing to read",
          { sel: sel(el) });
      break;
    }
  }

  return out;
})()
"""


# State fingerprint before and after a click. Cheap enough to run twice per
# control, specific enough to tell "something happened" from "nothing happened".
# The `root` field exists because of claude-setup#57: theme toggles and similar
# controls flip attributes on <html> (e.g. documentElement.dataset.theme) without
# touching body markup, so a fingerprint that only reads the body is blind to a
# full repaint. Attributes are serialized canonically (sorted name=value pairs)
# so the comparison is deterministic across reads.
STATE_JS = r"""
(() => ({
  url: location.href,
  nodes: document.querySelectorAll("*").length,
  text: (document.body ? (document.body.innerText || "") : "").replace(/\s+/g, " ").trim().length,
  html: (document.body ? document.body.innerHTML.length : 0),
  root: (() => { const el = document.documentElement;
                 if (!el || !el.attributes) return "";
                 const out = [];
                 for (let i = 0; i < el.attributes.length; i++) {
                   const a = el.attributes[i];
                   out.push(a.name + "=" + a.value);
                 }
                 out.sort();
                 return out.join(";"); })(),
  focus: document.activeElement ? (document.activeElement.tagName || "") +
         "#" + (document.activeElement.id || "") : "",
  scroll: Math.round(window.scrollY),
}))()
"""


# --------------------------------------------------------------- CDP session

class Page:
    """One tab, with the event domains a flow audit needs already enabled."""

    def __init__(self, viewport: str = "mobile", verbose: bool = False):
        self.verbose = verbose
        self.vp = VIEWPORTS[viewport]
        cdp.launch()
        tab = cdp.new_tab("about:blank")
        ws_url = tab.get("webSocketDebuggerUrl")
        if not ws_url:
            raise RuntimeError("tab has no webSocketDebuggerUrl")
        self.tid = tab["id"]
        self.ws = cdp.WS(ws_url)
        self.ws.call("Page.enable")
        self.ws.call("Runtime.enable")
        self.ws.call("Network.enable")
        self.ws.call("Log.enable")
        # A file chooser left open blocks the renderer, and then every later
        # route times out for a reason that has nothing to do with that route.
        # Not every Chrome build exposes this, and its absence is not worth
        # aborting an audit over.
        try:
            self.ws.call("Page.setInterceptFileChooserDialog", {"enabled": True})
        except Exception:
            pass
        self._emulate()

    def mark(self) -> int:
        """Index into the event log, so a later read can be scoped to after now.

        Without this the driver miscounts badly: every navigation emits its own
        requestWillBeSent events, so "did a request happen after the click"
        answers yes for a completely dead button, and every console error from
        page load gets reported a second time against whichever control was
        pressed next.
        """
        return len(self.ws.events)

    def since(self, mark: int, *names: str) -> list[dict]:
        evs = self.ws.events[mark:]
        if not names:
            return list(evs)
        want = set(names)
        return [e for e in evs if e.get("method") in want]

    def _emulate(self) -> None:
        vp = self.vp
        self.ws.call("Emulation.setDeviceMetricsOverride", {
            "width": vp["width"], "height": vp["height"],
            "deviceScaleFactor": vp["deviceScaleFactor"], "mobile": vp["mobile"],
        })
        self.ws.call("Emulation.setTouchEmulationEnabled", {
            "enabled": bool(vp["mobile"]), "maxTouchPoints": 5 if vp["mobile"] else 0,
        })
        if vp["ua"]:
            self.ws.call("Emulation.setUserAgentOverride", {"userAgent": vp["ua"]})

    def goto(self, url: str, settle_s: float = 1.6, timeout_s: float = 30.0) -> None:
        self.ws.events.clear()
        self.ws.call("Page.navigate", {"url": url})
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            res = self.ws.call("Runtime.evaluate",
                               {"expression": "document.readyState", "returnByValue": True})
            if res.get("result", {}).get("value") == "complete":
                break
            time.sleep(0.25)
        # Client-rendered pages reach readyState complete with an empty shell,
        # so the settle is not optional padding, it is the difference between
        # auditing the app and auditing its loading spinner.
        time.sleep(settle_s)
        self.ws.pump(0.35)

    def js(self, expr: str, timeout_s: float = 45.0) -> object:
        res = self.ws.call("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": True,
        }, timeout_s=timeout_s)
        if res.get("exceptionDetails"):
            raise RuntimeError("probe threw: " +
                               json.dumps(res["exceptionDetails"])[:400])
        return res.get("result", {}).get("value")

    def close(self) -> None:
        try:
            self.ws.close()
        finally:
            try:
                cdp.close_tab(self.tid)
            except Exception:
                pass


# --------------------------------------------------------------- event reading

IGNORE = re.compile(
    r"(?i)(favicon\.ico|"
    r"download the react devtools|"
    r"\[vite\] connect|\[hmr\]|webpack-dev-server|"
    r"was preloaded using link preload but not used)")


def _by(events: list[dict], name: str) -> list[dict]:
    return [e for e in events if e.get("method") == name]


def browser_findings(events: list[dict], origin: str) -> list[dict]:
    """Turn a slice of the CDP event stream into findings.

    Takes a list rather than the socket so the caller controls the window: the
    route-level call passes everything since navigation, and the per-click call
    passes only what arrived after that click.

    Console noise is filtered narrowly: only the specific messages a dev server
    emits about itself, never by severity, because downgrading real errors to
    keep the report short is how a gate becomes decorative.
    """
    out: list[dict] = []

    for ev in _by(events, "Runtime.exceptionThrown"):
        d = ev.get("params", {}).get("exceptionDetails", {})
        exc = d.get("exception") or {}
        msg = exc.get("description") or d.get("text") or "uncaught exception"
        out.append({"kind": "js", "sev": FAIL,
                    "msg": "uncaught exception: " + str(msg).split("\n")[0][:300],
                    "detail": str(msg)[:800]})

    for ev in _by(events, "Runtime.consoleAPICalled"):
        p = ev.get("params", {})
        t = p.get("type")
        if t not in ("error", "warning", "assert"):
            continue
        parts = []
        for a in p.get("args", []):
            v = a.get("value", a.get("description", a.get("unserializableValue")))
            if v is None and a.get("type") == "object":
                v = a.get("className") or "[object]"
            parts.append(str(v))
        msg = " ".join(parts).strip()[:400]
        if not msg or IGNORE.search(msg):
            continue
        out.append({"kind": "console", "sev": FAIL if t != "warning" else WARN,
                    "msg": "console." + t + ": " + msg})

    for ev in _by(events, "Log.entryAdded"):
        e = ev.get("params", {}).get("entry", {})
        if e.get("level") not in ("error",):
            continue
        msg = (e.get("text") or "")[:400]
        if not msg or IGNORE.search(msg):
            continue
        # A network 4xx also arrives here; the network arm below reports it with
        # the status code, so this would be the same defect counted twice.
        if e.get("source") == "network":
            continue
        out.append({"kind": "browserlog", "sev": FAIL,
                    "msg": "browser log error: " + msg, "detail": e.get("url", "")})

    for ev in _by(events, "Network.responseReceived"):
        r = ev.get("params", {}).get("response", {})
        st = r.get("status", 0)
        url = r.get("url", "")
        if st < 400:
            continue
        if IGNORE.search(url):
            continue
        same = url.startswith(origin)
        out.append({"kind": "network", "sev": FAIL if same else WARN,
                    "msg": "HTTP {} on {}{}".format(st, "own origin " if same else "third party ",
                                                    url[:180])})

    for ev in _by(events, "Network.loadingFailed"):
        p = ev.get("params", {})
        if p.get("canceled"):
            continue
        err = p.get("errorText", "")
        if err in ("net::ERR_ABORTED",):
            continue
        out.append({"kind": "network", "sev": FAIL,
                    "msg": "request failed: {} ({})".format(err, p.get("type", "?"))})

    return out


# --------------------------------------------------------------- route discovery

def same_origin_links(page: Page, origin: str) -> list[str]:
    js = r"""
    (() => Array.from(document.querySelectorAll('a[href]'))
      .map(a => a.href)
      .filter(h => h && h.indexOf(location.origin) === 0)
      .filter(h => !/\.(png|jpe?g|gif|svg|pdf|zip|css|js|ico|webp|mp4|woff2?)($|\?)/i.test(h))
      .slice(0, 200))()
    """
    try:
        got = page.js(js) or []
    except Exception:
        return []
    seen: list[str] = []
    for h in got:
        p = urllib.parse.urlsplit(str(h))
        path = p.path or "/"
        if p.query:
            path += "?" + p.query
        if path not in seen:
            seen.append(path)
    return seen


def reachable(base: str, timeout: float = 4.0) -> tuple[bool, str]:
    p = urllib.parse.urlsplit(base)
    host = p.hostname or "localhost"
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError as exc:
        return False, "cannot connect to {}:{} ({})".format(host, port, exc)
    try:
        req = urllib.request.Request(base, headers={"User-Agent": "flow-audit"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, "HTTP {} from {}".format(r.status, base)
    except urllib.error.HTTPError as exc:
        return True, "HTTP {} from {}".format(exc.code, base)
    except Exception as exc:
        return False, "connected to {}:{} but no HTTP answer ({})".format(host, port, exc)


# --------------------------------------------------------------- the audit

def audit_route(page: Page, origin: str, route: str, drive: bool,
                max_controls: int, verbose: bool) -> dict:
    url = origin.rstrip("/") + route if route.startswith("/") else route
    result: dict = {"route": route, "url": url, "findings": [], "controls": 0,
                    "flows": [], "ok": True}

    try:
        page.goto(url)
    except Exception as exc:
        result["findings"].append({"kind": "load", "sev": FAIL,
                                   "msg": "navigation failed: {}".format(exc)})
        result["ok"] = False
        return result

    result["findings"].extend(browser_findings(page.ws.events, origin))

    try:
        probe = page.js(PROBE_JS.replace("__TARGET_W__", str(page.vp["width"]))) or {}
    except Exception as exc:
        result["findings"].append({"kind": "probe", "sev": FAIL,
                                   "msg": "page probe could not run: {}".format(exc)})
        probe = {}
    for c in probe.get("checks", []):
        result["findings"].append(c)
    controls = probe.get("controls", []) or []
    result["controls"] = len(controls)
    result["title"] = (probe.get("meta", {}) or {}).get("title", "")
    result["text_len"] = (probe.get("meta", {}) or {}).get("text_len", 0)

    if drive and controls:
        result["flows"] = drive_controls(page, origin, url, controls[:max_controls], verbose)

    result["ok"] = not any(f.get("sev") == FAIL for f in result["findings"]) and \
        not any(f.get("sev") == FAIL for fl in result["flows"] for f in fl.get("findings", []))
    return result


def drive_controls(page: Page, origin: str, url: str, controls: list[dict],
                   verbose: bool) -> list[dict]:
    """Click every control, one per fresh load, and judge what happened.

    Fresh load per control is the expensive choice and the correct one: click
    control 3 after control 2 opened a modal and you are testing a state no user
    reached, and a failure there teaches nothing. It also means a control that
    navigates away cannot silently skip the rest of the list.
    """
    flows: list[dict] = []
    for idx, c in enumerate(controls):
        flow = {"sel": c["sel"], "name": c.get("name", ""), "tag": c["tag"],
                "findings": [], "effect": None}
        try:
            page.goto(url, settle_s=1.0)
            before = page.js(STATE_JS)
            mark = page.mark()

            # Typing into a field is its own flow: an input that rejects
            # keystrokes looks identical to one that works until you try.
            if c["tag"] in ("input", "textarea") and c.get("type") not in (
                    "checkbox", "radio", "submit", "button", "file", "range", "color", "image"):
                got = page.js(fill_js(c["sel"]))
                if isinstance(got, dict) and got.get("error"):
                    flow["findings"].append({"kind": "flow", "sev": FAIL,
                                             "msg": "field did not accept input: " + str(got["error"])[:200],
                                             "sel": c["sel"]})
                elif isinstance(got, dict) and not got.get("held"):
                    flow["findings"].append({
                        "kind": "flow", "sev": FAIL,
                        "msg": "field discarded what was typed into it, which is a controlled "
                               "input with no state behind it: " + (c.get("name") or c["sel"]),
                        "sel": c["sel"]})
                flow["effect"] = "typed"
            else:
                clicked = page.js(click_js(c["sel"]))
                if isinstance(clicked, dict) and clicked.get("error"):
                    flow["findings"].append({"kind": "flow", "sev": FAIL,
                                             "msg": "could not click: " + str(clicked["error"])[:200],
                                             "sel": c["sel"]})
                    flows.append(flow)
                    continue
                time.sleep(0.9)
                page.ws.pump(0.4)
                after = page.js(STATE_JS)
                effect = describe_effect(before, after)
                new_requests = len(page.since(mark, "Network.requestWillBeSent"))
                dialogs = len(page.since(mark, "Page.javascriptDialogOpening"))
                if dialogs:
                    effect = effect or "dialog"
                    try:
                        page.ws.call("Page.handleJavaScriptDialog", {"accept": True})
                    except Exception:
                        pass
                if not effect and new_requests:
                    effect = "network"
                flow["effect"] = effect
                if not effect:
                    flow["findings"].append({
                        "kind": "flow", "sev": FAIL,
                        "msg": "control does nothing when pressed: no navigation, no DOM change, "
                               "no request, no dialog: " + (c.get("name") or c["sel"]),
                        "sel": c["sel"]})

            # Scoped to after the click, so page-load errors are not charged to
            # whichever control happened to be pressed next.
            verb = "typing into" if flow["effect"] == "typed" else "pressing"
            for f in browser_findings(page.since(mark), origin):
                f = dict(f)
                f["msg"] = "after {} {}: {}".format(
                    verb, c.get("name") or c["sel"], f["msg"])
                f["sel"] = c["sel"]
                flow["findings"].append(f)
        except Exception as exc:
            flow["findings"].append({"kind": "flow", "sev": WARN,
                                     "msg": "flow could not be driven: {}".format(exc)[:200],
                                     "sel": c["sel"]})
        if verbose:
            n = sum(1 for f in flow["findings"] if f["sev"] == FAIL)
            print("      [{}/{}] {} -> {}{}".format(
                idx + 1, len(controls), (c.get("name") or c["sel"])[:40],
                flow.get("effect") or "no effect", "  {} FAIL".format(n) if n else ""),
                file=sys.stderr)
        flows.append(flow)
    return flows


def click_js(selector: str) -> str:
    s = json.dumps(selector)
    return (
        "(() => { const el = document.querySelector(" + s + ");"
        " if (!el) return { error: 'selector no longer matches after reload' };"
        " const r = el.getBoundingClientRect();"
        " if (r.width < 1 || r.height < 1) return { error: 'control has no box' };"
        " el.scrollIntoView({ block: 'center' });"
        " try { el.click(); } catch (e) { return { error: String(e) }; }"
        " return { ok: true }; })()"
    )


def fill_js(selector: str) -> str:
    s = json.dumps(selector)
    # A React controlled input ignores a plain value assignment, so the native
    # setter plus a bubbling input event is the only way to reach its state.
    return (
        "(() => { const el = document.querySelector(" + s + ");"
        " if (!el) return { error: 'selector no longer matches after reload' };"
        " const probe = el.type === 'number' ? '42' : (el.type === 'email' ? 'a@b.co' : 'flowprobe');"
        " el.focus();"
        " const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype"
        "                                                 : HTMLInputElement.prototype;"
        " const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;"
        " try { setter.call(el, probe); } catch (e) { return { error: String(e) }; }"
        " el.dispatchEvent(new Event('input', { bubbles: true }));"
        " el.dispatchEvent(new Event('change', { bubbles: true }));"
        " return { held: el.value === probe, value: String(el.value).slice(0, 40) }; })()"
    )


def describe_effect(before: object, after: object) -> str | None:
    if not isinstance(before, dict) or not isinstance(after, dict):
        return None
    if before.get("url") != after.get("url"):
        return "navigated"
    if abs((after.get("nodes") or 0) - (before.get("nodes") or 0)) >= 1:
        return "dom"
    # claude-setup#57: an attribute flip on <html> (theme toggles live there)
    # changes no body markup, so the html-length gate below cannot see it.
    if before.get("root") != after.get("root"):
        return "dom"
    if abs((after.get("html") or 0) - (before.get("html") or 0)) > 24:
        return "dom"
    if abs((after.get("text") or 0) - (before.get("text") or 0)) > 2:
        return "text"
    if before.get("focus") != after.get("focus"):
        return "focus"
    if abs((after.get("scroll") or 0) - (before.get("scroll") or 0)) > 8:
        return "scroll"
    return None


# --------------------------------------------------------------- reporting

def render(report: dict, strict: bool) -> str:
    lines: list[str] = []
    n_fail = report["totals"]["fail"]
    n_warn = report["totals"]["warn"]
    lines.append("flow audit: {}".format(report["base"]))
    lines.append("  viewports {}   routes {}   controls {}   flows driven {}".format(
        ",".join(report["viewports"]), len(report["routes"]),
        report["totals"]["controls"], report["totals"]["flows"]))
    lines.append("  {} fail   {} warn".format(n_fail, n_warn))
    lines.append("")

    for vp, routes in report["by_viewport"].items():
        for r in routes:
            fails = [f for f in all_findings(r) if f["sev"] == FAIL]
            warns = [f for f in all_findings(r) if f["sev"] == WARN]
            mark = "FAIL" if fails else ("warn" if warns else "ok  ")
            lines.append("[{}] {:<7} {}   ({} controls, {} fail, {} warn)".format(
                mark, vp, r["route"], r["controls"], len(fails), len(warns)))
            for f in fails[:12]:
                lines.append("       FAIL  {:<9} {}".format(f["kind"], f["msg"]))
                if f.get("sel"):
                    lines.append("                       at {}".format(f["sel"]))
            if len(fails) > 12:
                lines.append("       ... {} more fail findings on this route".format(len(fails) - 12))
            lines.extend(
                "       warn  {:<9} {}".format(f["kind"], f["msg"])
                for f in warns[:6])
            if len(warns) > 6:
                lines.append("       ... {} more warnings on this route".format(len(warns) - 6))
    lines.append("")
    dead = [(r["route"], fl["sel"], fl.get("name"))
            for routes in report["by_viewport"].values() for r in routes
            for fl in r.get("flows", [])
            if any("does nothing when pressed" in f["msg"] for f in fl.get("findings", []))]
    if dead:
        lines.append("dead controls, pressed and nothing happened:")
        for route, sel, name in dead[:20]:
            lines.append("  {}  {}  {}".format(route, (name or "")[:30], sel))
        lines.append("")

    verdict = "PASS" if n_fail == 0 and not (strict and n_warn) else "FAIL"
    lines.append("VERDICT: {}{}".format(
        verdict, "" if verdict == "PASS" else
        "  ({} fail{})".format(n_fail, ", strict mode counts warnings" if strict else "")))
    if verdict == "PASS" and n_warn:
        lines.append("  {} warnings did not fail the run. They are in the report and they are "
                     "real; nothing here says they are acceptable.".format(n_warn))
    return "\n".join(lines)


def all_findings(route: dict) -> list[dict]:
    out = list(route.get("findings", []))
    for fl in route.get("flows", []):
        out.extend(fl.get("findings", []))
    return out


# --------------------------------------------------------------- commands

def cmd_audit(args: argparse.Namespace) -> int:
    base = args.base.rstrip("/")
    if "://" not in base:
        base = "http://" + base
    ok, why = reachable(base)
    print("target: " + why, file=sys.stderr)
    if not ok:
        print("VERDICT: CANNOT RUN. " + why, file=sys.stderr)
        print("Start the app first. An audit that cannot reach the app must not "
              "report a pass, so this exits 2 rather than 0.", file=sys.stderr)
        return 2

    origin = "{0.scheme}://{0.netloc}".format(urllib.parse.urlsplit(base))
    viewports = ["mobile", "desktop"] if args.viewport == "both" else [args.viewport]

    routes = list(args.route or [])
    if args.spec:
        with open(args.spec, encoding="utf-8") as fh:
            spec = json.load(fh)
        routes.extend(spec.get("routes", []))
    discovered: list[str] = []

    report = {"base": base, "origin": origin, "viewports": viewports,
              "routes": [], "by_viewport": {}, "strict": bool(args.strict),
              "totals": {"fail": 0, "warn": 0, "controls": 0, "flows": 0}}

    for vp in viewports:
        page = Page(vp, verbose=args.verbose)
        try:
            if not routes:
                start = urllib.parse.urlsplit(base).path or "/"
                page.goto(base)
                discovered = [start] + [r for r in same_origin_links(page, origin) if r != start]
                routes = discovered[:args.max_routes]
                print("discovered {} route(s): {}".format(
                    len(routes), ", ".join(routes)), file=sys.stderr)
                if len(discovered) > len(routes):
                    print("note: {} more link(s) found and NOT audited because of "
                          "--max-routes {}. This run does not cover them.".format(
                              len(discovered) - len(routes), args.max_routes), file=sys.stderr)
            out = []
            for route in routes:
                if args.verbose:
                    print("  [{}] {}".format(vp, route), file=sys.stderr)
                r = audit_route(page, origin, route, drive=not args.no_drive,
                                max_controls=args.max_controls, verbose=args.verbose)
                out.append(r)
            report["by_viewport"][vp] = out
        finally:
            page.close()

    report["routes"] = routes
    for vp, out in report["by_viewport"].items():
        for r in out:
            fs = all_findings(r)
            report["totals"]["fail"] += sum(1 for f in fs if f["sev"] == FAIL)
            report["totals"]["warn"] += sum(1 for f in fs if f["sev"] == WARN)
            report["totals"]["controls"] += r["controls"]
            report["totals"]["flows"] += len(r.get("flows", []))

    text = render(report, args.strict)
    print(text)

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1)
        print("\nreport: " + args.out)

    if report["totals"]["fail"]:
        return 1
    if args.strict and report["totals"]["warn"]:
        return 1
    return 0


SELFTEST_PAGE = """<!doctype html>
<html><head><title>flow selftest</title></head><body style="margin:0">
<div style="width:1200px;background:#eee">wide block that forces horizontal scroll</div>
<button id="works" onclick="document.getElementById('o').textContent='changed'">Works</button>
<button id="dead">Dead</button>
<button id="unnamed" style="width:10px;height:10px"></button>
<input id="free" type="text">
<input id="controlled" type="text" value="fixed" oninput="this.value='fixed'">
<img src="/definitely-missing.png">
<p style="color:#bbb;background:#fff;font-size:9px">low contrast tiny text</p>
<div id="o">start</div>
<script>console.error("selftest console error"); setTimeout(() => { null.x }, 50);</script>
</body></html>
"""


def cmd_selftest(args: argparse.Namespace) -> int:
    """Prove the harness detects planted defects, then that it clears a clean page.

    A checker nobody has shown to fail is indistinguishable from a checker that
    always passes, which is the failure mode this whole tool exists to stop. So
    the selftest serves a page with nine known defects and asserts each is
    caught, and serves a clean page and asserts silence.
    """
    import http.server
    import threading

    clean = ("<!doctype html><html lang=\"en\"><head><title>clean</title>"
             "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
             "</head><body style=\"margin:0;background:#fff;color:#111;font:16px system-ui\">"
             "<h1>Clean page</h1><p>Enough visible text on this page that the render check has "
             "something real to measure, and the contrast is deliberately high.</p>"
             "<button id=\"b\" style=\"min-width:120px;min-height:48px;font-size:16px\" "
             "onclick=\"document.getElementById('t').textContent='pressed and the dom changed'\">"
             "Press me</button><div id=\"t\">not pressed yet</div>"
             "<label for=\"n\">Your name</label>"
             "<input id=\"n\" name=\"n\" style=\"font-size:16px;min-height:44px\">"
             "</body></html>")

    pages = {"/": SELFTEST_PAGE, "/clean": clean}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = pages.get(self.path)
            if body is None:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"missing")
                return
            b = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:{}".format(port)
    print("selftest server on " + base, file=sys.stderr)

    expect = [
        ("overflow", "scrolls horizontally"),
        ("head", "no viewport meta tag"),
        ("name", "no accessible name"),
        ("target", "under the 24x24"),
        ("image", "image failed to load"),
        ("contrast", "below the"),
        ("text", "too small to read"),
        ("js", "uncaught exception"),
        ("console", "selftest console error"),
        ("flow", "does nothing when pressed"),
        ("flow", "discarded what was typed"),
    ]
    rc = 0
    try:
        page = Page("mobile", verbose=args.verbose)
        try:
            bad = audit_route(page, base, "/", drive=True, max_controls=10,
                              verbose=args.verbose)
            good = audit_route(page, base, "/clean", drive=True, max_controls=10,
                              verbose=args.verbose)
        finally:
            page.close()

        found = all_findings(bad)
        print("\nplanted-defect page produced {} findings".format(len(found)))
        for kind, needle in expect:
            hit = any(f["kind"] == kind and needle in f["msg"] for f in found)
            print("  {}  {:<9} {}".format("ok  " if hit else "MISS", kind, needle))
            if not hit:
                rc = 1

        gf = [f for f in all_findings(good) if f["sev"] == FAIL]
        print("\nclean page produced {} fail-level findings".format(len(gf)))
        for f in gf:
            print("  FALSE POSITIVE  {:<9} {}".format(f["kind"], f["msg"]))
            rc = 1
    finally:
        srv.shutdown()

    print("\nVERDICT: {}".format(
        "harness detects every planted defect and clears the clean page"
        if rc == 0 else "harness is not trustworthy yet, see MISS and FALSE POSITIVE above"))
    return rc


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(prog="flow.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="audit a running web app")
    a.add_argument("base")
    a.add_argument("--route", action="append", help="explicit route; repeatable")
    a.add_argument("--spec", help="json file with a routes array")
    a.add_argument("--viewport", choices=["mobile", "desktop", "both"], default="mobile")
    a.add_argument("--max-routes", type=int, default=MAX_ROUTES_DEFAULT)
    a.add_argument("--max-controls", type=int, default=MAX_CONTROLS_PER_ROUTE)
    a.add_argument("--no-drive", action="store_true",
                   help="static checks only, do not press controls")
    a.add_argument("--strict", action="store_true", help="warnings fail the run too")
    a.add_argument("--out", help="write the json report here")
    a.add_argument("-v", "--verbose", action="store_true")
    a.set_defaults(fn=cmd_audit)

    s = sub.add_parser("selftest", help="prove the harness catches planted defects")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(fn=cmd_selftest)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
