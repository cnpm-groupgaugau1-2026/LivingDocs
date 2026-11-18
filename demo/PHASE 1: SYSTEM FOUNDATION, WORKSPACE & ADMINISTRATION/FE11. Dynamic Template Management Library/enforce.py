import re

from .catalog import MERMAID_KEYWORDS

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*([\w+\-]*)")
LIQUID_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)
PLACEHOLDER_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


def _heading_pattern(title):
    if "{{" not in title and "{%" not in title:
        return None
    pieces = LIQUID_RE.split(title)
    regex = r"\s*".join(re.escape(p.strip()) if p.strip() else "" for p in pieces)
    parts = []
    for i, p in enumerate(pieces):
        if i:
            parts.append(r".+?")
        parts.append(re.escape(p))
    return "^" + "".join(parts) + "$"


def derive_structure(body):
    headings, fences, tables = [], [], []
    in_for = in_if = 0
    fence = None
    for line_no, line in enumerate(body.split("\n"), 1):
        fm = FENCE_RE.match(line)
        if fence is None and fm:
            fence = fm.group(1)[0]
            lang = fm.group(2)
            if lang:
                fences.append({"language": lang, "optional": bool(in_for or in_if), "line": line_no})
        elif fence is not None:
            if fm and fm.group(1)[0] == fence and not fm.group(2):
                fence = None
            continue
        if fence is not None:
            continue
        for tag in re.findall(r"\{%-?\s*(\w+)", line):
            if tag == "for":
                in_for += 1
            elif tag == "endfor":
                in_for = max(in_for - 1, 0)
            elif tag in ("if", "unless"):
                in_if += 1
            elif tag in ("endif", "endunless"):
                in_if = max(in_if - 1, 0)
        if TABLE_SEP_RE.match(LIQUID_RE.sub("", line)) and "-" in line:
            tables.append({"optional": bool(in_for or in_if), "line": line_no})
        clean = LIQUID_RE.sub(lambda m: m.group(0) if m.group(0).startswith("{{") else "", line)
        m = HEADING_RE.match(clean)
        if m:
            title = m.group(2).strip()
            headings.append({
                "level": len(m.group(1)),
                "title": title,
                "pattern": _heading_pattern(title),
                "optional": bool(in_for or in_if),
                "repeatable": bool(in_for),
                "line": line_no,
            })
    return {"headings": headings, "code_blocks": fences, "tables": tables}


def parse_output(text):
    headings, blocks = [], []
    fence, cur = None, None
    for line_no, line in enumerate(text.split("\n"), 1):
        fm = FENCE_RE.match(line)
        if fence is None:
            if fm:
                fence = fm.group(1)[0]
                cur = {"language": fm.group(2), "line": line_no, "lines": []}
                continue
            m = HEADING_RE.match(line)
            if m:
                headings.append({"level": len(m.group(1)), "title": m.group(2).strip(), "line": line_no})
        else:
            if fm and fm.group(1)[0] == fence and not fm.group(2):
                blocks.append(cur)
                fence, cur = None, None
            else:
                cur["lines"].append(line)
    unbalanced = fence is not None
    return headings, blocks, unbalanced


def _matches(t, h):
    if t["level"] != h["level"]:
        return False
    if t["pattern"]:
        return re.match(t["pattern"], h["title"], re.I) is not None
    return t["title"].strip().lower() == h["title"].strip().lower()


def check(output, structure, constraints):
    violations = []

    def add(code, message, line=None):
        violations.append({"code": code, "message": message, "line": line})

    if not output or not output.strip():
        add("EMPTY_OUTPUT", "The generated document is empty.")
        return violations
    constraints = constraints or {}
    headings, blocks, unbalanced = parse_output(output)
    if unbalanced:
        add("UNBALANCED_CODE_FENCE", "A fenced code block is not closed.")
    for m in PLACEHOLDER_RE.finditer(output):
        add("UNRESOLVED_PLACEHOLDER", f"Unresolved template placeholder {m.group(0)[:40]!r}.", output[: m.start()].count("\n") + 1)
    template_headings = structure["headings"]
    last_idx = -1
    matched = set()
    last_matched_level = 0
    max_level = max([t["level"] for t in template_headings], default=0)
    for h in headings:
        candidates = [i for i, t in enumerate(template_headings) if _matches(t, h)]
        if not candidates:
            nested = last_matched_level and h["level"] > last_matched_level
            if not constraints.get("allow_extra_sections", False) and not nested and h["level"] <= max_level:
                add("EXTRA_SECTION", f"Section '{h['title']}' is not part of the template.", h["line"])
            continue
        placed = None
        for i in candidates:
            if i > last_idx or (i == last_idx and template_headings[i]["repeatable"]):
                placed = i
                break
        if placed is None:
            add("SECTION_ORDER", f"Section '{h['title']}' is duplicated or out of order.", h["line"])
            placed = candidates[-1]
        last_idx = max(last_idx, placed)
        matched.add(placed)
        last_matched_level = h["level"]
    for i, t in enumerate(template_headings):
        if not t["optional"] and i not in matched:
            add("MISSING_SECTION", f"Required section '{t['title']}' is missing.", None)
    langs = {b["language"].lower() for b in blocks}
    for cb in structure["code_blocks"]:
        if not cb["optional"] and cb["language"].lower() not in langs:
            add("MISSING_CODE_BLOCK", f"A '{cb['language']}' code block is required.")
    for b in blocks:
        if b["language"].lower() == "mermaid":
            first = next((l.strip() for l in b["lines"] if l.strip()), "")
            if not any(first.startswith(k) for k in MERMAID_KEYWORDS):
                add("INVALID_MERMAID", "Mermaid block does not start with a valid diagram type.", b["line"])
    if any(not t["optional"] for t in structure["tables"]):
        if not any(TABLE_SEP_RE.match(l) and "-" in l for l in output.split("\n")):
            add("MISSING_TABLE", "A Markdown table is required.")
    max_chars = constraints.get("max_chars")
    if isinstance(max_chars, int) and len(output) > max_chars:
        add("TOO_LONG", f"Document has {len(output)} characters; the limit is {max_chars}.")
    lowered = output.lower()
    for phrase in constraints.get("forbidden_phrases", []) or []:
        idx = lowered.find(phrase.lower())
        if idx >= 0:
            add("FORBIDDEN_PHRASE", f"Forbidden phrase '{phrase}' found.", output[:idx].count("\n") + 1)
    return violations
