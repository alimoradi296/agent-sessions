"""Measure when transcript-like file edits can be matched to local Git history.

All repositories and file contents are fictional and temporary. This measures
Git object matching only; it does not establish archive timing, a clean session
baseline, user intent, dependency state, or a valid regression oracle.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


BEFORE = "def count_valid(rows):\n    return 1\n"
AFTER = "def count_valid(rows):\n    return 2\n"
RELATIVE = "parser.py"


def _git(repo: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "Synthetic",
        "GIT_AUTHOR_EMAIL": "synthetic@example.invalid",
        "GIT_COMMITTER_NAME": "Synthetic",
        "GIT_COMMITTER_EMAIL": "synthetic@example.invalid",
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
    }
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args], cwd=repo,
        env=env, check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _repo(root: Path, name: str, *, readme: str = "base\n") -> tuple[Path, str]:
    repo = root / name
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / RELATIVE).write_text(BEFORE, encoding="utf-8")
    (repo / "README.md").write_text(readme, encoding="utf-8")
    return repo, _commit(repo, "synthetic base")


def _changed_paths(repo: Path, parent: str, commit: str) -> set[str]:
    value = _git(repo, "diff", "--name-only", parent, commit)
    return set(value.splitlines()) if value else set()


def _blob(repo: Path, revision: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"], cwd=repo,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
        capture_output=True, text=True,
    )
    return result.stdout if result.returncode == 0 else None


def _find_file_transition(repo: Path, path: str, before: str, after: str) -> dict:
    matches = []
    commits = _git(repo, "rev-list", "--all").splitlines()
    for commit in commits:
        fields = _git(repo, "rev-list", "--parents", "-n", "1", commit).split()
        for parent in fields[1:]:
            if _blob(repo, parent, path) != before or _blob(repo, commit, path) != after:
                continue
            changed = _changed_paths(repo, parent, commit)
            matches.append({
                "parent": parent,
                "commit": commit,
                "changed_paths_count": len(changed),
                "changed_paths_are_exact": changed == {path},
            })
    exact = [row for row in matches if row["changed_paths_are_exact"]]
    if len(exact) == 1:
        status = "unique_full_commit_transition"
    elif len(exact) > 1:
        status = "ambiguous_full_commit_transitions"
    elif matches:
        status = "partial_file_transition_only"
    else:
        status = "no_reachable_transition"
    return {
        "status": status,
        "candidate_count": len(matches),
        "exact_candidate_count": len(exact),
        "candidate_commit_ids_emitted": False,
    }


def _evaluate(root: Path) -> dict:
    isolated, _ = _repo(root, "isolated")
    (isolated / RELATIVE).write_text(AFTER, encoding="utf-8")
    _commit(isolated, "synthetic agent edit")

    uncommitted, _ = _repo(root, "uncommitted")
    (uncommitted / RELATIVE).write_text(AFTER, encoding="utf-8")

    duplicate, _ = _repo(root, "duplicate")
    branch_a = _git(duplicate, "rev-parse", "HEAD")
    (duplicate / RELATIVE).write_text(AFTER, encoding="utf-8")
    _commit(duplicate, "synthetic transition A")
    _git(duplicate, "checkout", "-q", "-b", "alternate", branch_a)
    (duplicate / "other.txt").write_text("alternate context\n", encoding="utf-8")
    _commit(duplicate, "different surrounding tree")
    (duplicate / RELATIVE).write_text(AFTER, encoding="utf-8")
    _commit(duplicate, "synthetic transition B")

    mixed, _ = _repo(root, "mixed")
    (mixed / RELATIVE).write_text(AFTER, encoding="utf-8")
    (mixed / "README.md").write_text("unrelated change in same commit\n", encoding="utf-8")
    _commit(mixed, "mixed synthetic changes")

    return {
        "synthetic_only": True,
        "source_file_count": 1,
        "scenarios": {
            "isolated_reachable_commit": _find_file_transition(isolated, RELATIVE, BEFORE, AFTER),
            "uncommitted_edit": _find_file_transition(uncommitted, RELATIVE, BEFORE, AFTER),
            "same_edit_on_two_branches": _find_file_transition(duplicate, RELATIVE, BEFORE, AFTER),
            "edit_committed_with_unrelated_file": _find_file_transition(mixed, RELATIVE, BEFORE, AFTER),
        },
        "limits": [
            "A Git transition match does not prove it belongs to the archived session.",
            "Even a unique match does not prove the session began from a clean worktree.",
            "A file transition does not reconstruct untracked files or dependency state.",
            "A recorded passing command does not prove intended behavior or rule out a flake.",
        ],
    }


if __name__ == "__main__":
    import json

    with tempfile.TemporaryDirectory(prefix="synthetic-git-reconstruction-") as directory:
        print(json.dumps(_evaluate(Path(directory)), indent=2))
