"""Synthetic fixtures only. Never use developer transcripts in public tests."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from agent_sessions.cli import cmd_bulk, load_source_session
from agent_sessions.models import Agent, Message, Session, ToolCall, ToolResult
from agent_sessions.parsers.codex import CodexParser
from agent_sessions.parsers.cursor import CursorParser
from agent_sessions.renderers.markdown import MarkdownRenderer
from agent_sessions.renderers.json_index import JsonIndexRenderer
from agent_sessions.analysis.distiller import Distiller, DistilledSession
from agent_sessions.analysis.report import WeeklyReport

SID = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'


def event(kind, payload, second=0):
    return {'type': kind, 'payload': payload, 'timestamp': f'2026-02-03T10:00:{second:02d}Z'}


def meta(sid=SID):
    return event('session_meta', {'id': sid, 'cwd': '/workspace/example-project',
                                'model_provider': 'example-provider',
                                'git': {'branch': 'feature/example'}})


def message(role, text, second, **extra):
    return event('response_item', {'type': 'message', 'role': role,
                 'content': [{'type': 'input_text' if role == 'user' else 'output_text', 'text': text}],
                 **extra}, second)


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        home_patch = patch.object(Path, 'home', return_value=self.home)
        home_patch.start()
        self.addCleanup(home_patch.stop)

    def write(self, name, records):
        path = self.home / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n'.join(json.dumps(r) for r in records) + '\n', encoding='utf-8')
        return path

    def test_codex_preserves_tool_evidence_and_real_metadata(self):
        long_input = 'x' * 800
        long_output = 'y' * 1500
        path = self.write('rollout.jsonl', [meta(),
            event('turn_context', {'model': 'example-model'}, 1),
            message('user', 'Please inspect the example.', 2),
            event('response_item', {'type': 'function_call', 'name': 'run_example',
                  'arguments': long_input, 'call_id': 'call-a'}, 3),
            event('response_item', {'type': 'function_call_output', 'output': long_output,
                  'call_id': 'call-a'}, 4),
            event('response_item', {'type': 'custom_tool_call', 'name': 'edit_example',
                  'input': 'synthetic patch', 'call_id': 'call-b'}, 5),
            event('response_item', {'type': 'custom_tool_call_output', 'output': {'ok': True},
                  'call_id': 'call-b'}, 6),
            event('event_msg', {'type': 'token_count', 'info': {'total_token_usage': {'input_tokens': 100}}}, 7),
            event('event_msg', {'type': 'token_count', 'info': {'total_token_usage': {'input_tokens': 150}}}, 8),
            message('assistant', 'The example check passed.', 9, phase='final_answer'),
            event('event_msg', {'type': 'task_complete', 'completed_at': '2026-02-03T10:00:12Z'}, 10),
        ])
        session = CodexParser.parse(path)
        self.assertEqual(session.branch, 'feature/example')
        self.assertEqual(session.model, 'example-model')
        self.assertEqual(session.model_provider, 'example-provider')
        self.assertEqual(session.usage.input_tokens, 150)
        self.assertEqual(session.ended_at.second, 12)
        calls = [c for m in session.messages for c in m.tool_calls]
        results = [r for m in session.messages for r in m.tool_results]
        self.assertEqual([c.call_id for c in calls], ['call-a', 'call-b'])
        self.assertEqual(calls[0].arguments, long_input)
        self.assertEqual(results[0].content, long_output)
        self.assertEqual(results[0].call_id, 'call-a')
        self.assertEqual(session.messages[-1].phase, 'final_answer')
        rendered = MarkdownRenderer.render(session)
        self.assertIn('## Tool', rendered)
        self.assertIn(long_input, rendered)
        self.assertIn(long_output, rendered)
        self.assertEqual(session.messages[0].source_line, 3)

    def test_resume_overlap_and_repeat_prompts_survive_single_and_bulk_export(self):
        prefix = '.codex/sessions/2026/02/03/'
        shared = [meta(), message('user', 'Check again.', 1),
                  message('assistant', 'First result.', 2)]
        first = self.write(prefix + f'rollout-{SID}.jsonl', shared)
        second = self.write(prefix + f'rollout-{SID}_{OTHER}.jsonl', shared + [
            message('user', 'Check again.', 3), message('assistant', 'Second result.', 4)])
        session = CodexParser.parse_many([second, first])
        self.assertEqual([m.text for m in session.messages],
                         ['Check again.', 'First result.', 'Check again.', 'Second result.'])
        self.assertEqual(len(session.source_paths), 2)
        self.assertEqual(load_source_session('codex', SID).message_count, 4)
        self.assertEqual(CodexParser.find_session_files(OTHER), [])
        out = self.home / 'exported'
        args = Namespace(agent='codex', project=None, output=str(out), cwd=None,
                         dry_run=False, coverage=True, since='2026-02-01', until='2026-03-01')
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_bulk(args)
        self.assertEqual(len(list(out.glob('*.md'))), 2)  # transcript and index
        index = json.loads((out / 'sessions.json').read_text())
        self.assertEqual(index['count'], 1)
        self.assertEqual(index['sessions'][0]['message_count'], 4)
        coverage = json.loads((out / 'coverage.json').read_text())
        self.assertEqual(coverage['source_files'], 2)
        self.assertEqual(coverage['exported_sessions'], 1)

    def test_legacy_mirrors_are_deduplicated_per_turn(self):
        path = self.write('legacy.jsonl', [meta(),
            event('event_msg', {'type': 'task_started'}, 1),
            event('event_msg', {'type': 'user_message', 'message': 'Repeat.'}, 2),
            message('user', 'Repeat.', 2),
            event('event_msg', {'type': 'task_started'}, 3),
            event('event_msg', {'type': 'user_message', 'message': 'Repeat.'}, 4),
            message('user', 'Repeat.', 4),
            event('event_msg', {'type': 'agent_message', 'message': 'Legacy-only response.'}, 5),
        ])
        self.assertEqual([m.text for m in CodexParser.parse(path).messages],
                         ['Repeat.', 'Repeat.', 'Legacy-only response.'])

    def test_undated_repetition_and_different_session_ids(self):
        item = {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user',
                'content': [{'type': 'input_text', 'text': 'Repeat.'}]}}
        first = self.write('a.jsonl', [meta(), item, item])
        second = self.write('b.jsonl', [meta(), item, item])
        self.assertEqual(CodexParser.parse_many([first, second]).message_count, 2)
        other = self.write('other.jsonl', [meta(OTHER), item])
        with self.assertRaises(ValueError):
            CodexParser.parse_many([first, other])

    def test_cursor_estimated_date_and_result_only_message(self):
        path = self.write(f'.cursor/projects/workspace-example-project/agent-transcripts/{SID}/{SID}.jsonl', [
            {'role': 'user', 'message': {'content': [{'type': 'text', 'text': 'Inspect the example project.'}]}},
            {'role': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'read_example',
                'id': 'call-a', 'input': {'path': 'example.py'}}]}},
            {'role': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'call-a',
                'content': 'synthetic output' * 100}]}},
        ])
        stamp = datetime(2026, 2, 3, tzinfo=timezone.utc).timestamp()
        os.utime(path, (stamp, stamp))
        session = CursorParser.parse(path)
        self.assertEqual(session.date_str, '2026-02-03')
        self.assertEqual(session.date_source, 'file_mtime')
        self.assertIsNone(session.started_at)
        self.assertIsNone(session.ended_at)
        self.assertIsNone(session.duration_seconds)
        self.assertEqual(session.cwd, '')
        self.assertEqual(session.project_slug, 'workspace-example-project')
        self.assertEqual(session.messages[-1].role, 'tool')
        self.assertEqual(len(session.messages[-1].tool_results[0].content), 1600)
        row = JsonIndexRenderer.session_to_dict(session)
        self.assertEqual(row['date_source'], 'file_mtime')
        self.assertIn('file modification time', MarkdownRenderer.render(session))
        self.assertEqual(CursorParser.find_session_file(SID), path)
        nested = self.write(f'.cursor/projects/workspace-example-project/agent-transcripts/{SID}/subagents/child.jsonl', [])
        self.assertNotIn(nested, CursorParser.list_sessions())
        out = self.home / 'exported'
        JsonIndexRenderer.update(session, out / 'sessions.json')
        report = WeeklyReport.from_directory(out, since='2026-02-01')
        self.assertEqual(len(report.sessions), 1)
        self.assertIn('Estimated dates:', report.render())

    def test_empty_invalid_and_filtered_files_have_coverage(self):
        self.write('.codex/sessions/empty.jsonl', [meta(OTHER)])
        path = self.write('.codex/sessions/valid.jsonl', [meta(), message('user', 'Example.', 1)])
        with path.open('a') as stream:
            stream.write('invalid json\nnull\n')
        out = self.home / 'exported'
        args = Namespace(agent='codex', project=None, output=str(out), cwd=None,
                         dry_run=False, coverage=True, since='2026-03-01', until=None)
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_bulk(args)
        coverage = json.loads((out / 'coverage.json').read_text())
        self.assertEqual(sorted(r['status'] for r in coverage['sources']), ['empty', 'outside_period'])
        self.assertEqual(coverage['exported_sessions'], 0)

    def test_decisions_exclude_instructions_tools_quotes_and_code(self):
        session = Session(id=SID, agent=Agent.CODEX, messages=[
            Message(role='user', text='<environment_context>Decision: bogus environment text.</environment_context>'),
            Message(role='assistant', phase='commentary', text='Decision: intermediate candidate only.'),
            Message(role='assistant', text='', tool_calls=[ToolCall('example', 'Decision: bogus tool input.')]),
            Message(role='tool', text='Decision: bogus tool output.', tool_results=[ToolResult('Decision: bogus result.')]),
            Message(role='assistant', text='<system_reminder>Decision: bogus reminder text.</system_reminder>\n'
                '```python\nDecision: bogus code example.\n```\n'
                '> Decision: bogus quoted example.\n'
                'Decision: Keep the example cache local.\nInstead of a remote cache.'),
        ])
        distilled = Distiller.distill(session)
        self.assertEqual(distilled.decisions, ['Keep the example cache local.'])
        self.assertEqual(distilled.outcome_source, 'heuristic_unverified')
        out = self.home / 'exported'
        md = MarkdownRenderer.write(session, out)
        fallback = Distiller.distill_from_markdown(md)
        self.assertNotIn('bogus', ' '.join(fallback.decisions))
        distilled.save(out)
        self.assertEqual(DistilledSession.load(out / f'{SID}.distilled.json').distill_version, 3)

    def test_read_errors_are_reported_and_fail_bulk(self):
        out = self.home / 'exported'
        args = Namespace(agent='codex', project=None, output=str(out), cwd=None,
                         dry_run=False, coverage=True, since=None, until=None)
        with patch.object(CodexParser, 'list_sessions', return_value=[self.home / 'unreadable.jsonl']), \
             patch.object(CodexParser, 'session_id', side_effect=PermissionError), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                cmd_bulk(args)
        self.assertEqual(error.exception.code, 1)
        row = json.loads((out / 'coverage.json').read_text())['sources'][0]
        self.assertEqual(row['status'], 'error')
        self.assertEqual(row['error_type'], 'PermissionError')

    def test_bulk_dry_run_writes_no_export_files(self):
        self.write('.codex/sessions/example.jsonl', [meta(), message('user', 'Example.', 1)])
        out = self.home / 'exported'
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_bulk(Namespace(agent='codex', project=None, output=str(out), cwd=None,
                               dry_run=True, coverage=True, since=None, until=None))
        self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
