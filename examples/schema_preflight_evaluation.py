"""Measure existing schema and type checks on an invented local Django app.

Run with a separate environment containing the documented pinned dependencies.
This launches no model and imports no real application or archived commands.
"""

import argparse
import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path

from agent_sessions.storage import atomic_write_text

CASES = {
    'typed_field': 'def probe(entry: Entry) -> str:\n    return entry.title\n',
    'typed_property': 'def probe(entry: Entry) -> str:\n    return entry.display_label\n',
    'typed_missing': 'def probe(entry: Entry) -> str:\n    return entry.caption\n',
    'untyped_parameter_missing': 'def probe(entry):\n    return entry.caption\n',
    'untyped_query_missing': 'def probe():\n    entry = Entry.objects.first()\n    return entry.caption if entry else ""\n',
    'typed_query_missing': 'def probe() -> str:\n    entry = Entry.objects.first()\n    return entry.caption if entry else ""\n',
    'dynamic_getattr_missing': 'def probe(entry: Entry) -> str:\n    return getattr(entry, "caption")\n',
    'dynamic_getattr_valid': 'def probe(entry: Entry) -> str:\n    return getattr(entry, "title")\n',
}
MODELS = '''from django.db import models

class Entry(models.Model):
    title = models.CharField(max_length=100)

    @property
    def display_label(self) -> str:
        return self.title
'''
WORKER = '''import importlib.util, inspect, json, django
from django.core.exceptions import FieldDoesNotExist

django.setup()
from synthetic_app.models import Entry
model = Entry(title='Example')
fields = {}
static_attributes = {}
missing = object()
for name in ['title', 'display_label', 'caption']:
    try:
        Entry._meta.get_field(name)
        fields[name] = True
    except FieldDoesNotExist:
        fields[name] = False
    static_attributes[name] = inspect.getattr_static(Entry, name, missing) is not missing
results = {}
for name in ['typed_field', 'typed_property', 'typed_missing', 'untyped_parameter_missing', 'dynamic_getattr_missing', 'dynamic_getattr_valid']:
    spec = importlib.util.spec_from_file_location(name, name + '.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        results[name] = {'value': module.probe(model), 'error': None}
    except AttributeError as exc:
        results[name] = {'error': type(exc).__name__}
print(json.dumps({'model_fields': fields, 'static_class_attributes': static_attributes, 'runtime': results}))
'''


def evaluate(root):
    versions = {name: importlib.metadata.version(name) for name in ('Django', 'mypy', 'django-stubs', 'django-stubs-ext')}
    root.mkdir(parents=True, exist_ok=False, mode=0o700)
    app = root / 'synthetic_app'
    app.mkdir(mode=0o700)
    atomic_write_text(app / '__init__.py', '')
    atomic_write_text(app / 'models.py', MODELS)
    atomic_write_text(root / 'synthetic_settings.py', "INSTALLED_APPS = ['synthetic_app']\nSECRET_KEY = 'invented-fixture-only'\n"
                      "DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}\n")
    atomic_write_text(root / 'mypy.ini', '[mypy]\nplugins = mypy_django_plugin.main\n\n'
                      '[mypy.plugins.django-stubs]\ndjango_settings_module = synthetic_settings\n')
    for name, body in CASES.items():
        atomic_write_text(root / (name + '.py'), 'from synthetic_app.models import Entry\n\n' + body)
    env = dict(os.environ, PYTHONPATH=str(root), DJANGO_SETTINGS_MODULE='synthetic_settings', PYTHONDONTWRITEBYTECODE='1')
    worker = subprocess.run([sys.executable, '-B', '-c', WORKER], cwd=root, env=env,
                            text=True, capture_output=True, timeout=30, check=True)
    runtime = json.loads(worker.stdout)
    checks = {}
    for name in CASES:
        checks[name] = {}
        for mode, options in [('default', []), ('check_untyped_defs', ['--check-untyped-defs']), ('strict', ['--strict'])]:
            command = [sys.executable, '-m', 'mypy', '--config-file', str(root / 'mypy.ini'),
                       '--no-incremental', '--no-error-summary', '--no-pretty', *options, name + '.py']
            run = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True, timeout=60)
            if run.returncode not in (0, 1):
                raise ValueError('Type-check setup failed: ' + run.stderr + run.stdout)
            checks[name][mode] = dict(rejected=run.returncode == 1, diagnostics=run.stdout.strip())
    result = dict(synthetic_only=True, versions=versions, **runtime, type_checks=checks,
                  limits=['Only invented model and snippets; no historical application revision was reproduced.',
                          'Model metadata is not a complete Python-attribute validator.',
                          'A passing type check does not prove runtime safety or absence of data writes.',
                          'No real database, model provider, production endpoint or archived command was used.'])
    atomic_write_text(root / 'report.json', json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.output.expanduser().resolve()), indent=2))
