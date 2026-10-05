"""Path sandboxing: every file tool must stay inside ALLOWED_FOLDERS."""

import os

import pytest

from file_ops import FileOperations


@pytest.fixture
def sandbox(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    (allowed / "notes.txt").write_text("hello from inside the sandbox")
    (allowed / "sub").mkdir()

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("top secret")

    return FileOperations([str(allowed)]), allowed, outside


def test_path_inside_allowed_folder_is_accepted(sandbox):
    ops, allowed, _ = sandbox
    ok, resolved, err = ops._validate_path(str(allowed / "notes.txt"))
    assert ok and err == ""
    assert resolved == os.path.realpath(allowed / "notes.txt")


def test_allowed_folder_itself_is_accepted(sandbox):
    ops, allowed, _ = sandbox
    assert ops._is_path_allowed(str(allowed))


def test_dotdot_traversal_is_rejected(sandbox):
    ops, allowed, _ = sandbox
    ok, _, err = ops._validate_path(str(allowed / ".." / "outside" / "secret.txt"))
    assert not ok
    assert "outside allowed folders" in err


def test_symlink_escaping_the_sandbox_is_rejected(sandbox):
    ops, allowed, outside = sandbox
    link = allowed / "innocent_link"
    link.symlink_to(outside / "secret.txt")
    ok, _, _ = ops._validate_path(str(link))
    assert not ok


def test_sibling_folder_sharing_a_prefix_is_rejected(sandbox, tmp_path):
    # "/x/allowed-evil" starts with the string "/x/allowed" but is not inside it.
    ops, _, _ = sandbox
    evil = tmp_path / "allowed-evil"
    evil.mkdir()
    (evil / "loot.txt").write_text("x")
    assert not ops._is_path_allowed(str(evil / "loot.txt"))


def test_empty_path_is_rejected(sandbox):
    ops, _, _ = sandbox
    ok, _, err = ops._validate_path("")
    assert not ok and err == "Path is empty."


def test_nonexistent_allowed_folders_are_skipped(tmp_path):
    ops = FileOperations([str(tmp_path / "does-not-exist")])
    assert ops.allowed_folders == []
    assert not ops._is_path_allowed(str(tmp_path))


def test_root_allows_full_access(tmp_path):
    ops = FileOperations(["/"])
    assert ops._is_path_allowed(str(tmp_path))


def test_list_directory_outside_sandbox_returns_error(sandbox):
    ops, _, outside = sandbox
    result = ops.list_directory(str(outside))
    assert "error" in result and "Access denied" in result["error"]


def test_list_directory_hides_dotfiles(sandbox):
    ops, allowed, _ = sandbox
    (allowed / ".hidden").write_text("x")
    names = [item["name"] for item in ops.list_directory(str(allowed))["items"]]
    assert "notes.txt" in names and "sub" in names
    assert ".hidden" not in names


def test_read_preview_inside_sandbox(sandbox):
    ops, allowed, _ = sandbox
    result = ops.read_file_preview(str(allowed / "notes.txt"))
    assert "error" not in result
    assert "hello from inside the sandbox" in str(result)


@pytest.mark.parametrize("method,extra", [
    ("read_file_preview", {}),
    ("fetch_file", {}),
    ("delete_file", {}),
    ("write_file", {"content": "pwned"}),
    ("append_to_file", {"content": "pwned"}),
])
def test_every_file_tool_refuses_paths_outside_sandbox(sandbox, method, extra):
    ops, allowed, outside = sandbox
    target = allowed / ".." / "outside" / "secret.txt"
    result = getattr(ops, method)(path=str(target), **extra)
    assert "error" in result
    # The file outside the sandbox must be untouched.
    assert (outside / "secret.txt").read_text() == "top secret"


def test_create_file_outside_sandbox_does_not_create_it(sandbox):
    ops, allowed, outside = sandbox
    result = ops.create_file(str(allowed / ".." / "outside" / "new.txt"), "x")
    assert "error" in result
    assert not (outside / "new.txt").exists()


def test_write_then_read_round_trip_inside_sandbox(sandbox):
    ops, allowed, _ = sandbox
    target = allowed / "sub" / "out.txt"
    assert "error" not in ops.create_file(str(target), "first")
    assert "error" not in ops.append_to_file(str(target), " second")
    assert target.read_text().startswith("first")
    assert "second" in target.read_text()
    assert "error" not in ops.delete_file(str(target))
    assert not target.exists()
