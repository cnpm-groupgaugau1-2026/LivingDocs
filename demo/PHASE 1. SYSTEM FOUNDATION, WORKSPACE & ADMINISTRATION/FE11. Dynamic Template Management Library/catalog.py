CATEGORIES = (
    "API_DOCUMENTATION",
    "SYSTEM_ARCHITECTURE",
    "DATABASE_MODEL",
    "README",
    "MODULE_GUIDE",
    "ONBOARDING_GUIDE",
    "ADR",
)

AST_VARIABLES = {
    "service_name": {"type": "string", "description": "Name of the service or module"},
    "repo_name": {"type": "string", "description": "Repository name"},
    "commit_sha": {"type": "string", "description": "Commit SHA the document was generated from"},
    "generated_at": {"type": "string", "description": "Generation timestamp"},
    "endpoint_path": {"type": "string", "description": "HTTP path of the current endpoint"},
    "http_method": {"type": "string", "description": "HTTP method of the current endpoint"},
    "payload_schema": {"type": "string", "description": "JSON schema of the request payload"},
    "ast_struct_bind": {"type": "string", "description": "Identifier of the bound AST struct node"},
    "mermaid_c4_diagram": {"type": "string", "description": "Mermaid C4 diagram source"},
    "ocr_specs": {"type": "string", "description": "Specification text extracted by OCR"},
    "ast_structs": {"type": "collection", "description": "Structs parsed from source code"},
    "endpoints": {"type": "collection", "description": "API endpoints parsed from source code"},
    "entities": {"type": "collection", "description": "Database entities parsed from source code"},
    "dependencies": {"type": "collection", "description": "Service dependencies"},
}

SAMPLE_DATA = {
    "service_name": "core-payment-service",
    "repo_name": "acme/core-payment-service",
    "commit_sha": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4",
    "generated_at": "2026-11-18T08:00:00Z",
    "endpoint_path": "/api/v2/payments",
    "http_method": "POST",
    "payload_schema": '{"amount": "number", "currency": "string"}',
    "ast_struct_bind": "PaymentRequest",
    "mermaid_c4_diagram": "C4Context\n  title Payment System\n  Person(user, \"Customer\")\n  System(pay, \"Payment Service\")\n  Rel(user, pay, \"Pays\")",
    "ocr_specs": "Max payment amount: 10000 USD",
    "ast_structs": [
        {"name": "PaymentRequest", "kind": "struct", "file": "src/payment/request.go", "line": 12,
         "fields": [{"name": "amount", "type": "float64", "description": "Payment amount"},
                    {"name": "currency", "type": "string", "description": "ISO 4217 code"}]},
        {"name": "PaymentResult", "kind": "struct", "file": "src/payment/result.go", "line": 8,
         "fields": [{"name": "id", "type": "string", "description": "Payment id"}]},
    ],
    "endpoints": [
        {"path": "/api/v2/payments", "method": "POST", "summary": "Create a payment",
         "parameters": [{"name": "amount", "type": "number", "required": True, "description": "Amount"}],
         "responses": [{"status": 201, "description": "Created"}, {"status": 400, "description": "Invalid request"}]},
        {"path": "/api/v2/payments/{id}", "method": "GET", "summary": "Get a payment",
         "parameters": [{"name": "id", "type": "string", "required": True, "description": "Payment id"}],
         "responses": [{"status": 200, "description": "OK"}]},
    ],
    "entities": [
        {"name": "Payment", "table": "payments",
         "columns": [{"name": "id", "type": "uuid", "nullable": False, "description": "Primary key"},
                     {"name": "amount", "type": "numeric", "nullable": False, "description": "Amount"}]},
    ],
    "dependencies": [
        {"name": "postgres", "type": "database", "protocol": "tcp"},
        {"name": "kafka", "type": "queue", "protocol": "tcp"},
    ],
}

MERMAID_KEYWORDS = (
    "flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram", "erDiagram",
    "gantt", "pie", "journey", "gitGraph", "mindmap", "timeline", "C4Context", "C4Container",
    "C4Component", "C4Dynamic", "C4Deployment", "requirementDiagram", "quadrantChart",
)

SYSTEM_TEMPLATES = [
    {
        "id": "tmpl_openapi_v2",
        "name": "OpenAPI REST Spec",
        "category": "API_DOCUMENTATION",
        "prompt_instructions": "Follow OpenAPI 3.1 semantics. Describe every endpoint with parameters and responses.",
        "body": (
            "# {{ service_name }} API Reference\n\n"
            "## Overview\n\n"
            "Generated from commit {{ commit_sha }}.\n\n"
            "## Endpoints\n\n"
            "{% for endpoint in endpoints %}"
            "### {{ endpoint.method }} {{ endpoint.path }}\n\n"
            "{{ endpoint.summary }}\n\n"
            "{% if endpoint.parameters %}"
            "| Name | Type | Required | Description |\n"
            "|------|------|----------|-------------|\n"
            "{% for p in endpoint.parameters %}| {{ p.name }} | {{ p.type }} | {{ p.required }} | {{ p.description }} |\n{% endfor %}\n"
            "{% endif %}"
            "{% endfor %}"
            "## Schemas\n\n"
            "{% for s in ast_structs %}- {{ s.name }} ({{ s.file }}:{{ s.line }})\n{% endfor %}"
        ),
    },
    {
        "id": "tmpl_c4_microservice",
        "name": "Microservice C4 Spec",
        "category": "SYSTEM_ARCHITECTURE",
        "prompt_instructions": "Describe the service using the C4 model. Keep the diagram consistent with the dependency list.",
        "body": (
            "# {{ service_name }} Architecture\n\n"
            "## Context Diagram\n\n"
            "```mermaid\n{{ mermaid_c4_diagram }}\n```\n\n"
            "## Dependencies\n\n"
            "{% for d in dependencies %}- {{ d.name }} ({{ d.type }}, {{ d.protocol }})\n{% endfor %}\n"
            "## Components\n\n"
            "{% for s in ast_structs %}- {{ s.name }}\n{% endfor %}"
        ),
    },
    {
        "id": "tmpl_db_entity_model",
        "name": "Database Entity Model",
        "category": "DATABASE_MODEL",
        "prompt_instructions": "Document every table with its columns, types and nullability.",
        "body": (
            "# {{ service_name }} Data Model\n\n"
            "## Entities\n\n"
            "{% for e in entities %}"
            "### {{ e.name }}\n\n"
            "Table: {{ e.table }}\n\n"
            "| Column | Type | Nullable | Description |\n"
            "|--------|------|----------|-------------|\n"
            "{% for c in e.columns %}| {{ c.name }} | {{ c.type }} | {{ c.nullable }} | {{ c.description }} |\n{% endfor %}\n"
            "{% endfor %}"
        ),
    },
]
