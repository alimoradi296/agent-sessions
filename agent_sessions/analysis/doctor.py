"""Read-only diagnostics for local sources, exports, indexes, and hooks."""

from __future__ import annotations

import json
import re
import shlex
from collections import Counter
from pathlib import Path

from agent_sessions.parsers import PARSERS
from agent_sessions.parsers.codex import CodexParser

READ_ERRORS = (OSError, UnicodeError)
UNREADABLE = object()


class Doctor:
    def __init__(self, directory: Path, agents: list[str] | None = None,
                 project_dir: Path | None = None):
        self.directory = directory
        self.agents = agents if agents is not None else list(PARSERS)
        self.explicit_agents = agents is not None
        self.project_dir = project_dir
        self.findings: list[dict] = []
        self.counts: Counter = Counter()

    def add(self, level: str, code: str, message: str, **details) -> None:
        self.findings.append(dict(level=level, code=code, message=message, **details))

    def run(self) -> dict:
        # A Doctor instance can be reused without accumulating old findings.
        self.findings = []
        self.counts = Counter(source_files=0, source_sessions=0, indexed_sessions=0, sources_without_messages=0)
        self.index_readable = False
        rows = self.check_exports()
        if not self.index_readable:
            self.add('info', 'export_comparison_skipped', 'Source comparisons require a readable JSON index.')
        by_key = {(row['agent'], row['id']): row for row in rows}
        for agent in self.agents:
            self.check_sources(agent, by_key)
            self.check_hooks(agent)
        self.add('info', 'hook_runtime_unverified',
                 'Hook execution is unverified. Configuration inspection does not run hooks.')
        issues = sum(f['level'] in ('warning', 'error') for f in self.findings)
        return dict(version=1, read_only=True, directory=str(self.directory),
                    agents=self.agents, issue_count=issues,
                    exit_code=1 if issues else 0, counts=dict(self.counts), findings=self.findings)

    def read_json(self, path: Path, code: str):
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except (*READ_ERRORS, ValueError) as error:
            self.add('error', code, 'Cannot read a valid JSON document.',
                     path=str(path), error_type=type(error).__name__)
            return UNREADABLE

    def check_exports(self) -> list[dict]:
        rows = []
        index = self.directory / 'sessions.json'
        try:
            if not self.directory.is_dir():
                self.add('error', 'export_directory_missing', 'Export directory is missing or is not a directory.',
                         path=str(self.directory))
                return rows
            data = self.read_json(index, 'json_index_unreadable')
            if data is UNREADABLE:
                return rows
            entries = data.get('sessions') if isinstance(data, dict) else data
            if not isinstance(entries, list):
                self.add('error', 'json_index_shape', 'Expected a sessions list.', path=str(index))
                return rows
            self.index_readable = True
            if isinstance(data, dict) and data.get('count') != len(entries):
                self.add('error', 'json_index_count', 'The stored count differs from the sessions list.', path=str(index))
            seen = set()
            for row in entries:
                if not isinstance(row, dict):
                    self.add('error', 'json_index_entry', 'Index entry is not an object.')
                    continue
                sid, agent = row.get('id'), row.get('agent')
                if (not isinstance(sid, str) or not sid or sid in ('.', '..')
                        or not re.fullmatch(r'[\w-]+', sid) or not isinstance(agent, str) or agent not in PARSERS):
                    self.add('error', 'json_index_entry', 'Index entry has an invalid ID or agent.')
                    continue
                if sid in seen:
                    self.add('error', 'duplicate_index_id', 'The JSON index repeats a session ID.', session_id=sid)
                    continue
                seen.add(sid)
                rows.append(row)
                if agent not in self.agents:
                    continue
                self.counts['indexed_sessions'] += 1
                expected = f'{sid}.md'
                if row.get('file') != expected:
                    self.add('error', 'index_file_reference', 'Index filename differs from the canonical session filename.',
                             agent=agent, session_id=sid)
                path = self.directory / expected
                try:
                    text = path.read_text(encoding='utf-8')
                except READ_ERRORS as error:
                    self.add('error', 'transcript_unreadable', 'Indexed Markdown transcript is missing or unreadable.',
                             agent=agent, session_id=sid, path=str(path), error_type=type(error).__name__)
                    continue
                # Only export metadata before the conversation is relevant.
                header = text.split('\n---\n', 1)[0]
                if f'**Session ID:** `{sid}`' not in header or f'**Agent:** {agent}' not in header.splitlines():
                    self.add('error', 'transcript_metadata', 'Transcript ID or agent differs from the JSON index.',
                             agent=agent, session_id=sid, path=str(path))
                match = re.search(r'^\*\*Messages:\*\* (\d+) user / (\d+) assistant$', header, re.MULTILINE)
                if match and (int(match[1]) != row.get('user_messages') or int(match[2]) != row.get('assistant_messages')):
                    self.add('warning', 'transcript_message_counts', 'Transcript and JSON message counts differ.',
                             agent=agent, session_id=sid)
            # Filename sets use the whole index, including agents outside the
            # requested source scope, to avoid false orphan reports.
            for path in sorted(self.directory.glob('*.md')):
                if path.name != 'SESSION_INDEX.md' and path.stem not in seen:
                    self.add('warning', 'unindexed_markdown', 'Markdown file has no JSON index entry.', path=str(path))
            md_index = self.directory / 'SESSION_INDEX.md'
            try:
                text = md_index.read_text(encoding='utf-8')
                if '| ID | Agent |' not in text or '|---' not in text:
                    self.add('error', 'markdown_index_shape', 'Markdown index table header is missing.', path=str(md_index))
                links = re.findall(r'^\|.*\| \[([^\]\n]+\.md)\]\([^\n]*\) \|$', text, re.MULTILINE)
                counts = Counter(links)
                for row in rows:
                    if row['agent'] in self.agents and counts[f"{row['id']}.md"] != 1:
                        self.add('warning', 'markdown_index_entry', 'Markdown index must reference this session exactly once.',
                                 agent=row['agent'], session_id=row['id'])
                for name in counts:
                    if name[:-3] not in seen:
                        self.add('warning', 'markdown_index_orphan', 'Markdown index references a file absent from the JSON index.',
                                 path=name)
            except READ_ERRORS as error:
                self.add('error', 'markdown_index_unreadable', 'Markdown index is missing or unreadable.',
                         path=str(md_index), error_type=type(error).__name__)
        except READ_ERRORS as error:
            self.add('error', 'export_directory_unreadable', 'Cannot inspect the export directory.',
                     path=str(self.directory), error_type=type(error).__name__)
        return rows

    def check_sources(self, agent: str, by_key: dict) -> None:
        parser = PARSERS[agent]
        base = parser.find_sessions_dir()
        try:
            if not base.is_dir():
                self.add('warning' if self.explicit_agents else 'info', 'source_directory_missing',
                         'Source directory is absent. This agent can be uninstalled.', agent=agent, path=str(base))
                return
            paths = parser.list_sessions()
        except READ_ERRORS as error:
            self.add('error', 'source_discovery_failed', 'Cannot list source transcripts.',
                     agent=agent, path=str(base), error_type=type(error).__name__)
            return
        self.counts['source_files'] += len(paths)
        groups: dict[str, list[Path]] = {}
        for path in paths:
            try:
                sid = CodexParser.session_id(path) if agent == 'codex' else path.stem
                groups.setdefault(sid, []).append(path)
            except READ_ERRORS as error:
                self.add('error', 'source_unreadable', 'Cannot read source metadata.',
                         agent=agent, path=str(path), error_type=type(error).__name__)
        found = set()
        for group in groups.values():
            try:
                diagnostics = {}
                session = (CodexParser.parse_many(group, diagnostics=diagnostics) if agent == 'codex'
                           else parser.parse(group[0], diagnostics=diagnostics))
                for source_path, counts in diagnostics.items():
                    for key, value in counts.items():
                        self.counts['source_' + key] += value
                    if counts['malformed'] or counts['unsupported']:
                        self.add('warning', 'source_record_coverage',
                                 f"Record coverage: {counts['malformed']} malformed, "
                                 f"{counts['unsupported']} unsupported. Export completeness is uncertain.",
                                 agent=agent, path=source_path, record_counts=counts)
                if session is None:
                    self.counts['sources_without_messages'] += len(group)
                    continue
                self.counts['source_sessions'] += 1
                found.add(session.id)
                if not self.index_readable:
                    continue
                row = by_key.get((agent, session.id))
                if row is None:
                    self.add('warning', 'missing_export', 'Source session has no entry in this export directory.',
                             agent=agent, session_id=session.id)
                    continue
                path = self.directory / f'{session.id}.md'
                if path.is_file() and max(p.stat().st_mtime_ns for p in group) > path.stat().st_mtime_ns:
                    self.add('warning', 'stale_export', 'A source file is newer than its Markdown export.',
                             agent=agent, session_id=session.id, path=str(path))
                if row.get('message_count') != session.message_count:
                    self.add('warning', 'source_message_counts', 'Current parser and exported message counts differ.',
                             agent=agent, session_id=session.id)
            except (*READ_ERRORS, ValueError, TypeError, AttributeError, KeyError, IndexError) as error:
                self.add('error', 'source_parse_failed', 'Cannot inspect this source group with the current parser.',
                         agent=agent, path=str(group[0]), error_type=type(error).__name__)
        for (row_agent, sid), row in by_key.items():
            if row_agent == agent and sid not in found:
                self.add('warning', 'source_not_discovered', 'Indexed session was not found as a readable source session.',
                         agent=agent, session_id=sid)
        self.add('info', 'source_scan_complete', 'Source scan finished for this agent.', agent=agent)

    def check_hooks(self, agent: str) -> None:
        locations = {
            'claude': [Path.home() / '.claude/settings.json'],
            'codex': [Path.home() / '.codex/hooks.json'],
            'cursor': [Path.home() / '.cursor/hooks.json'],
        }
        if self.project_dir is not None:
            locations['cursor'].append(self.project_dir / '.cursor/hooks.json')
        for path in locations[agent]:
            try:
                if not path.exists():
                    self.add('info', 'hook_not_configured', 'No hook configuration at this location. Manual export remains available.',
                             agent=agent, path=str(path))
                    continue
                config = self.read_json(path, 'hook_config_unreadable')
                if config is UNREADABLE:
                    continue
                if not isinstance(config, dict) or not isinstance(config.get('hooks', {}), dict):
                    self.add('error', 'hook_config_shape', 'Expected a hooks object.', agent=agent, path=str(path))
                    continue
                if config.get('disableAllHooks') is True:
                    self.add('warning', 'hooks_disabled', 'Configuration disables all hooks.', agent=agent, path=str(path))
                if agent == 'cursor':
                    if type(config.get('version')) is not int or config['version'] != 1:
                        self.add('warning', 'hook_config_version', 'Cursor hook configuration requires version 1.', agent=agent, path=str(path))
                    if config.get('hooks', {}).get('agent-end'):
                        self.add('warning', 'hook_event_legacy', 'Cursor uses stop. Review the legacy agent-end entries.', agent=agent, path=str(path))
                event_names = ('agent-end', 'stop') if agent == 'cursor' else ('Stop',)
                candidates = []
                for event in event_names:
                    entries = config.get('hooks', {}).get(event, [])
                    if not isinstance(entries, list):
                        self.add('error', 'hook_config_shape', 'Expected a list of hook entries.', agent=agent, path=str(path))
                        continue
                    for entry in entries:
                        if not isinstance(entry, dict):
                            self.add('error', 'hook_config_shape', 'Expected a hook entry object.', agent=agent, path=str(path))
                            continue
                        hooks = entry.get('hooks', [entry])
                        if not isinstance(hooks, list):
                            self.add('error', 'hook_config_shape', 'Expected a list of hook commands.', agent=agent, path=str(path))
                            continue
                        for hook in hooks:
                            if not isinstance(hook, dict):
                                self.add('error', 'hook_config_shape', 'Expected a hook command object.', agent=agent, path=str(path))
                            elif not hook.get('disabled') and isinstance(hook.get('command'), str):
                                candidates.append(hook['command'])
                references = sum(self.inspect_hook(command, agent, path) for command in candidates)
                self.add('info', 'hook_export_reference' if references else 'hook_export_reference_absent',
                         'Exporter reference found. Execution remains unverified.' if references
                         else 'No exporter reference found in the inspected hook events.', agent=agent, path=str(path))
            except READ_ERRORS as error:
                self.add('error', 'hook_config_unreadable', 'Cannot inspect hook configuration.',
                         agent=agent, path=str(path), error_type=type(error).__name__)

    def inspect_hook(self, command: str, agent: str, config: Path) -> bool:
        # Never invoke a hook, shell, executable, or external service.
        try:
            words = shlex.split(command)
        except ValueError:
            self.add('warning', 'hook_command_unreadable', 'Cannot parse the configured command.', agent=agent, path=str(config))
            return False
        reference = any(Path(word).name == 'agent-sessions' for word in words) or 'agent_sessions' in words
        for word in words[:2]:
            script = Path(word).expanduser()
            if script.suffix not in ('.sh', '.py') or not script.is_absolute():
                continue
            try:
                content = script.read_text(encoding='utf-8')
                reference = reference or 'agent-sessions' in content or 'agent_sessions' in content
            except READ_ERRORS as error:
                self.add('warning', 'hook_script_unreadable', 'Configured script is missing or unreadable.',
                         agent=agent, path=str(script), error_type=type(error).__name__)
        return reference


def render_doctor(report: dict) -> str:
    lines = [f"Doctor: {report['issue_count']} issue(s). Read-only inspection.",
             f"Sources: {report['counts'].get('source_files', 0)} files / "
             f"{report['counts'].get('source_sessions', 0)} sessions. "
             f"Indexed sessions checked: {report['counts'].get('indexed_sessions', 0)}."]
    for finding in report['findings']:
        subject = ' / '.join(str(finding[key]) for key in ('agent', 'session_id', 'path') if key in finding)
        suffix = f' [{subject}]' if subject else ''
        lines.append(f"{finding['level'].upper()} {finding['code']}: {finding['message']}{suffix}")
    return '\n'.join(lines)
