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


def is_prose(s: str) -> bool:
    """Heuristic: does this string read like customer-facing copy rather than code or config?"""
    s = s.strip()
    if not re.search(r"[A-Za-z]{3}", s) or "://" in s and " " not in s:
        return False
    words = re.findall(r"[A-Za-z][A-Za-z'’]+", s)
    if not re.search(r"[A-Z]", s) and re.fullmatch(r"[\w\-:/.\[\]#%@$ ]+", s) and re.search(r"[-_/]", s):
        return False  # css classes, paths, slugs
    return len(words) >= 2 or bool(re.match(r"[A-Z]", s))


def json_strings(node, path=""):
    if isinstance(node, dict):
        for k in sorted(node):
            if CONFIG_KEYS.search(str(k)) and not isinstance(node[k], (dict, list)):
                continue
            yield from json_strings(node[k], f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from json_strings(v, f"{path}[{i}]")
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
        if bare and not re.search(r"[;={}()<>\[\]`'\"]|^\s*(import|export|return|const|let|if|else)\b", bare):
            found.append(bare)  # JSX text on its own line
        for text in found:
            text = strip_markup(text)
            if is_prose(text):
                yield i, text


def file_units(path: Path, display: str):
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
            for key, val in json_strings(data):
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
            units += list(file_units(f, f"{label}/{f.relative_to(root).as_posix()}"))
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
    touchpoints, findings = {}, []

    for tp in ws.touchpoints:
        status, units, nfiles = collect(ws, tp)
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
    return {"touchpoints": touchpoints, "matrix": matrix, "findings": findings}


def group_key(f: dict) -> str:
    """Findings that become one GitHub issue share a group key."""
    if f["check"] == "retired":
        return fingerprint("retired", f["message"], f["phrase"].lower())
    if f["check"] == "claim":
        return fingerprint("claim", f["rule"])
    if f["check"] == "missing":
        return fingerprint("missing", f["message"])
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
        self.matrix()
        self.messaging()
        self.findings_page(findings)
        for s in self.ws.stages:
            self.stage(s, [f for f in findings if f["stage"] == s])
        for tp in self.ws.touchpoints:
            self.touchpoint(tp, [f for f in findings if tp["id"] in f["touchpoint"].split(",")])
        self.history(findings)
        return self.files

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
            f"- {md_link('Messaging architecture', f, self.p('messaging.md'))}: why I want it, why I need it, and where each message shows up",
            f"- {md_link('All findings', f, self.p('findings.md'))}",
            f"- {md_link('History', f, self.p('history.md'))}",
            "",
            "## Blind spots",
            "",
        ]
        blind = [t for t in self.ws.touchpoints if self.r["touchpoints"][t["id"]]["status"] != "ok"]
        if blind:
            L += ["Touchpoints the audit cannot see yet. Customers can.", ""]
            L += [f"- {self.tp_link(t['id'], f)} ({self.stage_title(t['stage'])}): {self.r['touchpoints'][t['id']]['status']}" for t in blind]
        else:
            L.append("None. Every touchpoint is collected.")
        L += ["", "## Guided reviews", ""] + self.review_table(f)
        top = [x for x in findings if x["severity"] == "high"][:15]
        L += ["", "## Top findings", ""] + self.findings_table(top or findings[:15], f)
        self.files[f] = "\n".join(L) + "\n"

    def matrix(self):
        f = self.p("matrix.md")
        chans = list(self.ws.channel_ids)
        L = ["## Activation matrix", "", GENERATED]
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
        L = [f"## {self.stage_title(s)}", "", GENERATED, md_link("Back to journey", f, self.p("README.md")), "", "### Touchpoints", ""]
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
        L += ["", "### Messages detected", ""]
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
    print(f"render: wrote {len(files)} pages to {ws.out.relative_to(ws.root)}/")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="journey.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["validate", "scan", "render", "run", "issues"])
    ap.add_argument("workspace", type=Path)
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--apply", action="store_true", help="issues: actually create/update/close GitHub issues")
    a = ap.parse_args(argv)
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
