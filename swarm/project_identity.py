"""Lexical identity helpers for configured project identifiers."""

from __future__ import annotations

import posixpath


def project_identity(project: str) -> str:
    """Return the lexical POSIX path identity for a project identifier.

    Project identifiers are relative POSIX-style paths from the configured
    workdir. This intentionally handles only lexical aliases: dot segments,
    repeated separators, and trailing separators. It does not resolve
    symlinks, fold case, expand ``~``, or reinterpret absolute paths.

    Empty and surrounding-whitespace identifiers are outside the project
    contract. Rejecting them here keeps scheduler inputs aligned with the
    runtime dispatch validation used by status reporting.
    """
    if not isinstance(project, str) or not project or project != project.strip():
        raise ValueError("project identifier must be a non-empty, trimmed string")
    return posixpath.normpath(project)


def is_valid_project_identifier(project: object) -> bool:
    """Return whether ``project`` satisfies the shared identity boundary."""
    if not isinstance(project, str):
        return False
    try:
        project_identity(project)
    except ValueError:
        return False
    return True
