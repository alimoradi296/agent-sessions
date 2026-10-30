# Synthetic context-at-decision comparison

Evaluation date: October 28, 2026. This is one authored Pi runtime scenario. It used Pi 1.4.0, `pi-provider-trace` 0.1.1, an isolated Pi home under `/tmp`, and a fake OpenAI-compatible server bound to loopback. The fake model made no external request. No real session, credential, provider account, or repository project data was used.

## Scenario

The synthetic user request asked Pi to change `VALUE` while preserving a second line in `target.py`. A test-only `before_provider_request` extension removed the preservation sentence from the request sent to the provider but left Pi's saved user message unchanged. The fake provider then made the generated write depend on whether that sentence was present. This deliberately injects a context-loss bug; it does not model how often real agents lose instructions.

## Results

| Evidence | Observation |
|---|---|
| Normal control request | The saved session and provider request both contained the preservation instruction; the generated file retained the line |
| Altered request, saved Pi session | Still contained the user's original preservation instruction |
| Altered request, `pi-provider-trace` provider payload | Did not contain the preservation instruction |
| Altered request, local fake provider | Received two requests; neither contained the omitted instruction |
| Altered request, generated file | Changed `VALUE` and dropped the protected line, matching the fake model's scripted branch |
| Trace records | Included the Pi input, provider request/response stream, and tool-call/result lifecycle for the synthetic session |

The comparison confirms that the native session alone would not reveal this request-time omission. The existing Pi provider tracer exposes the effective request, and its session timeline plus the resulting file is enough to diagnose this deliberately constructed case. I inspected raw local trace records; I did not evaluate the tracer's rendered UI, reviewer time, or the quality of a real model's diagnosis. The synthetic provider was programmed to make its response depend on the request, so this is instrumentation feasibility—not evidence of general causal accuracy.

## Product decision

Close a Pi-only prompt-capture or context-debugging product for this scenario: [Pi's extension API](https://pi.dev/docs/latest/extensions) and [`pi-provider-trace`](https://github.com/Dwsy/pi-provider-trace) already expose the needed request and lifecycle evidence. Claude also documents full-content request telemetry in [OpenTelemetry](https://platform.claude.com/docs/en/manage-claude/opentelemetry), and other local session viewers overlap with the timeline. A product idea that only adds prompt capture or a Pi trace viewer would duplicate existing work.

The remaining untested hypothesis is a cross-agent workflow that joins effective model input, action/result, and the exact resulting code change with less analyst effort than the best available tools combined. No runtime comparison across Claude, Codex, Cursor, Pi, or other agents establishes that gap. No human buyer evidence, repeated use, or willingness to pay is established. Do not implement from this probe alone.
