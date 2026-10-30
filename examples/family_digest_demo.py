"""Complete synthetic MVP: export a forked family, digest it, pin, and audit.

Creates invented Claude parent/child sessions only. Reads no real agent history.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_sessions.analysis.continuity import (
    audit_bundle,
    compile_handoff,
    load_requirements,
    pin_requirement,
    write_bundle,
)
from agent_sessions.analysis.family import (
    build_family_digest,
    materialize_pin_suggestions,
    render_family_digest,
)
from agent_sessions.analysis.search import search_archive
from agent_sessions.cli import cmd_family
from agent_sessions.models import Agent, Message, Session
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.renderers.markdown import MarkdownRenderer


SCOPE = "Discovery only. Do not implement or publish."
FOLLOW_UP = "Continue the discovery notes for the fictional cache review."


def _export(session: Session, archive: Path) -> None:
    MarkdownRenderer.write(session, archive)
    JsonIndexRenderer.update(session, archive / "sessions.json")


def build_synthetic_archive(archive: Path) -> dict[str, str]:
    started = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    parent = Session(
        id="synthetic-family-parent",
        agent=Agent.CLAUDE,
        title="Synthetic family parent",
        cwd="/synthetic/family-project",
        branch="main",
        started_at=started,
        messages=[
            Message(role="user", text="Review the fictional cache design.", timestamp=started),
            Message(
                role="assistant",
                text=f"Plan recorded. {SCOPE}",
                timestamp=started,
            ),
        ],
    )
    child = Session(
        id="synthetic-family-child",
        agent=Agent.CLAUDE,
        title="Synthetic family child fork",
        cwd="/synthetic/family-project",
        branch="main",
        parent_id=parent.id,
        started_at=started.replace(minute=30),
        messages=[
            Message(role="user", text=FOLLOW_UP, timestamp=started.replace(minute=30)),
            Message(
                role="assistant",
                text=("Notes retained. The earlier scope restriction still applies.\n"
                      "Open question: should we keep cache eviction out of this scope?"),
                timestamp=started.replace(minute=31),
            ),
        ],
    )
    grandchild = Session(
        id="synthetic-family-grandchild",
        agent=Agent.CLAUDE,
        title="Synthetic family grandchild fork",
        cwd="/synthetic/family-project",
        branch="explore",
        parent_id=child.id,
        started_at=started.replace(hour=13),
        messages=[
            Message(
                role="user",
                text="Fork again for an alternate discovery outline.",
                timestamp=started.replace(hour=13),
            ),
            Message(
                role="assistant",
                text="Alternate outline drafted without implementation.",
                timestamp=started.replace(hour=13, minute=1),
            ),
        ],
    )
    codex_parent = Session(
        id="synthetic-codex-parent",
        agent=Agent.CODEX,
        title="Synthetic Codex parent",
        cwd="/synthetic/family-project",
        started_at=started.replace(hour=14),
        messages=[
            Message(role="user", text="Spawn a helper for the fictional check."),
            Message(role="assistant", text="Helper spawn requested."),
        ],
    )
    codex_child = Session(
        id="synthetic-codex-child",
        agent=Agent.CODEX,
        title="Synthetic Codex spawned child",
        cwd="/synthetic/family-project",
        parent_id=codex_parent.id,
        started_at=started.replace(hour=14, minute=5),
        messages=[
            Message(role="user", text="Run the fictional helper task."),
            Message(role="assistant", text="Helper task recorded as historical text only."),
        ],
    )
    for session in (parent, child, grandchild, codex_parent, codex_child):
        _export(session, archive)
    return {
        "claude_focus": child.id,
        "codex_focus": codex_child.id,
        "scope": SCOPE,
    }


def evaluate(archive: Path | None = None) -> dict:
    temporary = None
    if archive is None:
        temporary = tempfile.TemporaryDirectory(prefix="agent-sessions-family-mvp-")
        archive = Path(temporary.name) / "exports"
        archive.mkdir()
    try:
        ids = build_synthetic_archive(archive)
        digest = build_family_digest(archive, ids["claude_focus"])
        markdown = render_family_digest(digest)
        members = {member["session_id"]: member for member in digest["members"]}
        if set(members) != {
            "synthetic-family-parent",
            "synthetic-family-child",
            "synthetic-family-grandchild",
        }:
            raise AssertionError("Claude family membership is incomplete.")
        if members["synthetic-family-parent"]["relation"] != "ancestor":
            raise AssertionError("Parent must be an ancestor of the focus child.")
        if members["synthetic-family-grandchild"]["relation"] != "descendant":
            raise AssertionError("Grandchild must be a descendant of the focus child.")
        if members["synthetic-family-child"]["edge"] != "forked_from":
            raise AssertionError("Claude child edge should be forked_from.")
        if ids["scope"] not in members["synthetic-family-parent"]["quotes"][1]["text"]:
            raise AssertionError("Parent assistant quote must retain the scope restriction.")
        if digest["family_summary"]["signal_count"] < 1:
            raise AssertionError("Family summary should include continuation signals.")
        if not digest["pin_suggestions"]:
            raise AssertionError("Digest should suggest at least one follow-up pin.")

        codex = build_family_digest(archive, ids["codex_focus"])
        if codex["members"][1]["edge"] != "spawned_from":
            raise AssertionError("Codex child edge should be spawned_from.")

        hits = search_archive(archive, "Discovery only", view="dialogue")
        if hits["total_hits"] < 1:
            raise AssertionError("Scope text must remain searchable.")
        hit = hits["hits"][0]

        private = archive.parent / "private"
        private.mkdir(exist_ok=True)
        generated_requirements = private / "generated-requirements.json"
        generated = materialize_pin_suggestions(archive, digest, generated_requirements, overwrite=True)
        generated_contract = load_requirements(generated_requirements)
        if generated["pins_written"] < 1 or not generated_contract["requirements"]:
            raise AssertionError("Generated requirements should keep at least one anchor.")
        requirements = private / "requirements.json"
        pin_requirement(
            archive,
            requirements,
            "discovery-only",
            hit["session_id"],
            hit["section"],
            ids["scope"],
            unit="paragraph",
        )
        text, manifest = compile_handoff(archive, "family cache", requirements)
        if not manifest["ready"] or ids["scope"] not in text:
            raise AssertionError("Required family scope evidence was omitted.")
        bundle = private / "bundle"
        write_bundle(bundle, text, manifest)
        audit = audit_bundle(bundle, archive)
        if audit["exit_code"] != 0:
            raise AssertionError("Unchanged family evidence failed audit.")

        one_command_bundle = private / "one-command.bundle"
        one_command_requirements = private / "one-command.requirements.json"
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            cmd_family(
                Namespace(
                    session_id=ids["claude_focus"],
                    directory=str(archive),
                    max_quote_chars=400,
                    max_signals=8,
                    max_pin_suggestions=12,
                    signal_kinds=None,
                    pin_signal_kinds=None,
                    focus_priority_bonus=15,
                    min_signal_priority=0,
                    profile="strict",
                    require_signal_kinds=["scope_boundary"],
                    requirements_out=str(one_command_requirements),
                    overwrite_requirements=True,
                    bundle_out=str(one_command_bundle),
                    query="family-one-command",
                    last=5,
                    max_chars=24000,
                    max_total_chars=120000,
                    audit_family_bundle=True,
                    json=True,
                    output=None,
                )
            )
        one_command = json.loads(captured.getvalue())
        if not one_command.get("required_signals", {}).get("passed"):
            raise AssertionError("Required scope_boundary signal should pass on synthetic family.")
        if one_command.get("family_bundle", {}).get("audit", {}).get("exit_code") != 0:
            raise AssertionError("One-command family bundle audit should pass.")

        return dict(
            synthetic_only=True,
            focus=ids["claude_focus"],
            member_ids=[member["session_id"] for member in digest["members"]],
            codex_edge=codex["members"][1]["edge"],
            signal_count=digest["family_summary"]["signal_count"],
            pin_suggestion_count=len(digest["pin_suggestions"]),
            generated_pin_count=generated["pins_written"],
            one_command_ready=one_command["family_bundle"]["ready"],
            one_command_audit_exit_code=one_command["family_bundle"]["audit"]["exit_code"],
            required_scope_passed=one_command["required_signals"]["passed"],
            scope_retained=True,
            handoff_ready=manifest["ready"],
            audit_exit_code=audit["exit_code"],
            verification=manifest["verification"],
            markdown_chars=len(markdown),
            digest_path_hint=(
                "agent-sessions family synthetic-family-child -d ARCHIVE "
                "--profile strict --require-signal-kind scope_boundary "
                "--bundle-out PRIVATE/bundle --audit-family-bundle"
            ),
            limits=(
                "Authored synthetic exports only. No native agent stores, private "
                "transcripts, or willingness-to-pay evidence."
            ),
        )
    finally:
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optional directory that receives exports/ for CLI follow-up. Default: temporary.",
    )
    args = parser.parse_args()
    if args.output_dir is None:
        print(json.dumps(evaluate(), indent=2, ensure_ascii=False))
    else:
        archive = args.output_dir / "exports"
        archive.mkdir(parents=True, exist_ok=True)
        result = evaluate(archive)
        digest = build_family_digest(archive, result["focus"])
        (args.output_dir / "family-digest.md").write_text(
            render_family_digest(digest), encoding="utf-8"
        )
        (args.output_dir / "family-digest.json").write_text(
            json.dumps(digest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        result["archive"] = str(archive)
        result["digest_markdown"] = str(args.output_dir / "family-digest.md")
        print(json.dumps(result, indent=2, ensure_ascii=False))
