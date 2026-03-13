from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from loguru import logger
from tree_sitter import Node

from ... import constants as cs
from ..utils import safe_decode_text

if TYPE_CHECKING:
    from pathlib import Path
    from ..factory import ASTCacheProtocol
    from ..import_processor import ImportProcessor
    from ...types_defs import FunctionRegistryTrieProtocol, LanguageQueries


class NimAstAnalyzerMixin:
    __slots__ = ()
    queries: dict[cs.SupportedLanguage, LanguageQueries]
    module_qn_to_file_path: dict[str, Path]
    ast_cache: ASTCacheProtocol
    import_processor: ImportProcessor
    function_registry: FunctionRegistryTrieProtocol

    def _resolve_class_name(self, class_name: str, module_qn: str) -> str | None:
        from ..py.utils import resolve_class_name

        return resolve_class_name(
            class_name, module_qn, self.import_processor, self.function_registry
        )

    def _get_docstring(self, node: Node) -> str | None:
        # (H) Nim docstrings are often ## comments inside the body or after the proc header
        # For now, return None as a placeholder
        return None

    def _extract_decorators(self, node: Node) -> list[str]:
        # (H) Nim uses pragmas {. .} which are similar to decorators
        # They are usually children of the proc declaration
        pragmas = []
        for child in node.children:
            if child.type == "pragma":
                # pragma contains expression_list
                for subchild in child.children:
                    if subchild.type == "expression_list":
                        for expr in subchild.children:
                            if expr.type == cs.TS_IDENTIFIER:
                                pragmas.append(safe_decode_text(expr))
        return pragmas

    def _traverse_single_pass(
        self, node: Node, local_var_types: dict[str, str], module_qn: str
    ) -> None:
        """Basic implementation for Nim traversal."""
        stack: list[Node] = [node]
        while stack:
            current = stack.pop()

            # Handle variable declarations (let, var, const sections)
            if current.type in ("var_section", "let_section", "const_section"):
                for child in current.children:
                    if child.type == "variable_declaration":
                        # variable_declaration has names (symbol_declaration_list), optional type, and value
                        names = []
                        sym_list = child.child_by_field_name("names")
                        if sym_list:
                            for sym in sym_list.children:
                                if sym.type == "symbol_declaration":
                                    name_node = sym.child_by_field_name("name")
                                    if name_node:
                                        name = safe_decode_text(name_node)
                                        if name:
                                            names.append(name)

                        type_node = child.child_by_field_name("type")
                        var_type = None
                        if type_node:
                            var_type = safe_decode_text(type_node)

                        # If no explicit type, try to infer from value
                        if not var_type:
                            value_node = child.child_by_field_name("value")
                            if value_node:
                                # Very basic inference for 'new'
                                if value_node.type == "call":
                                    func_node = value_node.child_by_field_name("name")
                                    if (
                                        func_node
                                        and safe_decode_text(func_node) == "new"
                                    ):
                                        # new(User) -> User
                                        args = value_node.child_by_field_name(
                                            "arguments"
                                        )
                                        if args and len(args.children) >= 2:
                                            first_arg = args.children[
                                                1
                                            ]  # [0] is '(', [1] is first arg
                                            var_type = safe_decode_text(first_arg)

                        if var_type:
                            resolved_type = (
                                self._resolve_class_name(var_type, module_qn)
                                or var_type
                            )
                            for name in names:
                                local_var_types[name] = resolved_type

            stack.extend(reversed(current.children))
