from .container import Container
from .router import Router


def build_router(c: Container) -> Router:
    r = Router()

    def user(req):
        return c.auth.authenticate(req.headers.get("authorization"))

    def who(req):
        return c.auth.service_or_user(req.headers)

    def health(req):
        return 200, {"status": "ok"}

    def catalog(req):
        return 200, c.templates.catalog(user(req))

    def validate(req):
        return 200, c.templates.validate(user(req), req.json())

    def preview(req):
        return 200, c.templates.preview(user(req), req.json())

    def audit_logs(req):
        return 200, c.templates.audit_logs(user(req), req.query)

    def create(req):
        return 201, c.templates.create(user(req), req.json())

    def get(req, template_id):
        return 200, c.templates.get(who(req), template_id)

    def update(req, template_id):
        return 200, c.templates.update(user(req), template_id, req.json())

    def archive(req, template_id):
        return 200, c.templates.archive(user(req), template_id)

    def duplicate(req, template_id):
        return 201, c.templates.duplicate(user(req), template_id, req.json())

    def activate(req, template_id):
        return 200, c.templates.set_status(user(req), template_id, "ACTIVE")

    def deactivate(req, template_id):
        return 200, c.templates.set_status(user(req), template_id, "INACTIVE")

    def versions(req, template_id):
        return 200, c.templates.versions(user(req), template_id)

    def get_version(req, template_id, number):
        return 200, c.templates.get_version(user(req), template_id, number)

    def restore(req, template_id, number):
        return 200, c.templates.restore(user(req), template_id, number, req.json())

    def diff(req, template_id):
        return 200, c.templates.diff(user(req), template_id, req.query)

    def preview_saved(req, template_id):
        return 200, c.templates.preview_saved(user(req), template_id)

    def constraints(req, template_id):
        return 200, c.templates.constraints(who(req), template_id)

    def enforce(req, template_id):
        return 200, c.templates.enforce(who(req), template_id, req.json())

    def list_templates(req, workspace_id):
        return 200, c.templates.list(who(req), workspace_id, req.query)

    def usage(req, workspace_id, template_id):
        return 200, c.templates.record_usage(who(req), workspace_id, template_id, req.json())

    def list_bindings(req, workspace_id):
        return 200, c.bindings.list(who(req), workspace_id, req.query)

    def create_binding(req, workspace_id):
        return 201, c.bindings.create(user(req), workspace_id, req.json())

    def update_binding(req, workspace_id, binding_id):
        return 200, c.bindings.update(user(req), workspace_id, binding_id, req.json())

    def delete_binding(req, workspace_id, binding_id):
        return 200, c.bindings.delete(user(req), workspace_id, binding_id)

    def resolve(req, workspace_id):
        return 200, c.bindings.resolve(who(req), workspace_id, req.json())

    def validate_document(req, workspace_id):
        return 200, c.bindings.validate_document(who(req), workspace_id, req.json())

    r.add("GET", "/health", health)
    r.add("GET", "/templates/catalog", catalog)
    r.add("POST", "/templates/validate", validate)
    r.add("POST", "/templates/preview", preview)
    r.add("GET", "/templates/audit-logs", audit_logs)
    r.add("POST", "/templates", create)
    r.add("GET", "/templates/{template_id}", get)
    r.add("PUT", "/templates/{template_id}", update)
    r.add("DELETE", "/templates/{template_id}", archive)
    r.add("POST", "/templates/{template_id}/duplicate", duplicate)
    r.add("POST", "/templates/{template_id}/activate", activate)
    r.add("POST", "/templates/{template_id}/deactivate", deactivate)
    r.add("GET", "/templates/{template_id}/versions", versions)
    r.add("GET", "/templates/{template_id}/versions/{number}", get_version)
    r.add("POST", "/templates/{template_id}/versions/{number}/restore", restore)
    r.add("GET", "/templates/{template_id}/diff", diff)
    r.add("GET", "/templates/{template_id}/preview", preview_saved)
    r.add("GET", "/templates/{template_id}/constraints", constraints)
    r.add("POST", "/templates/{template_id}/enforce", enforce)
    r.add("GET", "/workspaces/{workspace_id}/templates", list_templates)
    r.add("POST", "/workspaces/{workspace_id}/templates/{template_id}/usage", usage)
    r.add("GET", "/workspaces/{workspace_id}/template-bindings", list_bindings)
    r.add("POST", "/workspaces/{workspace_id}/template-bindings", create_binding)
    r.add("POST", "/workspaces/{workspace_id}/template-bindings/resolve", resolve)
    r.add("POST", "/workspaces/{workspace_id}/template-bindings/validate-document", validate_document)
    r.add("PUT", "/workspaces/{workspace_id}/template-bindings/{binding_id}", update_binding)
    r.add("DELETE", "/workspaces/{workspace_id}/template-bindings/{binding_id}", delete_binding)
    return r
