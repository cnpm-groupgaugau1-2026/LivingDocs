import re
from dataclasses import dataclass, field

from .catalog import AST_VARIABLES

MAX_ITERATIONS = 10000
MAX_OUTPUT = 500000
MAX_DEPTH = 20
FILTERS = ("upcase", "downcase", "capitalize", "strip", "default", "join", "size", "first", "last",
           "truncate", "replace", "append", "prepend", "sort", "reverse", "escape")
KNOWN_TAGS = ("if", "elsif", "else", "endif", "unless", "endunless", "for", "endfor", "assign", "comment", "endcomment")

TOKEN_RE = re.compile(r"(\{%-?.*?-?%\})|(\{\{-?.*?-?\}\})", re.S)
EXPR_TOKEN = re.compile(
    r"""\s*(?:(?P<str>"[^"]*"|'[^']*')|(?P<num>-?\d+(?:\.\d+)?)|(?P<op>==|!=|>=|<=|>|<)"""
    r"""|(?P<word>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*|\[\d+\])*)|(?P<bad>\S))"""
)
PATH_PART = re.compile(r"[A-Za-z_]\w*|\[(\d+)\]")


class LiquidError(Exception):
    def __init__(self, message, line):
        super().__init__(message)
        self.message = message
        self.line = line


@dataclass
class Text:
    value: str


@dataclass
class Output:
    expr: tuple
    filters: list
    line: int


@dataclass
class Assign:
    name: str
    expr: tuple
    filters: list
    line: int


@dataclass
class For:
    var: str
    source: tuple
    body: list
    line: int


@dataclass
class If:
    branches: list
    otherwise: list
    line: int
    negate: bool = False


def _tokenize_expr(s, line):
    tokens, pos = [], 0
    s = s.strip()
    while pos < len(s):
        m = EXPR_TOKEN.match(s, pos)
        if not m:
            break
        pos = m.end()
        kind = m.lastgroup
        if kind == "bad":
            raise LiquidError(f"Unexpected character '{m.group('bad')}' in expression", line)
        val = m.group(kind)
        if kind == "str":
            tokens.append(("lit", val[1:-1]))
        elif kind == "num":
            tokens.append(("lit", float(val) if "." in val else int(val)))
        elif kind == "op":
            tokens.append(("op", val))
        else:
            if val in ("true", "false", "nil"):
                tokens.append(("lit", {"true": True, "false": False, "nil": None}[val]))
            elif val in ("and", "or", "contains"):
                tokens.append(("kw", val))
            else:
                tokens.append(("var", val))
    return tokens


def _split_pipes(s):
    parts, cur, quote = [], "", None
    for ch in s:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            cur += ch
        elif ch == "|":
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts]


def _split_commas(s):
    parts, cur, quote = [], "", None
    for ch in s:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            cur += ch
        elif ch == ",":
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts]


def _operand(tokens, line):
    if len(tokens) != 1 or tokens[0][0] not in ("lit", "var"):
        raise LiquidError("Invalid expression", line)
    return tokens[0]


def parse_value(text, line):
    pieces = _split_pipes(text)
    if not pieces[0]:
        raise LiquidError("Empty expression", line)
    expr = _operand(_tokenize_expr(pieces[0], line), line)
    filters = []
    for f in pieces[1:]:
        name, _, args = f.partition(":")
        name = name.strip()
        if name not in FILTERS:
            raise LiquidError(f"Unknown filter '{name}'", line)
        arg_list = []
        if args.strip():
            for a in _split_commas(args):
                arg_list.append(_operand(_tokenize_expr(a, line), line))
        filters.append((name, arg_list))
    return expr, filters


def parse_condition(text, line):
    tokens = _tokenize_expr(text, line)
    if not tokens:
        raise LiquidError("Empty condition", line)

    def clause(toks):
        if len(toks) == 1 and toks[0][0] in ("lit", "var"):
            return ("truthy", toks[0])
        if len(toks) == 3 and toks[0][0] in ("lit", "var") and toks[2][0] in ("lit", "var") and (
            toks[1][0] == "op" or toks[1] == ("kw", "contains")
        ):
            return ("cmp", toks[1][1], toks[0], toks[2])
        raise LiquidError("Invalid condition", line)

    def split(toks, word):
        groups, cur = [], []
        for t in toks:
            if t == ("kw", word):
                groups.append(cur)
                cur = []
            else:
                cur.append(t)
        groups.append(cur)
        return groups

    ors = []
    for og in split(tokens, "or"):
        ands = [clause(g) for g in split(og, "and")]
        ors.append(ands)
    return ors


def _lex(source):
    out, pos, line = [], 0, 1
    for m in TOKEN_RE.finditer(source):
        if m.start() > pos:
            chunk = source[pos:m.start()]
            out.append(("text", chunk, line))
            line += chunk.count("\n")
        raw = m.group(0)
        kind = "tag" if raw.startswith("{%") else "out"
        inner = raw[2:-2]
        strip_left = inner.startswith("-")
        strip_right = inner.endswith("-")
        inner = inner.strip("-").strip()
        if strip_left and out and out[-1][0] == "text":
            out[-1] = ("text", out[-1][1].rstrip(), out[-1][2])
        out.append((kind, inner, line, strip_right))
        line += raw.count("\n")
        pos = m.end()
    if pos < len(source):
        out.append(("text", source[pos:], line))
    cleaned = []
    skip_left = False
    for t in out:
        if t[0] == "text":
            cleaned.append(("text", t[1].lstrip() if skip_left else t[1], t[2]))
            skip_left = False
        else:
            skip_left = t[3]
            cleaned.append(t[:3])
    return cleaned


def parse(source):
    tokens = _lex(source)
    errors = []
    root = []
    stack = [("root", root, None)]

    def top_body():
        return stack[-1][1]

    for tok in tokens:
        kind, value, line = tok
        if kind == "text":
            if "{{" in value or "{%" in value:
                bad = "{{" if "{{" in value else "{%"
                errors.append((("Unclosed output tag" if bad == "{{" else "Unclosed tag") + " (missing closing delimiter)", line + value[: value.index(bad)].count("\n")))
            top_body().append(Text(value))
            continue
        if kind == "out":
            try:
                expr, filters = parse_value(value, line)
                top_body().append(Output(expr, filters, line))
            except LiquidError as e:
                errors.append((e.message, e.line))
            continue
        name = value.split(None, 1)[0] if value else ""
        rest = value[len(name):].strip()
        if name not in KNOWN_TAGS:
            errors.append((f"Unknown tag '{name}'" if name else "Empty tag", line))
            continue
        try:
            if name == "comment":
                stack.append(("comment", [], line))
            elif name == "endcomment":
                if stack[-1][0] != "comment":
                    raise LiquidError("Unexpected endcomment", line)
                stack.pop()
            elif stack[-1][0] == "comment":
                continue
            elif name == "assign":
                m = re.match(r"^([A-Za-z_]\w*)\s*=\s*(.+)$", rest, re.S)
                if not m:
                    raise LiquidError("Malformed assign tag", line)
                expr, filters = parse_value(m.group(2), line)
                top_body().append(Assign(m.group(1), expr, filters, line))
            elif name == "for":
                m = re.match(r"^([A-Za-z_]\w*)\s+in\s+(.+)$", rest)
                if not m:
                    raise LiquidError("Malformed for tag. Expected: for item in collection", line)
                src = _operand(_tokenize_expr(m.group(2), line), line)
                node = For(m.group(1), src, [], line)
                top_body().append(node)
                if len(stack) >= MAX_DEPTH:
                    raise LiquidError("Template nesting is too deep", line)
                stack.append(("for", node.body, node))
            elif name in ("if", "unless"):
                cond = parse_condition(rest, line)
                node = If([(cond, [])], [], line, negate=(name == "unless"))
                top_body().append(node)
                if len(stack) >= MAX_DEPTH:
                    raise LiquidError("Template nesting is too deep", line)
                stack.append((name, node.branches[0][1], node))
            elif name in ("elsif", "else"):
                kind_top = stack[-1][0]
                if kind_top not in ("if", "unless", "else", "elsif"):
                    raise LiquidError(f"Unexpected {name}", line)
                owner = stack[-1][2]
                if name == "elsif":
                    if owner.negate:
                        raise LiquidError("elsif is not allowed in unless", line)
                    cond = parse_condition(rest, line)
                    stack.pop()
                    owner.branches.append((cond, []))
                    stack.append(("elsif", owner.branches[-1][1], owner))
                else:
                    stack.pop()
                    stack.append(("else", owner.otherwise, owner))
            elif name in ("endif", "endunless", "endfor"):
                expected = {"endif": ("if", "elsif", "else"), "endunless": ("unless", "else"), "endfor": ("for",)}[name]
                if stack[-1][0] not in expected:
                    raise LiquidError(f"Unexpected {name}", line)
                stack.pop()
        except LiquidError as e:
            errors.append((e.message, e.line))
    while len(stack) > 1:
        kind_open, _, node = stack.pop()
        if kind_open == "comment":
            errors.append(("Unclosed comment tag", node))
        else:
            errors.append((f"Unclosed {node_name(kind_open)} tag", node.line))
    return root, errors


def node_name(kind):
    return {"elsif": "if", "else": "if", "unless": "unless"}.get(kind, kind)


def walk_variables(nodes, scope, used, problems, allowed):
    def check(operand, line):
        if operand[0] != "var":
            return
        root = re.match(r"[A-Za-z_]\w*", operand[1]).group(0)
        if root in scope or root == "forloop":
            return
        if root in allowed:
            used.add(root)
        else:
            problems.append((f"Unknown variable '{root}'. It is not an available AST binding.", line))

    for n in nodes:
        if isinstance(n, Output):
            check(n.expr, n.line)
            for _, args in n.filters:
                for a in args:
                    check(a, n.line)
        elif isinstance(n, Assign):
            check(n.expr, n.line)
            scope.add(n.name)
        elif isinstance(n, For):
            check(n.source, n.line)
            walk_variables(n.body, scope | {n.var}, used, problems, allowed)
        elif isinstance(n, If):
            for cond, body in n.branches:
                for ands in cond:
                    for c in ands:
                        if c[0] == "truthy":
                            check(c[1], n.line)
                        else:
                            check(c[2], n.line)
                            check(c[3], n.line)
                walk_variables(body, set(scope), used, problems, allowed)
            walk_variables(n.otherwise, set(scope), used, problems, allowed)


def analyze(source, allowed=None):
    allowed = set(AST_VARIABLES) if allowed is None else set(allowed)
    nodes, errors = parse(source)
    used, problems = set(), []
    walk_variables(nodes, set(), used, problems, allowed)
    all_errors = sorted(errors + problems, key=lambda e: e[1])
    return nodes, [{"line": l, "message": m} for m, l in all_errors], sorted(used)


def resolve(path, ctx):
    parts = [p for p in re.findall(r"[A-Za-z_]\w*|\[\d+\]", path)]
    cur = ctx
    for p in parts:
        if p.startswith("["):
            idx = int(p[1:-1])
            if isinstance(cur, list) and 0 <= idx < len(cur):
                cur = cur[idx]
            else:
                return None
        elif isinstance(cur, dict) and p in cur:
            cur = cur[p]
        elif p == "size" and isinstance(cur, (list, dict, str)):
            cur = len(cur)
        elif p == "first" and isinstance(cur, list):
            cur = cur[0] if cur else None
        elif p == "last" and isinstance(cur, list):
            cur = cur[-1] if cur else None
        else:
            return None
    return cur


def truthy(v):
    return not (v is None or v is False or v == "" or v == [] or v == {})


def to_str(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    if isinstance(v, list):
        return "".join(to_str(x) for x in v)
    return str(v)


def apply_filter(name, value, args):
    a = [x for x in args]
    if name == "upcase":
        return to_str(value).upper()
    if name == "downcase":
        return to_str(value).lower()
    if name == "capitalize":
        s = to_str(value)
        return s[:1].upper() + s[1:].lower()
    if name == "strip":
        return to_str(value).strip()
    if name == "default":
        return value if truthy(value) else (a[0] if a else "")
    if name == "join":
        sep = to_str(a[0]) if a else " "
        return sep.join(to_str(x) for x in (value if isinstance(value, list) else [value]))
    if name == "size":
        return len(value) if isinstance(value, (list, dict, str)) else 0
    if name == "first":
        return value[0] if isinstance(value, list) and value else None
    if name == "last":
        return value[-1] if isinstance(value, list) and value else None
    if name == "truncate":
        n = int(a[0]) if a and isinstance(a[0], (int, float)) else 50
        s = to_str(value)
        return s if len(s) <= n else s[: max(n - 3, 0)] + "..."
    if name == "replace":
        return to_str(value).replace(to_str(a[0]), to_str(a[1])) if len(a) >= 2 else to_str(value)
    if name == "append":
        return to_str(value) + (to_str(a[0]) if a else "")
    if name == "prepend":
        return (to_str(a[0]) if a else "") + to_str(value)
    if name == "sort":
        return sorted(value, key=lambda x: to_str(x)) if isinstance(value, list) else value
    if name == "reverse":
        return list(reversed(value)) if isinstance(value, list) else value
    if name == "escape":
        return to_str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    return value


class Renderer:
    def __init__(self, ctx):
        self.ctx = ctx
        self.iterations = 0
        self.missing = set()
        self.size = 0

    def value(self, operand, scope):
        if operand[0] == "lit":
            return operand[1]
        name = operand[1]
        root = re.match(r"[A-Za-z_]\w*", name).group(0)
        base = scope if root in scope else self.ctx
        result = resolve(name, base)
        if result is None and not (root in scope or root in self.ctx):
            self.missing.add(name)
        return result

    def compare(self, op, left, right):
        try:
            if op == "==":
                return left == right
            if op == "!=":
                return left != right
            if op == "contains":
                if isinstance(left, (list, str)):
                    return right in left
                return False
            if left is None or right is None:
                return False
            if op == ">":
                return left > right
            if op == "<":
                return left < right
            if op == ">=":
                return left >= right
            if op == "<=":
                return left <= right
        except TypeError:
            return False
        return False

    def test(self, cond, scope):
        for ands in cond:
            ok = True
            for c in ands:
                if c[0] == "truthy":
                    ok = truthy(self.value(c[1], scope))
                else:
                    ok = self.compare(c[1], self.value(c[2], scope), self.value(c[3], scope))
                if not ok:
                    break
            if ok:
                return True
        return False

    def emit(self, out, text):
        self.size += len(text)
        if self.size > MAX_OUTPUT:
            raise LiquidError("Rendered output is too large", 0)
        out.append(text)

    def render(self, nodes, scope, out):
        for n in nodes:
            if isinstance(n, Text):
                self.emit(out, n.value)
            elif isinstance(n, Output):
                v = self.value(n.expr, scope)
                for name, args in n.filters:
                    v = apply_filter(name, v, [self.value(a, scope) for a in args])
                self.emit(out, to_str(v))
            elif isinstance(n, Assign):
                v = self.value(n.expr, scope)
                for name, args in n.filters:
                    v = apply_filter(name, v, [self.value(a, scope) for a in args])
                scope[n.name] = v
            elif isinstance(n, For):
                items = self.value(n.source, scope)
                if not isinstance(items, list):
                    items = []
                for i, item in enumerate(items):
                    self.iterations += 1
                    if self.iterations > MAX_ITERATIONS:
                        raise LiquidError("Too many loop iterations", n.line)
                    inner = dict(scope)
                    inner[n.var] = item
                    inner["forloop"] = {"index": i + 1, "index0": i, "first": i == 0, "last": i == len(items) - 1, "length": len(items)}
                    self.render(n.body, inner, out)
            elif isinstance(n, If):
                matched = False
                for cond, body in n.branches:
                    result = self.test(cond, scope)
                    if n.negate:
                        result = not result
                    if result:
                        self.render(body, scope, out)
                        matched = True
                        break
                if not matched:
                    self.render(n.otherwise, scope, out)


def render_template(source, ctx):
    nodes, errors = parse(source)
    if errors:
        raise LiquidError(errors[0][0], errors[0][1])
    r = Renderer(ctx)
    out = []
    r.render(nodes, {}, out)
    return "".join(out), sorted(r.missing)
