"""Synthetic-only probe of session-source versus provider-index diagnosis.

The SQLite and JSON shapes are authored from public incident descriptions.
They are illustrative fixtures, not current-provider compatibility tests.
The probe writes only under TemporaryDirectory and never attempts repair.
"""

from __future__ import annotations

import json
import hashlib
import sqlite3
import tempfile
from pathlib import Path

from agent_sessions.parsers.claude import ClaudeParser
from agent_sessions.parsers.codex import CodexParser


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def ids_from_jsonl(paths: list[Path], parser) -> set[str]:
    found = set()
    for path in paths:
        session = parser.parse(path)
        if session is not None:
            found.add(session.id)
    return found


def sqlite_kv(path: Path, table: str = "ItemTable") -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute(f"CREATE TABLE {table} (key TEXT PRIMARY KEY, value BLOB NOT NULL)")
    return db


def insert_kv(db: sqlite3.Connection, key: str, value: dict) -> None:
    db.execute("INSERT INTO ItemTable(key, value) VALUES (?, ?)",
               (key, json.dumps(value).encode("utf-8")))


def read_kv(db_path: Path, key: str) -> dict:
    if not db_path.exists():
        return {}
    with sqlite3.connect(db_path) as db:
        row = db.execute("SELECT value FROM ItemTable WHERE key = ?", (key,)).fetchone()
    if not row:
        return {}
    try:
        value = row[0].decode("utf-8") if isinstance(row[0], bytes) else row[0]
        parsed = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def codex_fixture(root: Path, case: str) -> tuple[set[str], set[str], bool]:
    source = root / "codex" / "sessions" / "synthetic.jsonl"
    session_id = "codex-synthetic-session"
    if case != "missing_source":
        write_jsonl(source, [
            {"type": "session_meta", "payload": {"id": session_id, "cwd": "/synthetic/project"}},
            {"type": "event_msg", "payload": {"type": "user_message", "message": "synthetic prompt"}},
        ])
    index = root / "codex" / "session_index.jsonl"
    index.parent.mkdir(parents=True, exist_ok=True)
    if case != "missing_index":
        index.write_text(json.dumps({"id": session_id, "thread_name": "Synthetic"}) + "\n", encoding="utf-8")
    db_path = root / "codex" / "state_5.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, rollout_path TEXT, archived INTEGER)")
        if case != "missing_source":
            db.execute("INSERT INTO threads VALUES (?, ?, 0)", (session_id, "synthetic.jsonl"))
    before = tree_fingerprint(root)
    source_ids = ids_from_jsonl([source] if source.exists() else [], CodexParser)
    index_ids = set()
    for line in index.read_text(encoding="utf-8").splitlines() if index.exists() else []:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("id"):
            index_ids.add(str(item["id"]))
    unchanged = before == tree_fingerprint(root)
    return source_ids, index_ids, unchanged


def claude_fixture(root: Path, case: str) -> tuple[set[str], set[str], bool]:
    session_id = "claude-synthetic-session"
    transcript = root / "claude" / "projects" / "synthetic-project" / f"{session_id}.jsonl"
    if case != "missing_source":
        write_jsonl(transcript, [
            {"type": "user", "sessionId": session_id, "message": {"content": "synthetic prompt"}},
            {"type": "assistant", "sessionId": session_id, "message": {"content": "synthetic response"}},
        ])
    metadata = root / "claude" / "desktop-index.json"
    entries = [] if case == "missing_index" else [{"sessionId": session_id, "summary": "Synthetic"}]
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    before = tree_fingerprint(root)
    source_ids = ids_from_jsonl([transcript] if transcript.exists() else [], ClaudeParser)
    try:
        data = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    index_ids = {str(row["sessionId"]) for row in data.get("entries", [])
                 if isinstance(row, dict) and row.get("sessionId")}
    unchanged = before == tree_fingerprint(root)
    return source_ids, index_ids, unchanged


def cursor_fixture(root: Path, case: str) -> tuple[set[str], set[str], bool]:
    composer_id = "cursor-synthetic-session"
    global_db = root / "cursor" / "global.vscdb"
    workspace_db = root / "cursor" / "workspace.vscdb"
    global_store = sqlite_kv(global_db)
    header_workspace = None if case == "missing_index" else {"id": "synthetic-workspace"}
    headers = {"allComposers": [{"type": "head", "composerId": composer_id,
                                "workspaceIdentifier": header_workspace}]}
    insert_kv(global_store, "composer.composerHeaders", headers)
    global_store.execute("CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value BLOB NOT NULL)")
    if case != "missing_source":
        # Presence of a composer payload is only a source-presence hint. It does
        # not prove that every message or file edit is intact.
        global_store.execute("INSERT INTO cursorDiskKV VALUES (?, ?)",
                             (f"composerData:{composer_id}", b'{"synthetic": true}'))
    global_store.commit()
    global_store.close()

    workspace_store = sqlite_kv(workspace_db)
    listed = [] if case == "missing_index" else [{"type": "head", "composerId": composer_id}]
    insert_kv(workspace_store, "composer.composerData", {"allComposers": listed})
    workspace_store.commit()
    workspace_store.close()

    before = tree_fingerprint(root)
    header_data = read_kv(global_db, "composer.composerHeaders")
    header_ids = {str(row["composerId"]) for row in header_data.get("allComposers", [])
                  if isinstance(row, dict) and row.get("composerId")}
    with sqlite3.connect(global_db) as db:
        payload_ids = {key.split(":", 1)[1] for (key,) in db.execute(
            "SELECT key FROM cursorDiskKV WHERE key LIKE 'composerData:%'")}
    workspace_data = read_kv(workspace_db, "composer.composerData")
    index_ids = {str(row["composerId"]) for row in workspace_data.get("allComposers", [])
                 if isinstance(row, dict) and row.get("composerId")}
    source_ids = header_ids & payload_ids
    unchanged = before == tree_fingerprint(root)
    return source_ids, index_ids, unchanged


PROVIDERS = {
    "codex": codex_fixture,
    "claude": claude_fixture,
    "cursor": cursor_fixture,
}


def classify(source_ids: set[str], index_ids: set[str]) -> str:
    if source_ids - index_ids:
        return "source_present_index_missing_review"
    if index_ids - source_ids:
        return "index_entry_without_source_do_not_repair"
    if source_ids:
        return "source_and_index_agree_no_action"
    return "no_source_evidence_no_repair"


def tree_fingerprint(root: Path) -> tuple[tuple[str, str], ...]:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append((path.relative_to(root).as_posix(), digest))
    return tuple(rows)


def run_probe() -> list[dict]:
    results = []
    for provider, fixture in PROVIDERS.items():
        for case in ("healthy", "missing_index", "missing_source"):
            with tempfile.TemporaryDirectory(prefix="session-recovery-synthetic-") as temp:
                temp_root = Path(temp)
                source_ids, index_ids, unchanged = fixture(temp_root, case)
                finding = classify(source_ids, index_ids)
                if not unchanged:
                    raise AssertionError("Read-only diagnosis modified a synthetic provider store")
                expected = {
                    "healthy": "source_and_index_agree_no_action",
                    "missing_index": "source_present_index_missing_review",
                    "missing_source": "index_entry_without_source_do_not_repair",
                }[case]
                if finding != expected:
                    raise AssertionError(f"Unexpected finding for synthetic {provider}/{case}")
                results.append({"provider": provider, "case": case, "finding": finding,
                                "source_count": len(source_ids), "index_count": len(index_ids),
                                "fixture": "synthetic", "fixture_hashes_unchanged": True,
                                "writes_to_provider_data": False})
    return results


if __name__ == "__main__":
    print(json.dumps({"results": run_probe(),
                      "limits": [
                          "Authored schemas are illustrative and are not provider compatibility fixtures.",
                          "Cursor payload presence does not prove complete message recovery.",
                          "No current client, native UI, repair tool, or private store was exercised.",
                          "The probe does not establish uniqueness, lower review effort, or willingness to pay.",
                      ]}, indent=2))
