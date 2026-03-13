"""Nim language handler for AST processing.

Provides Nim-specific handling for:
- Export detection (trailing * suffix)
- Function/method name extraction
- Type declaration processing
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ... import constants as cs
from ..utils import safe_decode_text
from .base import BaseLanguageHandler

if TYPE_CHECKING:
    from ...types_defs import ASTNode


class NimHandler(BaseLanguageHandler):
    """Handler for Nim language-specific AST processing."""

    __slots__ = ()

    def extract_function_name(self, node: ASTNode) -> str | None:
        """Extract function name from Nim proc/method/func/template/macro declarations.

        Nim procs can have:
        - Simple names: proc foo() = ...
        - Exported names: proc foo*() = ...
        - Generic names: proc foo[T]() = ...
        """
        # First, try the standard 'name' field
        if (name_node := node.child_by_field_name(cs.TS_FIELD_NAME)) and name_node.text:
            name = safe_decode_text(name_node)
            return self._strip_export_marker(name)

        # For proc declarations, find identifier after 'proc' keyword
        if node.type == cs.TS_NIM_PROC_DECLARATION:
            return self._extract_proc_name(node)

        # For other function-like nodes, try generic extraction
        return self._extract_generic_nim_name(node)

    def _extract_proc_name(self, node: ASTNode) -> str | None:
        """Extract name from a proc_declaration node."""
        found_proc = False
        for child in node.children:
            if child.type == "proc":
                found_proc = True
            elif found_proc and child.type == cs.TS_IDENTIFIER:
                name = safe_decode_text(child)
                return self._strip_export_marker(name)
            elif found_proc and child.type == "postfix_expression":
                # postfix_expression is used for exported procs: getName*
                # first child is identifier
                if child.children and child.children[0].type == cs.TS_IDENTIFIER:
                    name = safe_decode_text(child.children[0])
                    return self._strip_export_marker(name)
        return None

    def _extract_generic_nim_name(self, node: ASTNode) -> str | None:
        """Extract name from other Nim declaration types."""
        # Try to find the first identifier child
        for child in node.children:
            if child.type == cs.TS_IDENTIFIER:
                name = safe_decode_text(child)
                return self._strip_export_marker(name)
            elif child.type == "postfix_expression":
                if child.children and child.children[0].type == cs.TS_IDENTIFIER:
                    name = safe_decode_text(child.children[0])
                    return self._strip_export_marker(name)
        return None

    def _strip_export_marker(self, name: str | None) -> str | None:
        """Strip trailing * used for exporting in Nim."""
        if name and name.endswith("*"):
            return name[:-1]
        return name

    def is_function_exported(self, node: ASTNode) -> bool:
        """Check if a Nim function is exported (has * suffix on name)."""
        # Check if the name has an export marker
        for child in node.children:
            if child.type == "postfix_expression":
                # postfix_expression indicates exported symbol
                return True
            if child.type == cs.TS_IDENTIFIER:
                name = safe_decode_text(child)
                if name and name.endswith("*"):
                    return True

        # Also check the name field
        if (name_node := node.child_by_field_name(cs.TS_FIELD_NAME)) and name_node.text:
            name = safe_decode_text(name_node)
            return name is not None and name.endswith("*")

        return False

    def should_process_as_impl_block(self, node: ASTNode) -> bool:
        """Check if node is a Nim type section that needs special processing."""
        return node.type == cs.TS_NIM_TYPE_DECLARATION

    def extract_impl_target(self, node: ASTNode) -> str | None:
        """Extract the type name from a type declaration.

        Nim type sections can define multiple types:
        type
          User = object
            name: string
          Admin = object of User
            permissions: seq[string]
        """
        if node.type != cs.TS_NIM_TYPE_DECLARATION:
            return None

        # Look for type_symbol_declaration children
        for child in node.children:
            if child.type == "symbol_declaration_list":
                for subchild in child.children:
                    if subchild.type == "symbol_declaration":
                        name_node = subchild.child_by_field_name(cs.TS_FIELD_NAME)
                        if name_node and name_node.text:
                            name = safe_decode_text(name_node)
                            return self._strip_export_marker(name)
            elif child.type == "type_symbol_declaration":
                name_node = child.child_by_field_name(cs.TS_FIELD_NAME)
                if name_node and name_node.text:
                    name = safe_decode_text(name_node)
                    return self._strip_export_marker(name)

        return None
