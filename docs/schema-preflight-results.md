# Existing schema and type-checking baseline

Run date: October 25, 2026. The application, model, and snippets are entirely synthetic.
This does not reproduce a historical application revision or establish production safety.

Used an isolated Python 3.13 environment with Django 5.2.7, mypy 1.18.2, django-stubs 5.2.7, and django-stubs-ext 5.2.7.
These pins identify the experiment rather than a deployment recommendation.
No dependency was added to the exporter package or the user's global Python environment.

## Fixture

An invented `Entry` model has a `title` field and a `display_label` property.
It has no `caption` attribute.
The settings contain only this synthetic application and an in-memory SQLite database.
Runtime checks use an unsaved instance; query-based snippets are checked statically without executing their queries.

[Django model metadata](https://docs.djangoproject.com/en/5.2/ref/models/meta/) correctly identifies `title` as a field and rejects the other names as fields.
The valid property still works on the instance.
[Python's static attribute inspection](https://docs.python.org/3/library/inspect.html#inspect.getattr_static) finds both the field descriptor and property, while the missing attribute remains absent.
This shows why field lookup alone is not a complete Python-attribute check.

## Type-checking results

The [django-stubs plugin](https://github.com/typeddjango/django-stubs) was configured with the synthetic settings module.
Every snippet ran through default mypy, `--check-untyped-defs`, and `--strict`.

| Snippet | Default | Check untyped bodies | Strict |
|---|---|---|---|
| Typed valid field | Accept | Accept | Accept |
| Typed valid property | Accept | Accept | Accept |
| Typed missing attribute | Reject: missing attribute | Reject: missing attribute | Reject: missing attribute and Any return |
| Untyped parameter, missing attribute | Accept | Accept | Reject: missing annotation |
| Untyped query, missing attribute | Accept | Reject: missing attribute | Reject: missing return annotation and attribute |
| Typed query, missing attribute | Reject: missing attribute | Reject: missing attribute | Reject: missing attribute |
| Dynamic `getattr`, missing attribute | Accept | Accept | Reject: Any return |
| Dynamic `getattr`, valid field | Accept | Accept | Reject: Any return |

The runtime checks confirmed that both valid direct accesses and valid dynamic access returned the expected text.
The typed, untyped-parameter, and dynamic missing accesses each raised `AttributeError`.
Strict mode rejected the valid dynamic case because its return type was unknown, not because the field was missing.
These are configuration trade-offs, rather than proof that the checker has a complete runtime model.

## Reproduce

Create a separate temporary virtual environment and install the four pinned packages there.
From this repository, run with that environment's Python:

```sh
python -m examples.schema_preflight_evaluation /path/to/new-private-exercise
```

The [script](../examples/schema_preflight_evaluation.py) creates the application, runs existing checks, and records diagnostics in `report.json`.
The destination must not exist.
The script launches no model, imports no real application, and executes no archived command.
Additional resolved dependency versions can affect future runs.

## Product decision

Existing tools cover the basic typed missing-attribute failure class in this exercise.
The experiment does not justify a new schema or type-checking engine.
Untyped and dynamic code show limits, but strict policies and explicit typing already address part of the problem.
Further work should test the preparation and evidence-matching workflow against existing tools before adding a feature.
Keep runtime exceptions paired with the earlier supplied snippet, while separating reported execution from independently reproduced behavior.
No general detection rate, production safety, willingness to pay, or exclusive capability is established.
