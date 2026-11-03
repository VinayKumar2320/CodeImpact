from __future__ import annotations

from dataclasses import dataclass, field

import tree_sitter_python
from tree_sitter import Language, Node, Parser

from app.core.logging import get_logger
from app.services.analysis.diff_parser import FileDiff

logger = get_logger(__name__)


@dataclass
class FunctionSymbol:
    name: str
    parent_class: str | None = None
    start_line: int = 1
    end_line: int = 1
    parameters: list[str] = field(default_factory=list)
    is_public: bool = True
    is_async: bool = False
    decorators: list[str] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        if self.parent_class:
            return f"{self.parent_class}.{self.name}"
        return self.name


@dataclass
class ClassSymbol:
    name: str
    start_line: int = 1
    end_line: int = 1
    base_classes: list[str] = field(default_factory=list)
    is_public: bool = True
    methods: list[FunctionSymbol] = field(default_factory=list)


@dataclass
class ImportSymbol:
    module: str
    names: list[str] = field(default_factory=list)
    alias: str | None = None
    is_wildcard: bool = False


@dataclass
class CallSymbol:
    caller_name: str
    callee_name: str
    line_number: int


@dataclass
class ModuleASTSummary:
    file_path: str
    functions: list[FunctionSymbol] = field(default_factory=list)
    classes: list[ClassSymbol] = field(default_factory=list)
    imports: list[ImportSymbol] = field(default_factory=list)
    calls: list[CallSymbol] = field(default_factory=list)
    has_parse_errors: bool = False


@dataclass
class ASTDiffImpact:
    file_path: str
    functions_modified: list[FunctionSymbol] = field(default_factory=list)
    functions_added: list[FunctionSymbol] = field(default_factory=list)
    functions_deleted: list[FunctionSymbol] = field(default_factory=list)
    classes_modified: list[ClassSymbol] = field(default_factory=list)
    public_api_changes_count: int = 0


class PythonASTParser:
    """
    Parses Python source code using Tree-sitter to extract syntax symbols,
    call relationships, and map diff modifications to AST nodes.
    """

    def __init__(self):
        self._language = Language(tree_sitter_python.language())
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
        current_function: str | None = None,
    ) -> None:
        """
        Recursively extract functions, classes, imports, and calls from Tree-sitter node.
        """
        node_type = node.type

        # Handle Import statements: import x, from x import y
        if node_type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    mod_name = source_bytes[child.start_byte : child.end_byte].decode("utf-8")
                    summary.imports.append(ImportSymbol(module=mod_name))
        elif node_type == "import_from_statement":
            module_name = ""
            imported_names: list[str] = []
            is_wildcard = False

            for child in node.children:
                if child.type in ("dotted_name", "relative_import"):
                    module_name = source_bytes[child.start_byte : child.end_byte].decode("utf-8")
                elif child.type == "wildcard_import":
                    is_wildcard = True
                elif child.type == "dotted_name" and module_name:
                    imported_names.append(
                        source_bytes[child.start_byte : child.end_byte].decode("utf-8")
                    )
                elif child.type == "aliased_import":
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        imported_names.append(
                            source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")
                        )

            if module_name:
                summary.imports.append(
                    ImportSymbol(
                        module=module_name,
                        names=imported_names,
                        is_wildcard=is_wildcard,
                    )
                )

        # Handle Classes
        elif node_type == "class_definition":
            name_node = node.child_by_field_name("name")
            class_name = (
                source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")
                if name_node
                else "AnonymousClass"
            )

            # Base classes
            bases: list[str] = []
            superclasses_node = node.child_by_field_name("superclasses")
            if superclasses_node:
                for child in superclasses_node.children:
                    if child.type in ("identifier", "attribute"):
                        bases.append(
                            source_bytes[child.start_byte : child.end_byte].decode("utf-8")
                        )

            is_public = not class_name.startswith("_")
            class_sym = ClassSymbol(
                name=class_name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                base_classes=bases,
                is_public=is_public,
            )
            summary.classes.append(class_sym)

            # Traverse class body with current_class context
            body_node = node.child_by_field_name("body")
            if body_node:
                for child in body_node.children:
                    self._extract_symbols(child, source_bytes, summary, current_class=class_name)
            return

        # Handle Functions (normal & decorated)
        elif node_type in ("function_definition", "async_function_definition"):
            name_node = node.child_by_field_name("name")
            func_name = (
                source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")
                if name_node
                else "anonymous"
            )

            # Parameters
            params: list[str] = []
            params_node = node.child_by_field_name("parameters")
            if params_node:
                for p in params_node.children:
                    if p.type in ("identifier", "typed_parameter", "default_parameter"):
                        p_name_node = p.child_by_field_name("name") or p
                        param_name = source_bytes[
                            p_name_node.start_byte : p_name_node.end_byte
                        ].decode("utf-8")
                        if param_name not in (",", "(", ")"):
                            params.append(param_name)

            # Decorators (checked from parent if decorated_definition)
            decorators: list[str] = []
            if node.parent and node.parent.type == "decorated_definition":
                for child in node.parent.children:
                    if child.type == "decorator":
                        decorators.append(
                            source_bytes[child.start_byte : child.end_byte]
                            .decode("utf-8")
                            .removeprefix("@")
                            .strip()
                        )

            # Public if not starting with '_' or is dunder method
            is_public = not func_name.startswith("_") or (
                func_name.startswith("__") and func_name.endswith("__")
            )

            func_sym = FunctionSymbol(
                name=func_name,
                parent_class=current_class,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                parameters=params,
                is_public=is_public,
                is_async=(node_type == "async_function_definition"),
                decorators=decorators,
            )
            summary.functions.append(func_sym)
            if current_class:
                for cls in summary.classes:
                    if cls.name == current_class:
                        cls.methods.append(func_sym)
                        break

            # Traverse function body with current_function context to capture calls
            body_node = node.child_by_field_name("body")
            if body_node:
                for child in body_node.children:
                    self._extract_symbols(
                        child,
                        source_bytes,
                        summary,
                        current_class=current_class,
                        current_function=func_sym.qualified_name,
                    )
            return

        elif node_type == "decorated_definition":
            # Pass through to inner function or class
            for child in node.children:
                if child.type in (
                    "function_definition",
                    "async_function_definition",
                    "class_definition",
                ):
                    self._extract_symbols(child, source_bytes, summary, current_class=current_class)
            return

        # Handle Function Invocations / Calls
        elif node_type == "call" and current_function:
            fn_node = node.child_by_field_name("function")
            if fn_node:
                callee = source_bytes[fn_node.start_byte : fn_node.end_byte].decode("utf-8")
                # Clean attribute chain e.g. self.method -> method or retain call
                summary.calls.append(
                    CallSymbol(
                        caller_name=current_function,
                        callee_name=callee,
                        line_number=node.start_point[0] + 1,
                    )
                )

        # Traverse remaining children
        for child in node.children:
            self._extract_symbols(
                child,
                source_bytes,
                summary,
                current_class=current_class,
                current_function=current_function,
            )

    def analyze_diff_impact(
        self,
        base_source: str | None,
        head_source: str | None,
        file_diff: FileDiff,
    ) -> ASTDiffImpact:
        """
        Compare base and head ASTs against modified line intervals in FileDiff.
        """
        file_path = file_diff.file_path
        impact = ASTDiffImpact(file_path=file_path)

        base_summary = self.parse_source(base_source or "", file_path) if base_source else None
        head_summary = self.parse_source(head_source or "", file_path) if head_source else None

        base_funcs = {f.qualified_name: f for f in (base_summary.functions if base_summary else [])}
        head_funcs = {f.qualified_name: f for f in (head_summary.functions if head_summary else [])}

        modified_lines = file_diff.modified_head_lines

        # Added & Modified functions
        for name, h_func in head_funcs.items():
            # Check if any modified line falls within function scope
            func_line_range = set(range(h_func.start_line, h_func.end_line + 1))
            intersects = bool(func_line_range & modified_lines)

            if name not in base_funcs:
                # Newly added function
                impact.functions_added.append(h_func)
                if h_func.is_public:
                    impact.public_api_changes_count += 1
            elif intersects:
                # Modified existing function
                impact.functions_modified.append(h_func)
                if h_func.is_public:
                    impact.public_api_changes_count += 1

        # Deleted functions (in base but not in head)
        for name, b_func in base_funcs.items():
            if name not in head_funcs:
                impact.functions_deleted.append(b_func)
                if b_func.is_public:
                    impact.public_api_changes_count += 1

        # Classes modified
        if head_summary:
            base_classes = {c.name: c for c in (base_summary.classes if base_summary else [])}
            for h_cls in head_summary.classes:
                cls_lines = set(range(h_cls.start_line, h_cls.end_line + 1))
                if cls_lines & modified_lines:
                    impact.classes_modified.append(h_cls)
                    if h_cls.name not in base_classes and h_cls.is_public:
                        impact.public_api_changes_count += 1

        return impact


python_ast_parser = PythonASTParser()
