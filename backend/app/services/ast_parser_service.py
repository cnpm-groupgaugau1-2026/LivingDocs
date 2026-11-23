import os
from typing import List, Optional
from tree_sitter import Language, Parser, Node
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript

from app.schemas.ast_doc import CodeEntity, CodeParameter, ASTParseResponse


class ASTParserService:
    """Module 4.1: Multi-language AST Code Entity Parser Engine."""

    EXTENSION_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
    }

    BRANCH_NODE_TYPES = {
        "if_statement",
        "elif_clause",
        "for_statement",
        "while_statement",
        "try_statement",
        "except_clause",
        "catch_clause",
        "conditional_expression",
        "ternary_expression",
        "switch_case",
    }

    def __init__(self) -> None:
        self.languages = {
            "python": Language(tspython.language()),
            "javascript": Language(tsjavascript.language()),
            "typescript": Language(tstypescript.language_typescript()),
            "tsx": Language(tstypescript.language_tsx()),
        }

    def detect_language(self, file_path: str, explicit_lang: Optional[str] = None) -> str:
        if explicit_lang:
            lang = explicit_lang.lower().strip()
            if lang in self.languages:
                return lang
        _, ext = os.path.splitext(file_path.lower())
        if ext in self.EXTENSION_MAP:
            return self.EXTENSION_MAP[ext]
        raise ValueError(f"Ngôn ngữ chưa được hỗ trợ cho tệp: {file_path}")

    def parse_code(
        self, file_path: str, source_code: str, language: Optional[str] = None
    ) -> ASTParseResponse:
        resolved_lang = self.detect_language(file_path, language)
        parser = Parser(self.languages[resolved_lang])
        source_bytes = source_code.encode("utf-8")
        tree = parser.parse(source_bytes)

        entities: List[CodeEntity] = []
        if resolved_lang == "python":
            self._walk_python(tree.root_node, source_bytes, entities, parent_class=None)
        else:
            self._walk_js_ts(tree.root_node, source_bytes, entities, parent_class=None)

        documented_count = sum(1 for e in entities if e.has_docstring)
        return ASTParseResponse(
            file_path=file_path,
            language=resolved_lang,
            total_entities=len(entities),
            documented_entities=documented_count,
            entities=entities,
        )

    def _get_text(self, node: Optional[Node], source_bytes: bytes) -> str:
        if node is None:
            return ""
        return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    def _calculate_complexity(self, node: Node) -> int:
        score = 1
        stack = [node]
        while stack:
            curr = stack.pop()
            if curr.type in self.BRANCH_NODE_TYPES:
                score += 1
            stack.extend(curr.children)
        return score

    # ==================== PYTHON AST EXTRACTION ====================

    def _walk_python(
        self,
        node: Node,
        source_bytes: bytes,
        entities: List[CodeEntity],
        parent_class: Optional[str],
    ) -> None:
        for child in node.children:
            target = child
            if child.type == "decorated_definition":
                definition = child.child_by_field_name("definition")
                if definition:
                    target = definition

            if target.type == "class_definition":
                name_node = target.child_by_field_name("name")
                class_name = self._get_text(name_node, source_bytes)
                body_node = target.child_by_field_name("body")
                docstring = self._extract_python_docstring(body_node, source_bytes)

                entities.append(
                    CodeEntity(
                        entity_type="class",
                        name=class_name,
                        parent_name=None,
                        signature=f"class {class_name}",
                        start_line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        docstring=docstring,
                        has_docstring=bool(docstring),
                        complexity_score=self._calculate_complexity(target),
                    )
                )
                if body_node:
                    self._walk_python(body_node, source_bytes, entities, parent_class=class_name)

            elif target.type == "function_definition":
                name_node = target.child_by_field_name("name")
                func_name = self._get_text(name_node, source_bytes)
                params_node = target.child_by_field_name("parameters")
                return_node = target.child_by_field_name("return_type")
                body_node = target.child_by_field_name("body")

                params = self._parse_python_params(params_node, source_bytes)
                return_type = self._get_text(return_node, source_bytes).lstrip("-> ").strip() or None
                docstring = self._extract_python_docstring(body_node, source_bytes)

                params_str = self._get_text(params_node, source_bytes)
                ret_str = f" -> {return_type}" if return_type else ""
                signature = f"def {func_name}{params_str}{ret_str}"

                entities.append(
                    CodeEntity(
                        entity_type="method" if parent_class else "function",
                        name=func_name,
                        parent_name=parent_class,
                        signature=signature,
                        start_line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        parameters=params,
                        return_type=return_type,
                        docstring=docstring,
                        has_docstring=bool(docstring),
                        complexity_score=self._calculate_complexity(target),
                    )
                )

    def _extract_python_docstring(
        self, body_node: Optional[Node], source_bytes: bytes
    ) -> Optional[str]:
        if not body_node or not body_node.named_children:
            return None
        first_stmt = body_node.named_children[0]
        if first_stmt.type == "expression_statement" and first_stmt.named_children:
            expr = first_stmt.named_children[0]
            if expr.type == "string":
                raw = self._get_text(expr, source_bytes).strip()
                for quote in ('"""', "'''", '"', "'"):
                    if raw.startswith(quote) and raw.endswith(quote) and len(raw) >= 2 * len(quote):
                        return raw[len(quote) : -len(quote)].strip()
        return None

    def _parse_python_params(
        self, params_node: Optional[Node], source_bytes: bytes
    ) -> List[CodeParameter]:
        params: List[CodeParameter] = []
        if not params_node:
            return params
        for child in params_node.named_children:
            if child.type == "identifier":
                name = self._get_text(child, source_bytes)
                if name not in ("self", "cls"):
                    params.append(CodeParameter(name=name))
            elif child.type == "typed_parameter":
                name_node = child.children[0] if child.children else None
                type_node = child.child_by_field_name("type")
                name = self._get_text(name_node, source_bytes)
                if name not in ("self", "cls"):
                    params.append(
                        CodeParameter(
                            name=name,
                            type_annotation=self._get_text(type_node, source_bytes) or None,
                        )
                    )
            elif child.type in ("default_parameter", "typed_default_parameter"):
                name_node = child.child_by_field_name("name")
                type_node = child.child_by_field_name("type")
                val_node = child.child_by_field_name("value")
                name = self._get_text(name_node, source_bytes)
                if name not in ("self", "cls"):
                    params.append(
                        CodeParameter(
                            name=name,
                            type_annotation=self._get_text(type_node, source_bytes) or None,
                            default_value=self._get_text(val_node, source_bytes) or None,
                        )
                    )
        return params

    # ==================== JS / TS AST EXTRACTION ====================

    def _walk_js_ts(
        self,
        node: Node,
        source_bytes: bytes,
        entities: List[CodeEntity],
        parent_class: Optional[str],
    ) -> None:
        for child in node.children:
            target = child
            comment_anchor = child
            if child.type == "export_statement":
                decl = child.child_by_field_name("declaration")
                if decl:
                    target = decl

            if target.type == "class_declaration":
                name_node = target.child_by_field_name("name")
                class_name = self._get_text(name_node, source_bytes) or "AnonymousClass"
                docstring = self._extract_jsdoc(comment_anchor, source_bytes)

                entities.append(
                    CodeEntity(
                        entity_type="class",
                        name=class_name,
                        parent_name=None,
                        signature=f"class {class_name}",
                        start_line=comment_anchor.start_point[0] + 1,
                        end_line=comment_anchor.end_point[0] + 1,
                        docstring=docstring,
                        has_docstring=bool(docstring),
                        complexity_score=self._calculate_complexity(target),
                    )
                )
                body_node = target.child_by_field_name("body")
                if body_node:
                    self._walk_js_ts(body_node, source_bytes, entities, parent_class=class_name)

            elif target.type in ("function_declaration", "method_definition"):
                name_node = target.child_by_field_name("name")
                func_name = self._get_text(name_node, source_bytes) or "anonymous"
                params_node = target.child_by_field_name("parameters")
                return_node = target.child_by_field_name("return_type")

                params = self._parse_js_params(params_node, source_bytes)
                return_type = self._get_text(return_node, source_bytes).lstrip(": ").strip() or None
                docstring = self._extract_jsdoc(comment_anchor, source_bytes)
                params_str = self._get_text(params_node, source_bytes)
                ret_str = f": {return_type}" if return_type else ""

                entities.append(
                    CodeEntity(
                        entity_type="method" if parent_class else "function",
                        name=func_name,
                        parent_name=parent_class,
                        signature=f"{func_name}{params_str}{ret_str}",
                        start_line=comment_anchor.start_point[0] + 1,
                        end_line=comment_anchor.end_point[0] + 1,
                        parameters=params,
                        return_type=return_type,
                        docstring=docstring,
                        has_docstring=bool(docstring),
                        complexity_score=self._calculate_complexity(target),
                    )
                )

            elif target.type in ("lexical_declaration", "variable_declaration"):
                for declarator in target.named_children:
                    if declarator.type == "variable_declarator":
                        val_node = declarator.child_by_field_name("value")
                        if val_node and val_node.type in ("arrow_function", "function_expression"):
                            name_node = declarator.child_by_field_name("name")
                            func_name = self._get_text(name_node, source_bytes)
                            params_node = val_node.child_by_field_name("parameters")
                            return_node = val_node.child_by_field_name("return_type")

                            params = self._parse_js_params(params_node, source_bytes)
                            return_type = (
                                self._get_text(return_node, source_bytes).lstrip(": ").strip() or None
                            )
                            docstring = self._extract_jsdoc(comment_anchor, source_bytes)
                            params_str = self._get_text(params_node, source_bytes)
                            ret_str = f": {return_type}" if return_type else ""

                            entities.append(
                                CodeEntity(
                                    entity_type="function",
                                    name=func_name,
                                    parent_name=parent_class,
                                    signature=f"const {func_name} = {params_str}{ret_str} => ...",
                                    start_line=comment_anchor.start_point[0] + 1,
                                    end_line=comment_anchor.end_point[0] + 1,
                                    parameters=params,
                                    return_type=return_type,
                                    docstring=docstring,
                                    has_docstring=bool(docstring),
                                    complexity_score=self._calculate_complexity(val_node),
                                )
                            )

    def _extract_jsdoc(self, node: Node, source_bytes: bytes) -> Optional[str]:
        prev = node.prev_named_sibling
        if prev and prev.type == "comment":
            raw = self._get_text(prev, source_bytes).strip()
            if raw.startswith("/**") and raw.endswith("*/"):
                cleaned = raw[3:-2].strip()
                lines = [line.lstrip(" *").strip() for line in cleaned.splitlines()]
                return "\n".join(line for line in lines if line)
        return None

    def _parse_js_params(
        self, params_node: Optional[Node], source_bytes: bytes
    ) -> List[CodeParameter]:
        params: List[CodeParameter] = []
        if not params_node:
            return params
        for child in params_node.named_children:
            if child.type == "identifier":
                params.append(CodeParameter(name=self._get_text(child, source_bytes)))
            elif child.type in ("required_parameter", "optional_parameter"):
                pattern = child.child_by_field_name("pattern")
                type_node = child.child_by_field_name("type")
                val_node = child.child_by_field_name("value")
                params.append(
                    CodeParameter(
                        name=self._get_text(pattern, source_bytes),
                        type_annotation=self._get_text(type_node, source_bytes).lstrip(": ").strip()
                        or None,
                        default_value=self._get_text(val_node, source_bytes) or None,
                    )
                )
        return params


ast_parser_service = ASTParserService()