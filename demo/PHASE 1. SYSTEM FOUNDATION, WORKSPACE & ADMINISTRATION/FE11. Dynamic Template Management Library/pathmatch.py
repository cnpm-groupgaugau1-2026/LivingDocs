import re

from .errors import ServiceError

ALLOWED = re.compile(r"^[A-Za-z0-9._\-/*?]+$")


def normalize_path(path):
    if not isinstance(path, str) or not path.strip():
        raise ServiceError(422, "path is required")
    p = path.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    p = p.lstrip("/")
    if any(seg == ".." for seg in p.split("/")):
        raise ServiceError(422, "Path traversal is not allowed")
    return p


def compile_glob(pattern):
    if not isinstance(pattern, str) or not pattern.strip():
        raise ServiceError(422, "The path_pattern field is required.")
    pattern = pattern.strip()
    if len(pattern) > 300:
        raise ServiceError(422, "Exceed maximum length of 300 characters.")
    if not ALLOWED.match(pattern) or any(seg == ".." for seg in pattern.split("/")):
        raise ServiceError(422, "Invalid glob path pattern. Use letters, digits, . _ - / and the wildcards * ** ?")
    pattern = pattern.lstrip("/")
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += r"(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += r".*"
            i += 2
        elif pattern[i] == "*":
            out += r"[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += r"[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile("^" + out + "$")


def specificity(pattern):
    return sum(1 for ch in pattern if ch not in "*?")


def matches(pattern, path):
    return compile_glob(pattern).match(normalize_path(path)) is not None
