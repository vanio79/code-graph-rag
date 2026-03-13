from __future__ import annotations

from typing import TYPE_CHECKING

from ...types_defs import ASTNode
from .ast_analyzer import NimAstAnalyzerMixin

if TYPE_CHECKING:
    from pathlib import Path
    from ...types_defs import FunctionRegistryTrieProtocol, LanguageQueries, SimpleNameLookup
    from ..import_processor import ImportProcessor
    from ..factory import ASTCacheProtocol


class NimTypeInferenceEngine(NimAstAnalyzerMixin):
    __slots__ = (
        "import_processor",
        "function_registry",
        "project_name",
        "queries",
        "module_qn_to_file_path",
        "ast_cache",
    )

    def __init__(
        self,
        import_processor: ImportProcessor,
        function_registry: FunctionRegistryTrieProtocol,
        project_name: str,
        queries: dict[SupportedLanguage, LanguageQueries],
        module_qn_to_file_path: dict[str, Path],
        ast_cache: ASTCacheProtocol,
    ):
        self.import_processor = import_processor
        self.function_registry = function_registry
        self.project_name = project_name
        self.queries = queries
        self.module_qn_to_file_path = module_qn_to_file_path
        self.ast_cache = ast_cache

    def _get_docstring(self, node: ASTNode) -> str | None:
        return None

    def _extract_decorators(self, node: ASTNode) -> list[str]:
        return []

    def build_local_variable_type_map(
        self, caller_node: ASTNode, module_qn: str
    ) -> dict[str, str]:
        local_var_types: dict[str, str] = {}
        try:
            self._traverse_single_pass(caller_node, local_var_types, module_qn)
        except Exception as e:
            logger.debug(f"Failed to build Nim variable map: {e}")

        return local_var_types
