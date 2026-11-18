import re
from dataclasses import dataclass, field

from .container import Container
from .errors import ServiceError


@dataclass
class Req:
    method: str
    path: str
    query: dict = field(default_factory=dict)
    headers: dict = field(default_factory=dict)
    body: bytes = b""

    def json(self):
        import json

        try:
            data = json.loads(self.body.decode() or "{}")
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}


class Router:
    PREFIX = "/api/v1"

    def __init__(self, c: Container):
        self.c = c
        self.routes = []
        self._register()

    def add(self, method, pattern, fn):
        regex = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[0-9]+)", pattern) + "$")
        self.routes.append((method, regex, fn))

    def user(self, req):
        return self.c.auth.authenticate(req.headers.get("authorization"))

    def handle(self, req: Req):
        path = req.path[len(self.PREFIX):] if req.path.startswith(self.PREFIX) else None
        if path is None:
            return 404, {"detail": "Not found"}, None
        path_matched = False
        for method, regex, fn in self.routes:
            m = regex.match(path)
            if not m:
                continue
            path_matched = True
            if method != req.method.upper():
                continue
            try:
                result = fn(req, **{k: int(v) for k, v in m.groupdict().items()})
            except ServiceError as e:
                return e.status, {"detail": e.message}, None
            if len(result) == 3:
                return result
            return result[0], result[1], None
        if path_matched:
            return 405, {"detail": "Method not allowed"}, None
        return 404, {"detail": "Not found"}, None

    def _register(self):
        c = self.c

        def health(req):
            return 200, {"status": "ok"}

        def login(req):
            url = c.auth.login_url()
            if req.query.get("redirect") == "true":
                return 307, {}, url
            return 200, {"authorization_url": url}

        def callback(req):
            token, u = c.auth.handle_callback(req.query.get("code", ""), req.query.get("state", ""))
            if req.query.get("redirect") == "true":
                return 307, {}, f"{c.settings.frontend_url.rstrip('/')}/auth/callback#token={token}"
            return 200, {"access_token": token, "token_type": "bearer", "user": u}

        def me(req):
            return 200, c.auth.public_user(self.user(req))

        def logout(req):
            c.auth.logout(self.user(req))
            return 200, {"status": "logged_out"}

        def list_workspaces(req):
            return 200, c.workspaces.list(self.user(req))

        def create_workspace(req):
            d = req.json()
            return 201, c.workspaces.create(self.user(req), d.get("name"), d.get("description", ""))

        def get_workspace(req, wid):
            return 200, c.workspaces.get(wid, self.user(req))

        def update_workspace(req, wid):
            d = req.json()
            return 200, c.workspaces.update(wid, self.user(req), d.get("name"), d.get("description", ""))

        def delete_workspace(req, wid):
            c.workspaces.delete(wid, self.user(req))
            return 200, {"status": "deleted"}

        def add_member(req, wid):
            d = req.json()
            return 200, c.workspaces.add_member(wid, self.user(req), d.get("github_login", ""), d.get("role", "DEV"))

        def remove_member(req, wid, member_id):
            return 200, c.workspaces.remove_member(wid, self.user(req), member_id)

        def available_repos(req):
            return 200, c.repos.available_repos(self.user(req))

        def list_repos(req, wid):
            return 200, c.repos.list(wid, self.user(req))

        def connect_repo(req, wid):
            d = req.json()
            u = self.user(req)
            try:
                installation_id = int(d.get("installation_id"))
            except (TypeError, ValueError):
                raise ServiceError(422, "installation_id is required")
            out = c.repos.connect(
                wid, u, d.get("full_name"), installation_id, d.get("doc_branch"), bool(d.get("enable_webhook", True))
            )
            return 201, out

        def sync_repo(req, wid, bid):
            return 200, c.repos.sync(wid, bid, self.user(req))

        def disconnect_repo(req, wid, bid):
            return 200, c.repos.disconnect(wid, bid, self.user(req))

        def get_webhooks(req, wid, bid):
            return 200, c.repos.get_webhook(wid, bid, self.user(req))

        def put_webhooks(req, wid, bid):
            d = req.json()
            return 200, c.repos.update_webhook(
                wid, bid, self.user(req), d.get("events"), bool(d.get("regenerate_secret", False))
            )

        def ping_webhook(req, wid, bid):
            return 200, c.repos.ping_webhook(wid, bid, self.user(req))

        def receive(req):
            status, payload = c.webhooks.receive(
                req.body,
                req.headers.get("x-github-event"),
                req.headers.get("x-github-delivery"),
                req.headers.get("x-hub-signature-256"),
            )
            return status, payload

        self.add("GET", "/health", health)
        self.add("GET", "/auth/github/login", login)
        self.add("GET", "/auth/github/callback", callback)
        self.add("GET", "/auth/me", me)
        self.add("POST", "/auth/logout", logout)
        self.add("GET", "/workspaces", list_workspaces)
        self.add("POST", "/workspaces", create_workspace)
        self.add("GET", "/workspaces/{wid}", get_workspace)
        self.add("PUT", "/workspaces/{wid}", update_workspace)
        self.add("DELETE", "/workspaces/{wid}", delete_workspace)
        self.add("POST", "/workspaces/{wid}/members", add_member)
        self.add("DELETE", "/workspaces/{wid}/members/{member_id}", remove_member)
        self.add("GET", "/github/repos", available_repos)
        self.add("GET", "/workspaces/{wid}/repositories", list_repos)
        self.add("POST", "/workspaces/{wid}/repositories", connect_repo)
        self.add("POST", "/workspaces/{wid}/repositories/{bid}/sync", sync_repo)
        self.add("DELETE", "/workspaces/{wid}/repositories/{bid}", disconnect_repo)
        self.add("GET", "/workspaces/{wid}/repositories/{bid}/webhooks", get_webhooks)
        self.add("PUT", "/workspaces/{wid}/repositories/{bid}/webhooks", put_webhooks)
        self.add("POST", "/workspaces/{wid}/repositories/{bid}/webhooks/ping", ping_webhook)
        self.add("POST", "/webhooks/github/receive", receive)
