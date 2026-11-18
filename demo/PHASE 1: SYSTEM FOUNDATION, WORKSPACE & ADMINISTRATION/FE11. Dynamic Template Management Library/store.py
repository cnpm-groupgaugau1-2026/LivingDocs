import json
import sqlite3
import threading

SCHEMA = """
CREATE TABLE IF NOT EXISTS templates(
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    workspace_id TEXT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    current_version INTEGER NOT NULL,
    source_template_id TEXT,
    created_by TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS template_versions(
    template_id TEXT NOT NULL,
    version_no INTEGER NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    body TEXT NOT NULL,
    ast_bindings TEXT NOT NULL,
    constraints TEXT NOT NULL,
    prompt_instructions TEXT NOT NULL,
    author_id TEXT,
    change_note TEXT,
    created_at REAL NOT NULL,
    PRIMARY KEY(template_id, version_no)
);
CREATE TABLE IF NOT EXISTS bindings(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL,
    template_id TEXT NOT NULL,
    repository_id TEXT NOT NULL,
    path_pattern TEXT NOT NULL,
    enforce_mandatory INTEGER NOT NULL,
    auto_trigger_tier1_review INTEGER NOT NULL,
    enable_ast_drift_tracking INTEGER NOT NULL,
    created_by TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(workspace_id, repository_id, path_pattern)
);
CREATE TABLE IF NOT EXISTS usage(
    template_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    repository_id TEXT NOT NULL,
    doc_ref TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY(template_id, workspace_id, doc_ref)
);
CREATE TABLE IF NOT EXISTS audit_logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    actor_id TEXT,
    workspace_id TEXT,
    action TEXT NOT NULL,
    target TEXT,
    detail TEXT,
    created_at REAL NOT NULL
);
"""


class Store:
    def __init__(self, path=":memory:"):
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def one(self, sql, args=()):
        with self._lock:
            row = self.conn.execute(sql, args).fetchone()
        return dict(row) if row else None

    def all(self, sql, args=()):
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def exec(self, sql, args=()):
        with self._lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur.lastrowid

    def insert_template(self, row, version):
        with self._lock:
            self.conn.execute(
                "INSERT INTO templates(id, scope, workspace_id, name, category, status, current_version, source_template_id, created_by, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (row["id"], row["scope"], row["workspace_id"], row["name"], row["category"], row["status"], 1,
                 row.get("source_template_id"), row.get("created_by"), row["created_at"], row["created_at"]),
            )
            self._insert_version(row["id"], 1, version)
            self.conn.commit()

    def _insert_version(self, template_id, number, v):
        self.conn.execute(
            "INSERT INTO template_versions(template_id, version_no, name, category, body, ast_bindings, constraints, prompt_instructions, author_id, change_note, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (template_id, number, v["name"], v["category"], v["body"], json.dumps(v["ast_bindings"]), json.dumps(v["constraints"]),
             v["prompt_instructions"], v.get("author_id"), v.get("change_note", ""), v["created_at"]),
        )

    def add_version(self, template_id, v):
        with self._lock:
            number = self.conn.execute("SELECT current_version FROM templates WHERE id=?", (template_id,)).fetchone()[0] + 1
            self._insert_version(template_id, number, v)
            self.conn.execute(
                "UPDATE templates SET current_version=?, name=?, category=?, updated_at=? WHERE id=?",
                (number, v["name"], v["category"], v["created_at"], template_id),
            )
            self.conn.commit()
        return number

    def get_template(self, template_id):
        return self.one("SELECT * FROM templates WHERE id=?", (template_id,))

    def set_status(self, template_id, status, ts):
        self.exec("UPDATE templates SET status=?, updated_at=? WHERE id=?", (status, ts, template_id))

    def get_version(self, template_id, number):
        row = self.one("SELECT * FROM template_versions WHERE template_id=? AND version_no=?", (template_id, number))
        if row:
            row["ast_bindings"] = json.loads(row["ast_bindings"])
            row["constraints"] = json.loads(row["constraints"])
        return row

    def list_versions(self, template_id):
        rows = self.all("SELECT version_no, name, author_id, change_note, created_at FROM template_versions WHERE template_id=? ORDER BY version_no DESC", (template_id,))
        return rows

    def visible_templates(self, workspace_id):
        return self.all(
            "SELECT * FROM templates WHERE scope='SYSTEM_DEFAULT' OR (scope='CUSTOM_WORKSPACE' AND workspace_id=?)",
            (workspace_id,),
        )

    def name_taken(self, workspace_id, name, exclude_id=None):
        row = self.one(
            "SELECT id FROM templates WHERE scope='CUSTOM_WORKSPACE' AND workspace_id=? AND lower(name)=lower(?) AND status<>'ARCHIVED' AND id<>?",
            (workspace_id, name, exclude_id or ""),
        )
        return row is not None

    def usage_count(self, template_id, workspace_id):
        return self.one("SELECT COUNT(*) AS n FROM usage WHERE template_id=? AND workspace_id=?", (template_id, workspace_id))["n"]

    def usage_by_repo(self, template_id, workspace_id):
        rows = self.all("SELECT repository_id, COUNT(*) AS n FROM usage WHERE template_id=? AND workspace_id=? GROUP BY repository_id", (template_id, workspace_id))
        return {r["repository_id"]: r["n"] for r in rows}

    def set_usage(self, template_id, workspace_id, repository_id, doc_ref, active, ts):
        if active:
            self.exec(
                "INSERT OR REPLACE INTO usage(template_id, workspace_id, repository_id, doc_ref, created_at) VALUES(?,?,?,?,?)",
                (template_id, workspace_id, repository_id, doc_ref, ts),
            )
        else:
            self.exec("DELETE FROM usage WHERE template_id=? AND workspace_id=? AND doc_ref=?", (template_id, workspace_id, doc_ref))

    def binding_count(self, template_id):
        return self.one("SELECT COUNT(*) AS n FROM bindings WHERE template_id=?", (template_id,))["n"]

    def create_binding(self, b, ts):
        return self.exec(
            "INSERT INTO bindings(workspace_id, template_id, repository_id, path_pattern, enforce_mandatory, auto_trigger_tier1_review, enable_ast_drift_tracking, created_by, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (b["workspace_id"], b["template_id"], b["repository_id"], b["path_pattern"], int(b["enforce_mandatory"]),
             int(b["auto_trigger_tier1_review"]), int(b["enable_ast_drift_tracking"]), b.get("created_by"), ts, ts),
        )

    def get_binding(self, binding_id):
        return self.one("SELECT * FROM bindings WHERE id=?", (binding_id,))

    def list_bindings(self, workspace_id, repository_id=None):
        if repository_id:
            return self.all("SELECT * FROM bindings WHERE workspace_id=? AND repository_id=? ORDER BY id", (workspace_id, repository_id))
        return self.all("SELECT * FROM bindings WHERE workspace_id=? ORDER BY id", (workspace_id,))

    def find_binding(self, workspace_id, repository_id, pattern, exclude_id=None):
        return self.one(
            "SELECT * FROM bindings WHERE workspace_id=? AND repository_id=? AND path_pattern=? AND id<>?",
            (workspace_id, repository_id, pattern, exclude_id or 0),
        )

    def update_binding(self, binding_id, ts, **fields):
        fields["updated_at"] = ts
        cols = ", ".join(f"{k}=?" for k in fields)
        self.exec(f"UPDATE bindings SET {cols} WHERE id=?", (*fields.values(), binding_id))

    def delete_binding(self, binding_id):
        self.exec("DELETE FROM bindings WHERE id=?", (binding_id,))

    def add_audit(self, category, actor_id, workspace_id, action, target, detail, ts):
        rid = self.exec(
            "INSERT INTO audit_logs(category, actor_id, workspace_id, action, target, detail, created_at) VALUES(?,?,?,?,?,?,?)",
            (category, actor_id, workspace_id, action, target, json.dumps(detail), ts),
        )
        return f"AUD-{category}-{rid:04d}"

    def list_audit(self, workspace_id, category, limit, offset):
        where, args = [], []
        if workspace_id:
            where.append("workspace_id=?")
            args.append(workspace_id)
        if category:
            where.append("category=?")
            args.append(category)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        total = self.one(f"SELECT COUNT(*) AS n FROM audit_logs {clause}", args)["n"]
        rows = self.all(f"SELECT * FROM audit_logs {clause} ORDER BY id DESC LIMIT ? OFFSET ?", (*args, limit, offset))
        for r in rows:
            r["audit_code"] = f"AUD-{r['category']}-{r['id']:04d}"
            r["detail"] = json.loads(r["detail"])
        return rows, total
