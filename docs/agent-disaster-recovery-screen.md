# Agent-aware disaster recovery screen

Date: 2026-10-28

## Decision

Do not build another agent undo button, local snapshotter, or generic backup product. Public reports establish that destructive agent actions can cause serious loss, but they do not establish how often the loss occurs or whether a new product has a buyer. Existing products already cover local recovery beyond the agent's own edit checkpoints.

## Evidence

| Source | What it documents | Limit |
|---|---|---|
| [Reported repository deletion incident](https://www.techradar.com/ai-platforms-assistants/do-not-let-programs-run-commands-on-your-machine-claude-code-allegedly-deleted-48-000-files-in-103-seconds-and-its-a-terrifying-warning) | A developer report says an agent deleted tens of thousands of files, including Git object data, leaving no local Git recovery path. | One reported incident is not a prevalence estimate, independent reproduction, or buying signal. |
| [Rollcage snapshots](https://rollcage.app/features/snapshots) and [session undo](https://rollcage.app/features/sessions) | The product documents APFS snapshots of protected folders and session-level restore for shell and file changes, including deletes the agent's own checkpoint may miss. | Vendor documentation; it does not establish guarantees against whole-device loss, every volume failure, or remote side effects. |
| [uhoh](https://uhoh.it/) | The product documents local filesystem snapshots, restore, and encrypted recovery artifacts, with a wider tool-call and external-effect workflow. | Vendor description; runtime coverage and restoration guarantees were not independently tested. |
| [StepBack](https://github.com/Archerkattri/stepback) | The project documents cross-agent file snapshots, rewind, and recovery for interrupted restore operations. | Its README describes local filesystem/Git-backed recovery; it does not establish off-device disaster recovery. |
| [doover](https://github.com/CaydenChik/doover) and [bashback](https://github.com/trouties/bashback) | Both document recovery for shell-driven destructive changes, including files Git does not track. | Their described scope is undo/recovery, not a tested substitute for independent backup systems. |

## Product implication

The broad job—undo coding-agent file changes, including shell changes—is already served by agent-specific and filesystem-level products. A narrower claim about surviving simultaneous loss of a project and its backup target could be different, but this screen has no reproducible case showing that existing isolated or remote backups fail, no tested recovery design, and no buyer evidence. Do not infer a product gap from missing guarantees in public marketing pages.

## Next gate

Return to a different outcome category. Reopen this only with a specific, reproducible loss scenario that defeats the user's normal backup layer and the available agent-aware recovery products, plus measured recovery value. Do not inspect real user archives or publish personal data as part of this screen.
