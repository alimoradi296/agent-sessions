/** A synthetic probe of a separately installed Qarinah checkout.
 * Usage: node examples/compare_context_selection.mjs /path/to/qarinah
 * No downloads, accounts, telemetry, hooks, or real agent history are used.
 * Qarinah machine state and the synthetic workspace stay in a new /tmp folder.
 */
import { execFileSync } from 'node:child_process';
import { mkdtemp, readFile, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const source = process.argv[2];
if (!source) throw new Error('Supply the path to a reviewed Qarinah checkout with its dependencies installed.');
const root = path.resolve(source);
const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const fixture = JSON.parse(await readFile(path.join(repo, 'tests/fixtures/continuity_tail_case.json'), 'utf8'));
const base = await mkdtemp(path.join(os.tmpdir(), 'agent-sessions-comparison-'));
process.env.QARINAH_STATE_DIR = path.join(base, 'machine-state');
const { initializeWorkspace } = await import(pathToFileURL(path.join(root, 'src/workspace.js')));
const { appendEvent } = await import(pathToFileURL(path.join(root, 'src/store.js')));
const { compileContext } = await import(pathToFileURL(path.join(root, 'src/compiler.js')));
const { recallChatMemory } = await import(pathToFileURL(path.join(root, 'src/chat-memory.js')));
const { canonicalStringify } = await import(pathToFileURL(path.join(root, 'src/canonical.js')));
const workspace = path.join(base, 'synthetic-project');
await initializeWorkspace(workspace, { capture: 'content' });
const body = fixture.prefix + fixture.detail.repeat(fixture.repeat) + '\n' + fixture.required_quote;
const sourceEvent = await appendEvent({ kind: 'decision', title: fixture.title, body, confidence: 'claimed',
  provenance: { adapter: 'synthetic-comparison', sourceId: 'synthetic-tail-scope' }
}, { cwd: workspace, capture: 'content' });
const outcomes = [];
const citedEventIds = new Map();
for (const maxChars of fixture.budgets) {
  try {
    const pack = await compileContext(fixture.query, {
      cwd: workspace, maxChars, limit: 5, inMemory: true, minimumCoverage: 'direct'
    });
    citedEventIds.set(maxChars, pack.items.map(item => item.eventId));
    outcomes.push({ maxChars, returned: true,
      scope_retained: pack.items.some(item => item.excerpt.includes(fixture.required_quote)),
      truncated: pack.truncated, usedChars: pack.budget.usedChars,
      excerptChars: pack.items.map(item => item.excerpt.length) });
  } catch (error) {
    outcomes.push({ maxChars, returned: false, error_code: error.code ?? error.name });
  }
}
const recallOutcomes = [];
for (const maxChars of fixture.budgets) {
  try {
    const eventId = citedEventIds.get(maxChars)?.find(id => id === sourceEvent.eventId);
    if (!eventId) throw new Error('The compiler did not cite the source needed for full recall.');
    let offset = 0;
    let recovered = '';
    const pages = [];
    while (pages.length < 10) {
      const pack = await recallChatMemory(fixture.query, {
        cwd: workspace, maxChars, limit: 1, detail: 'full', eventIds: [eventId], offset
      });
      const item = pack.items[0];
      if (!item || item.offset !== offset || item.hash !== sourceEvent.hash || item.excerpt.length === 0) {
        throw new Error('Full recall returned missing, changed, or noncontiguous source evidence.');
      }
      recovered += item.excerpt;
      const packetChars = canonicalStringify(pack).length;
      if (packetChars > maxChars) throw new Error('Full recall exceeded its per-call packet budget.');
      pages.push({ offset: item.offset, nextOffset: item.nextOffset, excerptChars: item.excerpt.length,
        packetChars, scope_retained: item.excerpt.includes(fixture.required_quote), truncated: pack.truncated });
      if (item.nextOffset === null) break;
      if (item.nextOffset <= offset) throw new Error('Full recall did not advance the source offset.');
      offset = item.nextOffset;
    }
    recallOutcomes.push({ maxChars, returned: true, pages,
      complete_source_recovered: recovered === body,
      scope_retained_across_pages: recovered.includes(fixture.required_quote),
      same_source_hash: true, source_cited_by_compiler: true });
  } catch (error) {
    recallOutcomes.push({ maxChars, returned: false, error_code: error.code ?? error.name });
  }
}
const packageInfo = JSON.parse(await readFile(path.join(root, 'package.json'), 'utf8'));
const result = {
  synthetic_only: true, comparison_kind: 'One API behavior probe, not a product ranking or equal-budget benchmark.',
  repository: 'https://github.com/AjnasNB/qarinah',
  revision: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
  version: packageInfo.version, api: 'compileContext', input_body_chars: body.length,
  outcomes, full_recall_api: 'recallChatMemory with detail=full and an explicit source event ID',
  full_recall_outcomes: recallOutcomes,
  boundary: 'Full recall uses a caller-selected source and may require multiple per-call budgets. '
    + 'This does not test receiving-agent discovery, understanding, explicit required-quote gates, or every Qarinah API.'
};
await writeFile(path.join(base, 'result.json'), JSON.stringify(result, null, 2), { mode: 0o600 });
console.log(JSON.stringify(result, null, 2));
console.error('Synthetic runtime artifacts: ' + base);
