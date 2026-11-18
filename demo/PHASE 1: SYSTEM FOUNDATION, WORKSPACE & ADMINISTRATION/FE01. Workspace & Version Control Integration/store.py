import json
import sqlite3
import threading
import time


SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    github_id INTEGER UNIQUE NOT NULL,
    login TEXT NOT NULL,
    name TEXT,
    email TEXT,
    avatar_url TEXT,
    role TEXT NOT NULL DEFAULT 'DEV',
    access_token_enc TEXT,
    current_session TEXT,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS workspaces(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    owner_id INTEGER NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS memberships(
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    PRIMARY KEY(workspace_id, user_id)
);
CREATE TABLE IF NOT EXISTS repository_bindings(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    github_repo_id INTEGER NOT NULL,
    full_name TEXT NOT NULL,
    installation_id INTEGER,
    doc_branch TEXT NOT NULL,
    status TEXT NOT NULL,
    last_synced_at REAL,
    created_at REAL NOT NULL,
    UNIQUE(workspace_id, github_repo_id)
);
CREATE TABLE IF NOT EXISTS webhook_configurations(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_binding_id INTEGER UNIQUE NOT NULL,
    hook_id INTEGER,
    secret_enc TEXT NOT NULL,
    events TEXT NOT NULL,
    health TEXT NOT NULL DEFAULT 'UNKNOWN',
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS webhook_deliveries(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    delivery_id TEXT UNIQUE,
    repo_binding_id INTEGER,
    event TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    latency_ms REAL NOT NULL,
    result TEXT NOT NULL,
    received_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
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

    def _one(self, sql, args=()):
        with self._lock:
            row = self.conn.execute(sql, args).fetchone()
        return dict(row) if row else None

    def _all(self, sql, args=()):
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def _exec(self, sql, args=()):
        with self._lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur.lastrowid

    def upsert_user(self, github_id, login, name, email, avatar_url, role, token_enc):
        existing = self._one("SELECT * FROM users WHERE github_id=?", (github_id,))
        if existing:
            self._exec(
                "UPDATE users SET login=?, name=?, email=?, avatar_url=?, role=?, access_token_enc=? WHERE id=?",
                (login, name, email, avatar_url, role, token_enc, existing["id"]),
            )
            return existing["id"]
        return self._exec(
            "INSERT INTO users(github_id, login, name, email, avatar_url, role, access_token_enc, created_at) VALUES(?,?,?,?,?,?,?,?)",
            (github_id, login, name, email, avatar_url, role, token_enc, time.time()),
        )

    def get_user(self, user_id):
        return self._one("SELECT * FROM users WHERE id=?", (user_id,))

    def set_session(self, user_id, session_id):
        self._exec("UPDATE users SET current_session=? WHERE id=?", (session_id, user_id))

    def create_workspace(self, name, description, owner_id):
        wid = self._exec(
            "INSERT INTO workspaces(name, description, owner_id, created_at) VALUES(?,?,?,?)",
            (name, description, owner_id, time.time()),
        )
        self._exec("INSERT INTO memberships(workspace_id, user_id, role) VALUES(?,?,?)", (wid, owner_id, "OWNER"))
        return wid

    def get_workspace(self, workspace_id):
        return self._one("SELECT * FROM workspaces WHERE id=?", (workspace_id,))

    def list_workspaces(self, user_id):
        return self._all(
            "SELECT w.*, m.role AS member_role FROM workspaces w JOIN memberships m ON m.workspace_id=w.id WHERE m.user_id=? ORDER BY w.id",
            (user_id,),
        )

    def update_workspace(self, workspace_id, name, description):
        self._exec("UPDATE workspaces SET name=?, description=? WHERE id=?", (name, description, workspace_id))

    def delete_workspace(self, workspace_id):
        self._exec("DELETE FROM memberships WHERE workspace_id=?", (workspace_id,))
        self._exec("DELETE FROM workspaces WHERE id=?", (workspace_id,))

    def get_membership(self, workspace_id, user_id):
        return self._one("SELECT * FROM memberships WHERE workspace_id=? AND user_id=?", (workspace_id, user_id))

    def add_member(self, workspace_id, user_id, role):
        self._exec("INSERT OR REPLACE INTO memberships(workspace_id, user_id, role) VALUES(?,?,?)", (workspace_id, user_id, role))

    def list_members(self, workspace_id):
        return self._all(
            "SELECT u.id, u.login, u.name, u.avatar_url, m.role FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.workspace_id=?",
            (workspace_id,),
        )

    def remove_member(self, workspace_id, user_id):
        self._exec("DELETE FROM memberships WHERE workspace_id=? AND user_id=?", (workspace_id, user_id))

    def create_binding(self, workspace_id, github_repo_id, full_name, installation_id, doc_branch, status):
        return self._exec(
            "INSERT INTO repository_bindings(workspace_id, github_repo_id, full_name, installation_id, doc_branch, status, created_at) VALUES(?,?,?,?,?,?,?)",
            (workspace_id, github_repo_id, full_name, installation_id, doc_branch, status, time.time()),
        )

    def get_binding(self, binding_id):
        return self._one("SELECT * FROM repository_bindings WHERE id=?", (binding_id,))

    def find_binding_by_repo(self, github_repo_id=None, full_name=None):
        if github_repo_id is not None:
            return self._all("SELECT * FROM repository_bindings WHERE github_repo_id=?", (github_repo_id,))
        return self._all("SELECT * FROM repository_bindings WHERE full_name=?", (full_name,))

    def list_bindings(self, workspace_id):
        return self._all("SELECT * FROM repository_bindings WHERE workspace_id=? ORDER BY id", (workspace_id,))

    def update_binding(self, binding_id, **fields):
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        self._exec(f"UPDATE repository_bindings SET {cols} WHERE id=?", (*fields.values(), binding_id))

    def delete_binding(self, binding_id):
        self._exec("DELETE FROM webhook_configurations WHERE repo_binding_id=?", (binding_id,))
        self._exec("DELETE FROM repository_bindings WHERE id=?", (binding_id,))

    def save_webhook(self, binding_id, hook_id, secret_enc, events, health="UNKNOWN", active=1):
        existing = self._one("SELECT id FROM webhook_configurations WHERE repo_binding_id=?", (binding_id,))
        if existing:
            self._exec(
                "UPDATE webhook_configurations SET hook_id=?, secret_enc=?, events=?, health=?, active=? WHERE repo_binding_id=?",
                (hook_id, secret_enc, json.dumps(list(events)), health, active, binding_id),
            )
        else:
            self._exec(
                "INSERT INTO webhook_configurations(repo_binding_id, hook_id, secret_enc, events, health, active) VALUES(?,?,?,?,?,?)",
                (binding_id, hook_id, secret_enc, json.dumps(list(events)), health, active),
            )

    def get_webhook(self, binding_id):
        row = self._one("SELECT * FROM webhook_configurations WHERE repo_binding_id=?", (binding_id,))
        if row:
            row["events"] = json.loads(row["events"])
        return row

    def set_webhook_health(self, binding_id, health):
        self._exec("UPDATE webhook_configurations SET health=? WHERE repo_binding_id=?", (health, binding_id))

    def deactivate_webhook(self, binding_id):
        self._exec("UPDATE webhook_configurations SET active=0, health='REVOKED' WHERE repo_binding_id=?", (binding_id,))

    def record_delivery(self, delivery_id, binding_id, event, status_code, latency_ms, result):
        try:
            return self._exec(
                "INSERT INTO webhook_deliveries(delivery_id, repo_binding_id, event, status_code, latency_ms, result, received_at) VALUES(?,?,?,?,?,?,?)",
                (delivery_id, binding_id, event, status_code, latency_ms, result, time.time()),
            )
        except sqlite3.IntegrityError:
            return None

    def delivery_exists(self, delivery_id):
        return bool(delivery_id) and self._one("SELECT id FROM webhook_deliveries WHERE delivery_id=?", (delivery_id,)) is not None

    def list_deliveries(self, binding_id, limit=50):
        return self._all(
            "SELECT * FROM webhook_deliveries WHERE repo_binding_id=? ORDER BY id DESC LIMIT ?", (binding_id, limit)
        )

    def audit(self, user_id, action, detail=""):
        self._exec(
            "INSERT INTO audit_logs(user_id, action, detail, created_at) VALUES(?,?,?,?)",
            (user_id, action, detail, time.time()),
        )

    def list_audit(self, limit=100):
        return self._all("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
