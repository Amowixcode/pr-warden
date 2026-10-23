from __future__ import annotations

import pytest

from core.test_files import filenames_in_diff, find_test_files, is_test_file


@pytest.mark.parametrize(
    "path",
    [
        "tests/unit/test_api.py",
        "test/helpers.js",
        "src/__tests__/Button.js",
        "packages/react/src/__tests__/ReactFoo-test.js",
        "web/Button.test.tsx",
        "web/Button.spec.ts",
        "pkg/client_test.go",
        "test_utils.py",
        "pkg/test_utils.py",
    ],
)
def test_is_test_file_true(path: str) -> None:
    assert is_test_file(path)


@pytest.mark.parametrize(
    "path",
    [
        "src/app.py",
        "core/test_files.py.bak",
        "src/latest.py",
        "docs/testing.md",
        "src/contest/main.py",
        "frontend/src/Button.tsx",
        "src/attest_helper.py",
    ],
)
def test_is_test_file_false(path: str) -> None:
    assert not is_test_file(path)


def test_find_test_files_keeps_order_and_filters() -> None:
    names = ["src/a.py", "tests/test_a.py", "src/b.test.ts", "README.md"]

    assert find_test_files(names) == ["tests/test_a.py", "src/b.test.ts"]


def test_filenames_in_diff_reads_diff_headers() -> None:
    diff = (
        "diff --git a/src/a.py b/src/a.py\r\n@@ -1 +1 @@\r\n+x\r\n"
        "diff --git a/tests/test_a.py b/tests/test_a.py\n+y\n"
    )

    assert filenames_in_diff(diff) == ["src/a.py", "tests/test_a.py"]


def test_filenames_in_diff_empty() -> None:
    assert filenames_in_diff("") == []
