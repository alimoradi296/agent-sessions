# Evaluation index

These reports describe specific tests and observations rather than product or commercial guarantees.
All public fixtures are synthetic.
Private source material and incident reports stay outside this repository.

| Question | Reports |
|---|---|
| What overlaps with existing tools? | [Product direction](product-direction.md), [context-selection probe](context-selection-probe.md), [regression tools](regression-tool-comparison.md), [native importers](native-importer-comparison.md) |
| Does the reader retain the task? | [Reader protocol](reader-pilot.md), [fresh sessions](fresh-session-results.md), [long history](long-history-results.md), [actual coding continuation](changed-context-coding-results.md) |
| How much overhead and maintenance remain? | [Scaling and saved notes](review-scaling-results.md), [review burden](review-burden-evaluation.md), [inspection volume](inspection-volume-evaluation.md), [maintenance](maintenance-evaluation.md), [imported review maintenance](imported-review-maintenance.md) |
| Can the assistant operate the workflow? | [Automatic selection](automatic-selection-evaluation.md), [validated import](assistant-selection-import.md), [topic refresh](topic-review-refresh.md), [continuation skill](continuation-skill.md) |
| What does an incident actually establish? | [Chronology replay](chronology-replay-results.md), [source-origin hints](source-origin-hints.md), [incident evidence protocol](incident-evidence-protocol.md) |
| Is another command checker needed? | [Existing schema and typing checks](schema-preflight-results.md) |
| Can supplied code be matched to captured failures? | [Evidence search and candidate filtering](evidence-search.md) |
| Does evidence search improve an assistant investigation? | [Fresh receiving-assistant comparison](investigation-reader-results.md) |
| Does text output improve the interaction? | [Separate holdout and protocol ambiguity](investigation-text-holdout.md) |
| Does direct line citation reduce investigation work? | [Clarified numbered-evidence follow-up](numbered-investigation-followup.md) |
| What does a complete search command cost at the measured sizes? | [Fresh-index scans and mixed-size controls](search-scale-results.md) |
| Does another native importer retain the tested searchable evidence? | [Pinned CASS runtime comparison](cass-evidence-comparison.md), [agent-replay parser comparison](native-importer-comparison.md) |
| Does source matching establish a disclosure? | [Existing matching mechanisms and synthetic controls](disclosure-matching-controls.md) |
| Can existing agent parsers feed a staged-addition overlap check? | [Synthetic archive-to-diff evaluation and limits](archive-disclosure-evaluation.md) |
| Does the distributed package work outside the checkout? | [Source archive and isolated wheel check](distribution-check.md) |
| Does capture health establish written output and recovery? | [File-only persistence failure controls](capture-delivery-controls.md) |
| Can required handoffs retain tool messages? | [Raw evidence handoffs and receipt exercise](raw-evidence-handoffs.md) |
| What happens when raw investigation evidence changes? | [Repeated saved-topic review and source-inspection control](raw-evidence-handoffs.md#repeated-investigation-control-october-27) |
| Can future tool outputs use the existing evidence path? | [Synthetic Cursor hook-shaped results](cursor-output-evidence.md) |
| Does existing recovery replay preserve editor semantics? | [Pinned patch-module controls and uncertainty limits](regression-tool-comparison.md#pinned-recovery-implementation-check-october-26) |
| Does the restored project behave correctly? | [Two-module restoration and independent behavioral oracle](regression-tool-comparison.md#restored-project-behavior-october-27) |
| Can complete files survive inside orchestration wrappers? | [Static captured-file restoration and private feasibility boundaries](captured-file-restoration.md) |
| Is the wrapper advantage publicly reproducible? | [Synthetic captured-restoration comparison](captured-restoration-evaluation.md) |
| Can an archived child session preserve a missing subagent result? | [Subagent output durability screen](subagent-output-durability-screen.md) |
| Can a source-to-projection comparison locate a modeled migration omission? | [Session fidelity screen](session-fidelity-screen.md), [synthetic migration fidelity probe](../examples/evaluate_session_migration_fidelity.py), [isolated Codex migration probe](../examples/probe_codex_rollout_migration.py) |
| Can Git history reconstruct a session's exact starting tree? | [Native-session regression screen](native-session-regression-screen.md), [synthetic Git transition probe](../examples/evaluate_git_base_reconstruction.py) |

Historical prompt sizes describe the measured version and can change after later framing updates.
Test passing, source coverage, captured tool responses, and commercial value are separate claims.
