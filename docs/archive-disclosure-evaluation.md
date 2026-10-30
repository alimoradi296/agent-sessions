# Synthetic archive-to-diff disclosure evaluation

Evaluation date: October 27, 2026. All archives, Git repositories, and text in this probe are fictional and generated in temporary directories. The probe does not inspect the caller's archive directories, worktree, or Git index.

The evaluation exercises the existing Claude, Codex, and Cursor parsers, discovers message text from each synthetic native-format archive, and checks only added lines from staged Git diffs in disposable repositories. Its source-overlap method uses normalized literal windows. Two baselines are included: one manually registered fictional value, and a small authored credential-pattern regular expression. The latter is not Gitleaks; no mature credential scanner was available in the environment.

| Synthetic staged addition | All-history overlap | User-prompt-only overlap | Verified prompt links | Manual value | Credential pattern | Authored policy |
|---|---:|---:|---:|---:|---:|---|
| Long private-style phrase copied from history | Yes | Yes | 2 | Yes | No | Review |
| Same phrase with case and spacing changed | Yes | Yes | 2 | No | No | Review |
| Reworded private-style statement | No | No | 0 | No | No | Review |
| Shared public wording copied from assistant | Yes | No | 0 | No | No | Allow |
| Permitted public code copied from assistant | Yes | No | 0 | No | No | Allow |
| Short value registered manually | No | No | 0 | Yes | No | Review |
| Short fragment registered manually | No | No | 0 | Yes | No | Review |
| Credential-like value absent from history | No | No | 0 | No | Yes | Review |
| Unrelated text | No | No | 0 | No | No | Allow |

The all-history path detected the case/spacing variant, but missed the authored rewording and short fragments. It also flagged shared public wording and permitted code because those appeared in assistant messages. Restricting matching to `user` messages removed those two authored false alerts while retaining the long private-style copy and its case/spacing variant. For each of those two cases, the synthetic report produced two verified source-to-diff links: a source-message fingerprint and character/line anchor paired with the added `public.md` line. It emitted no excerpt or source path. That role filter also drops sensitive tool output and assistant text, so it trades coverage for precision. The manual-value baseline caught its two pre-registered short strings; the credential rule caught one credential-like value absent from history. The fixtures do not establish comparative accuracy or show an incremental result over the published scanner combination.

The script emitted no synthetic source strings in its report. That checks this one report path only; it does not establish a privacy guarantee. Source hashes and offsets are only safe to publish here because the source data is synthetic; reports built from real history must remain private. The fixtures and expected policy labels were authored, the credential rule is incomplete, and the evaluation measures neither realistic false-alert rates nor review time, user demand, or willingness to pay. A clean result would not certify a repository as safe to publish.

In this initial staged-diff evaluation, Gitleaks and the publication/session tools were not installed. A pinned Go invocation could not fetch Gitleaks because the sandbox denied DNS/network access. This table therefore has no runtime comparison against a mature scanner or the combined `prepublish-guard` + AgentSweep + Confessor baseline. Their public descriptions document substantial coverage of the surrounding job. Gitleaks' official repository documents staged Git scanning through its pre-commit helper ([source](https://github.com/gitleaks/gitleaks/blob/master/scripts/pre-commit.py)); that source inspection confirms workflow overlap, not runtime behavior in this initial evaluation. A later, separate synthetic blast-radius comparison is recorded below.

## Updated market screen: session and commit linkage

Public product descriptions found more direct overlap: [AgentLogs](https://agentlogs.ai/) links supported coding-agent sessions to Git commits and scans transcripts for secrets before upload; [Hooprs](https://github.com/hoophq/rs) scans local Claude Code, Cursor, and OpenCode histories for sensitive entities and ranks exposure; [ranwhat](https://ranwhat.com/) documents checks for credentials in histories across 30 agents plus credential authority; [Agensi Secret Scan](https://www.agensi.io/skills/secret-scan) documents scans of files, commits, and Git history plus write/commit/push hooks; [Stroq](https://stroq.dev/docs/) documents secret-aware agent action policies and an exact-value egress guard. These are vendor or project descriptions, not independently verified runtime results or adoption evidence.

An October 28 source review found further direct overlap in the broader history-to-code workflow: [ctx](https://ctx.rs/) documents blame from code lines and commits back to agent sessions; [Atlas](https://github.com/pacifio/atlas) links session records and patches to commits; [Atomic](https://docs.atomic.dev/guides/track-ai-agent-changes-and-reasoning) maps observed trace events to code changes and inferred causal edges; and the [TRACER research workflow](https://arxiv.org/abs/2610.34098) uses symbol-level agent history for security review and repair contracts. These public descriptions close generic session-to-commit attribution and history-backed code review as product claims. They are not runtime validation.

This additional coverage makes a general agent-history secret scanner, session-to-commit dashboard, or broad agent security layer a poor direction. A narrower hypothesis is whether a privacy-preserving, source-located link from a sensitive session value through a transformation to an exact committed line adds a useful result beyond separate history scanning, source scanning, and commit attribution. The combined comparison below found that none of its three tools emitted that link for one authored case. That is a technical residual in one fixture, not proof of a broad product gap or that no other implementation exists. Do not implement or market the candidate without evidence that the link changes a user's decision and saves reviewer effort.

Reproduce with:

```sh
python -m examples.evaluate_archive_disclosure
```

The evaluation uses temporary directories and local Git commands only. No repository files are written by the run.

## Encoded secret to committed line probe

Evaluation date: October 27, 2026. `examples.evaluate_encoded_secret_lineage` uses a fictional credential-like
value in one synthetic tool result, encodes its UTF-8 bytes as a Python integer tuple, and commits that tuple to a
temporary repository. The output contains only synthetic source identifiers, destination coordinates, and a short
temporary commit ID; it never prints the value.

| Check | Result |
|---|---:|
| Integer-tuple prototype links source to committed file and line | 1 link, `src/generated.py:2` |
| Literal archive overlap | Miss |
| User-prompt-only overlap | Miss |
| Small credential-pattern rule | Miss |
| Literal source value appears in committed candidate | No |
| Benign tuple control links | 0 |
| Synthetic secret emitted in report | No |

This shows the mechanics of one exact UTF-8 integer-tuple join. It does not show the transform is common, measure
false alerts beyond one benign tuple, or establish reviewer-time savings. The literal and regex baselines are local
controls, not Gitleaks or other mature scanners. A local runtime check on October 28 used Skarn 0.33.0 against a
separate synthetic Claude session: it reported the `.env` read as one incident, but produced no encoded-data finding,
cross-session chain, or committed-line destination. This check used one authored fixture and does not establish a
Skarn limitation generally. DeepBlame 0.5.0 was run against a separate disposable synthetic repository with matching
session read/write capture events; it attributed the generated line to the synthetic Claude Code run with 100%
coverage. It does not report that the line contains a transformed value from the earlier sensitive read. A reviewer
could potentially join those separate observations manually; reviewer effort was not measured. Gitleaks could not be
run because Docker access failed, so mature Git scanning remains untested. This is not a runtime comparison of the
combined baseline. No incremental advantage, customer demand, adoption, or willingness to pay is established. The
prototype does not handle other encodings, split values, lossy transforms, or transformations it does not know.
Reproduce the prototype with:

```sh
python -m examples.evaluate_encoded_secret_lineage
```

The prototype run uses a temporary directory and local Git commands. It does not read real archives, inspect the
caller's Git index, contact a network, or modify repository files. The Skarn and DeepBlame checks used disposable
synthetic inputs in `/tmp`; neither read the caller's archives or repository. Skarn was run from a pinned container;
DeepBlame 0.5.0 was installed under `/tmp` and its ledger stayed in the disposable repository. Gitleaks was not run.

### Runtime recheck (October 28)

`python -m examples.evaluate_encoded_secret_lineage` still reports one verified link from its authored synthetic source to the exact committed line, no benign-tuple link, and no synthetic source value in its report. This confirms only that the local prototype still runs on its synthetic fixture.

At this earlier default-sandbox recheck, Docker access and DeepBlame's child Git process were blocked. Those were environment limits, not scanner results. The local-only combined comparison below reran Gitleaks, Skarn, and DeepBlame on one authored fixture. AgentSweep, prepublish-guard, and Confessor were not run. No reviewer-time or buyer evidence was collected.

### October 28 competitive refresh

Published descriptions show strong surrounding coverage: [AgentDFIR](https://github.com/efij/AgentDFIR) documents sensitive-read-to-upload and injection-to-commit/push chains plus an offline decoder; [Chronicle](https://getchronicle.dev/) reconstructs code state at imported session messages and includes a secret scan; [GitHub's Secret Protection MCP tools](https://docs.github.com/en/code-security/how-tos/use-ghas-with-ai-coding-agents/scan-for-secrets-with-github-mcp-server) scan changed and staged files. The later combined synthetic comparison below found no exact transformed-value-to-committed-line output in Gitleaks, Skarn, or DeepBlame, but did not measure human analyst time. Close this as a product lead; keep the probe as research and reopen only with decision-changing user evidence and acceptable review cost.

### Synthetic transformation matrix (October 28)

`examples/evaluate_secret_lineage_matrix.py` extends the fabricated case to seven authored Python representations: integer tuple, `bytes([...]).decode()`, hex literal, hex decoding, base64 literal, base64 decoding, and split-string concatenation. It returned seven intended links and no links for three authored controls. The report emitted neither the fictional source value nor the temporary commit ID. The probe evaluates only literal syntax and the listed transforms; it does not execute candidate code or assess whether a value is truly sensitive. Three controls are not a false-positive rate. The matrix is a mechanism check; it does not estimate realistic false alerts, reviewer effort, or user demand. The separate one-case combined baseline below adds competitor runtime evidence but does not establish product differentiation. Keep implementation parked.

Reproduce with:

```sh
PYTHONPATH=. python examples/evaluate_secret_lineage_matrix.py
```

The script uses a temporary synthetic Claude archive and disposable Git repository. It does not read real archives or the caller's Git index and does not write repository files.

## Combined offline baseline (October 28, 2026)

One disposable Git repository and one authored Claude-shaped session contained a high-entropy fake GitHub token in `.env`; the session read it and wrote its UTF-8 bytes as an integer tuple to `src/generated.py`. The value was never printed. Gitleaks 8.30.1 ran from the official GHCR image pinned to digest `sha256:b109bc5f8f76a38196a3e413704fc5b9e3c32360bce4e4b603bd6f45b3721dbb`, with network disabled during scanning and redaction enabled. Skarn 0.33.0 scanned only the temporary session directory, read-only and offline. DeepBlame 0.5.0 imported one authored Agent Trace attribution record in the same temporary repository.

| Tool | Result on this fixture | Did it link the source value to the encoded destination line? |
|---|---|---|
| Gitleaks 8.30.1 | One `github-pat` finding at `.env:1`; no finding at `src/generated.py` | No |
| Skarn 0.33.0 | Five incidents, including `dotenv-file-read`; zero attack chains | No destination line was reported |
| DeepBlame 0.5.0 | One imported trace attributed `src/generated.py:1` to an external trace; `.env` was not attributed | No source-read/value relation was imported |

This shows an exact link missing from these three separate outputs in one deliberately encoded case. The source file, session-read finding, and line attribution provide enough clues for a human to investigate, but that manual join and its effort were not measured. The DeepBlame trace was authored for the fixture, not captured from a live agent. This does not establish tool limitations generally, realistic detection quality, a useful decision change, or buyer demand. Skarn's CLI printed that running it constitutes acceptance of its EULA; it was invoked only on this isolated synthetic fixture, and no explicit `eula accept` command was run.
