# Changed-context coding comparison

Two fresh assistants implemented the same small TTL change from equivalent historical evidence.
One received saved notes with a change notification; the other received a source-bound handoff.
Both produced identical code and passed all 13 checks declared before the readers ran.
This exercise showed no implementation advantage for the handoff.

| Complete-evidence arm | Prompt characters | Checks passed | Exclusion function preserved |
|---|---:|---:|---|
| Saved notes | 1,474 | 13 / 13 | Yes, exact text |
| Source-bound handoff | 4,852 | 13 / 13 | Yes, exact text |

The change replaced a 60-second default with 30 seconds and specified override validation.
Missing and `None` overrides use the default; integers from 1 through 300 are accepted.
Booleans, floats, strings, and other invalid values raise `ValueError`.
The current request authorized only TTL work, while exclusion policy remained unresolved.
Historical publication permission and claimed passing checks did not establish present authorization or verification.

Both readers received the same initial application and all four historical paragraphs.
Neither reader saw the facilitator checks or the other arm.
Both inherited parent model defaults; the exact model build and runtime settings were unavailable.
Their supplied request files remained unchanged, and only `cache.py` changed within each exercise arm.
Both reported local checks, and the separate grader checked the resulting code.
The handoff remained a draft because historical permissions conflicted; current authorization still permitted the bounded implementation.

## Invalid initial setup

An earlier setup accidentally limited the handoff to one source, omitting three required anchors.
That reader correctly declined to invent missing requirements; the saved-notes reader completed the change.
This was unequal evidence, so it is excluded from the complete-evidence comparison.
The initial artifacts remain separate, and the corrected run used two new fresh readers.
Preparation now rejects incomplete coverage or an exceeded handoff budget.

## Limits and decision

This is one small authored exercise with scripted evidence selection and refresh.
It does not measure discovering requirements, refresh effort, latency, cost, or general coding quality.
File inspection supports the local change claims; it is not a forensic audit of agent activity.
The findings establish no demand, willingness to pay, or exclusive capability.

Together with the saved-notes and checkpoint comparisons, this result does not justify expanding the requirements gate as a product distinction.
Keep the inspectable mechanisms available, but defer additional gate features until a concrete failure warrants them.
Investigate reproducible context-loss regression testing as another hypothesis, with an explicit comparison against existing evaluation tools.
That hypothesis is untested and may also overlap with existing projects.

## Reproduce

```sh
python3 -m examples.changed_context_coding prepare /path/to/private-exercise
```

Give each fresh assistant only its arm directory and its `request.md` task.
Keep the sibling arm and `facilitator` directory hidden.
After both readers finish, run:

```sh
python3 -m examples.changed_context_coding score /path/to/private-exercise
```

The script launches no models and reads no private archive.
