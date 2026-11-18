import time

from .crypto import make_app_jwt
from .errors import ServiceError
from .http import default_transport


class GitHubClient:
    def __init__(self, settings, transport=None):
        self.s = settings
        self.transport = transport or default_transport
        self._inst_tokens = {}

    def _api(self, method, path, token, json_body=None):
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        return self.transport(method, self.s.github_api_url + path, headers, json_body, None)

    def authorize_url(self, state, redirect_uri):
        from urllib.parse import urlencode

        q = urlencode(
            {
                "client_id": self.s.github_client_id,
                "redirect_uri": redirect_uri,
                "scope": self.s.oauth_scopes,
                "state": state,
            }
        )
        return f"{self.s.github_oauth_url}/login/oauth/authorize?{q}"

    def exchange_code(self, code, redirect_uri):
        status, body = self.transport(
            "POST",
            f"{self.s.github_oauth_url}/login/oauth/access_token",
            {"Accept": "application/json"},
            None,
            {
                "client_id": self.s.github_client_id,
                "client_secret": self.s.github_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        token = body.get("access_token") if isinstance(body, dict) else None
        if status != 200 or not token:
            raise ServiceError(401, "GitHub OAuth code exchange failed")
        return token

    def get_user(self, token):
        status, body = self._api("GET", "/user", token)
        if status != 200:
            raise ServiceError(401, "Cannot fetch GitHub user")
        return body

    def get_primary_email(self, token):
        status, body = self._api("GET", "/user/emails", token)
        if status != 200 or not isinstance(body, list):
            return None
        for item in body:
            if item.get("primary") and item.get("verified"):
                return item.get("email")
        return body[0].get("email") if body else None

    def get_orgs(self, token):
        status, body = self._api("GET", "/user/orgs", token)
        if status != 200 or not isinstance(body, list):
            return []
        return [o.get("login") for o in body]

    def app_jwt(self):
        return make_app_jwt(self.s.github_app_id, self.s.github_app_private_key)

    def installation_token(self, installation_id):
        cached = self._inst_tokens.get(installation_id)
        if cached and cached[1] > time.time() + 60:
            return cached[0]
        status, body = self._api("POST", f"/app/installations/{installation_id}/access_tokens", self.app_jwt())
        if status not in (200, 201) or "token" not in body:
            raise ServiceError(502, "Cannot obtain GitHub App installation token")
        self._inst_tokens[installation_id] = (body["token"], time.time() + 3000)
        return body["token"]

    def list_user_installations(self, user_token):
        status, body = self._api("GET", "/user/installations", user_token)
        if status != 200:
            raise ServiceError(502, "Cannot list GitHub App installations")
        return body.get("installations", [])

    def list_installation_repos(self, installation_id):
        token = self.installation_token(installation_id)
        repos = []
        page = 1
        while True:
            status, body = self._api("GET", f"/installation/repositories?per_page=100&page={page}", token)
            if status != 200:
                raise ServiceError(502, "Cannot list repositories")
            batch = body.get("repositories", [])
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return repos

    def get_repo(self, installation_id, full_name):
        token = self.installation_token(installation_id)
        status, body = self._api("GET", f"/repos/{full_name}", token)
        if status != 200:
            raise ServiceError(404, "Repository not accessible by GitHub App")
        return body

    def get_branch(self, installation_id, full_name, branch):
        token = self.installation_token(installation_id)
        status, body = self._api("GET", f"/repos/{full_name}/branches/{branch}", token)
        if status != 200:
            return None
        return body

    def create_hook(self, installation_id, full_name, url, secret, events):
        token = self.installation_token(installation_id)
        status, body = self._api(
            "POST",
            f"/repos/{full_name}/hooks",
            token,
            {
                "name": "web",
                "active": True,
                "events": list(events),
                "config": {"url": url, "content_type": "json", "secret": secret, "insecure_ssl": "0"},
            },
        )
        if status not in (200, 201):
            raise ServiceError(502, "Cannot create GitHub webhook")
        return body["id"]

    def update_hook(self, installation_id, full_name, hook_id, url, secret, events):
        token = self.installation_token(installation_id)
        status, _ = self._api(
            "PATCH",
            f"/repos/{full_name}/hooks/{hook_id}",
            token,
            {
                "active": True,
                "events": list(events),
                "config": {"url": url, "content_type": "json", "secret": secret, "insecure_ssl": "0"},
            },
        )
        if status != 200:
            raise ServiceError(502, "Cannot update GitHub webhook")

    def delete_hook(self, installation_id, full_name, hook_id):
        token = self.installation_token(installation_id)
        status, _ = self._api("DELETE", f"/repos/{full_name}/hooks/{hook_id}", token)
        return status in (200, 204, 404)

    def ping_hook(self, installation_id, full_name, hook_id):
        token = self.installation_token(installation_id)
        status, _ = self._api("POST", f"/repos/{full_name}/hooks/{hook_id}/pings", token)
        return status in (200, 204)
