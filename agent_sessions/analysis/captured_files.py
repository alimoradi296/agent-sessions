"""Recover captured file bytes without inferring historical execution."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from agent_sessions.storage import StorageError, atomic_write_many
from agent_sessions.workspace import _private_root


_NESTED_PATCH = re.compile(r"tools\.apply_patch\s*\(\s*")


def _parse_captured_time(value):
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value / 1000 if value > 1e12 else value, tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            return None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def _result_status(payload: dict) -> str:
    if payload.get("is_error") is True:
        return "failed"
    if payload.get("is_error") is False:
        return "confirmed_success"
    output = payload.get("output")
    if isinstance(output, dict):
        if isinstance(output.get("exit_code"), int):
            return "confirmed_success" if output["exit_code"] == 0 else "failed"
        if isinstance(output.get("ok"), bool):
            return "confirmed_success" if output["ok"] else "failed"
    text = output if isinstance(output, str) else ""
    if isinstance(output, list):
        text = "\n".join(item.get("text", "") for item in output
                         if isinstance(item, dict) and isinstance(item.get("text"), str))
    match = re.search(r"(?:exit code|exited with code)[\s:\"]+(-?\d+)", text, re.IGNORECASE)
    match = match or re.search(r'["\']?exit_code["\']?\s*:\s*(-?\d+)', text, re.IGNORECASE)
    if match:
        return "confirmed_success" if int(match.group(1)) == 0 else "failed"
    if re.search(r"\bScript completed\b", text, re.IGNORECASE):
        return "confirmed_success"
    return "unknown"


def _source_results(source: Path) -> dict[str, dict]:
    results = {}
    with source.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                event = json.loads(line)
            except ValueError:
                continue
            payload = event.get("payload") if isinstance(event, dict) else None
            if event.get("type") != "response_item" or not isinstance(payload, dict):
                continue
            if payload.get("type") not in ("function_call_output", "custom_tool_call_output"):
                continue
            call_id = str(payload.get("call_id", ""))
            if not call_id:
                continue
            status = _result_status(payload)
            previous = results.get(call_id)
            if previous is None:
                results[call_id] = dict(status=status, line=line_number,
                                        evidence="linked", ambiguous=False)
            else:
                results[call_id] = dict(status="unknown", line=None,
                                        evidence="ambiguous", ambiguous=True)
    return results


def _source_time_bounds(source: Path):
    timestamps = []
    with source.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                event = json.loads(line)
                if not isinstance(event, dict):
                    continue
                payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
                value = (event.get("timestamp") or payload.get("completed_at")
                         or payload.get("started_at") or payload.get("timestamp"))
                captured = _parse_captured_time(value)
                if captured is not None:
                    timestamps.append(captured)
            except (ValueError, TypeError):
                continue
    if not timestamps:
        return None
    try:
        return min(timestamps), max(timestamps)
    except TypeError:
        return None


def _literal_nested_patches(text: str) -> list[str]:
    """Return only complete JSON string literals passed directly to apply_patch."""
    decoder = json.JSONDecoder()
    patches = []
    for match in _NESTED_PATCH.finditer(text):
        try:
            value, end = decoder.raw_decode(text, match.end())
        except ValueError:
            continue
        if not isinstance(value, str) or not text[end:].lstrip().startswith(")"):
            continue
        if value.startswith("*** Begin Patch\n") and value.rstrip().endswith("*** End Patch"):
            patches.append(value)
    return patches


def _direct_patches(name: str, raw_input) -> list[str]:
    if name not in ("apply_patch", "functions.apply_patch"):
        return []
    value = raw_input
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except ValueError:
            decoded = value
        value = decoded
    if isinstance(value, dict):
        value = next((value[key] for key in ("patch", "input", "content")
                      if isinstance(value.get(key), str)), "")
    return [value] if isinstance(value, str) and value.startswith("*** Begin Patch\n") \
        and value.rstrip().endswith("*** End Patch") else []


def _added_files(patch: str) -> list[tuple[str, str]]:
    """Decode Add File bodies while ignoring other patch operations."""
    lines = patch.replace("\r\n", "\n").splitlines(keepends=True)
    if not lines or lines[0].rstrip("\n") != "*** Begin Patch":
        return []
    added = []
    index = 1
    while index < len(lines):
        line = lines[index].rstrip("\n")
        if line == "*** End Patch":
            return added
        if not line.startswith("*** Add File: "):
            index += 1
            continue
        path = line[len("*** Add File: "):]
        body = []
        index += 1
        while index < len(lines) and not lines[index].startswith("*** "):
            current = lines[index]
            if not current.startswith("+"):
                raise ValueError(f"Invalid Add File payload for {path}.")
            body.append(current[1:])
            index += 1
        text = "".join(body)
        if body and not text.endswith("\n"):
            text += "\n"
        added.append((path, text))
    raise ValueError("Patch does not end with End Patch.")


def _operations(patch: str) -> list[tuple[str, str, str]]:
    """Decode complete Add and Update operations without applying unknown bases."""
    lines = patch.replace("\r\n", "\n").splitlines(keepends=True)
    if not lines or lines[0].rstrip("\n") != "*** Begin Patch":
        return []
    operations = []
    index = 1
    while index < len(lines):
        header = lines[index].rstrip("\n")
        if header == "*** End Patch":
            return operations
        kind = next((kind for kind in ("Add", "Update", "Delete")
                     if header.startswith(f"*** {kind} File: ")), None)
        if kind is None:
            index += 1
            continue
        path = header[len(f"*** {kind} File: "):]
        body = []
        index += 1
        while index < len(lines) and not lines[index].startswith("*** "):
            body.append(lines[index])
            index += 1
        if kind == "Add":
            if any(not line.startswith("+") for line in body):
                raise ValueError(f"Invalid Add File payload for {path}.")
            text = "".join(line[1:] for line in body)
            if body and not text.endswith("\n"):
                text += "\n"
            operations.append(("add", path, text))
        elif kind == "Update":
            operations.append(("update", path, "".join(body)))
        else:
            if body:
                raise ValueError(f"Invalid Delete File payload for {path}.")
            operations.append(("delete", path, ""))
    raise ValueError("Patch does not end with End Patch.")


def _apply_exact_update(base: str, body: str) -> str:
    """Apply hunks only when each captured old fragment has one exact match."""
    lines = body.splitlines(keepends=True)
    hunks, current = [], None
    for line in lines:
        if line.startswith("@@"):
            current = []
            hunks.append(current)
        elif current is None or not line.startswith((" ", "+", "-")):
            raise ValueError("Unsupported captured Update File payload.")
        else:
            current.append(line)
    if not hunks:
        raise ValueError("Captured update has no complete hunk.")
    cursor = 0
    result = []
    for hunk in hunks:
        old = "".join(line[1:] for line in hunk if not line.startswith("+"))
        new = "".join(line[1:] for line in hunk if not line.startswith("-"))
        if not old:
            raise ValueError("Captured update has no exact base fragment.")
        position = base.find(old, cursor)
        if position < 0 or base.find(old, position + 1) >= 0:
            raise ValueError("Captured update base is missing or ambiguous.")
        result.extend((base[cursor:position], new))
        cursor = position + len(old)
    result.append(base[cursor:])
    return "".join(result)


def _source_targets_root(source: Path, source_root: Path) -> bool:
    cwd = None
    with source.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            payload = event.get("payload") if isinstance(event, dict) else None
            if event.get("type") in ("session_meta", "turn_context") and isinstance(payload, dict) and payload.get("cwd"):
                cwd = Path(payload["cwd"]).expanduser().resolve()
            if event.get("type") != "response_item" or not isinstance(payload, dict):
                continue
            name = payload.get("name", "")
            raw = payload.get("input", payload.get("arguments", ""))
            patches = _direct_patches(name, raw)
            if not patches and name == "exec" and isinstance(raw, str):
                patches = _literal_nested_patches(raw)
            for patch in patches:
                try:
                    operations = _operations(patch)
                except ValueError:
                    continue
                for _, captured_path, _ in operations:
                    path = Path(captured_path)
                    if not path.is_absolute() and cwd is None:
                        continue
                    absolute = path.resolve() if path.is_absolute() else (cwd / path).resolve()
                    try:
                        absolute.relative_to(source_root)
                        return True
                    except ValueError:
                        pass
    return False


def _discover_sources(directory: Path, source_root: Path):
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("The discovery source must be a regular directory.")
    scanned = [path.resolve() for path in directory.rglob("*.jsonl")
               if path.is_file() and not path.is_symlink()]
    relevant = [path for path in scanned if _source_targets_root(path, source_root)]
    if not relevant:
        raise ValueError("No Codex JSONL sources with captured operations under the selected root were found.")
    bounds = {path: _source_time_bounds(path) for path in relevant}
    if any(value is None for value in bounds.values()):
        raise ValueError("Discovered sources require captured timestamps to verify chronology.")
    return sorted(relevant, key=lambda path: bounds[path][0]), len(scanned)


def recover_captured_adds(source, source_root, output):
    """Write captured Add File bytes into a new private directory.

    This reads Codex JSONL. Nested orchestration calls are static string-literal
    extraction only. No archived code or command is executed.
    """
    source_root = Path(source_root).expanduser().resolve()
    supplied = [source] if isinstance(source, (str, Path)) else list(source)
    supplied_paths = [Path(item).expanduser().resolve() for item in supplied]
    discovery = None
    if len(supplied_paths) == 1 and supplied_paths[0].is_dir():
        sources, scanned = _discover_sources(supplied_paths[0], source_root)
        discovery = dict(mode="directory", files_scanned=scanned, relevant_sources=len(sources))
    else:
        sources = supplied_paths
    if not sources or len(set(sources)) != len(sources):
        raise ValueError("Provide one or more distinct Codex JSONL source files in chronological order.")
    output = _private_root(output)
    if any(not item.is_file() or item.is_symlink() for item in sources):
        raise ValueError("Provide regular Codex JSONL source files in chronological order.")
    time_bounds = [_source_time_bounds(item) for item in sources]
    chronology_verified = len(sources) == 1
    if len(sources) > 1:
        if any(bounds is None for bounds in time_bounds):
            raise ValueError("Multiple sources require captured timestamps to verify chronology.")
        if any(time_bounds[index][1] >= time_bounds[index + 1][0]
               for index in range(len(time_bounds) - 1)):
            raise ValueError("Source timestamp ranges overlap, tie, or are not in chronological order.")
        chronology_verified = True
    source_root_exists = source_root.exists()
    if source_root_exists and (not source_root.is_dir() or source_root.is_symlink()):
        raise ValueError("The captured source root must be a directory or an absent historical path.")
    if output.exists():
        raise StorageError("Choose a new private recovery directory.")

    candidates = {}
    blocked = set()
    deleted = {}
    exact_updates_applied = 0
    failed_operations_skipped = 0
    skipped_operations = []
    records = 0
    malformed = 0
    outside_root_skipped = 0
    for source_number, source_path in enumerate(sources, 1):
      source_cwd = None
      source_results = _source_results(source_path)
      with source_path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            records += 1
            try:
                event = json.loads(line)
            except ValueError:
                malformed += 1
                continue
            payload = event.get("payload") if isinstance(event, dict) else None
            if event.get("type") in ("session_meta", "turn_context") and isinstance(payload, dict) and payload.get("cwd"):
                source_cwd = Path(payload["cwd"]).expanduser().resolve()
            if event.get("type") != "response_item" or not isinstance(payload, dict):
                continue
            if payload.get("type") not in ("function_call", "custom_tool_call"):
                continue
            name = payload.get("name", "")
            call_id = str(payload.get("call_id", ""))
            receipt = source_results.get(call_id, dict(status="unknown", line=None,
                                                       evidence="missing", ambiguous=False))
            operation_execution = receipt["status"]
            raw_input = payload.get("input", payload.get("arguments", ""))
            patches = _direct_patches(name, raw_input)
            origin = "direct_call"
            if not patches and name == "exec" and isinstance(raw_input, str):
                patches = _literal_nested_patches(raw_input)
                origin = "nested_literal"
            if origin == "nested_literal":
                # The outer executor result cannot certify the nested patch.
                operation_execution = "unknown"
                receipt = dict(status="unknown", line=None,
                               evidence="nested_call", ambiguous=False)
            for patch_number, patch in enumerate(patches, 1):
                for operation, captured_path, body in _operations(patch):
                    path = Path(captured_path)
                    relative_base = source_cwd or source_root
                    absolute = path.resolve() if path.is_absolute() else (relative_base / path).resolve()
                    try:
                        relative = absolute.relative_to(source_root)
                    except ValueError as error:
                        if path.is_absolute():
                            outside_root_skipped += 1
                            continue
                        raise ValueError("A relative captured path escapes the selected source root.") from error
                    if not relative.parts or any(part in ("", ".", "..") for part in relative.parts):
                        raise ValueError("A captured Add File path is invalid.")
                    key = relative.as_posix()
                    previous = candidates.get(key)
                    if operation_execution == "failed":
                        failed_operations_skipped += 1
                        skipped_operations.append(dict(
                            path=key, operation=operation, source_number=source_number,
                            source_line=line_number, call_id=call_id,
                            result_line=receipt["line"], reason="captured_result_failed",
                        ))
                        continue
                    if operation == "delete":
                        candidates.pop(key, None)
                        blocked.discard(key)
                        deleted[key] = dict(source_line=line_number, source_number=source_number,
                                            call_id=call_id, patch_number=patch_number, origin=origin,
                                            execution_status=operation_execution,
                                            result_line=receipt["line"],
                                            result_evidence=receipt["evidence"],
                                            result_status=receipt["status"])
                        continue
                    if operation == "update":
                        if not previous or key in blocked:
                            blocked.add(key)
                            continue
                        try:
                            text = _apply_exact_update(previous["text"], body)
                        except ValueError:
                            blocked.add(key)
                            continue
                        previous.update(text=text, source_line=line_number,
                                        source_number=source_number,
                                        call_id=call_id,
                                        patch_number=patch_number, origin=origin,
                                        update_count=previous.get("update_count", 0) + 1,
                                        execution_status=("confirmed_success"
                                                          if previous["execution_status"] == operation_execution == "confirmed_success"
                                                          else "unknown"),
                                        result_line=(receipt["line"] if receipt["evidence"] == "linked" else None),
                                        result_evidence=receipt["evidence"],
                                        result_status=operation_execution)
                        exact_updates_applied += 1
                        continue
                    text = body
                    if previous and previous["text"] != text:
                        raise ValueError(f"Conflicting captured bytes for {key}.")
                    blocked.discard(key)
                    deleted.pop(key, None)
                    candidates[key] = dict(
                        text=text, source_line=line_number, source_number=source_number,
                        call_id=call_id, patch_number=patch_number, origin=origin, update_count=0,
                        execution_status=operation_execution,
                        result_line=(receipt["line"] if receipt["evidence"] == "linked" else None),
                        result_evidence=receipt["evidence"],
                        result_status=operation_execution,
                    )
    if not candidates and not deleted:
        raise ValueError("No complete literal file operations were found under the selected source root.")

    output.mkdir(mode=0o700)
    contents = {output / key: item["text"] for key, item in candidates.items()}
    manifest_files = []
    current_counts = {"missing": 0, "matching": 0, "different": 0, "non_regular": 0}
    for key, item in sorted(candidates.items()):
        raw = item["text"].encode()
        current = source_root / key
        if not current.exists():
            current_status = "missing"
        elif not current.is_file() or current.is_symlink():
            current_status = "non_regular"
        elif current.read_bytes() == raw:
            current_status = "matching"
        else:
            current_status = "different"
        current_counts[current_status] += 1
        manifest_files.append(dict(
            path=key, status="captured_prefix" if key in blocked else "captured_bytes",
            update_status="blocked" if key in blocked else "complete_through_last_captured_operation",
            execution_status=item["execution_status"],
            sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
            source_line=item["source_line"], call_id=item["call_id"],
            source_number=item["source_number"],
            patch_number=item["patch_number"], origin=item["origin"],
            update_count=item["update_count"],
            current_status=current_status,
            result_line=item["result_line"], result_status=item["result_status"],
            result_evidence=item["result_evidence"],
        ))
    source_entries = [dict(source=str(item), sha256=hashlib.sha256(item.read_bytes()).hexdigest())
                      for item in sources]
    manifest = dict(
        version=1,
        source=str(sources[0]) if len(sources) == 1 else None,
        source_sha256=source_entries[0]["sha256"] if len(sources) == 1 else None,
        sources=source_entries,
        source_discovery=discovery,
        chronology_verified=chronology_verified,
        source_root=str(source_root), source_root_exists=source_root_exists,
        files=manifest_files, records=records,
        deleted_files=[dict(path=key, status="captured_deletion", **item)
                       for key, item in sorted(deleted.items())],
        skipped_operations=skipped_operations,
        malformed_records=malformed, outside_root_skipped=outside_root_skipped,
        execution_verified=bool(candidates or deleted) and all(
            item["execution_status"] == "confirmed_success"
            for item in [*candidates.values(), *deleted.values()]),
        latest_state_verified=False,
        exact_updates_applied=exact_updates_applied,
        blocked_update_paths=len(blocked),
        failed_operations_skipped=failed_operations_skipped,
        current_comparison=current_counts,
        limits="Captured literal additions, exact-base updates, and deletion tombstones only. Historical execution and latest state remain unknown.",
    )
    contents[output / "manifest.json"] = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    atomic_write_many(contents)
    for path in sorted(output.rglob("*")):
        if path.is_symlink():
            raise StorageError("Recovery output contains an unexpected symlink.")
        path.chmod(0o700 if path.is_dir() else 0o600)
    return dict(manifest, output=str(output))
