# Inspection volume evaluation

Run date: October 25, 2026. The inputs contain invented conversations only.
No private archive, model, external service, or human participant took part.

## Reproduce

From the repository root, run:

```sh
python3 -m examples.evaluate_inspection_volume
```

The script creates temporary exports and removes them after the run.
It records scripted inspection notes as baseline controls.
Those notes do not represent actual human inspection.

## Scenario

Twelve invented sources contain 24 complete dialogue sections each.
Eight sources match an explicit project scope, and four belong to another project.
The initial queue includes all eight matching sources: 192 sections and 16,582 dialogue characters.
There is no initial reading-volume reduction.

After scripted notes, the replay makes seven updates:

1. Append a proposed instruction without repeating the topic query.
2. Edit an existing qualification.
3. Delete a qualification.
4. Change project metadata while retaining the source inside the scope.
5. Append a duplicate complete section.
6. Exchange the positions of two distinct turns.
7. Add a conversation with different wording and language.

Each update belongs to a different source.
The resulting queue contains seven pending sources among nine matching sources.

## Observed volume

Counts include complete cleaned dialogue text only, without headings, metadata, source coordinates, or explanatory notes.
They do not measure disk reads or total command output.

| Repeated-use view | Dialogue sections | Dialogue characters |
|---|---:|---:|
| Reread the current scoped archive | 195 | 16,734 |
| Read complete pending sources | 147 | 12,578 |
| Show changed sections only | 5 | 324 |
| Follow full-view recommendations | 99 | 8,464 |

The last row uses complete sources for four flagged cases and changed sections for the remaining cases.
It is a display-volume policy, not a proven sufficient reading strategy.

The changed-only view is incomplete in important ways.
Three pending sources show no added dialogue: a deletion, a metadata update, and reordered turns.
The implementation now reports these reasons and recommends the full view.
An edited qualification also recommends the full view because its earlier section no longer matches.
Both edited and deleted prior text remain unavailable from inspection notes.

## Product implication

The queue can narrow a repeated inspection to changed sources.
A changed-sections view can further reduce displayed text, but it cannot replace judgment about surrounding context.
An empty view does not establish that the conversation has no meaningful change.
Section order and deletion indicators therefore remain visible even when no new text appears.

These results establish display-volume behavior for one authored replay.
They do not establish reading-time savings, challenge discovery, correct understanding, reduced rework, or willingness to pay.
The large initial queue and unavailable prior text remain product limitations.
Do not present five displayed sections as the complete review effort.

The next evaluation needs actual users to inspect the same changes with and without this queue.
Record discovery success, missed qualifications, reading time, and uncertainty about removed evidence.
Keep private inputs and individual reports outside the public repository.
