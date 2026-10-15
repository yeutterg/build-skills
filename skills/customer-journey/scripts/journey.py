#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml>=6"]
# ///
"""customer-journey: audit every customer touchpoint against your messaging architecture.

Reads a workspace of Obsidian/GitHub-compatible markdown (messaging architecture,
journey map, activation matrix, claim guardrails), collects what each touchpoint
actually says, and writes a markdown report plus GitHub issues for the gaps.

Usage:
  journey.py validate <workspace>
  journey.py scan     <workspace>
  journey.py render   <workspace> [--date YYYY-MM-DD]
  journey.py run      <workspace> [--date YYYY-MM-DD]     # validate + scan + render
  journey.py issues   <workspace> [--apply]               # dry-run unless --apply
  journey.py crawl    <workspace> --url https://example.com # inventory a site and its products
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: run with `uv run scripts/journey.py` or `pip install pyyaml`.")

TOOL = "customer-journey"
DEFAULT_STAGES = ["awareness", "education", "acquisition", "product", "onboarding", "usage", "support", "loyalty"]
SEVERITIES = ["high", "medium", "low"]
SEV_WEIGHT = {"high": 9, "medium": 3, "low": 1}
SEV_ICON = {"high": "🔴", "medium": "🟠", "low": "🟡"}
CELL = {
    "ok": "✅",  # planned and present
    "missing": "❌",  # planned, not found in any collected touchpoint
    "stale": "⚠️",  # found, but only (or also) in retired wording
    "extra": "➕",  # present but not planned for this channel
    "blind": "❔",  # planned, but no touchpoint in this channel is collected yet
    "none": "·",
}
PLANNED_MARKS = {"✓", "✔", "✅", "x", "X", "y", "yes", "●", "•", "1", "true"}


# ---------------------------------------------------------------------------
# Workspace loading


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm = yaml.safe_load(text[3:end]) or {}
    body = text[end + 4 :].lstrip("\n")
    return fm, body


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


def as_list(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()
        cfg_path = self.root / "journey.config.yaml"
        if not cfg_path.exists():
            sys.exit(f"No journey.config.yaml in {self.root}")
        self.config = yaml.safe_load(cfg_path.read_text()) or {}
        self.out = self.root / self.config.get("output", "audit")
        self.data = self.out / "data"
        self.errors: list[str] = []
        self._load_messages()
        self._load_journey()
        self._load_claims()
        self._load_activation()
        self._load_reviews()
        self._load_context()

    # -- messaging architecture
    def _load_messages(self):
        self.messages: dict[str, dict] = {}
        mdir = self.root / "messaging"
        for p in sorted(mdir.rglob("*.md")) if mdir.exists() else []:
            fm, body = split_frontmatter(p.read_text())
            if not fm.get("id"):
                continue
            mid = str(fm["id"])
            if mid in self.messages:
                self.errors.append(f"duplicate message id '{mid}' in {p}")
            fm["_path"] = p.relative_to(self.root).as_posix()
            fm.setdefault("title", mid)
            fm.setdefault("kind", "pillar")
            fm.setdefault("status", "approved")
            fm.setdefault("priority", 3)
            for key in ("approved", "signals", "retired", "products", "proof"):
                fm[key] = as_list(fm.get(key))
            self.messages[mid] = fm

    # -- journey map
    def _load_journey(self):
        fm, _ = split_frontmatter((self.root / "journey.md").read_text()) if (self.root / "journey.md").exists() else ({}, "")
        self.stages = [slug(s) for s in fm.get("stages", DEFAULT_STAGES)]
        self.channels = [str(c) for c in fm.get("channels", [])]
        self.channel_ids = {slug(c): c for c in self.channels}
        self.touchpoints: list[dict] = []
        seen = set()
        for tp in fm.get("touchpoints", []) or []:
            tp = dict(tp)
            if not tp.get("id"):
                self.errors.append(f"touchpoint without id: {tp}")
                continue
            if tp["id"] in seen:
                self.errors.append(f"duplicate touchpoint id '{tp['id']}'")
            seen.add(tp["id"])
            tp["stage"] = slug(tp.get("stage", ""))
            tp["channel"] = slug(tp.get("channel", ""))
            tp.setdefault("name", tp["id"])
            if tp["stage"] not in self.stages:
                self.errors.append(f"touchpoint '{tp['id']}' has unknown stage '{tp['stage']}'")
            if tp["channel"] not in self.channel_ids:
                self.errors.append(f"touchpoint '{tp['id']}' has unknown channel '{tp['channel']}'")
            self.touchpoints.append(tp)

    # -- claim guardrails
    def _load_claims(self):
        p = self.root / "claims.md"
        fm, _ = split_frontmatter(p.read_text()) if p.exists() else ({}, "")
        self.rules = []
        for r in fm.get("rules", []) or []:
            r = dict(r)
            try:
                r["_re"] = re.compile(r["pattern"], re.IGNORECASE)
            except (re.error, KeyError) as e:
                self.errors.append(f"claim rule {r.get('id')}: bad pattern ({e})")
                continue
            r.setdefault("severity", "medium")
            r["except_touchpoints"] = as_list(r.get("except_touchpoints"))
            r["products"] = [slug(x) for x in as_list(r.get("products"))]
            self.rules.append(r)

    # -- activation matrix (first markdown table in activation.md)
    def _load_activation(self):
        self.planned: dict[str, set[str]] = {}
        p = self.root / "activation.md"
        if not p.exists():
            return
        _, body = split_frontmatter(p.read_text())
        rows = []
        for line in body.splitlines():
            if line.strip().startswith("|"):
                rows.append([c.strip() for c in line.strip().strip("|").split("|")])
            elif rows:
                break
        if len(rows) < 2:
            return
        header = [slug(re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", h)) for h in rows[0][1:]]
        for h in header:
            if h not in self.channel_ids:
                self.errors.append(f"activation.md column '{h}' is not a channel in journey.md")
        by_path = {m["_path"]: k for k, m in self.messages.items()}
        by_title = {slug(m["title"]): k for k, m in self.messages.items()}
        for row in rows[2:]:
            cell = row[0]
            link = re.search(r"\]\(([^)]+)\)", cell)
            mid = None
            if link:
                target = os.path.normpath(link.group(1)).replace(os.sep, "/")
                mid = by_path.get(target)
            text = slug(re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cell))
            mid = mid or (text if text in self.messages else by_title.get(text))
            if not mid:
                self.errors.append(f"activation.md row '{cell}' does not match a message")
                continue
            self.planned[mid] = {header[i] for i, c in enumerate(row[1:len(header) + 1]) if c in PLANNED_MARKS}

    # -- company, products and customers (written by the interview)
    def _load_context(self):
        self.warnings: list[str] = []
        cp = self.root / "company.md"
        self.company = split_frontmatter(cp.read_text())[0] if cp.exists() else {}
        self.products: dict[str, dict] = {}
        self.customers: dict[str, dict] = {}
        ap = self.root / "assumptions.md"
        self.assumptions = [a for a in as_list(split_frontmatter(ap.read_text())[0].get("assumptions")) if isinstance(a, dict)] if ap.exists() else []
        for folder, store in (("products", self.products), ("customers", self.customers)):
            d = self.root / folder
            for p in sorted(d.glob("*.md")) if d.exists() else []:
                fm, _ = split_frontmatter(p.read_text())
                if fm.get("id"):
                    fm["_path"] = p.relative_to(self.root).as_posix()
                    store[str(fm["id"])] = fm
        if self.products:
            known = {slug(k) for k in self.products} | {slug(a) for pr in self.products.values() for a in as_list(pr.get("aliases"))}
            for mid, m in self.messages.items():
                for pr in m["products"]:
                    if slug(pr) not in known:
                        self.warnings.append(f"message '{mid}' names product '{pr}', which is not an id or alias in products/")

    # -- guided reviews (human + AI sessions, one note per touchpoint per session)
    def _load_reviews(self):
        self.reviews: list[dict] = []
        rdir = self.root / "reviews"
        tp_ids = {t["id"] for t in self.touchpoints}
        for p in sorted(rdir.rglob("*.md")) if rdir.exists() else []:
            fm, body = split_frontmatter(p.read_text())
            if not fm.get("touchpoint"):
                continue
            fm["_path"] = p.relative_to(self.root).as_posix()
            fm["date"] = str(fm.get("date", ""))
            fm["touchpoints"] = [str(t) for t in as_list(fm["touchpoint"])]
            for t in fm["touchpoints"]:
                if t not in tp_ids:
                    self.errors.append(f"{fm['_path']}: unknown touchpoint '{t}'")
            fm["findings"] = as_list(fm.get("findings"))
            self.reviews.append(fm)

    def last_review(self, tid: str) -> dict | None:
        done = [r for r in self.reviews if tid in r["touchpoints"] and r.get("status", "done") == "done"]
        return max(done, key=lambda r: r["date"]) if done else None

    # -- source roots
    def resolve_root(self, name: str | None) -> Path:
        roots = self.config.get("roots", {}) or {}
        raw = roots.get(name, name or ".")
        path = Path(os.path.expandvars(os.path.expanduser(str(raw))))
        return path if path.is_absolute() else (self.root / path)


# ---------------------------------------------------------------------------
# Collection: turn each touchpoint source into (location, text) units


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        elif tag in ("p", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "tr", "section"):
            self.parts.append("\n")
        for k, v in attrs:
            if k in ("alt", "title", "content", "aria-label") and v and not self._skip:
                self.parts.append(f"\n{v}\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_lines(markup: str) -> list[str]:
    parser = _Text()
    parser.feed(markup)
    text = "".join(parser.parts)
    return [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]


def strip_markup(s: str) -> str:
    s = re.sub(r"\{\{.*?\}\}|\{%.*?%\}", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


# JSON keys whose values are configuration, not copy (matched on the last key segment)
CONFIG_KEYS = re.compile(
    r"(^|_)(id|type|handle|src|url|link|href|image|icon|video|color|colou?r_scheme|scheme|font|layout|position|"
    r"alignment|align|size|style|width|height|ratio|padding|margin|order|block_order|class|template|variant|sku|"
    r"gid|key|namespace|status|vendor|tags|created_at|updated_at|published_at|inventory\w*|option\d*)$",
    re.IGNORECASE,
)


CUSTOMER_KEYS = re.compile(r"reviews?|ratings?", re.IGNORECASE)


def is_prose(s: str) -> bool:
    """Heuristic: does this string read like customer-facing copy rather than code or config?"""
    s = s.strip()
    if not re.search(r"[A-Za-z]{3}", s) or "://" in s and " " not in s:
        return False
    if not re.search(r"\s", s) and re.search(r"[./@_$]", s):
        return False  # identifiers, import paths, file names
    words = re.findall(r"[A-Za-z][A-Za-z'’]+", s)
    if not re.search(r"[A-Z]", s) and re.fullmatch(r"[\w\-:/.\[\]#%@$ ]+", s) and re.search(r"[-_/]", s):
        return False  # css classes, paths, slugs
    return len(words) >= 2 or bool(re.match(r"[A-Z]", s))


def json_strings(node, path="", skip: re.Pattern | None = None):
    if isinstance(node, dict):
        for k in sorted(node):
            if CONFIG_KEYS.search(str(k)) and not isinstance(node[k], (dict, list)):
                continue
            if CUSTOMER_KEYS.search(str(k)) or (skip and skip.search(str(k))):
                continue  # customer-written content, or keys the source marks as non-copy
            yield from json_strings(node[k], f"{path}.{k}" if path else str(k), skip)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from json_strings(v, f"{path}[{i}]", skip)
    elif isinstance(node, str):
        yield path, node


def _blank(m: re.Match) -> str:
    """Replace a matched block with as many newlines, so line numbers stay true."""
    return "\n" * m.group(0).count("\n")


STRING_LIT = re.compile(r"""(['"`])((?:\\.|(?!\1)[^\\\n])*)\1""")


def code_units(raw: str):
    """Copy inside JS/TS source: string literals and JSX text, never comments or identifiers."""
    raw = re.sub(r"/\*.*?\*/", _blank, raw, flags=re.S)
    for i, line in enumerate(raw.splitlines(), 1):
        line = re.sub(r"(^|\s)//.*$", "", line)
        found = [m.group(2) for m in STRING_LIT.finditer(line)]
        found += re.findall(r">([^<>{}]+)<", line)
        bare = line.strip()
        if bare and not re.search(r"[;={}()<>\[\]`'\"]|^\s*(import|export|return|const|let|if|else)\b", bare) \
                and not re.match(r"[\w$.]+\s*:", bare) and not bare.endswith(","):
            found.append(bare)  # JSX text on its own line
        for text in found:
            text = strip_markup(re.sub(r"\$\{[^}]*\}", " ", text))
            if is_prose(text):
                yield i, text


def file_units(path: Path, display: str, skip_keys: str | None = None):
    """Yield (location, text) for the customer-facing copy in one file."""
    try:
        raw = path.read_text(errors="replace")
    except OSError:
        return
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            data = json.loads(re.sub(r"^\s*/\*.*?\*/", "", raw, flags=re.S))
        except json.JSONDecodeError:
            data = None
        if data is not None:
            for key, val in json_strings(data, skip=re.compile(skip_keys) if skip_keys else None):
                text = strip_markup(val)
                if is_prose(text):
                    yield f"{display}#{key}", text
            return
    if suffix in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".vue", ".svelte"):
        for i, text in code_units(raw):
            yield f"{display}:{i}", text
        return
    if suffix in (".html", ".htm", ".liquid"):
        raw = re.sub(r"\{%-?\s*(comment|schema|javascript|stylesheet|raw)\s*-?%\}.*?\{%-?\s*end\1\s*-?%\}", _blank, raw, flags=re.S)
        raw = re.sub(r"\{%-?\s*liquid\b.*?-?%\}", _blank, raw, flags=re.S)
        raw = re.sub(r"<(script|style)\b.*?</\1>", _blank, raw, flags=re.S | re.I)
        raw = re.sub(r"<!--.*?-->", _blank, raw, flags=re.S)
        for i, line in enumerate(raw.splitlines(), 1):
            text = strip_markup(line)
            if is_prose(text):
                yield f"{display}:{i}", text
        return
    if suffix in (".md", ".mdx", ".markdown"):
        raw = re.sub(r"^```.*?^```", _blank, raw, flags=re.S | re.M)
        for i, line in enumerate(raw.splitlines(), 1):
            if re.match(r"\s*(import|export)\s", line):
                continue
            text = strip_markup(line)
            if is_prose(text):
                yield f"{display}:{i}", text
        return
    for i, line in enumerate(raw.splitlines(), 1):
        if line.strip():
            yield f"{display}:{i}", line.strip()


def collect(ws: Workspace, tp: dict) -> tuple[str, list[tuple[str, str]], int]:
    """Return (status, units, file_count). A touchpoint may list several sources."""
    if tp.get("status") == "planned":
        return "planned", [], 0  # a page that does not exist yet (e.g. in a website rewrite); briefs describe it
    sources = as_list(tp.get("source")) or [{"type": "manual"}]
    statuses, units, nfiles = [], [], 0
    for src in sources:
        st, u, n = collect_one(ws, tp, src)
        statuses.append(st)
        units += u
        nfiles += n
    if any(st == "ok" for st in statuses):
        return "ok", units, nfiles
    return statuses[0], units, nfiles


def collect_one(ws: Workspace, tp: dict, src: dict) -> tuple[str, list[tuple[str, str]], int]:
    kind = src.get("type", "files" if "glob" in src else "manual")
    if kind == "manual":
        return "not collected", [], 0
    if kind == "text":
        return "ok", [(f"{tp['id']}:inline", t) for t in as_list(src.get("text"))], 1
    if kind == "url":
        units = []
        for url in as_list(src.get("url")):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": f"{TOOL}/1.0"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
            except Exception as e:  # noqa: BLE001
                return f"error: {e}", [], 0
            units += [(f"{url}#L{i}", ln) for i, ln in enumerate(html_to_lines(body), 1) if ln]
        return "ok", units, len(as_list(src.get("url")))
    if kind == "files":
        root = ws.resolve_root(src.get("root"))
        if not root.exists():
            return f"unavailable: {src.get('root')} not found", [], 0
        files = set()
        for g in as_list(src.get("glob")):
            files.update(p for p in root.glob(g) if p.is_file())
        for g in as_list(src.get("exclude")):
            files.difference_update(root.glob(g))
        units = []
        label = src.get("root") or "."
        for f in sorted(files):
            units += list(file_units(f, f"{label}/{f.relative_to(root).as_posix()}", src.get("skip_keys")))
        if not files:
            return "empty: glob matched no files", [], 0
        if not units:
            return f"empty: no copy found in {len(files)} file{'s' * (len(files) != 1)}", [], len(files)
        return "ok", units, len(files)
    return f"error: unknown source type '{kind}'", [], 0


# ---------------------------------------------------------------------------
# Scanning


def phrase_re(phrase: str) -> re.Pattern:
    words = [re.escape(w) for w in str(phrase).split()]
    return re.compile(r"(?<![\w])" + r"[\s\-]+".join(words) + r"(?![\w])", re.IGNORECASE)


def excerpt(text: str, start: int, end: int, width: int = 70) -> str:
    a, b = max(0, start - width), min(len(text), end + width)
    s = ("…" if a else "") + text[a:start] + "**" + text[start:end] + "**" + text[end:b] + ("…" if b < len(text) else "")
    return s.replace("|", "\\|").replace("\n", " ")


def fingerprint(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:10]


def scan(ws: Workspace) -> dict:
    compiled = {
        mid: {
            "approved": [(p, phrase_re(p)) for p in m["approved"]],
            "signals": [(s, re.compile(s, re.IGNORECASE)) for s in m["signals"]],
            "retired": [(p, phrase_re(p)) for p in m["retired"]],
        }
        for mid, m in ws.messages.items()
    }
    ignored = {str(i.get("fp")) for i in ws.config.get("ignore", []) or []}
    touchpoints, findings, category = {}, [], {}

    for tp in ws.touchpoints:
        status, units, nfiles = collect(ws, tp)
        findings += trademark_findings(ws, tp, units)
        category[tp["id"]] = category_hits(ws, units) if status == "ok" else None
        hits = {mid: {"approved": 0, "signals": 0, "retired": 0} for mid in ws.messages}
        for loc, text in units:
            for mid, c in compiled.items():
                spans = []
                for _, rx in c["approved"]:
                    for mt in rx.finditer(text):
                        hits[mid]["approved"] += 1
                        spans.append(mt.span())
                for _, rx in c["signals"]:
                    hits[mid]["signals"] += len(rx.findall(text))
                for phrase, rx in c["retired"]:
                    if tp["id"] in as_list(ws.messages[mid].get("retired_except_touchpoints")):
                        continue
                    for mt in rx.finditer(text):
                        if any(a <= mt.start() and mt.end() <= b for a, b in spans):
                            continue  # retired wording nested inside approved wording
                        hits[mid]["retired"] += 1
                        findings.append(
                            {
                                "check": "retired",
                                "severity": ws.messages[mid].get("retired_severity", "medium"),
                                "message": mid,
                                "phrase": phrase,
                                "touchpoint": tp["id"],
                                "location": loc,
                                "excerpt": excerpt(text, *mt.span()),
                                "suggest": (ws.messages[mid]["approved"] or [""])[0],
                            }
                        )
            for rule in ws.rules:
                if tp["id"] in rule["except_touchpoints"]:
                    continue
                if rule["products"] and not set(rule["products"]) & {slug(x) for x in as_list(tp.get("products"))}:
                    continue  # product-scoped rule, e.g. a spec that must not appear on another product's pages
                for mt in rule["_re"].finditer(text):
                    findings.append(
                        {
                            "check": "claim",
                            "severity": rule["severity"],
                            "rule": rule["id"],
                            "touchpoint": tp["id"],
                            "location": loc,
                            "excerpt": excerpt(text, *mt.span()),
                            "suggest": rule.get("suggest", ""),
                        }
                    )
        present = sorted(m for m, h in hits.items() if h["approved"] or h["signals"])
        stale = sorted(m for m, h in hits.items() if h["retired"])
        touchpoints[tp["id"]] = {
            "status": status,
            "files": nfiles,
            "units": len(units),
            "present": present,
            "stale": stale,
            "hits": {m: h for m, h in hits.items() if any(h.values())},
        }

    # Activation matrix: planned vs observed per channel
    matrix = {}
    for mid in ws.messages:
        for ch in ws.channel_ids:
            tps = [t for t in ws.touchpoints if t["channel"] == ch]
            collected = [t for t in tps if touchpoints[t["id"]]["status"] == "ok"]
            pres = any(mid in touchpoints[t["id"]]["present"] for t in collected)
            stl = any(mid in touchpoints[t["id"]]["stale"] for t in collected)
            planned = ch in ws.planned.get(mid, set())
            if stl:
                state = "stale"
            elif planned and not collected:
                state = "blind"
            elif planned and pres:
                state = "ok"
            elif planned:
                state = "missing"
            elif pres:
                state = "extra"
            else:
                state = "none"
            matrix.setdefault(mid, {})[ch] = state
            if state == "missing" and ws.messages[mid]["status"] == "approved":
                pr = int(ws.messages[mid].get("priority", 3))
                findings.append(
                    {
                        "check": "missing",
                        "severity": "high" if pr <= 1 else "medium" if pr == 2 else "low",
                        "message": mid,
                        "channel": ch,
                        "touchpoint": ",".join(t["id"] for t in collected),
                        "location": f"channel:{ch}",
                        "excerpt": "",
                        "suggest": (ws.messages[mid]["approved"] or [""])[0],
                    }
                )

    tp_meta = {t["id"]: t for t in ws.touchpoints}
    for f in findings:
        first = tp_meta.get(f["touchpoint"].split(",")[0], {})
        f.setdefault("channel", first.get("channel", ""))
        f["stage"] = first.get("stage", "")
        f["workstream"] = first.get("workstream", "")
        f["fp"] = fingerprint(f["check"], f.get("message", f.get("rule")), f.get("phrase", ""), f["touchpoint"], f["location"], f["excerpt"])
        f["group"] = group_key(f)
    findings = [f for f in findings if f["fp"] not in ignored and f["group"] not in ignored]
    findings.sort(key=lambda f: (SEVERITIES.index(f["severity"]) if f["severity"] in SEVERITIES else 9, f["check"], f.get("message", f.get("rule", "")), f["touchpoint"], f["location"]))
    return {"touchpoints": touchpoints, "matrix": matrix, "findings": findings, "category": category}


SYMBOLS = "™®℠"


def trademark_findings(ws: "Workspace", tp: dict, units: list[tuple[str, str]]) -> list[dict]:
    """Check how each mark in company.md `trademarks` is used in one touchpoint's copy."""
    out = []
    for tm in as_list(ws.company.get("trademarks")):
        if not isinstance(tm, dict) or not tm.get("mark"):
            continue
        mark, status = str(tm["mark"]), str(tm.get("status", "unknown"))
        exact = re.compile(r"(?<![\w])" + re.escape(mark) + r"(?![\w])(\s?[" + SYMBOLS + r"])?")
        loose = re.compile(r"(?<![\w])" + r"[\s\-]?".join(re.escape(c) for c in mark.replace(" ", "")) + r"(?![\w])", re.IGNORECASE)
        seen_docs = set()
        base = {"check": "trademark", "touchpoint": tp["id"]}
        for loc, text in units:
            doc = re.split(r"[:#]", loc, 1)[0]
            for mt in exact.finditer(text):
                sym = (mt.group(1) or "").strip()
                if sym == "®" and status != "registered":
                    out.append({**base, "severity": "high", "rule": f"{mark}:registered-symbol", "title": f"{mark}® used, but the mark is {status}",
                                "detail": "Only registered marks may carry ®. Use ™ until registration.", "location": loc, "excerpt": excerpt(text, *mt.span())})
                if tm.get("usage") == "first-mention" and doc not in seen_docs and not sym and tm.get("symbol"):
                    out.append({**base, "severity": "low", "rule": f"{mark}:first-mention", "title": f"{mark} first mention without {tm['symbol']}",
                                "detail": f"Brand rule: {mark}{tm['symbol']} on first mention per page.", "location": loc, "excerpt": excerpt(text, *mt.span())})
                if tm.get("usage") == "every-mention" and not sym and tm.get("symbol"):
                    out.append({**base, "severity": "low", "rule": f"{mark}:every-mention", "title": f"{mark} without {tm['symbol']}",
                                "detail": f"Brand rule: {mark}{tm['symbol']} on every mention.", "location": loc, "excerpt": excerpt(text, *mt.span())})
                seen_docs.add(doc)
            if tm.get("check_casing"):
                for mt in loose.finditer(text):
                    before, after = text[mt.start() - 1 : mt.start()], text[mt.end() : mt.end() + 1]
                    if before and before in "./_-@#'\"" or after and after in "./_-":
                        continue  # part of a path, slug or identifier
                    if mt.group(0) != mark:
                        out.append({**base, "severity": "low", "rule": f"{mark}:casing", "title": f"{mark} written as \"{mt.group(0)}\"",
                                    "detail": f"Write the mark exactly as \"{mark}\".", "location": loc, "excerpt": excerpt(text, *mt.span())})
    return out


def category_hits(ws: "Workspace", units: list[tuple[str, str]]) -> int:
    cat = ws.company.get("category") or {}
    terms = [t for t in [cat.get("term"), *as_list(cat.get("variants"))] if t]
    if not terms:
        return 0
    rx = [phrase_re(t) for t in terms]
    return sum(len(r.findall(text)) for _, text in units for r in rx)


def group_key(f: dict) -> str:
    """Findings that become one GitHub issue share a group key."""
    if f["check"] == "retired":
        return fingerprint("retired", f["message"], f["phrase"].lower())
    if f["check"] == "claim":
        return fingerprint("claim", f["rule"])
    if f["check"] == "missing":
        return fingerprint("missing", f["message"])
    if f["check"] == "trademark":
        return fingerprint("trademark", f["rule"])
    return fingerprint(f["check"], f.get("message", ""), f.get("touchpoint", ""), f.get("title", ""))


def load_review_findings(ws: Workspace) -> list[dict]:
    """Findings agreed in guided reviews. Only the latest review of a touchpoint counts."""
    out = []
    for r in ws.reviews:
        if any(ws.last_review(t) is not r for t in r["touchpoints"]):
            continue
        for f in r["findings"]:
            f = {**f, "check": f.get("check", "review"), "review": r["_path"]}
            f.setdefault("touchpoint", ",".join(r["touchpoints"]))
            out.append(f)
    return normalize_extra(ws, out)


def load_extra(ws: Workspace) -> list[dict]:
    return load_semantic(ws) + load_review_findings(ws)


def load_semantic(ws: Workspace) -> list[dict]:
    """Findings written by the skill's judgment pass (contradictions, voice, stage fit, ...)."""
    p = ws.data / "semantic.json"
    if not p.exists():
        return []
    return normalize_extra(ws, json.loads(p.read_text()))


def normalize_extra(ws: Workspace, items: list[dict]) -> list[dict]:
    out = []
    for f in items:
        f.setdefault("severity", "medium")
        f.setdefault("touchpoint", "")
        f.setdefault("location", "")
        f.setdefault("excerpt", "")
        tp = next((t for t in ws.touchpoints if t["id"] == f["touchpoint"].split(",")[0]), {})
        f.setdefault("stage", tp.get("stage", ""))
        f.setdefault("channel", tp.get("channel", ""))
        f.setdefault("workstream", tp.get("workstream", ""))
        f["fp"] = fingerprint(f["check"], f.get("title", ""), f["touchpoint"], f["location"])
        f["group"] = group_key(f)
        out.append(f)
    return out


# ---------------------------------------------------------------------------
# Rendering (deterministic markdown: GitHub + Obsidian compatible)

GENERATED = "> [!NOTE]\n> Generated by `customer-journey`. Do not edit; change the inputs and re-run.\n"


def rel(from_file: str, to_path: str) -> str:
    return os.path.relpath(to_path, os.path.dirname(from_file) or ".").replace(os.sep, "/")


def md_link(text: str, from_file: str, to_path: str) -> str:
    return f"[{text}]({rel(from_file, to_path).replace(' ', '%20')})"


class Renderer:
    def __init__(self, ws: Workspace, result: dict, issues: dict, date: str):
        self.ws, self.r, self.issues, self.date = ws, result, issues, date
        self.out_rel = ws.out.relative_to(ws.root).as_posix()
        self.files: dict[str, str] = {}
        self.pages: dict[str, dict] = {}  # page key -> basis, for summaries written by the judgment pass
        sp = ws.data / "summaries.json"
        self.summaries = json.loads(sp.read_text()) if sp.exists() else {}
        hp = ws.data / "history.json"
        prior = [h for h in (json.loads(hp.read_text()) if hp.exists() else []) if h["date"] < date]
        self.previous = max(prior, key=lambda h: h["date"]) if prior else None

    # -- executive summaries

    def ranked_groups(self, findings: list[dict]) -> list[list[dict]]:
        groups: dict[str, list[dict]] = {}
        for x in findings:
            groups.setdefault(x["group"], []).append(x)
        return sorted(groups.values(), key=lambda g: (-max(SEV_WEIGHT.get(x["severity"], 0) for x in g), -len(g), self.group_label(g[0])))

    def group_label(self, f: dict) -> str:
        m = self.ws.messages.get(f.get("message", ""), {})
        if f["check"] == "retired":
            return f"retired wording \"{f['phrase']}\" ({m.get('title', f['message'])})"
        if f["check"] == "claim":
            return f"`{f['rule']}` claims"
        if f["check"] == "missing":
            return f"{m.get('title', f['message'])} is missing"
        return f.get("title") or f["check"]

    def where(self, g: list[dict], from_file: str, limit: int = 3) -> str:
        tids = []
        for x in g:
            for t in x["touchpoint"].split(","):
                if t and t not in tids:
                    tids.append(t)
        links = [self.tp_link(t, from_file) for t in tids[:limit]]
        return ", ".join(links) + (f" and {len(tids) - limit} more" if len(tids) > limit else "")

    def recommend(self, g: list[dict], from_file: str) -> str:
        f, n = g[0], len(g)
        locs = f"{n} location{'s' * (n != 1)}"
        issue = f" {self.issue_ref(f)}" if self.issue_ref(f) else ""
        if f["check"] == "retired":
            to = f" with \"{f['suggest']}\"" if f.get("suggest") else ""
            return f"Replace \"{f['phrase']}\"{to} ({locs}: {self.where(g, from_file)}){issue}"
        if f["check"] == "claim":
            rule = next((r for r in self.ws.rules if r["id"] == f["rule"]), {})
            how = rule.get("suggest") or rule.get("reason", "")
            return f"Remove `{f['rule']}` wording ({locs}: {self.where(g, from_file)}). {how}".rstrip() + issue
        if f["check"] == "missing":
            m = self.ws.messages.get(f["message"], {})
            chans = ", ".join(sorted({self.ws.channel_ids.get(x["channel"], x["channel"]) for x in g}))
            return f"Add {self.msg_link(f['message'], from_file)} to {chans}" + (f": \"{f['suggest']}\"" if f.get("suggest") else "") + issue
        detail = f": {f['detail']}" if f.get("detail") else ""
        return f"{f.get('title', f['check'])} ({self.where(g, from_file)}){detail}{issue}"

    def summary(self, key: str, from_file: str, findings: list[dict], facts: list[str], extra_recs: list[str] | None = None, show_where: bool = True) -> list[str]:
        """Bulleted executive summary. Uses the judgment pass's summary when it was written for exactly these findings."""
        basis = fingerprint(*sorted(x["fp"] for x in findings))
        self.pages[key] = {"basis": basis, "file": from_file, "findings": len(findings)}
        L = ["### Executive summary", ""]
        ai = self.summaries.get(key)
        if ai and ai.get("basis") == basis:
            L += ["**Key findings**", ""] + [f"- {b}" for b in ai.get("key_findings", [])]
            L += ["", "**Recommended improvements**", ""] + [f"{i}. {b}" for i, b in enumerate(ai.get("recommendations", []), 1)]
            return L + [""]
        groups = self.ranked_groups(findings)
        key_lines = list(facts)
        for g in groups[:4]:
            n, first = len(g), g[0]
            label = self.group_label(first)
            label = label[:1].upper() + label[1:]
            if first["check"] == "missing":
                chans = ", ".join(sorted({self.ws.channel_ids.get(x["channel"], x["channel"]) for x in g}))
                line = f"{label} from {chans}"
            elif show_where:
                line = f"{label}: {n} location{'s' * (n != 1)} in {self.where(g, from_file)}"
            else:
                line = f"{label}" + (f" ({n} locations)" if n > 1 else "")
            key_lines.append(f"{SEV_ICON.get(first['severity'], '')} {line}")
        recs = [self.recommend(g, from_file) for g in groups if g[0]["severity"] in ("high", "medium")][:5]
        recs += extra_recs or []
        L += ["**Key findings**", ""] + [f"- {b}" for b in key_lines]
        L += ["", "**Recommended improvements**", ""] + ([f"{i}. {b}" for i, b in enumerate(recs, 1)] or ["- Nothing urgent. Keep the cadence of guided reviews."])
        return L + [""]

    def planned_here(self, tp: dict) -> list[str]:
        """Approved messages planned for this touchpoint's channel that apply to its products."""
        tprods = {slug(x) for x in as_list(tp.get("products"))}
        out = []
        for mid, chans in self.ws.planned.items():
            m = self.ws.messages[mid]
            mprods = {slug(x) for x in m["products"]}
            if tp["channel"] in chans and m["status"] == "approved" and not (tprods and mprods and not tprods & mprods):
                out.append(mid)
        return sorted(out, key=lambda x: (int(self.ws.messages[x].get("priority", 3)), x))

    # paths relative to workspace root
    def p(self, *parts) -> str:
        return "/".join((self.out_rel,) + parts)

    def msg_link(self, mid: str, from_file: str) -> str:
        m = self.ws.messages.get(mid)
        return md_link(m["title"], from_file, m["_path"]) if m else mid

    def tp_link(self, tid: str, from_file: str) -> str:
        tp = next((t for t in self.ws.touchpoints if t["id"] == tid), None)
        return md_link(tp["name"], from_file, self.p("touchpoints", f"{tid}.md")) if tp else tid

    def issue_ref(self, f: dict) -> str:
        i = self.issues.get(f["group"])
        return f"[#{i['number']}]({i['url']})" if i else ""

    def subject(self, f: dict, from_file: str) -> str:
        if f["check"] == "claim":
            return f"rule `{f['rule']}`"
        if f.get("message"):
            return self.msg_link(f["message"], from_file)
        return f.get("title", "")

    def detail(self, f: dict) -> str:
        if f["check"] == "retired":
            return f"retired wording \"{f['phrase']}\"" + (f"; use \"{f['suggest']}\"" if f.get("suggest") else "")
        if f["check"] == "missing":
            return f"planned for {self.ws.channel_ids.get(f['channel'], f['channel'])} but not found"
        if f["check"] == "claim":
            return f.get("suggest") or "guardrail"
        return f.get("detail", "")

    def findings_table(self, findings: list[dict], from_file: str, show_tp: bool = True) -> list[str]:
        if not findings:
            return ["None."]
        head = "| | Check | Subject | " + ("Touchpoint | " if show_tp else "") + "Location | Excerpt | Note | Issue |"
        lines = [head, "|" + "---|" * (head.count("|") - 1)]
        for f in findings:
            tps = ", ".join(self.tp_link(t, from_file) for t in f["touchpoint"].split(",") if t)
            row = [SEV_ICON.get(f["severity"], ""), f["check"], self.subject(f, from_file)]
            if show_tp:
                row.append(tps)
            row += [f"`{f['location']}`" if f["location"] else "", f["excerpt"], self.detail(f).replace("|", "\\|"), self.issue_ref(f)]
            lines.append("| " + " | ".join(row) + " |")
        return lines

    def stage_title(self, s: str) -> str:
        return s.replace("-", " ").title()

    def render(self) -> dict[str, str]:
        findings = self.r["findings"]
        self.readme(findings)
        self.matrix(findings)
        self.messaging()
        self.findings_page(findings)
        for s in self.ws.stages:
            self.stage(s, [f for f in findings if f["stage"] == s])
        for tp in self.ws.touchpoints:
            self.touchpoint(tp, [f for f in findings if tp["id"] in f["touchpoint"].split(",")])
        self.history(findings)
        if self.ws.company or self.ws.products or self.ws.customers or self.ws.assumptions:
            self.context()
        return self.files

    def context(self):
        f = self.p("context.md")
        c = self.ws.company
        L = ["## Company, products and customers", "", GENERATED, "Summarized from `company.md`, `products/` and `customers/` (built in the interview).", ""]
        if c:
            L += [f"### {c.get('name', self.ws.config.get('brand', 'Company'))}", ""]
            for key, label in (("one_liner", "In one line"), ("stage", "Stage"), ("url", "Website")):
                if c.get(key):
                    L.append(f"- {label}: {c[key]}")
            omtm = c.get("one_metric") or {}
            if isinstance(omtm, dict) and omtm.get("metric"):
                L += ["", f"**The one metric that matters: {omtm['metric']}**", ""]
                for key, label in (("target", "Target"), ("stretch", "Stretch"), ("by", "By"), ("baseline", "Today"), ("why", "Why this metric")):
                    if omtm.get(key):
                        L.append(f"- {label}: {omtm[key]}")
                drivers = as_list(omtm.get("drivers"))
                if drivers:
                    L += ["", "| Driver | Target | Today |", "|---|---|---|"]
                    for d in drivers:
                        d = d if isinstance(d, dict) else {"driver": d}
                        L.append(f"| {d.get('driver', '')} | {d.get('target', '')} | {d.get('baseline', '')} |")
            goals = as_list(c.get("goals"))
            if goals:
                L += ["", "| Goal | Metric | Target | By |", "|---|---|---|---|"]
                for g in goals:
                    g = g if isinstance(g, dict) else {"goal": g}
                    L.append(f"| {g.get('goal', '')} | {g.get('metric', '')} | {g.get('target', '')} | {g.get('by', '')} |")
            cat = c.get("category") or {}
            if cat.get("term"):
                hits = self.r.get("category", {})
                using = sorted((t for t, n in hits.items() if n), key=lambda t: -hits[t])
                L += ["", f"**Category we want to own: {cat['term']}**" + (f" ({cat['status']})" if cat.get("status") else ""), ""]
                if cat.get("definition"):
                    L.append(f"- Definition: {cat['definition']}")
                L.append(f"- Used in {len(using)} of {sum(1 for n in hits.values() if n is not None)} readable touchpoints" + (": " + ", ".join(f"{self.tp_link(t, f)} ({hits[t]})" for t in using[:8]) if using else ""))
            marks = [t for t in as_list(c.get("trademarks")) if isinstance(t, dict)]
            if marks:
                L += ["", "**Trademarks**", "", "| Mark | Status | Symbol | Usage rule | Jurisdictions | Classes | Registration |", "|---|---|---|---|---|---|---|"]
                for t in marks:
                    L.append(f"| {t.get('mark', '')} | {t.get('status', 'unknown')} | {t.get('symbol', '')} | {t.get('usage', '')} | {', '.join(map(str, as_list(t.get('jurisdictions'))))} | {', '.join(map(str, as_list(t.get('classes'))))} | {t.get('registration', '')} |")
            models = [m for m in as_list(c.get("role_models")) if isinstance(m, dict) and m.get("name")]
            if models:
                L += ["", "**Who we look up to**", "", "| Company | Space | Borrow | Avoid |", "|---|---|---|---|"]
                L += [f"| {m.get('name', '')} | {m.get('space', '')} | {m.get('borrow', '')} | {m.get('avoid', '')} |" for m in models]
            alts = as_list(c.get("alternatives"))
            if alts:
                L += ["", "**What customers use instead**", "", "| Alternative | Why people choose it | Our edge |", "|---|---|---|"]
                for a in alts:
                    a = a if isinstance(a, dict) else {"name": a}
                    L.append(f"| {a.get('name', '')} | {a.get('why', '')} | {a.get('our_edge', '')} |")
            L.append("")
        if self.ws.products:
            L += ["### Products", "", "| Product | Status | Generation | Launch | Price | For | Summary |", "|---|---|---|---|---|---|---|"]
            order = {"current": 0, "upcoming": 1, "discontinued": 2}
            for pid, pr in sorted(self.ws.products.items(), key=lambda kv: (order.get(kv[1].get("status", ""), 3), kv[1].get("name", kv[0]))):
                draft = " *(draft)*" if pr.get("review") == "draft" else ""
                personas = ", ".join(md_link(self.ws.customers[x].get("name", x), f, self.ws.customers[x]["_path"]) if x in self.ws.customers else str(x) for x in as_list(pr.get("personas")))
                L.append(f"| {md_link(pr.get('name', pid), f, pr['_path'])}{draft} | {pr.get('status', '')} | {pr.get('generation', '')} | {pr.get('launch', '')} | {pr.get('price', '')} | {personas} | {str(pr.get('summary', '')).replace('|', '/')} |")
            L.append("")
        if self.ws.customers:
            L += ["### Customers", "", "| Who | Kind | Share | Top pain | Where they find us |", "|---|---|---|---|---|"]
            for cid, cu in sorted(self.ws.customers.items(), key=lambda kv: (kv[1].get("kind") != "icp", kv[0])):
                pains = as_list(cu.get("pains"))
                L.append(f"| {md_link(cu.get('name', cid), f, cu['_path'])} | {cu.get('kind', '')} | {cu.get('share', '')} | {str(pains[0]) if pains else ''} | {', '.join(map(str, as_list(cu.get('channels'))))} |")
            L.append("")
        if self.ws.assumptions:
            open_ = [a for a in self.ws.assumptions if a.get("status", "open") == "open"]
            L += ["### Assumptions", "", f"{len(open_)} open of {len(self.ws.assumptions)} recorded. Messaging that rests on an open assumption is a bet, not a fact.", "",
                  "| Assumption | Status | Evidence so far | How to test | Owner | Affects |", "|---|---|---|---|---|---|"]
            order = {"open": 0, "testing": 1, "confirmed": 2, "rejected": 3}
            for a in sorted(self.ws.assumptions, key=lambda a: (order.get(a.get("status", "open"), 9), str(a.get("claim", "")))):
                cells = [a.get("claim", ""), a.get("status", "open"), a.get("evidence", ""), a.get("test", ""), a.get("owner", ""), ", ".join(map(str, as_list(a.get("affects"))))]
                L.append("| " + " | ".join(str(x).replace("|", "/") for x in cells) + " |")
        self.files[f] = "\n".join(L) + "\n"

    def coverage(self) -> tuple[int, int]:
        cells = [st for row in self.r["matrix"].values() for st in row.values()]
        planned_seen = sum(1 for s in cells if s in ("ok", "missing", "stale"))
        ok = sum(1 for s in cells if s == "ok")
        return ok, planned_seen

    def readme(self, findings):
        f = self.p("README.md")
        brand = self.ws.config.get("brand", "")
        counts = {s: sum(1 for x in findings if x["severity"] == s) for s in SEVERITIES}
        ok, total = self.coverage()
        L = [f"## {brand} customer journey audit".replace("  ", " "), "", GENERATED, f"Last run: {self.date}", ""]
        L += [
            "| Findings | 🔴 High | 🟠 Medium | 🟡 Low | Activation coverage |",
            "|---|---|---|---|---|",
            f"| {len(findings)} | {counts['high']} | {counts['medium']} | {counts['low']} | {ok}/{total} planned cells on-message |",
            "",
        ]
        L += self.summary("README", f, findings, self.readme_facts(findings), self.readme_recs(f))
        L += [
            "## Journey",
            "",
            "```mermaid",
            "flowchart LR",
        ]
        prev = None
        for s in self.ws.stages:
            tps = [t for t in self.ws.touchpoints if t["stage"] == s]
            col = sum(1 for t in tps if self.r["touchpoints"][t["id"]]["status"] == "ok")
            sf = [x for x in findings if x["stage"] == s]
            worst = next((sev for sev in SEVERITIES if any(x["severity"] == sev for x in sf)), None)
            cls = worst or ("ok" if col else "blind")
            status = f"{col}/{len(tps)} collected<br/>{len(sf)} findings" if tps else "no touchpoints mapped"
            L.append(f'  {s.replace("-", "_")}["{self.stage_title(s)}<br/>{status}"]:::{cls}')
            if prev:
                L.append(f"  {prev} --> {s.replace('-', '_')}")
            prev = s.replace("-", "_")
        L += [
            "  classDef high fill:#fde2e1,stroke:#c0392b,color:#000",
            "  classDef medium fill:#fdebd3,stroke:#d35400,color:#000",
            "  classDef low fill:#fcf6d5,stroke:#b7950b,color:#000",
            "  classDef ok fill:#e3f4e8,stroke:#1e8449,color:#000",
            "  classDef blind fill:#eeeeee,stroke:#999999,color:#555,stroke-dasharray:4 3",
            "```",
            "",
            "Stages: " + " · ".join(md_link(self.stage_title(s), f, self.p("stages", f"{s}.md")) for s in self.ws.stages),
            "",
            "## Reports",
            "",
            f"- {md_link('Activation matrix', f, self.p('matrix.md'))}: planned vs observed messages per channel",
            *([f"- {md_link('Company, products and customers', f, self.p('context.md'))}: goals, product line, who we serve, and open assumptions"] if (self.ws.company or self.ws.products or self.ws.customers or self.ws.assumptions) else []),
            f"- {md_link('Messaging architecture', f, self.p('messaging.md'))}: why I want it, why I need it, and where each message shows up",
            f"- {md_link('All findings', f, self.p('findings.md'))}",
            f"- {md_link('History', f, self.p('history.md'))}",
            "",
            "## Blind spots",
            "",
        ]
        blind = [t for t in self.ws.touchpoints if self.r["touchpoints"][t["id"]]["status"] not in ("ok", "planned")]
        if blind:
            L += ["Touchpoints the audit cannot see yet. Customers can.", ""]
            L += [f"- {self.tp_link(t['id'], f)} ({self.stage_title(t['stage'])}): {self.r['touchpoints'][t['id']]['status']}" for t in blind]
        else:
            L.append("None. Every touchpoint is collected.")
        planned = [t for t in self.ws.touchpoints if self.r["touchpoints"][t["id"]]["status"] == "planned"]
        if planned:
            L += ["", "## Planned pages", "", "New touchpoints described by briefs; the audit reads them once they exist and get a source.", ""]
            L += [f"- {self.tp_link(t['id'], f)} ({self.stage_title(t['stage'])})" + (f", replaces {self.tp_link(t['replaces'], f)}" if t.get("replaces") else "") for t in planned]
        L += ["", "## Guided reviews", ""] + self.review_table(f)
        top = [x for x in findings if x["severity"] == "high"][:15]
        L += ["", "## Top findings", ""] + self.findings_table(top or findings[:15], f)
        self.files[f] = "\n".join(L) + "\n"

    def readme_facts(self, findings: list[dict]) -> list[str]:
        facts = []
        counts = {s: sum(1 for x in findings if x["severity"] == s) for s in SEVERITIES}
        line = f"{len(findings)} findings: {counts['high']} high, {counts['medium']} medium, {counts['low']} low"
        if self.previous:
            delta = len(findings) - self.previous["total"]
            line += f" ({'+' if delta > 0 else ''}{delta} since {self.previous['date']})"
        facts.append(line)
        ok, total = self.coverage()
        if total:
            facts.append(f"{ok} of {total} planned message placements are on-message ({round(100 * ok / total)}%)")
        by_stage = sorted(
            ((sum(SEV_WEIGHT.get(x["severity"], 0) for x in findings if x["stage"] == s), s) for s in self.ws.stages), reverse=True
        )
        worst = [self.stage_title(s) for w, s in by_stage if w][:2]
        if worst:
            facts.append(f"Weakest stages: {' and '.join(worst)}")
        blind = [t for t in self.ws.touchpoints if self.r["touchpoints"][t["id"]]["status"] not in ("ok", "planned")]
        if blind:
            facts.append(f"{len(blind)} of {len(self.ws.touchpoints)} touchpoints are blind spots the audit cannot read yet")
        cat = (self.ws.company.get("category") or {}).get("term")
        if cat:
            hits = self.r.get("category", {})
            seen = [t for t, n in hits.items() if n is not None]
            using = [t for t in seen if hits[t]]
            facts.append(f"Category term \"{cat}\" appears in {len(using)} of {len(seen)} readable touchpoints")
        omtm = self.ws.company.get("one_metric") or {}
        if isinstance(omtm, dict) and omtm.get("metric"):
            facts.insert(0, f"One metric that matters: {omtm['metric']}" + (f", target {omtm['target']}" if omtm.get("target") else "") + (f" by {omtm['by']}" if omtm.get("by") else ""))
        open_ = [a for a in self.ws.assumptions if a.get("status", "open") == "open"]
        if open_:
            n = len(open_)
            facts.append(f"{n} open assumption{'s' * (n != 1)} behind the messaging still need{'s' * (n == 1)} testing")
        return facts

    def readme_recs(self, from_file: str) -> list[str]:
        recs = []
        blind = [t for t in self.ws.touchpoints if self.r["touchpoints"][t["id"]]["status"] not in ("ok", "planned")]
        if blind:
            order = {s: i for i, s in enumerate(["acquisition", "onboarding", "awareness", "education", "support", "loyalty", "usage", "product"])}
            blind.sort(key=lambda t: (order.get(t["stage"], 9), t["name"]))
            recs.append("Make blind spots collectable, starting with " + ", ".join(self.tp_link(t["id"], from_file) for t in blind[:3]))
        never = [t for t in self.ws.touchpoints if not self.ws.last_review(t["id"]) and self.r["touchpoints"][t["id"]]["status"] == "ok"]
        if never:
            weight = lambda t: sum(SEV_WEIGHT.get(x["severity"], 0) for x in self.r["findings"] if t["id"] in x["touchpoint"].split(","))
            first = max(never, key=lambda t: (weight(t), t["name"]))
            recs.append(f"Run a guided review of {self.tp_link(first['id'], from_file)} ({len(never)} collected touchpoints have never been reviewed)")
        return recs

    def matrix(self, findings: list[dict] | None = None):
        f = self.p("matrix.md")
        chans = list(self.ws.channel_ids)
        L = ["## Activation matrix", "", GENERATED]
        cells = [(mid, c, st) for mid, row in self.r["matrix"].items() for c, st in row.items()]
        gaps = {}
        for mid, c, st in cells:
            if st in ("missing", "stale"):
                gaps.setdefault(c, []).append(mid)
        facts = [f"{self.ws.channel_ids[c]}: {len(v)} message{'s' * (len(v) != 1)} missing or in retired wording" for c, v in sorted(gaps.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:4]]
        blind = sorted({c for _, c, st in cells if st == "blind"})
        if blind:
            facts.append("Not collected yet, so unknown: " + ", ".join(self.ws.channel_ids[c] for c in blind))
        L += self.summary("matrix", f, [x for x in (findings or []) if x["check"] in ("missing", "retired")], facts)
        L += [
            "Planned (from `activation.md`) vs observed (from collected touchpoints).",
            "",
            f"{CELL['ok']} planned and present · {CELL['missing']} planned, missing · {CELL['stale']} retired wording found · "
            f"{CELL['extra']} present, not planned · {CELL['blind']} planned, channel not collected · {CELL['none']} n/a",
            "",
            "| Message | " + " | ".join(self.ws.channel_ids[c] for c in chans) + " |",
            "|---|" + "---|" * len(chans),
        ]
        order = sorted(self.ws.messages, key=lambda m: (int(self.ws.messages[m].get("priority", 3)), self.ws.messages[m]["title"].lower()))
        for mid in order:
            m = self.ws.messages[mid]
            badge = " *(pending)*" if m["status"] != "approved" else ""
            L.append(f"| {self.msg_link(mid, f)}{badge} | " + " | ".join(CELL[self.r["matrix"][mid][c]] for c in chans) + " |")
        self.files[f] = "\n".join(L) + "\n"

    def messaging(self):
        f = self.p("messaging.md")
        L = ["## Messaging architecture", "", GENERATED]
        tps = self.r["touchpoints"]
        groups: dict[str, list[str]] = {}
        for mid, m in self.ws.messages.items():
            groups.setdefault(", ".join(m["products"]) or "Company", []).append(mid)
        for g in sorted(groups, key=lambda k: (k != "Company", k)):
            L += [f"### {g}", ""]
            mids = sorted(groups[g], key=lambda x: (int(self.ws.messages[x].get("priority", 3)), x))
            grid = [x for x in mids if self.ws.messages[x].get("want") or self.ws.messages[x].get("pain")]
            if grid:
                L += ["| Message | Why I want it | What's my pain | | Painkiller | |", "|---|---|---|---|---|---|"]
                for mid in grid:
                    m = self.ws.messages[mid]
                    want, pain, pain_word, killer, killer_word = (str(m.get(k) or "") for k in ("want", "pain", "pain_word", "painkiller", "painkiller_word"))
                    cells = [want, f"**{pain_word}**" if pain_word else "", pain, killer, f"**{killer_word}**" if killer_word else ""]
                    draft = " *(draft)*" if m.get("grid_status", "approved") != "approved" else ""
                    L.append(f"| {self.msg_link(mid, f)}{draft} | " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
                L.append("")
            L += ["| Message | Kind | Status | Approved wording | Found in | Retired wording still live in |", "|---|---|---|---|---|---|"]
            for mid in mids:
                m = self.ws.messages[mid]
                found = [t for t, d in tps.items() if mid in d["present"]]
                stale = [t for t, d in tps.items() if mid in d["stale"]]
                L.append(
                    f"| {self.msg_link(mid, f)} | {m['kind']} | {m['status']} | "
                    + "<br/>".join(f"\"{a}\"" for a in m["approved"])
                    + f" | {len(found)} touchpoints | "
                    + (", ".join(self.tp_link(t, f) for t in stale) or "·")
                    + " |"
                )
            L.append("")
        self.files[f] = "\n".join(L)

    def findings_page(self, findings):
        f = self.p("findings.md")
        L = ["## All findings", "", GENERATED]
        for sev in SEVERITIES:
            sf = [x for x in findings if x["severity"] == sev]
            if sf:
                L += [f"### {SEV_ICON[sev]} {sev.title()} ({len(sf)})", ""] + self.findings_table(sf, f) + [""]
        if not findings:
            L.append("No findings.")
        self.files[f] = "\n".join(L) + "\n"

    def stage(self, s, findings):
        f = self.p("stages", f"{s}.md")
        tps = [t for t in self.ws.touchpoints if t["stage"] == s]
        L = [f"## {self.stage_title(s)}", "", GENERATED, md_link("Back to journey", f, self.p("README.md")), ""]
        col = [t for t in tps if self.r["touchpoints"][t["id"]]["status"] == "ok"]
        facts = [f"{len(col)} of {len(tps)} touchpoints collected; {len(findings)} findings"] if tps else ["No touchpoints mapped to this stage yet"]
        recs = []
        blind = [t for t in tps if t not in col]
        if blind:
            recs.append("Make collectable: " + ", ".join(self.tp_link(t["id"], f) for t in blind))
        never = [t for t in col if not self.ws.last_review(t["id"])]
        if never:
            recs.append("Review together: " + ", ".join(self.tp_link(t["id"], f) for t in never[:3]))
        L += self.summary(f"stage:{s}", f, findings, facts, recs)
        L += ["### Touchpoints", ""]
        if tps:
            L += ["| Touchpoint | Channel | Workstream | Status | Messages present | Findings |", "|---|---|---|---|---|---|"]
            for t in tps:
                d = self.r["touchpoints"][t["id"]]
                n = sum(1 for x in findings if t["id"] in x["touchpoint"].split(","))
                L.append(f"| {self.tp_link(t['id'], f)} | {self.ws.channel_ids.get(t['channel'], t['channel'])} | {t.get('workstream', '')} | {d['status']} | {len(d['present'])} | {n} |")
        else:
            L.append("No touchpoints mapped to this stage yet.")
        L += ["", "### Findings", ""] + self.findings_table(findings, f)
        self.files[f] = "\n".join(L) + "\n"

    def touchpoint(self, tp, findings):
        f = self.p("touchpoints", f"{tp['id']}.md")
        d = self.r["touchpoints"][tp["id"]]
        src_desc = "; ".join(", ".join(f"{k}: `{v}`" for k, v in src.items()) for src in as_list(tp.get("source")) or [{"type": "manual"}])
        L = [
            f"## {tp['name']}",
            "",
            GENERATED,
            f"- Stage: {md_link(self.stage_title(tp['stage']), f, self.p('stages', tp['stage'] + '.md'))}",
            f"- Channel: {self.ws.channel_ids.get(tp['channel'], tp['channel'])}",
            f"- Workstream: {tp.get('workstream', '')}",
            f"- Source: {src_desc}",
            f"- Status: {d['status']} ({d['files']} files, {d['units']} text units)",
        ]
        L.append(f"- Last guided review: {self.review_cell(tp['id'], f)}")
        if tp.get("notes"):
            L.append(f"- Notes: {tp['notes']}")
        L.append("")
        planned = self.planned_here(tp)
        facts, recs = [], []
        if d["status"] != "ok":
            facts.append(f"Not collected ({d['status']}), so the audit cannot see what customers see here")
            recs.append("Add a source (file glob, URL, or pasted text) in `journey.md`")
        else:
            here = [m for m in planned if m in d["present"]]
            gone = [m for m in planned if m not in d["present"]]
            facts.append(f"Carries {len(here)} of {len(planned)} messages planned for {self.ws.channel_ids.get(tp['channel'], tp['channel'])}")
            if gone:
                facts.append("Not here: " + ", ".join(self.msg_link(m, f) for m in gone[:6]) + (f" and {len(gone) - 6} more" if len(gone) > 6 else ""))
        if not self.ws.last_review(tp["id"]):
            recs.append("Schedule a guided review with `/customer-journey review`")
        L += self.summary(f"touchpoint:{tp['id']}", f, findings, facts, recs, show_where=False)
        L += ["### Messages detected", ""]
        if d["hits"]:
            L += ["| Message | Approved | Signals | Retired | Planned here |", "|---|---|---|---|---|"]
            for mid in sorted(d["hits"]):
                h = d["hits"][mid]
                planned = "yes" if tp["channel"] in self.ws.planned.get(mid, set()) else ""
                L.append(f"| {self.msg_link(mid, f)} | {h['approved']} | {h['signals']} | {h['retired']} | {planned} |")
        else:
            L.append("None.")
        L += ["", "### Findings", ""] + self.findings_table(findings, f, show_tp=False)
        self.files[f] = "\n".join(L) + "\n"

    def review_cell(self, tid: str, from_file: str) -> str:
        r = self.ws.last_review(tid)
        if not r:
            return "never"
        due = self.review_due(r)
        return md_link(r["date"], from_file, r["_path"]) + f" ({r.get('verdict', 'no verdict')})" + (" · due again" if due else "")

    def review_due(self, r: dict) -> bool:
        days = int(self.ws.config.get("review_every_days", 90))
        try:
            return (dt.date.fromisoformat(self.date) - dt.date.fromisoformat(r["date"])).days > days
        except ValueError:
            return True

    def review_table(self, from_file: str) -> list[str]:
        tps = self.ws.touchpoints
        reviewed = [t for t in tps if self.ws.last_review(t["id"])]
        due = [t for t in reviewed if self.review_due(self.ws.last_review(t["id"]))]
        L = [f"{len(reviewed)}/{len(tps)} touchpoints reviewed together by a person and the AI; {len(due)} due again "
             f"(every {int(self.ws.config.get('review_every_days', 90))} days). Start one with `/customer-journey review`.", ""]
        L += ["| Stage | Touchpoint | Last review | Open review findings |", "|---|---|---|---|"]
        extra = load_review_findings(self.ws)
        for t in sorted(tps, key=lambda t: (self.ws.stages.index(t["stage"]) if t["stage"] in self.ws.stages else 99, t["name"])):
            n = sum(1 for x in extra if t["id"] in x["touchpoint"].split(","))
            L.append(f"| {self.stage_title(t['stage'])} | {self.tp_link(t['id'], from_file)} | {self.review_cell(t['id'], from_file)} | {n or ''} |")
        return L

    def history(self, findings):
        hist_path = self.ws.data / "history.json"
        hist = json.loads(hist_path.read_text()) if hist_path.exists() else []
        ok, total = self.coverage()
        row = {"date": self.date, **{s: sum(1 for x in findings if x["severity"] == s) for s in SEVERITIES}, "total": len(findings), "coverage": f"{ok}/{total}"}
        hist = [h for h in hist if h["date"] != self.date] + [row]
        hist.sort(key=lambda h: h["date"])
        self.history_rows = hist
        f = self.p("history.md")
        L = ["## History", "", GENERATED, "| Date | 🔴 | 🟠 | 🟡 | Total | Coverage |", "|---|---|---|---|---|---|"]
        L += [f"| {h['date']} | {h['high']} | {h['medium']} | {h['low']} | {h['total']} | {h['coverage']} |" for h in reversed(hist)]
        self.files[f] = "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# Discovery crawl: inventory a public site and extract its products before the interview


class _PageMeta(HTMLParser):
    """Title, meta description, canonical, headings and JSON-LD from one HTML page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.description, self.og_type, self.canonical = "", "", "", ""
        self.h1, self.h2, self.ld = [], [], []
        self._tag, self._buf, self._ld, self._skip = None, [], False, 0

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            if name in ("description", "og:description") and not self.description:
                self.description = a.get("content", "")
            elif name == "og:type":
                self.og_type = a.get("content", "")
        elif tag == "link" and a.get("rel", "").lower() == "canonical":
            self.canonical = a.get("href", "")
        elif tag == "script" and "ld+json" in a.get("type", ""):
            self._ld, self._buf = True, []
        elif tag in ("script", "style", "noscript"):
            self._skip += 1
        elif tag in ("title", "h1", "h2"):
            self._tag, self._buf = tag, []

    def handle_endtag(self, tag):
        if tag == "script" and self._ld:
            self.ld.append("".join(self._buf))
            self._ld = False
        elif tag in ("script", "style", "noscript"):
            self._skip = max(0, self._skip - 1)
        elif tag == self._tag:
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if tag == "title":
                self.title = text
            elif text:
                (self.h1 if tag == "h1" else self.h2).append(text)
            self._tag = None

    def handle_data(self, data):
        if self._ld or (self._tag and not self._skip):
            self._buf.append(data)


def http_get(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": f"{TOOL}/1.0 (+https://github.com/yeutterg/build-skills)", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def sitemap_urls(base: str, limit: int) -> list[str]:
    seen, urls, queue = set(), [], [base.rstrip("/") + "/sitemap.xml"]
    while queue and len(urls) < limit:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        try:
            xml = http_get(sm)
        except Exception:  # noqa: BLE001
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)
        if "<sitemapindex" in xml:
            queue += [html.unescape(u) for u in locs]
        else:
            urls += [html.unescape(u) for u in locs if not re.search(r"\.(jpe?g|png|gif|webp|svg|pdf)(\?|$)", u, re.I)]
    return list(dict.fromkeys(urls))[:limit]


def ld_products(blocks: list[str]) -> list[dict]:
    out = []

    def walk(node):
        if isinstance(node, list):
            for n in node:
                walk(n)
        elif isinstance(node, dict):
            types = as_list(node.get("@type"))
            if any(str(t).lower() in ("product", "productgroup") for t in types):
                offers = as_list(node.get("offers"))
                offer = offers[0] if offers and isinstance(offers[0], dict) else {}
                brand = node.get("brand")
                out.append({
                    "name": node.get("name", ""),
                    "description": strip_markup(str(node.get("description", ""))),
                    "sku": node.get("sku", ""),
                    "brand": brand.get("name", "") if isinstance(brand, dict) else str(brand or ""),
                    "price": offer.get("price") or offer.get("lowPrice") or "",
                    "currency": offer.get("priceCurrency", ""),
                    "availability": str(offer.get("availability", "")).rsplit("/", 1)[-1],
                    "url": node.get("url", ""),
                })
            for v in node.values():
                if isinstance(v, (dict, list)):
                    walk(v)

    for b in blocks:
        try:
            walk(json.loads(b))
        except json.JSONDecodeError:
            continue
    return out


def shopify_products(base: str) -> list[dict]:
    """Shopify stores expose published products at /products.json. Other platforms simply return nothing."""
    out, page = [], 1
    while page <= 10:
        try:
            data = json.loads(http_get(f"{base.rstrip('/')}/products.json?limit=250&page={page}"))
        except Exception:  # noqa: BLE001
            break
        items = data.get("products", []) if isinstance(data, dict) else []
        if not items:
            break
        for p in items:
            prices = sorted({float(v["price"]) for v in p.get("variants", []) if v.get("price")})
            out.append({
                "handle": p.get("handle", ""),
                "name": p.get("title", ""),
                "description": strip_markup(p.get("body_html") or ""),
                "category": p.get("product_type", ""),
                "brand": p.get("vendor", ""),
                "tags": p.get("tags", []) if isinstance(p.get("tags"), list) else [t.strip() for t in str(p.get("tags", "")).split(",") if t.strip()],
                "price": (f"{prices[0]:g}" if len(prices) == 1 else f"{prices[0]:g}-{prices[-1]:g}") if prices else "",
                "variants": len(p.get("variants", [])),
                "url": f"{base.rstrip('/')}/products/{p.get('handle', '')}",
                "published_at": (p.get("published_at") or "")[:10],
            })
        page += 1
    return out


PAGE_KINDS = [
    ("product", r"/products?/"), ("collection", r"/collections?/|/shop\b|/category/"), ("blog", r"/blogs?/|/news/|/articles?/|/posts?/"),
    ("support", r"faq|help|support|contact|warranty|returns|shipping|troubleshoot"), ("about", r"about|story|mission|team|press"),
    ("legal", r"privacy|terms|polic|legal|regulatory|patent|accessibility|ccpa"), ("account", r"/account|/cart|/checkout|/login"),
]
KIND_STAGE = {"product": "education", "collection": "education", "blog": "education", "support": "support", "about": "awareness",
              "legal": "education", "account": "acquisition", "page": "education", "home": "awareness"}


def page_kind(url: str, og_type: str) -> str:
    path = urllib.parse.urlparse(url).path
    if path in ("", "/"):
        return "home"
    if og_type.lower() == "product":
        return "product"
    for kind, rx in PAGE_KINDS:
        if re.search(rx, path, re.I):
            return kind
    return "page"


def crawl(base: str, max_pages: int, delay: float = float(os.environ.get("JOURNEY_CRAWL_DELAY", "0.3"))) -> dict:
    base = base.rstrip("/")
    urls = sitemap_urls(base, max_pages) or [base + "/"]
    pages, ld_found = [], []
    for u in urls:
        try:
            body = http_get(u)
        except Exception as e:  # noqa: BLE001
            pages.append({"url": u, "error": str(e)[:120]})
            continue
        m = _PageMeta()
        m.feed(body)
        prods = ld_products(m.ld)
        for p in prods:
            p.setdefault("url", u)
            p["url"] = p["url"] or u
        ld_found += prods
        pages.append({
            "url": u, "kind": page_kind(u, m.og_type), "title": m.title, "description": m.description.strip(),
            "h1": m.h1[:2], "h2": m.h2[:6], "products": [p["name"] for p in prods],
        })
        time.sleep(delay)
    shop = shopify_products(base)
    products: dict[str, dict] = {}
    for p in shop:
        products[p["handle"]] = {**p, "source": "shopify products.json"}
    for p in ld_found:
        handle = slug(urllib.parse.urlparse(p["url"]).path.rstrip("/").rsplit("/", 1)[-1] or p["name"])
        if handle in products:
            products[handle].setdefault("sku", p.get("sku"))
            products[handle]["availability"] = p.get("availability", "")
        else:
            products[handle] = {**p, "handle": handle, "source": "schema.org JSON-LD"}
    return {"base": base, "pages": pages, "products": [products[k] for k in sorted(products)], "platform": "shopify" if shop else "unknown"}


def cmd_crawl(root: Path, url: str, max_pages: int, date: str):
    root = root.resolve()
    out = root / "discovery"
    out.mkdir(parents=True, exist_ok=True)
    print(f"crawl: {url} (up to {max_pages} pages)")
    res = crawl(url, max_pages)
    res["date"] = date
    (out / "crawl.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    ok = [p for p in res["pages"] if "error" not in p]
    kinds: dict[str, list] = {}
    for p in ok:
        kinds.setdefault(p["kind"], []).append(p)

    gen = "> [!NOTE]\n> Generated by `customer-journey crawl`. Re-crawl to refresh; the interview turns this into inputs.\n"
    L = ["## Site inventory", "", gen, f"Crawled {res['base']} on {date}: {len(ok)} pages, {len(res['pages']) - len(ok)} errors. Platform: {res['platform']}.", ""]
    L += ["| Kind | Pages | Suggested stage |", "|---|---|---|"]
    L += [f"| {k} | {len(v)} | {KIND_STAGE.get(k, '')} |" for k, v in sorted(kinds.items(), key=lambda kv: -len(kv[1]))]
    for k, v in sorted(kinds.items()):
        L += ["", f"### {k.title()} ({len(v)})", "", "| Page | Title | H1 | Meta description |", "|---|---|---|---|"]
        for p in sorted(v, key=lambda p: p["url"]):
            path = urllib.parse.urlparse(p["url"]).path or "/"
            cells = [f"[{path}]({p['url']})", p["title"], " / ".join(p["h1"]), p["description"][:160]]
            L.append("| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in cells) + " |")
    (out / "site.md").write_text("\n".join(L) + "\n")

    P = ["## Products found", "", gen, f"{len(res['products'])} products from {res['base']}.", "",
         "| Product | Price | Category | Source | Draft file |", "|---|---|---|---|---|"]
    pdir = root / "products"
    existing = {}
    for f in pdir.glob("*.md") if pdir.exists() else []:
        fm, _ = split_frontmatter(f.read_text())
        for key in [fm.get("id"), fm.get("url"), *as_list(fm.get("aliases"))]:
            if key:
                existing[str(key)] = f
    created = 0
    for p in res["products"]:
        known = existing.get(p["handle"]) or existing.get(p.get("url", ""))
        target = known or pdir / f"{p['handle']}.md"
        if not known:
            pdir.mkdir(exist_ok=True)
            fm = {"id": p["handle"], "name": p["name"], "status": "current", "review": "draft", "url": p.get("url", ""),
                  "price": str(p.get("price", "")), "category": p.get("category", ""), "aliases": [], "generation": "",
                  "personas": [], "summary": "", "source": p["source"]}
            body = f"Draft created from the {date} crawl. Confirm, merge duplicates (bundles, preorders, variants) and fill in the rest during the interview.\n\n### Description as published\n\n{p.get('description', '')[:2000]}\n"
            target.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=1000) + "---\n\n" + body)
            existing[p["handle"]] = target
            created += 1
        P.append(f"| [{p['name']}]({p.get('url', '')}) | {p.get('price', '')} | {p.get('category', '')} | {p['source']} | [{target.name}](../products/{target.name}) |")
    (out / "products.md").write_text("\n".join(P) + "\n")
    print(f"crawl: {len(ok)} pages, {len(res['products'])} products ({created} new draft product files) -> discovery/")


# ---------------------------------------------------------------------------
# GitHub issues


def gh(*args, input_text: str | None = None) -> str:
    res = subprocess.run(["gh", *args], capture_output=True, text=True, input=input_text)
    if res.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout


def issue_groups(ws: Workspace, findings: list[dict]) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    for f in findings:
        g = groups.setdefault(f["group"], {"findings": [], "first": f})
        g["findings"].append(f)
    for key, g in groups.items():
        f, n = g["first"], len(g["findings"])
        sev = min((x["severity"] for x in g["findings"]), key=lambda s: SEVERITIES.index(s) if s in SEVERITIES else 9)
        msg = ws.messages.get(f.get("message", ""), {})
        if f["check"] == "retired":
            title = f"Retired wording \"{f['phrase']}\" ({msg.get('title', '')}) in {n} location{'s' * (n != 1)}"
            why = f"`{msg.get('title')}` retired this wording. Approved: " + ", ".join(f"\"{a}\"" for a in msg.get("approved", [])) + "."
        elif f["check"] == "claim":
            rule = next((r for r in ws.rules if r["id"] == f["rule"]), {})
            title = f"Claim guardrail `{f['rule']}`: {n} location{'s' * (n != 1)}"
            why = rule.get("reason", "") + (f"\n\nSuggested: {rule['suggest']}" if rule.get("suggest") else "")
        elif f["check"] == "missing":
            chans = sorted({ws.channel_ids.get(x["channel"], x["channel"]) for x in g["findings"]})
            title = f"Missing message: {msg.get('title', f['message'])} not on {', '.join(chans)}"
            why = "The activation matrix plans this message here, but no collected touchpoint carries it. Approved: " + ", ".join(f"\"{a}\"" for a in msg.get("approved", [])) + "."
        else:
            title = f.get("title") or f"{f['check']}: {f['touchpoint']}"
            why = f.get("detail", "")
        rows = "\n".join(
            f"- [ ] `{x['location']}` ({x['touchpoint']}): {x['excerpt']}" if x["excerpt"] else f"- [ ] `{x['location']}` ({x['touchpoint']})"
            for x in g["findings"][:60]
        )
        if n > 60:
            rows += f"\n- …and {n - 60} more (see the audit report)"
        body = (
            f"**Severity:** {sev} · **Check:** {f['check']} · **Stage:** {f.get('stage', '')} · **Workstream:** {f.get('workstream', '')}\n\n"
            f"{why}\n\n### Locations\n\n{rows}\n\n"
            f"<sub>Opened by `{TOOL}`. Closes automatically when a later audit no longer finds it. "
            f"To accept it, close as *not planned* or add the key to `ignore` in journey.config.yaml.</sub>\n"
            f"<!-- {TOOL}:{key} -->"
        )
        g.update(title=title[:250], body=body, severity=sev, workstream=f.get("workstream", ""))
    return groups


def sync_issues(ws: Workspace, findings: list[dict], apply: bool, date: str) -> dict:
    cfg = ws.config.get("github") or {}
    repo = cfg.get("repo")
    if not repo:
        sys.exit("journey.config.yaml needs github.repo to sync issues")
    label = cfg.get("label", TOOL)
    groups = issue_groups(ws, findings)
    existing = json.loads(gh("issue", "list", "-R", repo, "--label", label, "--state", "all", "--limit", "1000", "--json", "number,state,stateReason,title,body,url"))
    by_key = {}
    for i in existing:
        m = re.search(rf"<!-- {TOOL}:([0-9a-f]+) -->", i["body"] or "")
        if m:
            by_key.setdefault(m.group(1), i)
    plan, record = [], {}
    for key, g in sorted(groups.items(), key=lambda kv: (SEVERITIES.index(kv[1]["severity"]), kv[1]["title"])):
        cur = by_key.get(key)
        if not cur:
            plan.append(("create", key, g, None))
        elif cur["state"] == "OPEN":
            plan.append(("update" if (cur["title"], cur["body"]) != (g["title"], g["body"]) else "keep", key, g, cur))
        elif cur.get("stateReason") == "NOT_PLANNED":
            plan.append(("skip (closed as not planned)", key, g, cur))
        else:
            plan.append(("reopen", key, g, cur))
    for key, cur in by_key.items():
        if key not in groups and cur["state"] == "OPEN":
            plan.append(("close", key, None, cur))

    for action, key, g, cur in plan:
        print(f"{action:8} {('#' + str(cur['number'])) if cur else '':6} {g['title'] if g else cur['title']}")
    if not apply:
        print(f"\nDry run: {sum(1 for p in plan if p[0] == 'create')} to create, "
              f"{sum(1 for p in plan if p[0] in ('update', 'reopen'))} to update/reopen, {sum(1 for p in plan if p[0] == 'close')} to close. Re-run with --apply.")
        return {}

    gh("label", "create", label, "-R", repo, "--color", "5319e7", "--description", "Opened by the customer-journey audit", "--force")
    project = cfg.get("project")
    fields = None
    if project:
        pv = json.loads(gh("project", "view", str(project["number"]), "--owner", project["owner"], "--format", "json"))
        fl = json.loads(gh("project", "field-list", str(project["number"]), "--owner", project["owner"], "--format", "json"))
        fields = {"project_id": pv["id"], "fields": {fld["name"]: fld for fld in fl["fields"]}}

    def set_select(item_id: str, field: str, value: str):
        if not fields or not value:
            return
        fld = fields["fields"].get(field)
        opt = next((o for o in (fld or {}).get("options", []) if o["name"].lower() == value.lower()), None)
        if fld and opt:
            gh("project", "item-edit", "--id", item_id, "--project-id", fields["project_id"], "--field-id", fld["id"], "--single-select-option-id", opt["id"])

    for action, key, g, cur in plan:
        if action == "create":
            url = gh("issue", "create", "-R", repo, "--title", g["title"], "--label", label, "--body-file", "-", input_text=g["body"]).strip()
            cur = {"number": int(url.rstrip("/").split("/")[-1]), "url": url, "state": "OPEN"}
            if project:
                item = json.loads(gh("project", "item-add", str(project["number"]), "--owner", project["owner"], "--url", url, "--format", "json"))
                set_select(item["id"], "Status", project.get("status", "Inbox"))
                set_select(item["id"], "Workstream", g["workstream"])
                set_select(item["id"], "Priority", {"high": "P1", "medium": "P2", "low": "P3"}.get(g["severity"], ""))
        elif action == "update":
            gh("issue", "edit", str(cur["number"]), "-R", repo, "--title", g["title"], "--body-file", "-", input_text=g["body"])
        elif action == "reopen":
            gh("issue", "reopen", str(cur["number"]), "-R", repo, "--comment", f"Regression: the {date} audit found this again.")
            gh("issue", "edit", str(cur["number"]), "-R", repo, "--title", g["title"], "--body-file", "-", input_text=g["body"])
        elif action == "close":
            gh("issue", "close", str(cur["number"]), "-R", repo, "--reason", "completed", "--comment", f"Resolved: the {date} audit no longer finds this.")
            continue
        if g and cur:
            record[key] = {"number": cur["number"], "url": cur["url"]}
    return record


# ---------------------------------------------------------------------------
# CLI


def write_files(ws: Workspace, files: dict[str, str]):
    for relpath, content in files.items():
        p = ws.root / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def cmd_validate(ws: Workspace) -> bool:
    for e in ws.errors:
        print(f"error: {e}")
    for w in ws.warnings:
        print(f"warning: {w}")
    print(f"{len(ws.messages)} messages, {len(ws.touchpoints)} touchpoints, {len(ws.channels)} channels, {len(ws.rules)} claim rules, "
          f"{len(ws.planned)} activation rows: {'OK' if not ws.errors else f'{len(ws.errors)} errors'}")
    return not ws.errors


def cmd_scan(ws: Workspace) -> dict:
    result = scan(ws)
    ws.data.mkdir(parents=True, exist_ok=True)
    (ws.data / "scan.json").write_text(json.dumps(result, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"scan: {len(result['findings'])} findings across {len(result['touchpoints'])} touchpoints")
    return result


def cmd_render(ws: Workspace, date: str):
    result = json.loads((ws.data / "scan.json").read_text())
    result["findings"] = result["findings"] + load_extra(ws)
    issues_path = ws.data / "issues.json"
    issues = json.loads(issues_path.read_text()) if issues_path.exists() else {}
    r = Renderer(ws, result, issues, date)
    files = r.render()
    # remove stale generated pages (renamed stages/touchpoints)
    for sub in ("stages", "touchpoints"):
        d = ws.out / sub
        if d.exists():
            for old in d.glob("*.md"):
                if old.relative_to(ws.root).as_posix() not in files:
                    old.unlink()
    write_files(ws, files)
    (ws.data / "history.json").write_text(json.dumps(r.history_rows, indent=1) + "\n")
    (ws.data / "pages.json").write_text(json.dumps(r.pages, indent=1, sort_keys=True) + "\n")
    print(f"render: wrote {len(files)} pages to {ws.out.relative_to(ws.root)}/")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="journey.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["validate", "scan", "render", "run", "issues", "crawl"])
    ap.add_argument("workspace", type=Path)
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--apply", action="store_true", help="issues: actually create/update/close GitHub issues")
    ap.add_argument("--url", help="crawl: site to inventory (default: url in company.md)")
    ap.add_argument("--max-pages", type=int, default=150, help="crawl: page limit")
    a = ap.parse_args(argv)
    if a.command == "crawl":
        url = a.url
        if not url and (a.workspace / "company.md").exists():
            url = split_frontmatter((a.workspace / "company.md").read_text())[0].get("url")
        if not url:
            sys.exit("crawl needs --url (or url: in company.md)")
        cmd_crawl(a.workspace, url, a.max_pages, a.date)
        return
    ws = Workspace(a.workspace)
    if a.command == "validate":
        sys.exit(0 if cmd_validate(ws) else 1)
    if a.command in ("scan", "run"):
        if not cmd_validate(ws):
            sys.exit(1)
        cmd_scan(ws)
    if a.command in ("render", "run"):
        cmd_render(ws, a.date)
    if a.command == "issues":
        result = json.loads((ws.data / "scan.json").read_text())
        record = sync_issues(ws, result["findings"] + load_extra(ws), a.apply, a.date)
        if a.apply:
            (ws.data / "issues.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
            cmd_render(ws, a.date)


if __name__ == "__main__":
    main()
