from __future__ import annotations

import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from app.core.logging import get_logger
from app.services.analysis.ast_parser import (
    ASTDiffImpact,
    ClassSymbol,
    FunctionSymbol,
    ImportSymbol,
    ModuleASTSummary,
)
from app.services.analysis.diff_parser import FileDiff

logger = get_logger(__name__)


class TypeScriptASTParser:
    """
    Parses TypeScript and TSX source code using Tree-sitter to extract syntax symbols
    and determine diff impact.
    """

    def __init__(self):
        self._language = Language(tree_sitter_typescript.language_typescript())
        self._parser = Parser(self._language)

    def parse_source(self, source_code: str, file_path: str = "") -> ModuleASTSummary:
        if not source_code or not source_code.strip():
            return ModuleASTSummary(file_path=file_path)

        source_bytes = source_code.encode("utf-8")
        tree = self._parser.parse(source_bytes)
        root = tree.root_node

        summary = ModuleASTSummary(
            file_path=file_path,
            has_parse_errors=root.has_error,
        )

        self._extract_symbols(root, source_bytes, summary)
        return summary

    def _extract_symbols(
        self,
        node: Node,
        source_bytes: bytes,
        summary: ModuleASTSummary,
        current_class: str | None = None,
        is_exported: bool = False,
    ) -> None:
        node_type = node.type

        # Check export wrappers
        if node_type == "export_statement":
            for child in node.children:
                if child.type != "export":
                    self._extract_symbols(
                        child, source_bytes, summary, current_class=current_class, is_exported=True
                    )
            return

        # Classes
        if node_type == "class_declaration":
            name_node = node.child_by_field_name("name")
            class_name = (
                source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")
                if name_node
                else "AnonymousClass"
            )

            class_sym = ClassSymbol(
                name=class_name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                is_public=is_exported or not class_name.startswith("_"),
            )
            summary.classes.append(class_sym)

            body_node = node.child_by_field_name("body")
            if body_node:
                for child in body_node.children:
                    self._extract_symbols(child, source_bytes, summary, current_class=class_name)
            return

        # Methods inside classes
        if node_type == "method_definition":
            name_node = node.child_by_field_name("name")
            method_name = (
                source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")
                if name_node
                else "anonymous"
            )

            # Check accessibility modifier (private/public/protected)
            is_private = False
            for child in node.children:
                if child.type == "accessibility_modifier":
                    mod_text = source_bytes[child.start_byte : child.end_byte].decode("utf-8")
                    if mod_text == "private":
                        is_private = True
                        break

            func_sym = FunctionSymbol(
                name=method_name,
                parent_class=current_class,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                is_public=not is_private and not method_name.startswith("_"),
            )
            summary.functions.append(func_sym)
            if current_class:
                for cls in summary.classes:
                    if cls.name == current_class:
                        cls.methods.append(func_sym)
                        break
            return

        # Standalone Functions
        if node_type == "function_declaration":
            name_node = node.child_by_field_name("name")
            func_name = (
                source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")
                if name_node
                else "anonymous"
            )

            func_sym = FunctionSymbol(
                name=func_name,
                parent_class=current_class,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                is_public=is_exported or not func_name.startswith("_"),
            )
            summary.functions.append(func_sym)
            return

        # Arrow Functions assigned to variables (const fn = () => {})
        if node_type == "lexical_declaration":
            for decl in node.children:
                if decl.type == "variable_declarator":
                    name_node = decl.child_by_field_name("name")
                    value_node = decl.child_by_field_name("value")
                    if name_node and value_node and value_node.type == "arrow_function":
                        fn_name = source_bytes[name_node.start_byte : name_node.end_byte].decode(
                            "utf-8"
                        )
                        func_sym = FunctionSymbol(
                            name=fn_name,
                            start_line=decl.start_point[0] + 1,
                            end_line=decl.end_point[0] + 1,
                            is_public=is_exported or not fn_name.startswith("_"),
                        )
                        summary.functions.append(func_sym)
            return

        # Imports: import { x } from 'y'
        if node_type == "import_statement":
            source_node = node.child_by_field_name("source")
            if source_node:
                mod_name = (
                    source_bytes[source_node.start_byte : source_node.end_byte]
                    .decode("utf-8")
                    .strip("'\"")
                )
                summary.imports.append(ImportSymbol(module=mod_name))

        # Recurse children
        for child in node.children:
            self._extract_symbols(
                child,
                source_bytes,
                summary,
                current_class=current_class,
                is_exported=is_exported,
            )

    def analyze_diff_impact(
        self,
        base_source: str | None,
        head_source: str | None,
        file_diff: FileDiff,
    ) -> ASTDiffImpact:
        file_path = file_diff.file_path
        impact = ASTDiffImpact(file_path=file_path)

        base_summary = self.parse_source(base_source or "", file_path) if base_source else None
        head_summary = self.parse_source(head_source or "", file_path) if head_source else None

        base_funcs = {f.qualified_name: f for f in (base_summary.functions if base_summary else [])}
        head_funcs = {f.qualified_name: f for f in (head_summary.functions if head_summary else [])}

        modified_lines = file_diff.modified_head_lines

        for name, h_func in head_funcs.items():
            func_line_range = set(range(h_func.start_line, h_func.end_line + 1))
            intersects = bool(func_line_range & modified_lines)

            if name not in base_funcs:
                impact.functions_added.append(h_func)
                if h_func.is_public:
                    impact.public_api_changes_count += 1
            elif intersects:
                impact.functions_modified.append(h_func)
                if h_func.is_public:
                    impact.public_api_changes_count += 1

        for name, b_func in base_funcs.items():
            if name not in head_funcs:
                impact.functions_deleted.append(b_func)
                if b_func.is_public:
                    impact.public_api_changes_count += 1

        return impact


ts_ast_parser = TypeScriptASTParser()
