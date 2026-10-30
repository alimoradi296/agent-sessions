# Cross-agent session recovery screen

**Date:** 2026-10-28
**Status:** Closed as a generic product lead; no product or demand validation.

## User problem

The conversation file can remain on the user's computer while an agent application's sidebar or resume index stops exposing it. The user then has to identify the affected storage layer and repair provider-owned state by hand. This is different from a transcript parser failing to read a record or a backup tool restoring a file.

## Public problem evidence

| Provider | Public report | What it supports | Limit |
|---|---|---|---|
| Codex | [Issue #40779](https://github.com/openai/codex/issues/40779) requests a local recovery/reindex path after sessions disappeared from the UI while JSONL files remained. The report describes repeat occurrences and links earlier reports. | A concrete index-versus-transcript failure and user request for first-party recovery. | User-reported cases do not establish prevalence or a market. |
| Claude Code | [Issue #60341](https://github.com/anthropics/claude-code/issues/60341) and [issue #78130](https://github.com/anthropics/claude-code/issues/78130) describe sessions that remain resumable from local records but disappear from Desktop navigation. | A related failure across separate Desktop/session-index paths and triggers. | Issue reports are not a measured incident rate; behavior may change by version and installer. |
| Cursor | [A community recovery guide](https://forum.cursor.com/t/how-i-recovered-my-vanished-cursor-chat-so-you-dont-have-to/151158) describes several hours of investigation to recover one vanished chat from local databases. Another [Cursor forum report](https://forum.cursor.com/t/cursor-lost-all-my-agent-chat-history/158837) describes a local database workaround for 175 conversations. | High manual effort in two reported local-index failures. | Community reports are not official specifications or independent reproductions; the Cursor team said a repair was being worked on. |

As checked on October 28, 2026, Codex issue #40779 remains open. Claude issue #78130 remains open and reports repeated losses within one day; issue #60341 was closed as not planned, while later comments still report similar navigation failures. Cursor's [release notes](https://prod.cursor.com/docs/release-notes) document improvements to loading long chat history, but this review did not find an official note confirming that the separate local-database repair case is fixed. This is a bounded review of public issue pages and release notes, not a live product reproduction.

These reports show a costly failure mode can occur across several clients. They do not establish how often it occurs, how many people will pay to prevent it, or whether the current provider versions still reproduce it.

## Existing tools and gap

| Tool | Documented coverage | Remaining boundary |
|---|---|---|
| [SessionArk](https://git.mitgai.net/julescules/sessionark) | Read-only consistency audit and snapshot/restore for Codex and Claude stores, with damaged JSONL salvage. | It restores into an isolated directory and does not repair live provider indexes; Cursor support is listed as future work. |
| [Codex Session Recovery](https://github.com/fengyazi/Codex-session-recovery) | A Codex-specific skill documents backups, index reconciliation, SQLite state repair, and metadata normalization. | Provider-specific; its public repository has limited evidence of maintained/runtime coverage. |
| [Claude Code Session Recovery](https://github.com/BasedGPT/claude-code-session-recovery) | A dedicated toolkit documents read-only diagnosis and dry-run/apply repairs for missing Desktop metadata, duplicate links, blank history, missing transcripts, and backup-based restoration. | Provider- and installer-specific; its docs warn some MSIX paths are not repaired by metadata synthesis. Its own coverage claims have not been independently validated here. |
| [Claude session-recovery](https://github.com/ibrews/claude-session-recovery) and [ccdiag](https://github.com/kolkov/ccdiag) | Additional Claude-specific projects document backup, index repair, or transcript analysis/recovery. | Project descriptions are not runtime or adoption evidence; neither claims cross-provider native-index repair. |
| [AllSessions](https://github.com/yuluod/AllSessions) | Broad local browsing across many agent stores and a Codex visibility-repair tool. | Its documentation limits that repair tool to the primary `CODEX_HOME`; other providers are read-only. |
| [cursor-chat-recovery](https://pypi.org/project/cursor-chat-recovery/) and [Cursor Chat Transit](https://marketplace.visualstudio.com/items?itemName=oshokin.cursor-chat-transit) | Cursor-specific tools document local database recovery, moving/exporting chats, backups, and restoring usable history from incomplete exports. | Project/extension descriptions are not independent runtime results or adoption evidence; the store format is undocumented and version-sensitive. |

This repository parses Codex and Claude Code transcript JSONL and Cursor project `agent-transcripts` JSONL, and has a separate, evidence-labeled Codex captured-file restore command. It does not inspect Codex `state_5.sqlite`, Claude Desktop's native session metadata/index stores, or Cursor's reported global/workspace SQLite databases; it does not reconcile or repair native history indexes. Parser support is not native-store repair capability, and the affected Cursor database case would need a new adapter.

## Product hypothesis

A local-first **session recovery doctor** could identify whether a missing conversation is absent, corrupt, orphaned, or merely disconnected from the provider's UI index; explain the evidence; and, only when a provider/version-specific repair is well understood, prepare a backup-backed repair with a verified rollback path. The first useful outcome is “find and safely restore access to the conversation,” not another transcript browser or cloud backup service.

The potential distinction was one consistent diagnostic and recovery workflow across Codex, Claude Code, and Cursor. Current public tools now cover Codex and Claude repair, broad cross-agent browsing plus some Codex visibility repair, and Cursor database recovery/export. A unified wrapper might reduce tool switching, but this is not a distinct technical outcome and no buyer evidence shows that users value it. The synthetic probe did not change that assessment.

## Synthetic probe and decision

The [synthetic probe](cross-agent-session-recovery-prototype.md) correctly classified nine authored examples across the three providers: healthy, source without UI-index entry, and index without source. The Cursor SQLite shape is only illustrative; it is not a validated provider adapter. No competitor was run against the fixtures, and no repair was attempted. The probe demonstrates a common vocabulary, but its output does not improve on the existing provider-specific diagnostics.

Close the generic recovery-doctor direction. The existing tools cover the reported workflows closely enough that a shared report format alone is not a product wedge. Reopen only for a newly reported, reproducible failure that all available recovery tools miss and that produces a materially better user outcome. No such residual case or willingness-to-pay evidence is established.

No real transcripts, databases, paths, session identifiers, or recovery reports were read or included. Any real local run must remain private; public fixtures must be synthetic.
