from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codebase_rag.tests.conftest import (
    get_node_names,
    get_nodes,
    get_qualified_names,
    get_relationships,
    run_updater,
)
from codebase_rag import constants as cs


@pytest.fixture
def nim_comprehensive_project(temp_repo: Path) -> Path:
    """Create a comprehensive Nim project with various syntax patterns."""
    project_path = temp_repo / "nim_test_project"
    project_path.mkdir()

    (project_path / "src").mkdir()

    # main.nim
    (project_path / "src" / "main.nim").write_text(
        encoding="utf-8",
        data="""
proc main() =
  echo "Main function"

main()
""",
    )

    # utils.nim
    (project_path / "src" / "utils.nim").write_text(
        encoding="utf-8",
        data="""
proc add*(a, b: int): int =
  return a + b

func subtract*(a, b: int): int =
  a - b

template withFile*(f: untyped, filename: string, mode: FileMode, body: untyped): untyped =
  let f = open(filename, mode)
  try:
    body
  finally:
    close(f)

macro staticRead*(filename: string): string =
  result = newLit(readFile(filename))
""",
    )

    # models.nim
    (project_path / "src" / "models.nim").write_text(
        encoding="utf-8",
        data="""
type
  User* = object
    name*: string
    age*: int

  Admin* = object of User
    permissions*: seq[string]

proc getName*(u: User): string =
  u.name

method login*(u: User) {.base.} =
  echo "User login"

method login*(a: Admin) =
  echo "Admin login"
""",
    )

    return project_path


def test_nim_basic_ingestion(
    nim_comprehensive_project: Path,
    mock_ingestor: MagicMock,
) -> None:
    """Test basic Nim ingestion including procs, funcs, and types."""
    run_updater(nim_comprehensive_project, mock_ingestor)

    # Check for functions (procs, funcs, templates, macros)
    func_names = get_node_names(mock_ingestor, cs.NodeLabel.FUNCTION)
    assert any(name.endswith(".main") for name in func_names)
    assert any(name.endswith(".add") for name in func_names)
    assert any(name.endswith(".subtract") for name in func_names)
    assert any(name.endswith(".withFile") for name in func_names)
    assert any(name.endswith(".staticRead") for name in func_names)
    assert any(name.endswith(".getName") for name in func_names)

    # Check for methods
    method_names = get_node_names(mock_ingestor, cs.NodeLabel.METHOD)
    assert any(name.endswith(".login") for name in func_names) or any(
        name.endswith(".login") for name in method_names
    )

    # Check for types (classes in our model)
    type_names = get_node_names(mock_ingestor, cs.NodeLabel.CLASS)
    assert any(name.endswith(".User") for name in type_names)
    assert any(name.endswith(".Admin") for name in type_names)


def test_nim_module_relationships(
    nim_comprehensive_project: Path,
    mock_ingestor: MagicMock,
) -> None:
    """Test that Nim modules define their functions and types."""
    run_updater(nim_comprehensive_project, mock_ingestor)

    # Check relationships from models module
    # FQN usually starts with project name
    relationships = get_relationships(mock_ingestor, cs.RelationshipType.DEFINES)

    models_qn_suffix = "src.models"
    models_defines = [
        rel
        for rel in relationships
        if isinstance(rel.args[0][2], str)
        and rel.args[0][2].endswith(models_qn_suffix)  # source qualified_name
    ]

    defined_names = [rel.args[2][2].split(".")[-1] for rel in models_defines]
    assert "User" in defined_names
    assert "Admin" in defined_names
    assert "getName" in defined_names
    assert "login" in defined_names


def test_nim_imports(
    temp_repo: Path,
    mock_ingestor: MagicMock,
) -> None:
    """Test Nim import ingestion."""
    project_path = temp_repo / "nim_import_test"
    project_path.mkdir()

    (project_path / "lib.nim").write_text('proc libFunc*() = echo "lib"')
    (project_path / "app.nim").write_text("""
import lib
import os, strutils
from math import sqrt

libFunc()
""")

    run_updater(project_path, mock_ingestor)

    # Check for IMPORTS relationship
    relationships = get_relationships(mock_ingestor, cs.RelationshipType.IMPORTS)

    # app.nim imports lib.nim
    # Note: Qualified names depend on project structure
    import_pairs = [(rel.args[0][2], rel.args[2][2]) for rel in relationships]

    # We expect app to import lib
    # FQN might be nim_import_test.app -> nim_import_test.lib
    assert any("app" in str(p[0]) and "lib" in str(p[1]) for p in import_pairs)


def test_nim_import_edge_cases(
    temp_repo: Path,
    mock_ingestor: MagicMock,
) -> None:
    """Test Nim import edge cases: path imports, aliases, include statements."""
    project_path = temp_repo / "nim_import_edge_test"
    project_path.mkdir()

    # Create subdirectory for path import
    (project_path / "pkg").mkdir()
    (project_path / "pkg" / "submodule.nim").write_text('proc subFunc*() = echo "sub"')

    # Create lib for alias test
    (project_path / "longlibname.nim").write_text('proc aliasedFunc*() = echo "alias"')

    # Create include file
    (project_path / "helpers.nim").write_text('proc helperProc*() = echo "helper"')

    (project_path / "app.nim").write_text("""
import pkg/submodule
import longlibname as ll
include helpers

subFunc()
ll.aliasedFunc()
helperProc()
""")

    run_updater(project_path, mock_ingestor)

    # Check for IMPORTS relationship
    relationships = get_relationships(mock_ingestor, cs.RelationshipType.IMPORTS)

    import_pairs = [(rel.args[0][2], rel.args[2][2]) for rel in relationships]

    # Should have imports for submodule, longlibname (via alias ll), and helpers (via include)
    imported_targets = [str(p[1]) for p in import_pairs]

    # Check that we have imports from app
    app_imports = [p for p in import_pairs if "app" in str(p[0])]
    assert len(app_imports) >= 2  # At least submodule and longlibname


def test_nim_cross_file_ufcs_calls(
    temp_repo: Path,
    mock_ingestor: MagicMock,
) -> None:
    """Test Nim cross-file UFCS calls resolution."""
    project_path = temp_repo / "nim_ufcs_test"
    project_path.mkdir()

    (project_path / "models.nim").write_text("""
type
  User* = object
    name*: string

proc getName*(u: User): string =
  u.name
""")

    (project_path / "app.nim").write_text("""
import models

proc run() =
  var u: User
  echo u.getName()
""")

    run_updater(project_path, mock_ingestor)

    # Check for CALLS relationship
    relationships = get_relationships(mock_ingestor, cs.RelationshipType.CALLS)

    call_pairs = [(rel.args[0][2], rel.args[2][2]) for rel in relationships]

    # app.run calls models.getName
    # FQN should be nim_ufcs_test.app.run -> nim_ufcs_test.models.getName
    assert any("run" in str(p[0]) and "getName" in str(p[1]) for p in call_pairs)
