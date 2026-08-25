"""Lexical identity helpers for configured project identifiers."""

from __future__ import annotations

import posixpath


def project_identity(project: str) -> str:
    """Return the lexical POSIX path identity for a project identifier.

    Project identifiers are relative POSIX-style paths from the configured
    workdir. This intentionally handles only lexical aliases: dot segments,
    repeated separators, and trailing separators. It does not resolve
    symlinks, fold case, expand ``~``, or reinterpret absolute paths.
    """
    return posixpath.normpath(project)
