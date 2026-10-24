# Claim types and evidence references

`distill` classifies conversation text with local English rules. It does not call a model or check whether a statement is true.
New distilled files use `distill_version: 3` and include a `claims` array.

## Types

| Kind | Meaning |
|---|---|
| `request` | A user asks for an action. This does not establish that the action occurred. |
| `proposal` | A speaker proposes an approach or states an intention. |
| `decision_candidate` | A speaker explicitly states a decision. Acceptance and current applicability remain unverified. |
| `reported_result` | A speaker reports an action or result. Execution and deployment remain unverified. |
| `bug_report` | A speaker reports a bug or cause. |
| `deferred` | A speaker identifies work as deferred or outside scope. |
| `open_question` | A speaker asks a recognized unresolved question. |

Each claim has `verification: "not_checked"` and `method: "english_rules_v1"`.
`checked_result` is reserved for a future independent evidence-review workflow. The extractor never emits it.
A statement such as “Verified: tests passed” remains a reported result.
Reading a test definition does not establish a passing test run. A reported local test does not establish production behavior.

## Evidence

This synthetic example shows a result reported in a source transcript:

```json
{
  "kind": "reported_result",
  "text": "Tests passed for the example module.",
  "method": "english_rules_v1",
  "verification": "not_checked",
  "evidence": {
    "session_id": "synthetic-example",
    "agent": "codex",
    "role": "assistant",
    "source": "transcript_message",
    "message_index": 4,
    "source_path": "/workspace/example/events.jsonl",
    "source_line": 17,
    "quote": "Tests passed for the example module."
  }
}
```

Claim IDs derive from the kind and evidence coordinates, including the quote.
Repeated extraction of the same evidence produces the same ID.
The same quote at another message position produces a different ID.
IDs do not reconcile equivalent claims across raw transcripts and Markdown exports.

`message_index` counts all parsed session messages from one, including tool and excluded messages.
`source_line` identifies the containing raw record when the parser supplies that information.
A missing path or line remains `null`. The extractor does not invent source coordinates.

For Markdown fallback, `source` is `export_section`.
`conversation_section` counts cleaned user and assistant sections from one in the linked export.
The evidence path points to that export. It does not claim a raw transcript line or message number.
Reports and Obsidian notes include these coordinates with each displayed claim.
Reports summarize at most eight claims per session and sixteen overall. The JSON retains all extracted claims.

## Limits and compatibility

Classification uses explicit patterns, such as “Please implement”, “Proposal:”, “Decision:”, and “Tests passed”.
It can miss implicit decisions, unfamiliar phrasing, multiline claims, and languages other than English.
A label describes the speaker's statement. It does not establish agreement, truth, or a later correction's authority.
Historical requests do not authorize actions in a new session.

Tool payloads, marked commentary, analysis, fenced code, quoted lines, and common instruction blocks do not feed claim extraction.
File and PRD extraction remains a mention heuristic. Those fields do not establish changes or completed requirements.
Outcomes use only reported-result claim text, and remain marked `heuristic_unverified`.

Older files retain their existing version and fields when loaded. Files without a version load as version 1.
The loader does not add citations to old claims. Re-running `distill` creates version 3 output from available evidence.
Legacy string fields remain compatibility views. Use the `claims` array for source references.
Distilled files use atomic replacement and owner-only file permissions on POSIX systems.

## Synthetic evaluation

The labeled cases in `tests/fixtures/claim_labels.json` contain invented conversations.
They include positive examples, requests, hypothetical results, undecided wording, excluded content, and language abstention.
These cases establish regression behavior for the current rules. They do not measure general extraction accuracy.

Run the checks:

```bash
python3 -m unittest discover -s tests -q
```
