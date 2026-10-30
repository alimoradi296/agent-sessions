// Synthetic controls for one pinned upstream module; no shell replay or restoration.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const revision = '7fe5e66fe7d07f427adf83a08ad6508704a1337e';
const expectedHash = 'c5b5dd70e8e7397607aafe71e04078cd7d8607e556448fa18cd3dc6548c59c52';
if (process.argv.length !== 3) {
  throw new Error('Supply the pinned upstream src/patch.ts path. Use Node with TypeScript stripping enabled.');
}
const source = resolve(process.argv[2]);
const digest = createHash('sha256').update(readFileSync(source)).digest('hex');
if (digest !== expectedHash) {
  throw new Error('Upstream source does not match the documented pin; import refused.');
}
const { applyUpdatePatch } = await import(pathToFileURL(source).href);
const cases = [
  {
    name: 'ordinary-context', base: 'old\n',
    patch: '*** Update File: example.py\n@@\n-old\n+new\n', expected: 'new\n',
  },
  {
    name: 'missing-context', base: 'different\n',
    patch: '*** Update File: example.py\n@@\n-old\n+new\n', expected: null,
  },
  {
    name: 'function-context-selector',
    base: 'def first():\n    return 1\n\ndef second():\n    return 1\n',
    patch: '*** Update File: example.py\n@@ def second():\n-    return 1\n+    return 2\n',
    expected: 'def first():\n    return 1\n\ndef second():\n    return 2\n',
  },
  {
    name: 'end-of-file-selector', base: 'value = 1\nseparator\nvalue = 1\n',
    patch: '*** Update File: example.py\n@@\n-value = 1\n+value = 2\n*** End of File\n',
    expected: 'value = 1\nseparator\nvalue = 2\n',
  },
];
const results = cases.map(({ name, base, patch, expected }) => {
  const result = applyUpdatePatch(base, patch);
  return {
    case: name, replay: result,
    matches_expected: expected === null ? !result.ok : result.ok && result.content === expected,
  };
});
console.log(JSON.stringify({
  synthetic_only: true, revision, source_sha256: digest, node: process.version, cases: results,
  limits: 'Pinned patch module only, not the Bun CLI or final archive. Selector expectations were checked with the available patch editor on synthetic files. No private history, archived commands, model, or live restoration used.',
}, null, 2));
