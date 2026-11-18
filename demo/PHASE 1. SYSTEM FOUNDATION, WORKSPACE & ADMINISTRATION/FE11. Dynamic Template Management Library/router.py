import json
import re
from dataclasses import dataclass, field

from .errors import ServiceError


@dataclass
class Req:
    method: str
    path: str
    query: dict = field(default_factory=dict)
    headers: dict = field(default_factory=dict)
    body: bytes = b""

    def json(self):
        if not self.body.strip():
            return {}
        try:
            data = json.loads(self.body.decode())
        except Exception:
            raise ServiceError(422, "Invalid JSON body")
        if not isinstance(data, dict):
            raise ServiceError(422, "JSON body must be an object")
        return data


class Router:
    PREFIX = "/api/v1"

    def __init__(self):
        self.routes = []

    def add(self, method, pattern, fn):
        regex = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern) + "$")
        self.routes.append((method, regex, fn))

    def handle(self, req: Req):
        if not req.path.startswith(self.PREFIX):
            return 404, {"detail": "Not found"}
        path = req.path[len(self.PREFIX):]
        path_matched = False
        for method, regex, fn in self.routes:
            m = regex.match(path)
            if not m:
                continue
            path_matched = True
            if method != req.method.upper():
                continue
            try:
                return fn(req, **m.groupdict())
            except ServiceError as e:
                return e.status, {"detail": e.message, **e.extra}
        if path_matched:
            return 405, {"detail": "Method not allowed"}
        return 404, {"detail": "Not found"}
