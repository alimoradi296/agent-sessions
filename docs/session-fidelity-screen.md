# Session-format fidelity and recovery screen

Date: 2026-10-28

## Decision

Do not build a generic transcript parser, format-conformance suite, archive, or history-repair product. Recent public reports describe serious mismatches between persisted source records and what agent applications can export, display, or resume. Direct projects now cover preservation packages, integrity checks, backup/restore, format conversion, conformance tests, and provider-specific index repair.

A narrower diagnostic question remains: can a read-only tool prove exactly where a provider's stored session and its visible/exported history diverge, then recover a useful view without writing to provider-owned state? This is a research question, not a product direction. No unique advantage, demand, or willingness to pay is established.

## Public evidence

| Evidence | What it supports | Limit |
|---|---|---|
| [Claude Code issue #42290](https://github.com/anthropics/claude-code/issues/42290) | A report says `/export` and `/resume` omit content when parallel tool results arrive out of order, while the local JSONL still contains it. | One reporter's version-specific case is not a prevalence estimate or current independent reproduction. |
| [Codex issue #42025](https://github.com/openai/codex/issues/42025) | A report links a structured `token_count` record to a stuck history projection while rollout JSONL remained intact; later comments say affected histories stayed unavailable after upgrades. | Issue evidence is reporter-provided and does not establish all clients, versions, or affected sessions. |
| [Codex issue #37673](https://github.com/openai/codex/issues/37673) | A source-level report describes migration silently omitting valid JSONL records larger than its line limit while reporting migration success. | This is a specific migration path and does not establish general transcript-parser failure. |
| [Unified Agent Session Specification](https://github.github.com/gh-aw/specs/unified-agent-session-specification/) | Specifies broad edge-case matrices and normative conformance testing across many provider formats, including malformed, unknown, partial, and reordered records. | It is a GitHub Agentic Workflows specification, not proof that every provider or third-party reader conforms. |
| [Session Preserve](https://github.com/davidqyc/session-preserve) | Documents read-only exports with provider-specific coverage, provenance, privacy boundaries, and manifest-relative hash verification. | It explicitly does not attest that all UI-visible content was persisted or repair provider-owned state. |
| [Agent Session Pack](https://github.com/YosefHayim/agent-session-pack) | Documents local archives, copy-based proof checks, byte-exact restore, and coverage across multiple agent stores. | Archival integrity is distinct from semantic completeness of an exported transcript or native UI recovery. |
| [ectype](https://github.com/chaybits/ectype) | Documents reading, filtering, redacting, exporting, and importing histories across ten coding agents and three chat applications. | Its documentation warns that redaction is best effort and conversion does not restore original runtime state. |
| [SessionArk](https://git.mitgai.net/julescules/sessionark) | Describes integrity-first backup and recovery for local coding-agent session stores. | The project page does not establish cross-provider runtime quality or adoption. |

## Fit with this repository

This repository already records parser-level malformed and unsupported-record counts in coverage/`doctor` output and has synthetic provider fixtures. It exports readable views from local sources, but it does not compare a provider's internal UI projection against a parsed source snapshot, nor does it repair provider-owned indexes or restore imported application state.

The strongest supported outcome here is therefore “show what this reader preserved and what it could not parse,” which overlaps existing conformance and preservation work. Claiming “the session is complete” would exceed available evidence: a persisted file cannot prove that all application-visible messages reached disk.

## Next gate

Do not add another parser/backup feature. First map whether the three reports above are already addressed in their current provider versions and whether an existing read-only source reader exposes a verifiable gap. Compare the proposed output with the current native export, Session Preserve's receipt, and one provider-specific repair workflow using invented records only. Continue only if a current, reproducible failure remains and this repository can expose a materially better recovery outcome without mutating native state. Keep issue IDs, local paths, transcripts, and real session identifiers out of public fixtures.

## October 28 follow-up: migration can discard a valid oversized record

The report statuses were rechecked. Claude Code #42290 is closed as not planned after inactivity. Codex #42025 remains open; its latest visible reporter follow-up says 16 histories were still blank or truncated on a September Desktop build, but this is not a current-version reproduction. Codex #37673 remains open and describes a deterministic legacy-migration path that omits JSONL records larger than 16 MiB. A second open report, Codex #44141, describes the same reader limit affecting compacted checkpoints and says the size-limit/discard path was also present in the inspected main-branch source. The [current public Codex migration source](https://github.com/openai/codex/blob/main/codex-rs/thread-store/src/local/rollout_migration.rs) still declares the 16 MiB line limit, and its migration loop skips records without a parsed line. This is source evidence, not proof of behavior in every released binary.

### Synthetic source-to-projection probe

`examples/evaluate_session_migration_fidelity.py` creates an authored source transcript with a tool result whose JSONL line exceeds 16 MiB, then models the documented reader behavior by omitting that physical line from a second temporary transcript. The repository's current `CodexParser` reads all six message records from the source. A semantic comparison using role, text/tool fingerprints, and call IDs attributes the missing tool result to source line 5; the modelled projection contains five records and no tool result. The report emits only sizes, counts, and line numbers, not the synthetic payload.

The expanded five-case matrix found:

| Synthetic change | Whole-file SHA | Raw record comparison | Semantic comparison |
|---|---|---|---|
| Unchanged control | Equal | Equal | Same order, no omissions |
| Oversized tool-result omission | Detects change | Locates missing source line 5 | Identifies missing tool result at line 5 |
| Duplicate message | Detects change | Counts one extra record | Counts one extra parsed message |
| Reordered messages | Detects change | Same record multiset | Detects order change |
| Unsupported record omitted | Detects change | Locates missing source line 8 | Does not invent meaning; source parser reports one unsupported record |

The source-to-projection matrix is still modeled locally from authored data. Separately, a current local runtime check now used the installed Codex CLI `0.164.0` with an isolated temporary `CODEX_HOME`, telemetry disabled, and only authored synthetic legacy rollouts. The fixture shape follows Codex's public test helper for legacy session metadata and records ([source](https://github.com/openai/codex/blob/main/codex-rs/app-server/tests/common/rollout.rs#L1558-L1635)).

The small control used a 128-byte assistant response: the before and after files both parsed as two messages, with no missing source lines. The paired response placed an assistant `output_text` record larger than 16 MiB on source line 4. Codex CLI `0.164.0` returned `status: migrated` with no failure reason; the before file parsed as two messages, the migrated file as one, and the semantic comparison identified source line 4 as missing. The JSONL shrank from 16,778,623 bytes to 1,262 bytes, and stdout/stderr contained no oversize warning. This is a reproducible behavior of this installed CLI build and authored fixture, not a release-wide claim or proof about other migration paths. The probe used `--apply` only inside a disposable temporary home; it did not read or modify the user's Codex data. The synthetic reproduction is available as [`examples/probe_codex_rollout_migration.py`](../examples/probe_codex_rollout_migration.py).

The runtime result makes the issue materially stronger than the modeled matrix alone. It does not establish how often real sessions encounter this shape, whether all versions behave this way, whether provider repair tools preserve the omitted message, or whether source-linked comparison saves user time.

### Workflow comparison

| Workflow | Documented or observed result | What it answers for this fixture |
|---|---|---|
| Codex CLI 0.164.0 `migrate-rollouts --apply` | **Observed locally** with a small control and an over-16-MiB assistant response | Reports `migrated`; preserves both small-control messages, but drops the assistant response at source line 4 without a matching warning |
| Session Preserve receipt | **Documented only**: records source coverage/provenance and checks packaged files against recorded SHA-256 and size; source sessions remain read-only and it does not restore or repair them ([README](https://github.com/davidqyc/session-preserve/blob/main/README.md)) | Can attest that the preserved source package is intact; its documented receipt does not compare semantic records with Codex's migrated output |
| Agent Session Pack archive/restore | **Documented only**: restores archives and compares SHA-256 before removing originals ([README](https://github.com/YosefHayim/agent-session-pack/blob/main/README.md)) | Can provide byte-exact source recovery from its archive; its documented workflow does not locate semantic records missing from the migrated projection |
| [session-migrate validation campaign](https://github.com/xhluca/session-migrate/blob/main/docs/validation-report.md) | **Documented only**: compares an independent source semantic projection with reparsed target values, order, roles, IDs, and tool linkage; checks expected-loss counters; treats unexplained differences as release blockers. It reports synthetic oversized-input coverage, but does not name this exact Codex 16 MiB migration case. Its architecture retains source record ordinals/types where available ([architecture](https://github.com/xhluca/session-migrate/blob/main/docs/architecture.md)) | Directly overlaps general source-to-target semantic reconciliation and omission accounting. Whether it detects this exact provider-native migration defect is unverified; the competitor was not run on the fixture |
| This repository's synthetic source-linked comparator | **Observed locally** on authored source and destination fixtures | Attributes an omitted semantic record to its source line and distinguishes omissions from duplicates, reordering, and unsupported records |

Session Preserve and Agent Session Pack document source preservation and byte integrity, while session-migrate documents semantic source-to-target verification and loss accounting. The competitor projects were not run on the local synthetic fixture; their public validation reports are evidence of workflow overlap, not independent proof of quality on this exact provider migration path.

The five-case matrix is a feasibility probe; the separate local Codex CLI run is a provider migration run against authored synthetic input. It does not establish release-wide behavior, product accuracy against arbitrary migrations, or market demand. It does show a candidate outcome beyond a byte-preservation receipt: identify which semantic record disappeared after a transformation and locate its source. Session Preserve documents source coverage, provenance, and integrity verification but says it does not reindex or repair provider state. Agent Session Pack documents byte-exact archive/restore before removal. Their public descriptions do not claim semantic source-to-destination reconciliation; neither CLI was run against this fixture.

### Decision

Close **broad source-linked migration fidelity checking** as a product lead. The Codex CLI 0.164.0 synthetic reproduction remains useful parser/correctness evidence. [session-migrate's validation report](https://github.com/xhluca/session-migrate/blob/main/docs/validation-report.md) describes independent semantic source/target comparisons and loss accounting across many formats, directly overlapping the general proposed outcome. [Moirai](https://github.com/october-dev/moirai) also documents cross-agent conversion. Neither was run against this exact Codex 16 MiB fixture, so behavior on that specific native migration remains unknown; that gap alone does not establish a viable product or buyer.

Reopen only around a specific transformation gap that these tools do not expose and that changes a user's recovery decision. Real-session prevalence, competitor runtime behavior, adoption, and willingness to pay remain unestablished. Do not access private archives or contact maintainers for this screen.

### October 28 follow-up: hidden native sessions

Newer reports describe intact local records that are absent from Codex, Claude Desktop, or Cursor navigation. As of this screen, Codex #40779 and Claude #78130 remain open. Cursor's public release notes mention history-loading improvements but do not establish a fix for its reported database-index corruption. The recovery surface is now covered by Codex and Claude repair projects, SessionArk, AllSessions, and Cursor-specific database recovery/export tools. These reports do not reopen a generic reindex or recovery product. The synthetic probe and competitor comparison are recorded in the [cross-agent session recovery screen](cross-agent-session-recovery-screen.md); no distinct residual outcome or buyer evidence was established.
