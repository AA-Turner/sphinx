from __future__ import annotations

import hashlib
import os.path
from typing import Any

from sphinx.util._pathlib import _StrPath


class FilenameUniqDict(dict[_StrPath, tuple[set[str], str]]):
    """
    A dictionary that automatically generates unique names for its keys,
    interpreted as filenames, and keeps track of a set of docnames they
    appear in.  Used for images and downloadable files in the environment.
    """

    def __init__(self) -> None:
        self._existing: set[str] = set()

    def add_file(self, docname: str, newfile: str | os.PathLike[str]) -> str:
        new_file = _StrPath(newfile).resolve()
        if new_file in self:
            docnames, unique_name = self[new_file]
            docnames.add(docname)
            return unique_name
        unique_name = new_file.name
        base = new_file.stem
        ext = new_file.suffix
        i = 0
        while unique_name in self._existing:
            i += 1
            unique_name = f'{base}{i}{ext}'
        self[new_file] = ({docname}, unique_name)
        self._existing.add(unique_name)
        return unique_name

    def purge_doc(self, docname: str) -> None:
        for filename, (docs, unique) in list(self.items()):
            docs.discard(docname)
            if not docs:
                del self[filename]
                self._existing.discard(unique)

    def merge_other(
        self, docnames: set[str], other: dict[_StrPath, tuple[set[str], Any]]
    ) -> None:
        for filename, (docs, _unique) in other.items():
            for doc in docs & set(docnames):
                self.add_file(doc, filename)

    def __getstate__(self) -> set[str]:
        return self._existing

    def __setstate__(self, state: set[str]) -> None:
        self._existing = state


class DownloadFiles(dict[str, tuple[set[str], str]]):
    """A special dictionary for download files.

    .. important:: This class would be refactored in nearly future.
                   Hence don't hack this directly.
    """

    def add_file(self, docname: str, filename: str) -> str:
        if filename not in self:
            digest = hashlib.md5(filename.encode(), usedforsecurity=False).hexdigest()
            dest = f'{digest}/{os.path.basename(filename)}'
            self[filename] = (set(), dest)

        self[filename][0].add(docname)
        return self[filename][1]

    def purge_doc(self, docname: str) -> None:
        for filename, (docs, _dest) in list(self.items()):
            docs.discard(docname)
            if not docs:
                del self[filename]

    def merge_other(
        self, docnames: set[str], other: dict[str, tuple[set[str], Any]]
    ) -> None:
        for filename, (docs, _dest) in other.items():
            for docname in docs & set(docnames):
                self.add_file(docname, filename)
