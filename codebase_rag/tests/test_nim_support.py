import pytest
from pathlib import Path
from codebase_rag.parser_loader import load_parsers
from codebase_rag import constants as cs

def test_nim_parser_loading():
    parsers, queries = load_parsers()
    assert cs.SupportedLanguage.NIM in parsers
    assert cs.SupportedLanguage.NIM in queries
    
    nim_parser = parsers[cs.SupportedLanguage.NIM]
    nim_queries = queries[cs.SupportedLanguage.NIM]
    
    code = """
proc hello(name: string) =
  echo "Hello, ", name

type
  User = object
    name: string
    age: int

proc getName(u: User): string =
  u.name

import os
from strutils import split
"""
    tree = nim_parser.parse(code.encode())
    root_node = tree.root_node
    assert root_node.type == "source_file"
    
    # Test queries
    from tree_sitter import QueryCursor
    if nim_queries["functions"]:
        cursor = QueryCursor(nim_queries["functions"])
        captures = cursor.captures(root_node)
        
        from codebase_rag.language_spec import NIM_FQN_SPEC
        func_names_fqn = []
        
        # In tree-sitter 0.25, captures() returns a dict mapping capture name to list of nodes
        for capture_name, nodes in captures.items():
            if capture_name == "function":
                for node in nodes:
                    name = NIM_FQN_SPEC.get_name(node)
                    if name:
                        func_names_fqn.append(name)
        
        assert "hello" in func_names_fqn
        assert "getName" in func_names_fqn

    if nim_queries["classes"]:
        cursor = QueryCursor(nim_queries["classes"])
        captures = cursor.captures(root_node)
        class_names = []
        for capture_name, nodes in captures.items():
            if capture_name == "class":
                for node in nodes:
                    name = NIM_FQN_SPEC.get_name(node)
                    if name:
                        class_names.append(name)
        # Should find User
        assert "User" in class_names
