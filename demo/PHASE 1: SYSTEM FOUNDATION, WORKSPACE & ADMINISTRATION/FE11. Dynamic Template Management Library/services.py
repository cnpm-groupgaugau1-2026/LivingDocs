import datetime
import difflib
import hmac
import uuid

from . import enforce, liquid
from .catalog import AST_VARIABLES, CATEGORIES, SAMPLE_DATA, SYSTEM_TEMPLATES
from .errors import ServiceError
from .pathmatch import compile_glob, matches, normalize_path, specificity

import jwt

WRITE_ROLES = ("MANAGER", "ADMINISTRATOR")
ROLE_ALIASES = {
    "DEVELOPER": "DEVELOPER", "DEV": "DEVELOPER", "STAFF": "STAFF",
    "MANAGER": "MANAGER", "MGR": "MANAGER", "TL": "MANAGER", "TECH_LEAD": "MANAGER", "TECHNICAL_LEAD": "MANAGER",
    "ADMINISTRATOR": "ADMINISTRATOR", "ADMIN": "ADMINISTRATOR",
}
SERVICE_ACTOR = {"id": "service", "role": "SERVICE", "status": "ACTIVE"}
CONSTRAINT_KEYS = ("max_chars", "forbidden_phrases", "allow_extra_sections")
STATUSES = ("ACTIVE", "INACTIVE", "ARCHIVED")
SCOPES = ("SYSTEM_DEFAULT", "CUSTOM_WORKSPACE")
SORTS = ("created_desc", "created_asc", "name", "usage")


def iso(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value, field):
    try:
        dt = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise ServiceError(422, f"{field} must be an ISO 8601 timestamp")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.timestamp()


def paging(query):
    try:
        page = int(query.get("page", 1))
        size = int(query.get("page_size", 20))
    except (TypeError, ValueError):
        raise ServiceError(422, "page and page_size must be integers")
    if page < 1 or size < 1 or size > 100:
        raise ServiceError(422, "page must be >= 1 and page_size between 1 and 100")
    return page, size


def need_str(data, field, maximum, required=True):
    v = data.get(field)
    if v is None or (isinstance(v, str) and not v.strip()):
        if required:
            raise ServiceError(422, f"The {field} field is required.")
        return None
    if not isinstance(v, str):
        raise ServiceError(422, f"The {field} field must be a string.")
    if len(v) > maximum:
        raise ServiceError(422, f"Exceed maximum length of {maximum} characters.")
    return v.strip() if field != "template_body" else v


class AuthService:
    def __init__(self, settings, clock, resolver=None):
        self.s = settings
        self.clock = clock
        self.resolver = resolver or self._claims_resolver

    @staticmethod
    def _claims_resolver(claims):
        role = ROLE_ALIASES.get(str(claims.get("role", "")).upper(), "DEVELOPER")
        return {"id": str(claims["sub"]), "role": role, "status": "ACTIVE"}

    def authenticate(self, header):
        if not header:
            raise ServiceError(401, "Missing token")
        token = header[7:] if header.lower().startswith("bearer ") else header
        try:
            claims = jwt.decode(token, self.s.jwt_secret, algorithms=["HS256"],
                                options={"verify_exp": False, "verify_iat": False, "require": ["sub"]})
        except Exception:
            raise ServiceError(401, "Invalid token")
        exp = claims.get("exp")
        if exp is not None and exp < self.clock():
            raise ServiceError(401, "Token expired")
        user = self.resolver(claims)
        if not user:
            raise ServiceError(401, "Unknown user")
        if user.get("status", "ACTIVE") != "ACTIVE":
            raise ServiceError(403, "Account is not active")
        return user

    def service_or_user(self, headers):
        key = headers.get("x-service-key")
        if key and self.s.service_key and hmac.compare_digest(key, self.s.service_key):
            return SERVICE_ACTOR
        return self.authenticate(headers.get("authorization"))


class Audit:
    def __init__(self, store, clock):
        self.store = store
        self.clock = clock

    def log(self, category, actor, workspace_id, action, target="", detail=None):
        return self.store.add_audit(category, actor["id"], workspace_id, action, target, detail or {}, self.clock())


def require_write(actor):
    if actor["role"] not in WRITE_ROLES:
        raise ServiceError(403, "You do not have permission to perform this action.")


def markdown_problems(body):
    errors, warnings = [], []
    if not body.strip():
        errors.append({"line": 1, "message": "Template body must not be empty."})
        return errors, warnings
    fences = [i for i, l in enumerate(body.split("\n"), 1) if enforce.FENCE_RE.match(l)]
    if len(fences) % 2:
        errors.append({"line": fences[-1], "message": "A fenced code block is not closed."})
    prev = 0
    for h in enforce.derive_structure(body)["headings"]:
        if prev and h["level"] > prev + 1:
            warnings.append({"line": h["line"], "message": f"Heading level jumps from {prev} to {h['level']}."})
        prev = h["level"]
    return errors, warnings


def validate_body(body, declared=None):
    nodes, errors, used = liquid.analyze(body)
    md_errors, warnings = markdown_problems(body)
    errors = sorted(errors + md_errors, key=lambda e: e["line"])
    bindings = used
    if declared is not None:
        if not isinstance(declared, list) or any(not isinstance(x, str) for x in declared):
            errors.append({"line": 1, "message": "ast_bindings must be a list of strings."})
        else:
            unknown = [x for x in declared if x not in AST_VARIABLES]
            if unknown:
                errors.append({"line": 1, "message": "Unknown ast_bindings: " + ", ".join(unknown)})
            missing = [x for x in used if x not in declared]
            if missing:
                errors.append({"line": 1, "message": "Used AST variables missing from ast_bindings: " + ", ".join(missing)})
            if not unknown:
                bindings = sorted(set(declared) | set(used))
    return {"valid": not errors, "errors": errors, "warnings": warnings, "variables_used": used, "ast_bindings": bindings}


def clean_constraints(value):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ServiceError(422, "constraints must be an object")
    unknown = [k for k in value if k not in CONSTRAINT_KEYS]
    if unknown:
        raise ServiceError(422, "Unknown constraints: " + ", ".join(unknown))
    out = {}
    if "max_chars" in value:
        v = value["max_chars"]
        if isinstance(v, bool) or not isinstance(v, int) or not 100 <= v <= 200000:
            raise ServiceError(422, "max_chars must be an integer between 100 and 200000")
        out["max_chars"] = v
    if "forbidden_phrases" in value:
        v = value["forbidden_phrases"]
        if not isinstance(v, list) or len(v) > 50 or any(not isinstance(x, str) or not x.strip() or len(x) > 100 for x in v):
            raise ServiceError(422, "forbidden_phrases must be a list of up to 50 non-empty strings of at most 100 characters")
        out["forbidden_phrases"] = [x.strip() for x in v]
    if "allow_extra_sections" in value:
        if not isinstance(value["allow_extra_sections"], bool):
            raise ServiceError(422, "allow_extra_sections must be true or false")
        out["allow_extra_sections"] = value["allow_extra_sections"]
    return out


class TemplateService:
    def __init__(self, settings, store, audit, bus, clock, membership=None):
        self.s = settings
        self.store = store
        self.audit = audit
        self.bus = bus
        self.clock = clock
        self.membership = membership
        self._seed()

    def _seed(self):
        for t in SYSTEM_TEMPLATES:
            if self.store.get_template(t["id"]):
                continue
            result = validate_body(t["body"])
            ts = self.clock()
            self.store.insert_template(
                {"id": t["id"], "scope": "SYSTEM_DEFAULT", "workspace_id": None, "name": t["name"], "category": t["category"],
                 "status": "ACTIVE", "created_by": "system", "created_at": ts},
                {"name": t["name"], "category": t["category"], "body": t["body"], "ast_bindings": result["ast_bindings"],
                 "constraints": {}, "prompt_instructions": t["prompt_instructions"], "author_id": "system",
                 "change_note": "System default", "created_at": ts},
            )

    def ws_access(self, actor, workspace_id):
        if actor["role"] in ("ADMINISTRATOR", "SERVICE") or self.membership is None:
            return
        if not self.membership(actor, workspace_id):
            raise ServiceError(403, "You are not a member of this workspace.")

    def _load(self, actor, template_id, writable=False):
        t = self.store.get_template(template_id)
        if not t:
            raise ServiceError(404, "Template not found")
        if t["scope"] == "CUSTOM_WORKSPACE":
            self.ws_access(actor, t["workspace_id"])
        if t["status"] != "ACTIVE" and actor["role"] not in WRITE_ROLES and actor["role"] != "SERVICE":
            raise ServiceError(404, "Template not found")
        if t["status"] == "ARCHIVED" and actor["role"] not in WRITE_ROLES:
            raise ServiceError(404, "Template not found")
        return t

    def _view(self, t, workspace_id=None, detail=False):
        v = self.store.get_version(t["id"], t["current_version"])
        out = {
            "id": t["id"], "template_name": t["name"], "category": t["category"], "scope": t["scope"],
            "status": t["status"], "version": t["current_version"], "workspace_id": t["workspace_id"],
            "ast_bindings": v["ast_bindings"], "source_template_id": t["source_template_id"],
            "created_at": iso(t["created_at"]), "updated_at": iso(t["updated_at"]),
        }
        ws = workspace_id or t["workspace_id"]
        if ws:
            out["usage"] = {"active_specs": self.store.usage_count(t["id"], ws), "repositories": self.store.usage_by_repo(t["id"], ws)}
        if detail:
            out.update({"template_body": v["body"], "constraints": v["constraints"], "prompt_instructions": v["prompt_instructions"]})
        return out

    def _content(self, data, current=None):
        if "template_name" in data or current is None:
            name = need_str(data, "template_name", self.s.max_name_chars)
        else:
            name = current["name"]
        category = data.get("category", current["category"] if current else None)
        if category not in CATEGORIES:
            raise ServiceError(422, "category must be one of: " + ", ".join(CATEGORIES))
        if "template_body" in data or current is None:
            body = data.get("template_body")
            if not isinstance(body, str) or not body.strip():
                raise ServiceError(422, "The template_body field is required.")
            if len(body) > self.s.max_body_chars:
                raise ServiceError(422, f"Exceed maximum length of {self.s.max_body_chars} characters.")
        else:
            body = current["body"]
        declared = data.get("ast_bindings")
        result = validate_body(body, declared)
        if not result["valid"]:
            raise ServiceError(422, "Template validation failed", {"errors": result["errors"], "warnings": result["warnings"]})
        prompt = data.get("prompt_instructions", current["prompt_instructions"] if current else "")
        if prompt is None:
            prompt = ""
        if not isinstance(prompt, str) or len(prompt) > self.s.max_prompt_chars:
            raise ServiceError(422, f"prompt_instructions must be a string of at most {self.s.max_prompt_chars} characters")
        constraints = clean_constraints(data["constraints"]) if "constraints" in data else (current["constraints"] if current else {})
        bindings = result["ast_bindings"]
        return {"name": name, "category": category, "body": body, "ast_bindings": bindings, "constraints": constraints, "prompt_instructions": prompt}

    def catalog(self, actor):
        return {
            "categories": list(CATEGORIES),
            "ast_variables": [{"name": k, **v} for k, v in AST_VARIABLES.items()],
            "filters": list(liquid.FILTERS),
            "tags": ["if", "elsif", "else", "unless", "for", "assign", "comment"],
            "constraint_options": list(CONSTRAINT_KEYS),
        }

    def validate(self, actor, data):
        body = data.get("template_body")
        if not isinstance(body, str):
            raise ServiceError(422, "The template_body field is required.")
        if len(body) > self.s.max_body_chars:
            raise ServiceError(422, f"Exceed maximum length of {self.s.max_body_chars} characters.")
        return validate_body(body, data.get("ast_bindings"))

    def _render(self, body, override):
        ctx = dict(SAMPLE_DATA)
        if override is not None:
            if not isinstance(override, dict):
                raise ServiceError(422, "data must be an object")
            ctx.update(override)
        try:
            text, missing = liquid.render_template(body, ctx)
        except liquid.LiquidError as e:
            raise ServiceError(422, "Template rendering failed", {"errors": [{"line": e.line, "message": e.message}]})
        return {"rendered": text, "missing_variables": missing}

    def preview(self, actor, data):
        if data.get("template_id"):
            t = self._load(actor, str(data["template_id"]))
            body = self.store.get_version(t["id"], t["current_version"])["body"]
        else:
            body = data.get("template_body")
            if not isinstance(body, str) or not body.strip():
                raise ServiceError(422, "Provide template_body or template_id.")
            result = validate_body(body)
            if not result["valid"]:
                raise ServiceError(422, "Template validation failed", {"errors": result["errors"], "warnings": result["warnings"]})
        return self._render(body, data.get("data"))

    def preview_saved(self, actor, template_id):
        t = self._load(actor, template_id)
        return self._render(self.store.get_version(t["id"], t["current_version"])["body"], None)

    def create(self, actor, data):
        require_write(actor)
        workspace_id = need_str(data, "workspace_id", 100)
        self.ws_access(actor, workspace_id)
        content = self._content(data)
        if self.store.name_taken(workspace_id, content["name"]):
            raise ServiceError(409, "A template with this name already exists in the workspace.")
        tid = "tmpl_" + uuid.uuid4().hex[:12]
        ts = self.clock()
        self.store.insert_template(
            {"id": tid, "scope": "CUSTOM_WORKSPACE", "workspace_id": workspace_id, "name": content["name"],
             "category": content["category"], "status": "ACTIVE", "created_by": actor["id"], "created_at": ts},
            {**content, "author_id": actor["id"], "change_note": data.get("change_note", "Initial version") or "Initial version", "created_at": ts},
        )
        code = self.audit.log("TMP", actor, workspace_id, "template.create", tid, {"name": content["name"]})
        self.bus.publish("template.created", {"template_id": tid, "workspace_id": workspace_id, "version": 1})
        out = self._view(self.store.get_template(tid), detail=True)
        out["audit_code"] = code
        return out

    def get(self, actor, template_id):
        return self._view(self._load(actor, template_id), detail=True)

    def _custom_for_write(self, actor, template_id):
        require_write(actor)
        t = self._load(actor, template_id)
        if t["scope"] == "SYSTEM_DEFAULT":
            raise ServiceError(403, "System default templates are immutable. Duplicate the template to customize it.")
        if t["status"] == "ARCHIVED":
            raise ServiceError(409, "Archived templates cannot be modified.")
        return t

    def update(self, actor, template_id, data):
        t = self._custom_for_write(actor, template_id)
        expected = data.get("expected_version")
        if expected is not None and expected != t["current_version"]:
            raise ServiceError(409, "The template was modified by another user. Reload and try again.", {"current_version": t["current_version"]})
        current = self.store.get_version(t["id"], t["current_version"])
        content = self._content(data, current)
        if content["name"].lower() != t["name"].lower() and self.store.name_taken(t["workspace_id"], content["name"], t["id"]):
            raise ServiceError(409, "A template with this name already exists in the workspace.")
        same = all(content[k] == current[k] for k in ("name", "category", "body", "ast_bindings", "constraints", "prompt_instructions"))
        if same:
            return self._view(t, detail=True)
        number = self.store.add_version(t["id"], {**content, "author_id": actor["id"], "change_note": data.get("change_note", "") or "", "created_at": self.clock()})
        code = self.audit.log("TMP", actor, t["workspace_id"], "template.update", t["id"], {"version": number})
        self.bus.publish("template.updated", {"template_id": t["id"], "workspace_id": t["workspace_id"], "version": number})
        out = self._view(self.store.get_template(t["id"]), detail=True)
        out["audit_code"] = code
        return out

    def duplicate(self, actor, template_id, data):
        require_write(actor)
        src = self._load(actor, template_id)
        workspace_id = need_str(data, "workspace_id", 100)
        self.ws_access(actor, workspace_id)
        if src["scope"] == "CUSTOM_WORKSPACE" and src["workspace_id"] != workspace_id:
            raise ServiceError(404, "Template not found")
        v = self.store.get_version(src["id"], src["current_version"])
        name = need_str(data, "template_name", self.s.max_name_chars, required=False) or f"{src['name']} (Copy)"
        base, n = name, 2
        while self.store.name_taken(workspace_id, name):
            name = f"{base} {n}"
            n += 1
        tid = "tmpl_" + uuid.uuid4().hex[:12]
        ts = self.clock()
        self.store.insert_template(
            {"id": tid, "scope": "CUSTOM_WORKSPACE", "workspace_id": workspace_id, "name": name, "category": src["category"],
             "status": "ACTIVE", "created_by": actor["id"], "source_template_id": src["id"], "created_at": ts},
            {"name": name, "category": src["category"], "body": v["body"], "ast_bindings": v["ast_bindings"], "constraints": v["constraints"],
             "prompt_instructions": v["prompt_instructions"], "author_id": actor["id"], "change_note": f"Duplicated from {src['id']} v{src['current_version']}", "created_at": ts},
        )
        code = self.audit.log("TMP", actor, workspace_id, "template.duplicate", tid, {"source": src["id"]})
        self.bus.publish("template.created", {"template_id": tid, "workspace_id": workspace_id, "version": 1})
        out = self._view(self.store.get_template(tid), detail=True)
        out["audit_code"] = code
        return out

    def set_status(self, actor, template_id, status):
        t = self._custom_for_write(actor, template_id)
        if t["status"] != status:
            self.store.set_status(t["id"], status, self.clock())
            self.audit.log("TMP", actor, t["workspace_id"], "template.status", t["id"], {"status": status})
            self.bus.publish("template.status_changed", {"template_id": t["id"], "workspace_id": t["workspace_id"], "status": status})
        return self._view(self.store.get_template(t["id"]))

    def archive(self, actor, template_id):
        t = self._custom_for_write(actor, template_id)
        if self.store.binding_count(t["id"]):
            raise ServiceError(409, f"Template deletion failed. Active document collections are bound to {t['name']}.")
        self.store.set_status(t["id"], "ARCHIVED", self.clock())
        code = self.audit.log("TMP", actor, t["workspace_id"], "template.archive", t["id"], {})
        self.bus.publish("template.status_changed", {"template_id": t["id"], "workspace_id": t["workspace_id"], "status": "ARCHIVED"})
        return {"id": t["id"], "status": "ARCHIVED", "audit_code": code}

    def list(self, actor, workspace_id, query):
        self.ws_access(actor, workspace_id)
        page, size = paging(query)
        status, scope, category = query.get("status"), query.get("scope"), query.get("category")
        sort = query.get("sort", "created_desc")
        if status and status not in STATUSES:
            raise ServiceError(422, "Invalid status filter")
        if scope and scope not in SCOPES:
            raise ServiceError(422, "Invalid scope filter")
        if category and category not in CATEGORIES:
            raise ServiceError(422, "Invalid category filter")
        if sort not in SORTS:
            raise ServiceError(422, "sort must be one of: " + ", ".join(SORTS))
        created_from = parse_iso(query["created_from"], "created_from") if query.get("created_from") else None
        created_to = parse_iso(query["created_to"], "created_to") if query.get("created_to") else None
        can_see_all = actor["role"] in WRITE_ROLES
        rows = []
        for t in self.store.visible_templates(workspace_id):
            if not can_see_all and t["status"] != "ACTIVE":
                continue
            if status:
                if t["status"] != status or (status != "ACTIVE" and not can_see_all):
                    continue
            elif t["status"] == "ARCHIVED":
                continue
            if scope and t["scope"] != scope:
                continue
            if category and t["category"] != category:
                continue
            q = (query.get("q") or "").strip().lower()
            if q and q not in t["name"].lower() and q not in t["category"].lower():
                continue
            if created_from is not None and t["created_at"] < created_from:
                continue
            if created_to is not None and t["created_at"] > created_to:
                continue
            rows.append(t)
        if sort == "name":
            rows.sort(key=lambda t: t["name"].lower())
        elif sort == "created_asc":
            rows.sort(key=lambda t: (t["created_at"], t["id"]))
        elif sort == "usage":
            rows.sort(key=lambda t: (-self.store.usage_count(t["id"], workspace_id), t["name"].lower()))
        else:
            rows.sort(key=lambda t: (-t["created_at"], t["id"]))
        total = len(rows)
        items = [self._view(t, workspace_id) for t in rows[(page - 1) * size: page * size]]
        out = {"items": items, "total": total, "page": page, "page_size": size}
        if total == 0:
            out["message"] = "No templates found matching your search."
        return out

    def versions(self, actor, template_id):
        t = self._load(actor, template_id)
        return {"template_id": t["id"], "current_version": t["current_version"],
                "items": [{**r, "created_at": iso(r["created_at"])} for r in self.store.list_versions(t["id"])]}

    def get_version(self, actor, template_id, number):
        t = self._load(actor, template_id)
        v = self._version(t, number)
        return {"template_id": t["id"], "version": v["version_no"], "template_name": v["name"], "category": v["category"],
                "template_body": v["body"], "ast_bindings": v["ast_bindings"], "constraints": v["constraints"],
                "prompt_instructions": v["prompt_instructions"], "author_id": v["author_id"], "change_note": v["change_note"],
                "created_at": iso(v["created_at"])}

    def _version(self, t, number):
        try:
            n = int(number)
        except (TypeError, ValueError):
            raise ServiceError(422, "Version must be an integer")
        v = self.store.get_version(t["id"], n)
        if not v:
            raise ServiceError(404, "Version not found")
        return v

    def restore(self, actor, template_id, number, data):
        t = self._custom_for_write(actor, template_id)
        old = self._version(t, number)
        current = self.store.get_version(t["id"], t["current_version"])
        if old["version_no"] == current["version_no"]:
            raise ServiceError(409, "This is already the current version.")
        if old["name"].lower() != t["name"].lower() and self.store.name_taken(t["workspace_id"], old["name"], t["id"]):
            raise ServiceError(409, "A template with this name already exists in the workspace.")
        new_no = self.store.add_version(t["id"], {
            "name": old["name"], "category": old["category"], "body": old["body"], "ast_bindings": old["ast_bindings"],
            "constraints": old["constraints"], "prompt_instructions": old["prompt_instructions"], "author_id": actor["id"],
            "change_note": (data.get("change_note") or f"Restored from v{old['version_no']}"), "created_at": self.clock()})
        code = self.audit.log("TMP", actor, t["workspace_id"], "template.restore", t["id"], {"from": old["version_no"], "to": new_no})
        self.bus.publish("template.updated", {"template_id": t["id"], "workspace_id": t["workspace_id"], "version": new_no})
        out = self._view(self.store.get_template(t["id"]), detail=True)
        out["audit_code"] = code
        return out

    def diff(self, actor, template_id, query):
        t = self._load(actor, template_id)
        to = int(query.get("to", t["current_version"]))
        frm = int(query.get("from", max(to - 1, 1)))
        a, b = self._version(t, frm), self._version(t, to)
        lines = list(difflib.unified_diff(a["body"].splitlines(), b["body"].splitlines(), f"v{frm}", f"v{to}", lineterm=""))
        added = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
        return {"template_id": t["id"], "from": frm, "to": to, "diff": "\n".join(lines), "added_lines": added, "removed_lines": removed}

    def constraints(self, actor, template_id):
        t = self._load(actor, template_id)
        v = self.store.get_version(t["id"], t["current_version"])
        return {
            "template_id": t["id"], "version": t["current_version"], "selectable": t["status"] == "ACTIVE",
            "structure": enforce.derive_structure(v["body"]), "constraints": v["constraints"],
            "prompt_instructions": v["prompt_instructions"], "ast_bindings": v["ast_bindings"],
        }

    def active_for_use(self, actor, template_id):
        t = self._load(actor, template_id)
        if t["status"] != "ACTIVE":
            raise ServiceError(409, "This template is not active and cannot be used for generation.")
        return t

    def enforce(self, actor, template_id, data):
        t = self.active_for_use(actor, template_id)
        text = data.get("output_markdown")
        if not isinstance(text, str):
            raise ServiceError(422, "The output_markdown field is required.")
        if len(text) > 1000000:
            raise ServiceError(422, "Exceed maximum length of 1000000 characters.")
        return self._check(t, text)

    def _check(self, t, text):
        v = self.store.get_version(t["id"], t["current_version"])
        violations = enforce.check(text, enforce.derive_structure(v["body"]), v["constraints"])
        return {"template_id": t["id"], "version": t["current_version"], "conforms": not violations, "violations": violations}

    def record_usage(self, actor, workspace_id, template_id, data):
        self.ws_access(actor, workspace_id)
        t = self.active_for_use(actor, template_id)
        if t["scope"] == "CUSTOM_WORKSPACE" and t["workspace_id"] != workspace_id:
            raise ServiceError(404, "Template not found")
        doc_ref = need_str(data, "doc_ref", 500)
        repo = need_str(data, "repository_id", 200)
        active = data.get("active", True)
        if not isinstance(active, bool):
            raise ServiceError(422, "active must be true or false")
        self.store.set_usage(t["id"], workspace_id, repo, doc_ref, active, self.clock())
        return {"template_id": t["id"], "workspace_id": workspace_id,
                "usage": {"active_specs": self.store.usage_count(t["id"], workspace_id), "repositories": self.store.usage_by_repo(t["id"], workspace_id)}}

    def audit_logs(self, actor, query):
        require_write(actor)
        page, size = paging(query)
        ws = query.get("workspace_id")
        if ws:
            self.ws_access(actor, ws)
        elif actor["role"] != "ADMINISTRATOR":
            raise ServiceError(422, "workspace_id is required")
        rows, total = self.store.list_audit(ws, query.get("category"), size, (page - 1) * size)
        for r in rows:
            r["created_at"] = iso(r["created_at"])
        return {"items": rows, "total": total, "page": page, "page_size": size}


class BindingService:
    def __init__(self, store, templates, audit, bus, clock):
        self.store = store
        self.templates = templates
        self.audit = audit
        self.bus = bus
        self.clock = clock

    def _view(self, b):
        t = self.store.get_template(b["template_id"])
        return {
            "id": b["id"], "workspace_id": b["workspace_id"], "template_id": b["template_id"],
            "template_name": t["name"] if t else None, "template_status": t["status"] if t else None,
            "repository_id": b["repository_id"], "path_pattern": b["path_pattern"],
            "enforce_mandatory": bool(b["enforce_mandatory"]),
            "auto_trigger_tier1_review": bool(b["auto_trigger_tier1_review"]),
            "enable_ast_drift_tracking": bool(b["enable_ast_drift_tracking"]),
            "created_at": iso(b["created_at"]), "updated_at": iso(b["updated_at"]),
        }

    @staticmethod
    def _flag(data, name, default):
        v = data.get(name, default)
        if not isinstance(v, bool):
            raise ServiceError(422, f"{name} must be true or false")
        return v

    def _template_for_binding(self, actor, workspace_id, template_id):
        t = self.templates._load(actor, str(template_id))
        if t["scope"] == "CUSTOM_WORKSPACE" and t["workspace_id"] != workspace_id:
            raise ServiceError(404, "Template not found")
        if t["status"] != "ACTIVE":
            raise ServiceError(409, "Only active templates can be bound.")
        return t

    def create(self, actor, workspace_id, data):
        require_write(actor)
        self.templates.ws_access(actor, workspace_id)
        template_id = need_str(data, "template_id", 100)
        repo = need_str(data, "repository_id", 200)
        pattern = need_str(data, "path_pattern", 300)
        compile_glob(pattern)
        t = self._template_for_binding(actor, workspace_id, template_id)
        flags = {
            "enforce_mandatory": self._flag(data, "enforce_mandatory", True),
            "auto_trigger_tier1_review": self._flag(data, "auto_trigger_tier1_review", False),
            "enable_ast_drift_tracking": self._flag(data, "enable_ast_drift_tracking", False),
        }
        documents = data.get("documents", [])
        if not isinstance(documents, list) or len(documents) > 200:
            raise ServiceError(422, "documents must be a list of at most 200 items")
        if self.store.find_binding(workspace_id, repo, pattern):
            raise ServiceError(409, "A template binding already exists for this repository and path pattern.")
        bid = self.store.create_binding({"workspace_id": workspace_id, "template_id": t["id"], "repository_id": repo,
                                         "path_pattern": pattern, "created_by": actor["id"], **flags}, self.clock())
        code = self.audit.log("BND", actor, workspace_id, "binding.create", str(bid), {"template_id": t["id"], "repository_id": repo, "path_pattern": pattern})
        self.bus.publish("template.binding.created", {"binding_id": bid, "workspace_id": workspace_id, "template_id": t["id"],
                                                      "repository_id": repo, "path_pattern": pattern, **flags})
        out = self._view(self.store.get_binding(bid))
        out["audit_code"] = code
        if documents:
            checks = []
            for d in documents:
                if not isinstance(d, dict) or not isinstance(d.get("path"), str) or not isinstance(d.get("content"), str):
                    raise ServiceError(422, "Each document needs a path and content")
                if matches(pattern, d["path"]):
                    r = self.templates._check(t, d["content"])
                    checks.append({"path": d["path"], "conforms": r["conforms"], "violations": r["violations"]})
            out["initial_check"] = {"checked": len(checks), "non_conforming": sum(1 for c in checks if not c["conforms"]), "results": checks}
        return out

    def list(self, actor, workspace_id, query):
        self.templates.ws_access(actor, workspace_id)
        items = [self._view(b) for b in self.store.list_bindings(workspace_id, query.get("repository_id"))]
        return {"items": items, "total": len(items)}

    def _get(self, workspace_id, binding_id):
        try:
            b = self.store.get_binding(int(binding_id))
        except ValueError:
            b = None
        if not b or b["workspace_id"] != workspace_id:
            raise ServiceError(404, "Binding not found")
        return b

    def update(self, actor, workspace_id, binding_id, data):
        require_write(actor)
        self.templates.ws_access(actor, workspace_id)
        b = self._get(workspace_id, binding_id)
        fields = {}
        if "template_id" in data:
            fields["template_id"] = self._template_for_binding(actor, workspace_id, need_str(data, "template_id", 100))["id"]
        if "path_pattern" in data:
            fields["path_pattern"] = need_str(data, "path_pattern", 300)
            compile_glob(fields["path_pattern"])
        if "repository_id" in data:
            fields["repository_id"] = need_str(data, "repository_id", 200)
        for f in ("enforce_mandatory", "auto_trigger_tier1_review", "enable_ast_drift_tracking"):
            if f in data:
                fields[f] = int(self._flag(data, f, True))
        if not fields:
            raise ServiceError(422, "No parameters provided")
        repo = fields.get("repository_id", b["repository_id"])
        pattern = fields.get("path_pattern", b["path_pattern"])
        if self.store.find_binding(workspace_id, repo, pattern, b["id"]):
            raise ServiceError(409, "A template binding already exists for this repository and path pattern.")
        self.store.update_binding(b["id"], self.clock(), **fields)
        code = self.audit.log("BND", actor, workspace_id, "binding.update", str(b["id"]), {k: v for k, v in fields.items()})
        self.bus.publish("template.binding.updated", {"binding_id": b["id"], "workspace_id": workspace_id})
        out = self._view(self.store.get_binding(b["id"]))
        out["audit_code"] = code
        return out

    def delete(self, actor, workspace_id, binding_id):
        require_write(actor)
        self.templates.ws_access(actor, workspace_id)
        b = self._get(workspace_id, binding_id)
        self.store.delete_binding(b["id"])
        code = self.audit.log("BND", actor, workspace_id, "binding.delete", str(b["id"]), {})
        self.bus.publish("template.binding.deleted", {"binding_id": b["id"], "workspace_id": workspace_id})
        return {"status": "deleted", "audit_code": code}

    def _resolve(self, workspace_id, repo, path):
        path = normalize_path(path)
        best = None
        for b in self.store.list_bindings(workspace_id, repo):
            if compile_glob(b["path_pattern"]).match(path):
                key = (specificity(b["path_pattern"]), b["id"])
                if best is None or key > best[0]:
                    best = (key, b)
        return best[1] if best else None

    def resolve(self, actor, workspace_id, data):
        self.templates.ws_access(actor, workspace_id)
        repo = need_str(data, "repository_id", 200)
        b = self._resolve(workspace_id, repo, data.get("path"))
        if not b:
            return {"bound": False}
        return {"bound": True, "binding": self._view(b)}

    def validate_document(self, actor, workspace_id, data):
        self.templates.ws_access(actor, workspace_id)
        repo = need_str(data, "repository_id", 200)
        content = data.get("content")
        if not isinstance(content, str):
            raise ServiceError(422, "The content field is required.")
        b = self._resolve(workspace_id, repo, data.get("path"))
        if not b:
            return {"bound": False, "allowed": True, "violations": []}
        t = self.store.get_template(b["template_id"])
        base = {"bound": True, "binding_id": b["id"], "template_id": t["id"], "enforce_mandatory": bool(b["enforce_mandatory"]),
                "route_to_tier1_review": bool(b["auto_trigger_tier1_review"]), "drift_tracking": bool(b["enable_ast_drift_tracking"])}
        if t["status"] != "ACTIVE":
            return {**base, "enforced": False, "allowed": True, "violations": [], "warning": "The bound template is not active; enforcement was skipped."}
        result = self.templates._check(t, content)
        allowed = result["conforms"] or not b["enforce_mandatory"]
        return {**base, "enforced": True, "conforms": result["conforms"], "allowed": allowed, "violations": result["violations"]}
