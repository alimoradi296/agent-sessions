# Source overlap and disclosure review

Review date: October 26, 2026. All runtime inputs were authored synthetic controls.
No real private corpus or pending repository diff was scanned by this experiment.
The question is whether source matching adds useful evidence before public changes are published.
It is not a claim that a passing scan certifies privacy.

## Existing mechanisms

[Gitleaks](https://github.com/gitleaks/gitleaks) supplies configurable secret-detection rules.
[Microsoft Purview](https://learn.microsoft.com/en-us/purview/sit-learn-about-exact-data-match-based-sits) documents matching registered sensitive values through schemas and hashed reference data.
[dlpscan](https://github.com/oxide11/dlpscan) supplies partial-document matching and known-value matching.
Their existence rules out treating source fingerprinting itself as a new mechanism.
Gitleaks and the enterprise service were reviewed through documentation rather than executed here.

The runtime probe loads two unchanged dlpscan modules from revision `eaf533e31bad6b107d39a38e4bed8658d5409350`.
The [reproducer](../examples/compare_disclosure_matching.py) checks each module's exact hash before loading it.
It installs no package, contacts no provider, and executes no transcript commands.
The partial matcher uses its existing 50-character windows and normalization.
A simple normalized literal-window baseline receives the same source strings.
The optional exact-data matcher receives one explicitly registered fictional account name.
This registration is authored test setup, not automatic sensitive-value discovery.

## Results

Public boilerplate and public code are deliberately registered alongside the private-style note.
This models a naive caller registering all conversation content without separating public material.
The matcher correctly finds registered text; any disclosure decision still needs that missing distinction.

| Authored case | Review needed by fixture policy | Partial overlap found | Declared account name found |
|---|---|---|---|
| Full private-style note | Yes | Yes | Yes |
| Copied fragment | Yes | Yes | Yes |
| Case and spacing changed | Yes | Yes | Yes |
| Paraphrase retaining the account name | Yes | No | Yes |
| Short account name alone | Yes | No | Yes |
| Shared public boilerplate | No | Yes | No |
| Authorized public code | No | Yes | No |
| Unrelated text | No | No | No |

The literal-window baseline and existing partial matcher return the same fragment decisions in all eight controls.
The declared-value matcher catches the short name and paraphrase because both still contain the registered value.
This does not demonstrate general paraphrase detection or discovery of which values are confidential.
The cases and policies were authored during development; they are not an independent evaluation set.
No general precision, recall, or market-value claim follows from these results.

A separate whitespace control shows that normalized match offsets do not directly identify the same raw-source slice.
Any review report needs explicit raw-source binding rather than assuming normalized offsets are raw citations.

## Product implication

Do not build another fingerprinting engine on this evidence.
Existing matching mechanisms already cover these controls with suitable configuration.
Overlap can nominate material for review, but it cannot alone establish a disclosure or authorize publication.
Known public material, permitted code, source ownership, and added-versus-removed content require explicit treatment.
A non-match also leaves privacy unestablished, especially when wording or identifiers change.

Repository controls below test added text and public-baseline exemptions.
The citation controls below test raw citation binding on synthetic sources.
No production privacy gate, automatic sensitive-value registry, or safe-publication certification is implemented by this probe.

## Synthetic repository boundaries

Eight controls use disposable Git repositories with fictional source text and authored confidentiality labels.
Each added run is checked against the target file's raw lines and SHA-256.
The caller's repository index and private history are not used.

| Change | Review new copy under authored policy | Added-run overlap | Whole-patch overlap |
| --- | --- | --- | --- |
| Add private text | Yes | Yes | Yes |
| Remove old private text | No | No | Yes |
| Edit beside unchanged private text | No | No | Yes |
| Add permitted public code | No | No | No |
| Copy previously public, now restricted text | Yes | Yes | Yes |
| Add public wording beside private text | Yes | Yes | Yes |
| Add private text wrapped across short lines | Yes | Yes | No |
| Add a new file containing private text | Yes | Yes | Yes |

Added-run matching follows the authored decision in all eight development controls.
Whole-patch matching flags removed text and unchanged context; diff prefixes also prevent a match on wrapped text.
A blanket exemption for runs overlapping the public baseline misses two cases: restricted republication and mixed public/private additions.
Prior public presence therefore cannot automatically authorize a new copy.
Removal does not establish that previous disclosure has been remediated from repository history.

These controls cover ordinary text diffs with simple paths, not binary files, renames, or every Git format.
Repository findings identify the registered synthetic document; their source coordinates are not yet integrated with the separate citation controls.
The labels and expected decisions were authored during development, so this is not independent privacy validation.

## Raw citation controls

The pinned matcher returns normalized character positions.
The probe now maps those positions to raw character spans, line numbers, and SHA-256 for both documents.
It verifies the normalized contents of each raw span before returning an anchor.
Invalid coordinates, unequal fragments, and windows that cut through a lowercase expansion are rejected.
Character offsets are not UTF-8 byte offsets.

| Synthetic source | Returned windows | Verified source locations |
| --- | --- | --- |
| Leading and expanded whitespace | 86 | Line 2 |
| Same fragment twice | 172 | Lines 1 and 3 |
| Unicode prefix and case changes | 88 | Lines 1 and 2 |

All 346 returned windows bind successfully.
Repeated text keeps its returned occurrence instead of silently selecting the first occurrence.
Fourteen regression tests cover citation boundaries, added-run extraction, overlapping-window reduction, and exhaustive literal lookup without a downloaded dependency.
These checks validate a small evidence adapter, not a new matching algorithm or an exclusive product capability.
The original 346 windows reduce to four verified findings by merging overlapping windows along the same source/candidate alignment.
The report preserves distinct source occurrences and does not merge gaps or different documents.
Repository controls now attach these findings to the added run's target-file line numbers and hash.
Across those eight cases, 519 windows reduce to seven findings, including permitted public matches.
This reduction preserves returned match evidence; it does not classify the findings or establish lower review effort.

A fourth citation control repeats the candidate text twice while registering one source occurrence.
The matcher returns 86 windows for the first candidate copy and none for the second.
Its pinned `scan` implementation deduplicates by source document and source position, regardless of candidate position.
Compaction cannot recover evidence absent from its input, so the single resulting finding is not an exhaustive list of copied locations.
This is a review-completeness limit, even though the document still receives a positive overlap result.
Neither confidentiality policy nor independent review accuracy was evaluated.

## Occurrence coverage and decision

A slow development baseline enumerates every normalized 50-character candidate window with ordinary literal lookup.
It checks all source occurrences and uses the same verified citation adapter.
Independent added runs are kept separate rather than concatenated across unchanged text or file boundaries.

| Authored control | Review needed | Upstream compact findings | Literal compact findings |
| --- | --- | --- | --- |
| Same candidate copied twice | Yes | 1 | 2 |
| Short declared name | Yes | 0 | 0 |
| Two separate 40-character additions | Yes | 0 | 0 |
| One contiguous 80-character addition | Yes | 1 | 1 |
| Unrelated wording | No | 0 | 0 |

Literal lookup recovers the repeated location without a new matching engine.
Neither 50-character mechanism detects the short name or independent short additions.
The earlier exact-data matcher covers the explicitly registered name; automatic registration remains untested.
Lowering a threshold would also require evaluating shared wording and permitted public content.
Combining independent changes into invented contiguous text would produce misleading source evidence.

Defer a production disclosure gate on this evidence.
These controls demonstrate useful citation and reporting mechanics, but no exclusive capability or willingness to pay.
Further matching-only controls will not resolve the missing confidentiality policy or establish user value.

## Reproduce

Obtain the pinned [partial matcher](https://github.com/oxide11/dlpscan/blob/eaf533e31bad6b107d39a38e4bed8658d5409350/dlpscan/rabin_karp.py)
and [exact-data matcher](https://github.com/oxide11/dlpscan/blob/eaf533e31bad6b107d39a38e4bed8658d5409350/dlpscan/edm.py) outside the checkout, then run:

```sh
python3 -m examples.compare_disclosure_matching \
  --matcher-source /path/to/rabin_karp.py --edm-source /path/to/edm.py
```

The report contains only synthetic case labels and matching observations.
No real-history inspection is needed to reproduce it.

Run the repository controls with the same pinned partial matcher:

```sh
python3 -m examples.compare_disclosure_matching \
  --matcher-source /path/to/rabin_karp.py --repository-controls
```

For raw source binding, use `--citation-controls` instead of `--repository-controls`.
For the exhaustive literal comparison, use `--occurrence-controls`.
