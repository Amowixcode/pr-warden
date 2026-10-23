from __future__ import annotations

import re
from pathlib import PurePosixPath

_TEST_DIRS = {"test", "tests", "__tests__"}
_DIFF_FILE_HEADER = re.compile(r"^diff --git a/(.+) b/\1$", re.MULTILINE)
_TEST_NAME = re.compile(r"(\.(test|spec)\.|_test\.|^test_.*\.py$)")


def is_test_file(filename: str) -> bool:
    """True if a path looks like a test file: a test/tests/__tests__ directory, *.test.*,
    *.spec.*, *_test.*, or test_*.py.
    """
    path = PurePosixPath(filename)
    return any(part in _TEST_DIRS for part in path.parts[:-1]) or bool(_TEST_NAME.search(path.name))


def find_test_files(filenames: list[str]) -> list[str]:
    """The subset of filenames that are test files, in their original order."""
    return [name for name in filenames if is_test_file(name)]


def filenames_in_diff(diff: str) -> list[str]:
    """Filenames from the ``diff --git a/X b/X`` headers of a combined diff, in order."""
    return _DIFF_FILE_HEADER.findall(diff.replace("\r", ""))
