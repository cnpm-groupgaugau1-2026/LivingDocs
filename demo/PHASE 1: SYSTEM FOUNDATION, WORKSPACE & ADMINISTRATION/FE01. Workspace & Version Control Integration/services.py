import secrets
import time
import uuid

from . import crypto
from .errors import ServiceError
from .events import EventBus
from .github_client import GitHubClient
from .store import Store

MANAGE_ROLES = ("OWNER", "TL", "ADMIN")
CREATE_ROLES = ("TL", "ADMIN")
PR_ACTIONS = ("opened", "synchronize", "reopened", "closed", "ready_for_review")


def _csv(value):
    return {x.strip().lower() for x in (value or "").split(",") if x.strip()}


class AuthService:
    def __init__(self, settings, store: Store, github: GitHubClient):
        self.s = settings
        self.store = store
        self.github = github

    def redirect_uri(self):
        return self.s.public_base_url.rstrip("/") + "/api/v1/auth/github/callback"

    def login_url(self):
        state = crypto.sign_state(self.s.jwt_secret)
        return self.github.authorize_url(state, self.redirect_uri())

    def _role_for(self, login):
        low = login.lower()
        if low in _csv(self.s.admin_logins):
            return "ADMIN"
        if low in _csv(self.s.lead_logins):
            return "TL"
        return "DEV"

    def handle_callback(self, code, state):
        if not code or not state or not crypto.verify_state(state, self.s.jwt_secret):
            raise ServiceError(400, "Invalid OAuth state or code")
        token = self.github.exchange_code(code, self.redirect_uri())
        gh = self.github.get_user(token)
        email = gh.get("email") or self.github.get_primary_email(token)
        role = self._role_for(gh["login"])
        enc = crypto.encrypt_text(token, self.s.token_encryption_key)
        user_id = self.store.upsert_user(gh["id"], gh["login"], gh.get("name"), email, gh.get("avatar_url"), role, enc)
        session_id = uuid.uuid4().hex
        self.store.set_session(user_id, session_id)
        self.store.audit(user_id, "auth.login", gh["login"])
        jwt_token = crypto.sign_session(user_id, session_id, self.s.jwt_secret, self.s.jwt_ttl_seconds)
        return jwt_token, self.public_user(self.store.get_user(user_id))

    def authenticate(self, bearer):
        if not bearer:
            raise ServiceError(401, "Missing token")
        token = bearer[7:] if bearer.lower().startswith("bearer ") else bearer
        try:
            claims = crypto.verify_session(token, self.s.jwt_secret)
        except Exception:
            raise ServiceError(401, "Invalid or expired token")
        user = self.store.get_user(int(claims["sub"]))
        if not user or user["current_session"] != claims.get("sid"):
            raise ServiceError(401, "Session is no longer active")
        return user

    def logout(self, user):
        self.store.set_session(user["id"], None)
        self.store.audit(user["id"], "auth.logout", user["login"])

    def user_token(self, user):
        return crypto.decrypt_text(user["access_token_enc"], self.s.token_encryption_key)

    @staticmethod
    def public_user(user):
        return {k: user[k] for k in ("id", "github_id", "login", "name", "email", "avatar_url", "role")}


class WorkspaceService:
    def __init__(self, store: Store):
        self.store = store

    def create(self, user, name, description=""):
        if user["role"] not in CREATE_ROLES:
            raise ServiceError(403, "Only Tech Lead or Admin can create workspaces")
        name = (name or "").strip()
        if not name:
            raise ServiceError(422, "Workspace name is required")
        wid = self.store.create_workspace(name, description or "", user["id"])
        self.store.audit(user["id"], "workspace.create", str(wid))
        return self.store.get_workspace(wid)

    def require_member(self, workspace_id, user, roles=None):
        ws = self.store.get_workspace(workspace_id)
        if not ws:
            raise ServiceError(404, "Workspace not found")
        m = self.store.get_membership(workspace_id, user["id"])
        if not m:
            raise ServiceError(403, "Not a member of this workspace")
        if roles and m["role"] not in roles and user["role"] not in roles:
            raise ServiceError(403, "Insufficient permission")
        return ws, m

    def list(self, user):
        return self.store.list_workspaces(user["id"])

    def get(self, workspace_id, user):
        ws, m = self.require_member(workspace_id, user)
        ws = dict(ws)
        ws["member_role"] = m["role"]
        ws["members"] = self.store.list_members(workspace_id)
        ws["repository_count"] = len(self.store.list_bindings(workspace_id))
        return ws

    def update(self, workspace_id, user, name, description):
        self.require_member(workspace_id, user, MANAGE_ROLES)
        name = (name or "").strip()
        if not name:
            raise ServiceError(422, "Workspace name is required")
        self.store.update_workspace(workspace_id, name, description or "")
        self.store.audit(user["id"], "workspace.update", str(workspace_id))
        return self.store.get_workspace(workspace_id)

    def delete(self, workspace_id, user):
        ws, m = self.require_member(workspace_id, user)
        if m["role"] != "OWNER" and user["role"] != "ADMIN":
            raise ServiceError(403, "Only owner can delete workspace")
        self.store.delete_workspace(workspace_id)
        self.store.audit(user["id"], "workspace.delete", str(workspace_id))

    def add_member(self, workspace_id, user, github_login, role):
        self.require_member(workspace_id, user, MANAGE_ROLES)
        target = self.store._one("SELECT * FROM users WHERE lower(login)=lower(?)", (github_login,))
        if not target:
            raise ServiceError(404, "User has not signed in to LivingDocs yet")
        if role not in ("TL", "DEV", "STAFF", "MGR"):
            raise ServiceError(422, "Invalid member role")
        self.store.add_member(workspace_id, target["id"], role)
        self.store.audit(user["id"], "workspace.add_member", f"{workspace_id}:{target['login']}")
        return self.store.list_members(workspace_id)

    def remove_member(self, workspace_id, user, member_id):
        ws, _ = self.require_member(workspace_id, user, MANAGE_ROLES)
        if member_id == ws["owner_id"]:
            raise ServiceError(422, "Cannot remove workspace owner")
        self.store.remove_member(workspace_id, member_id)
        self.store.audit(user["id"], "workspace.remove_member", f"{workspace_id}:{member_id}")
        return self.store.list_members(workspace_id)


class RepositoryService:
    def __init__(self, settings, store: Store, github: GitHubClient, bus: EventBus, workspaces: WorkspaceService, auth: AuthService):
        self.s = settings
        self.store = store
        self.github = github
        self.bus = bus
        self.workspaces = workspaces
        self.auth = auth

    def webhook_url(self):
        return self.s.public_base_url.rstrip("/") + "/api/v1/webhooks/github/receive"

    def available_repos(self, user):
        token = self.auth.user_token(user)
        out = []
        for inst in self.github.list_user_installations(token):
            for repo in self.github.list_installation_repos(inst["id"]):
                bound = bool(self.store.find_binding_by_repo(github_repo_id=repo["id"]))
                out.append(
                    {
                        "installation_id": inst["id"],
                        "account": (inst.get("account") or {}).get("login"),
                        "github_repo_id": repo["id"],
                        "full_name": repo["full_name"],
                        "private": repo.get("private", False),
                        "default_branch": repo.get("default_branch", "main"),
                        "bound": bound,
                    }
                )
        return out

    def connect(self, workspace_id, user, full_name, installation_id, doc_branch=None, enable_webhook=True):
        self.workspaces.require_member(workspace_id, user, MANAGE_ROLES)
        if not full_name or "/" not in full_name:
            raise ServiceError(422, "full_name must be owner/repo")
        repo = self.github.get_repo(installation_id, full_name)
        branch = doc_branch or repo.get("default_branch") or "main"
        if self.github.get_branch(installation_id, full_name, branch) is None:
            raise ServiceError(422, f"Branch '{branch}' does not exist")
        for b in self.store.list_bindings(workspace_id):
            if b["github_repo_id"] == repo["id"]:
                raise ServiceError(409, "Repository already connected to this workspace")
        bid = self.store.create_binding(workspace_id, repo["id"], repo["full_name"], installation_id, branch, "INDEXING")
        if enable_webhook:
            secret = secrets.token_hex(32)
            try:
                hook_id = self.github.create_hook(installation_id, repo["full_name"], self.webhook_url(), secret, self.s.webhook_events)
            except ServiceError:
                self.store.delete_binding(bid)
                raise
            self.store.save_webhook(
                bid, hook_id, crypto.encrypt_text(secret, self.s.token_encryption_key), self.s.webhook_events, "UNKNOWN"
            )
        self._request_index(bid, "initial")
        self.store.audit(user["id"], "repository.connect", f"{workspace_id}:{repo['full_name']}")
        return self.view(bid)

    def _request_index(self, binding_id, reason):
        b = self.store.get_binding(binding_id)
        self.bus.publish(
            "ast.index.requested",
            {
                "binding_id": binding_id,
                "workspace_id": b["workspace_id"],
                "repo": b["full_name"],
                "branch": b["doc_branch"],
                "installation_id": b["installation_id"],
                "reason": reason,
                "requested_at": time.time(),
            },
        )

    def view(self, binding_id):
        b = self.store.get_binding(binding_id)
        if not b:
            raise ServiceError(404, "Repository binding not found")
        hook = self.store.get_webhook(binding_id)
        out = dict(b)
        out["webhook"] = (
            {"hook_id": hook["hook_id"], "events": hook["events"], "health": hook["health"], "active": bool(hook["active"])}
            if hook
            else None
        )
        return out

    def list(self, workspace_id, user):
        self.workspaces.require_member(workspace_id, user)
        return [self.view(b["id"]) for b in self.store.list_bindings(workspace_id)]

    def _get_bound(self, workspace_id, binding_id):
        b = self.store.get_binding(binding_id)
        if not b or b["workspace_id"] != workspace_id:
            raise ServiceError(404, "Repository binding not found")
        return b

    def sync(self, workspace_id, binding_id, user):
        self.workspaces.require_member(workspace_id, user, MANAGE_ROLES)
        b = self._get_bound(workspace_id, binding_id)
        self.github.get_repo(b["installation_id"], b["full_name"])
        self.store.update_binding(binding_id, status="INDEXING")
        self._request_index(binding_id, "manual")
        self.store.audit(user["id"], "repository.sync", b["full_name"])
        return self.view(binding_id)

    def mark_indexed(self, binding_id, ok=True):
        if self.store.get_binding(binding_id):
            self.store.update_binding(binding_id, status="SYNCED" if ok else "FAILED", last_synced_at=time.time())

    def disconnect(self, workspace_id, binding_id, user):
        self.workspaces.require_member(workspace_id, user, MANAGE_ROLES)
        b = self._get_bound(workspace_id, binding_id)
        hook = self.store.get_webhook(binding_id)
        if hook and hook["hook_id"]:
            self.github.delete_hook(b["installation_id"], b["full_name"], hook["hook_id"])
        if hook:
            self.store.deactivate_webhook(binding_id)
        self.store.update_binding(binding_id, status="DISCONNECTED")
        self.store.audit(user["id"], "repository.disconnect", b["full_name"])
        return self.view(binding_id)

    def get_webhook(self, workspace_id, binding_id, user):
        self.workspaces.require_member(workspace_id, user)
        self._get_bound(workspace_id, binding_id)
        hook = self.store.get_webhook(binding_id)
        if not hook:
            raise ServiceError(404, "Webhook not configured")
        return {
            "hook_id": hook["hook_id"],
            "events": hook["events"],
            "health": hook["health"],
            "active": bool(hook["active"]),
            "url": self.webhook_url(),
            "deliveries": self.store.list_deliveries(binding_id),
        }

    def update_webhook(self, workspace_id, binding_id, user, events=None, regenerate_secret=False):
        self.workspaces.require_member(workspace_id, user, MANAGE_ROLES)
        b = self._get_bound(workspace_id, binding_id)
        hook = self.store.get_webhook(binding_id)
        if not hook:
            raise ServiceError(404, "Webhook not configured")
        events = list(events or hook["events"])
        invalid = [e for e in events if e not in self.s.webhook_events]
        if invalid or not events:
            raise ServiceError(422, "Unsupported webhook events")
        if regenerate_secret:
            secret = secrets.token_hex(32)
            secret_enc = crypto.encrypt_text(secret, self.s.token_encryption_key)
        else:
            secret_enc = hook["secret_enc"]
            secret = crypto.decrypt_text(secret_enc, self.s.token_encryption_key)
        self.github.update_hook(b["installation_id"], b["full_name"], hook["hook_id"], self.webhook_url(), secret, events)
        self.store.save_webhook(binding_id, hook["hook_id"], secret_enc, events, hook["health"], 1)
        self.store.audit(user["id"], "webhook.update", b["full_name"])
        return self.view(binding_id)["webhook"]

    def ping_webhook(self, workspace_id, binding_id, user):
        self.workspaces.require_member(workspace_id, user, MANAGE_ROLES)
        b = self._get_bound(workspace_id, binding_id)
        hook = self.store.get_webhook(binding_id)
        if not hook:
            raise ServiceError(404, "Webhook not configured")
        ok = self.github.ping_hook(b["installation_id"], b["full_name"], hook["hook_id"])
        if not ok:
            self.store.set_webhook_health(binding_id, "UNHEALTHY")
            raise ServiceError(502, "Ping request failed")
        return {"requested": True}


class WebhookService:
    def __init__(self, settings, store: Store, bus: EventBus):
        self.s = settings
        self.store = store
        self.bus = bus

    def receive(self, body: bytes, event, delivery_id, signature):
        started = time.time()
        if not event:
            return self._finish(400, "missing_event", None, delivery_id, "unknown", started)
        try:
            import json

            payload = json.loads(body.decode() or "{}")
        except Exception:
            return self._finish(400, "invalid_json", None, delivery_id, event, started)
        repo = payload.get("repository") or {}
        candidates = []
        if repo.get("id") is not None:
            candidates = self.store.find_binding_by_repo(github_repo_id=repo["id"])
        if not candidates and repo.get("full_name"):
            candidates = self.store.find_binding_by_repo(full_name=repo["full_name"])
        if not candidates and event == "ping" and (payload.get("hook") or {}).get("id") is not None:
            candidates = self._by_hook(payload["hook"]["id"])
        if not candidates:
            return self._finish(404, "unknown_repository", None, delivery_id, event, started)
        matched = None
        for b in candidates:
            hook = self.store.get_webhook(b["id"])
            if not hook or not hook["active"]:
                continue
            secret = crypto.decrypt_text(hook["secret_enc"], self.s.token_encryption_key)
            if crypto.verify_signature(secret, body, signature):
                matched = (b, hook)
                break
        if not matched:
            return self._finish(401, "invalid_signature", candidates[0]["id"], delivery_id, event, started)
        binding, hook = matched
        if self.store.delivery_exists(delivery_id):
            return 200, {"status": "duplicate"}
        if event == "ping":
            self.store.set_webhook_health(binding["id"], "HEALTHY")
            return self._finish(200, "pong", binding["id"], delivery_id, event, started)
        if event not in hook["events"]:
            return self._finish(202, "ignored_event", binding["id"], delivery_id, event, started)
        message = self._build_message(binding, event, payload, delivery_id)
        if message is None:
            return self._finish(202, "ignored", binding["id"], delivery_id, event, started)
        self.bus.publish("github.events", message)
        self.store.set_webhook_health(binding["id"], "HEALTHY")
        self.store.update_binding(binding["id"], status="INDEXING")
        return self._finish(202, "queued", binding["id"], delivery_id, event, started)

    def _by_hook(self, hook_id):
        rows = self.store._all("SELECT repo_binding_id FROM webhook_configurations WHERE hook_id=?", (hook_id,))
        return [self.store.get_binding(r["repo_binding_id"]) for r in rows]

    def _build_message(self, binding, event, payload, delivery_id):
        base = {
            "delivery_id": delivery_id,
            "event": event,
            "binding_id": binding["id"],
            "workspace_id": binding["workspace_id"],
            "repo": binding["full_name"],
            "installation_id": binding["installation_id"],
            "received_at": time.time(),
        }
        if event == "push":
            ref = payload.get("ref", "")
            branch = ref.split("/", 2)[-1] if ref.startswith("refs/heads/") else ref
            if branch != binding["doc_branch"]:
                return None
            commits = payload.get("commits") or []
            files = set()
            for c in commits:
                for k in ("added", "modified", "removed"):
                    files.update(c.get(k) or [])
            base.update(
                {
                    "branch": branch,
                    "before": payload.get("before"),
                    "after": payload.get("after"),
                    "commit_ids": [c.get("id") for c in commits],
                    "changed_files": sorted(files),
                    "pusher": (payload.get("pusher") or {}).get("name"),
                }
            )
            return base
        if event == "pull_request":
            action = payload.get("action")
            if action not in PR_ACTIONS:
                return None
            pr = payload.get("pull_request") or {}
            base.update(
                {
                    "action": action,
                    "pr_number": pr.get("number") or payload.get("number"),
                    "title": pr.get("title"),
                    "merged": bool(pr.get("merged")),
                    "head_sha": (pr.get("head") or {}).get("sha"),
                    "base_branch": (pr.get("base") or {}).get("ref"),
                }
            )
            return base
        base["payload_action"] = payload.get("action")
        return base

    def _finish(self, status, result, binding_id, delivery_id, event, started):
        latency = (time.time() - started) * 1000.0
        if delivery_id:
            self.store.record_delivery(delivery_id, binding_id, event, status, latency, result)
        return status, {"status": result}
