#!/usr/bin/env python3
"""Verify that an exact remote release tag still resolves to one commit."""

from __future__ import annotations

import argparse
import re
import subprocess


_TAG = re.compile(
    r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*)?$"
)
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


class ReleaseRefError(ValueError):
    """The remote release ref is absent, malformed, ambiguous, or moved."""


def parse_remote_ref(output: str, tag: str) -> str:
    if not _TAG.fullmatch(tag):
        raise ReleaseRefError("release tag must use canonical vMAJOR.MINOR.PATCH format")
    direct_name = f"refs/tags/{tag}"
    peeled_name = f"{direct_name}^{{}}"
    refs: dict[str, list[str]] = {}
    for raw_line in output.splitlines():
        parts = raw_line.split("\t")
        if len(parts) != 2 or not _COMMIT.fullmatch(parts[0]):
            raise ReleaseRefError("git ls-remote returned malformed release ref data")
        refs.setdefault(parts[1], []).append(parts[0])
    if set(refs) - {direct_name, peeled_name}:
        raise ReleaseRefError("git ls-remote returned an unexpected release ref")
    if len(refs.get(direct_name, [])) != 1 or len(refs.get(peeled_name, [])) > 1:
        raise ReleaseRefError("remote release tag is missing or ambiguous")
    return (refs.get(peeled_name) or refs[direct_name])[0]


def resolve_remote_ref(remote: str, tag: str) -> str:
    result = subprocess.run(
        [
            "git",
            "ls-remote",
            "--exit-code",
            remote,
            f"refs/tags/{tag}",
            f"refs/tags/{tag}^{{}}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ReleaseRefError(
            f"could not resolve exact remote release tag {tag}: {result.stderr.strip()}"
        )
    return parse_remote_ref(result.stdout, tag)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()

    if not _COMMIT.fullmatch(args.expected_commit):
        raise ReleaseRefError("expected commit must be a lowercase 40-character SHA")
    actual = resolve_remote_ref(args.remote, args.tag)
    if actual != args.expected_commit:
        raise ReleaseRefError(
            f"remote release tag {args.tag} resolves to {actual}, expected {args.expected_commit}"
        )
    print(f"Remote release tag {args.tag} resolves to {actual}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
