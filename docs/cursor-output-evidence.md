# Prospective tool-output evidence

This is a feasibility experiment, not an installed capture feature or a uniqueness claim.
Its public inputs are authored synthetic data.
Historical source material and investigation reports remain outside this repository.

An attempted tool call and an assistant's completion statement do not establish the returned result.
When the source omits that result, a larger handoff cannot supply it.
Preserving future observations is a separate problem from recovering historical file bytes.

## Existing mechanism

[Cursor's hook reference](https://cursor.com/docs/hooks) was checked on October 27, 2026.
It documents `postToolUse` with `tool_use_id`, input parameters, and a string `tool_output`.
It also documents `postToolUseFailure` with an error message and failure type.
Common fields include conversation and generation IDs.
These documented fields offer a possible capture source.
The installed CLI bundle also contains dispatch code for the two generic events.
Static source inspection does not establish native event delivery in the installed app or CLI.
A logger using these hooks is an existing mechanism, not an exclusive capability of this project.

## Synthetic data-path check

Run:

```sh
python3 -m examples.cursor_receipt_probe
```

The experiment maps three authored hook-shaped payloads to separate parser fixtures.
It passes them through the existing Cursor parser, Markdown export, JSON index, and evidence search.
It checks exact input and output retention, fixture call IDs, and source quote coordinates.
A call-only control contains no result.

| Authored payload | Retained through search | Parsed error flag |
| --- | --- | --- |
| Completed tool event containing an inconclusive inner check | Yes | Unknown |
| Completed tool event containing a backend error object | Yes | Unknown |
| Tool failure event reporting a timeout | Yes | True |

The completed-event name does not certify nested command success or application state.
The experiment retains the output string without interpreting it as a successful check.
It sets the failure flag only for the explicit failure event.

## Installed native component check

A second probe exercises the installed client's hook executor with synthetic inputs.
It checks 80 JavaScript files against bundle SHA-256
`c5e700595b697092a3d462a855f7c0c4de9a62373e7e1a0afa229151602a69c3` before importing their frozen bytes.
Node 22.23.2 is required for this recorded comparison.
The application entry point is replaced in memory with access to its module loader.
Installed source files remain unchanged.
This is an instrumented component check, not a normal agent session.

The native executor invokes a real disposable shell logger through a Node process adapter.
Its direct-stdin transport delivered all four authored events and accepted all four acknowledgements:

- A completed event with an inconclusive inner check.
- A failure event sharing the tool ID in another generation.
- A completed event containing a backend error object.
- A repeated delivery of the first event.

The logger uses a new filename per receipt, preserving repeated IDs and deliveries.
Four receipts do not establish four distinct tool operations.
The events were submitted together; this tests overlapping invocations rather than sustained concurrent capture.
No user configuration or installed hook file was changed.
Inherited account environment is cleared, and the test uses an empty temporary home.
The sandbox's Node child-process transport returned an error even for a benign echo control.
The same isolated component check passed outside that sandbox restriction.
The probe reports transport failures instead of accepting receipt creation alone as a clean pass.

Reproduce with a matching, separately installed client and a private report destination:

```sh
node examples/cursor_native_hook_probe.cjs /path/to/pinned/client > /private/native-report.json
python3 -m examples.cursor_receipt_probe --receipt-report /private/native-report.json
```

The second command retained all four outputs, fixture call IDs, and exported-source quote coordinates.
Those coordinates refer to separate normalized fixtures, not a merge into native conversation history.
The raw component report retains the conversation and generation fields separately.
A native event from an ordinary agent session, complete delivery, and production identity handling remain unverified.

## Existing cross-agent capture comparison

[OpenTelemetry Hooks](https://github.com/o11y-dev/opentelemetry-hooks/tree/2b922aeddab9e83bea5e932e3d2558f0bd397e3b)
already implements capture, session state, generation-aware correlation, and local span files.
A pinned execution used revision `2b922aeddab9e83bea5e932e3d2558f0bd397e3b`, package 0.15.0.
Its two runtime modules and package metadata have combined SHA-256
`90c163f80f5cd1db51373fac10b35c86f0c394a2f793aab73ff73b8636d7014c`.
Runtime dependencies were installed only in a temporary environment; this project's dependency list remains unchanged.
The [recorded environment](../examples/otel-hook-requirements.txt) includes the SDK and OTLP exporters at 1.45.1.
Twenty-three selected upstream tests passed; 75 were deselected.
This is not a full upstream test-suite result.

Fifteen actual CLI invocations exercised an authored session with prompts, tool calls, results, stops, and an orphan event.
File-only export was explicit: an empty config, empty exporter endpoint, and disabled log export.
Text capture was enabled with a 20,000-character limit for these short fictional outputs.
No account environment, private archive, agent session, or model was involved.

| Control | Observed output |
| --- | --- |
| Identical repeated result callback in one generation | One logical result retained |
| Same tool ID in a later generation | Separate result retained |
| Explicit timeout event | Failure text retained |
| Event with empty session and generation IDs | Output retained with empty session ID |

The four output records contain the expected fictional text.
This establishes bounded capture behavior under these settings, not complete delivery or exact retention at arbitrary sizes.
The earlier disposable raw logger kept every delivery; the telemetry path deliberately collapsed the repeated callback.
Neither receipt count alone establishes the number of distinct operations.

Reproduce after obtaining the pinned public source and preparing a separate dependency environment:

```sh
python3 -m examples.otel_hook_capture_probe --source /path/to/pinned/source --python /path/to/temporary/venv/bin/python
```

The probe refuses an unpinned source before execution and checks dependencies before upstream's import-time bootstrap can run.
A first exploratory run loaded the upstream example's localhost endpoint and emitted export-retry diagnostics.
That run is not the file-only result above.
The corrected reproducible run used explicit file-only configuration and emitted no diagnostics.

A [Cursor forum report](https://forum.cursor.com/t/cursor-hooks-intermittently-emit-empty-conversation-id-session-id-on-tool-execution-events/167095)
describes intermittently missing conversation identity in native events.
This is a reporter's observation, not an independently reproduced current-client defect here.
An orphan event must stay unattributed unless separate evidence establishes its origin.

**Decision:** do not build a new collector or correlation engine on the tested capabilities.
Existing capture is the stronger integration baseline.
The unresolved product question is whether retained outcomes improve a complete investigation compared with this existing capture plus ordinary source inspection.

## Native association and availability limits

A supported Cursor transcript can contain a tool call without an ID:

```json
{"role":"assistant","message":{"content":[{"type":"tool_use","name":"Shell","input":{"command":"fictional-check"}}]}}
```

This is an authored format example, not a real transcript.
A hook receipt's `tool_use_id` cannot establish an exact ID match to a native record that has no ID.
Matching tool names or arguments can nominate candidates but does not establish identity.
Repeated arguments and missing conversation identity need explicit treatment.
The earlier mapper fixtures deliberately included IDs; that check does not establish native transcript linkage.
Retain a receipt as its own evidence source rather than inventing a native join.

[Parsed availability metadata](evidence-search.md#parsed-tool-record-availability) now exposes counts in new exports and evidence search.
The metadata distinguishes missing result records and missing IDs from unavailable legacy counts.
These are parsed-record observations, not source-completeness, execution, or pairing certification.
Synthetic regressions cover call-only input, different call/result IDs with equal counts, and missing or invalid metadata.
This is a bounded diagnostic improvement, not a new collector or established commercial distinction.

## Local persistence is a separate gate

[Failure and recovery controls](capture-delivery-controls.md) expose a file-only batch-flush window in the pinned runtime.
Callback exit codes and configuration health pass while the blocked output is not written and the buffered result is cleared.
A small compatibility prototype retains the pending batch, reports degraded health, and writes the result after a retry.
This does not establish normal-client event delivery or justify a new collector.

## Decision and next gate

The existing parser and search can retain these authored result shapes without another search or recovery engine.
This does not prove a native receipt merge, reliable live capture, less investigation work, or commercial value.
The fixture mapper is an experiment, not a production importer.
No hook was installed, agent configuration changed, or normal agent session launched.

Before production integration, observe events from a normal authorized local session and verify stable identifiers.
Use an existing capture mechanism first.
Keep the original event distinct from normalized data, and test repeated IDs, concurrent events, failure delivery, and missing events.
Preserve local private storage and compare the complete workflow with a simple hook logger plus ordinary source inspection.
Do not infer historical results from prospective capture or require the user to select passages manually.
