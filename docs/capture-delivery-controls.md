# Check written output before trusting capture health

A successful producer callback does not establish that its result reached a local output file.
The pinned OpenTelemetry Hooks comparison now includes a controlled file-export failure and recovery.
All payloads and state are authored synthetic data in disposable directories.
No normal agent session, installed hook, private archive, or remote exporter participates.

## Method

The original runtime is [revision 2b922aeddab9e83bea5e932e3d2558f0bd397e3b](https://github.com/o11y-dev/opentelemetry-hooks/tree/2b922aeddab9e83bea5e932e3d2558f0bd397e3b).
The environment matches the [capture comparison](cursor-output-evidence.md#existing-cross-agent-capture-comparison).
Text capture is enabled, batching is enabled, logs are disabled, and the exporter endpoint is explicitly empty.
A temporary project has a real command registration pointing to the tested runtime.
No client session invokes that registration; the experiment submits callback payloads directly through the CLI.

Each case sends a session start, prompt, tool call, tool result, and stop.
The tool input is fictional data; no archived or fictional operational command is executed.
Before stop, the expected output marker is present in the buffered generation.

The healthy case has a usable local-output directory.
The failure case places a regular file where that directory should be.
After the failed flush, the test repairs only that temporary path and retries the stop callback.
Output checks parse the resulting JSONL and require the expected result text, session, generation, and tool ID.
Callback status and buffer presence alone do not pass that check.

## Observations

| Observation | Original runtime | Local persistence prototype |
| --- | --- | --- |
| Healthy result written to local span output | Yes | Yes |
| All five callback exit codes in the blocked case | 0 | 0 |
| Blocked result written to local span output | No | No |
| Blocked result retained in pending batch | No | Yes |
| Doctor status after the blocked flush | Healthy, exit 0 | Degraded, exit 1 |
| Output present after repairing the path and retrying stop | No | Yes |
| Pending batches after prototype recovery | — | 0 |

The original clears the buffered result despite the local exporter refusing the write.
Its local-only doctor status remains healthy with no pending batch.
This is a bounded observation at the pinned revision, not a claim about every collector or current release.
`local_only` describes exporter configuration; it does not independently prove delivery.

The prototype records local export failures and marks file-only trace flushes unsuccessful.
The existing retry path then retains the batch rather than clearing it.
A later successful flush writes the expected result and returns doctor to healthy.
For a configured remote exporter, an optional local-mirror failure does not change remote trace authority.
That authority condition has a unit control; no live remote export was tested.

Three new regression tests fail on the original runtime.
The patched selected run passes 26 tests, with 75 deselected.
The [reviewable patch](../examples/patches/otel-local-file-persistence.patch) applies cleanly to a separate copy and matches the tested runtime fingerprint.
The patch is not installed in the user's agent configuration or integrated into production capture here.

## Reproduce

With dependencies already installed in a separate temporary environment:

```sh
python3 -m examples.otel_capture_delivery_probe --source /path/to/original/pinned/source --python /path/to/temporary/venv/bin/python
python3 -m examples.otel_capture_delivery_probe --source /path/to/patched/source --python /path/to/temporary/venv/bin/python
```

The probe accepts only the documented source fingerprints and refuses missing dependencies before upstream bootstrap can run.
Exit 0 means the expected comparison observations matched; it does not mean every tested capture path was healthy.
Inspect the output-delivery and pending-state fields.
The original and modified runtimes are labeled separately, with the upstream parent revision retained.

## Product decision

Keep capture integration gated on observed output and recovery, rather than callback success or configuration health alone.
Reuse the existing capture and retry mechanisms with a bounded compatibility fix.
Do not add another collector to address this demonstrated case.

Normal-client delivery, source identity, orphan-event recovery, crashes, partial writes, sustained concurrency, and exactly-once delivery remain unestablished.
These controls establish a local failure window and a recovery path, not reader advantage, exclusivity, demand, or willingness to pay.
