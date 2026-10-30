/** Probe a pinned agent-replay parser without its database or CLI.
 * Usage: node examples/compare_native_importers.mjs CHECKOUT ESBUILD_MODULE OUTPUT
 * All fixtures are invented. Only ingestTrace is replaced, to capture its input.
 */
import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { execFileSync } from 'node:child_process';

const [checkoutArg, compilerArg, outputArg] = process.argv.slice(2);
if (!checkoutArg || !compilerArg || !outputArg) throw new Error('Provide checkout, esbuild module, and new private output directory.');
const checkout = resolve(checkoutArg), output = resolve(outputArg);
const revision = execFileSync('git', ['-C', checkout, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
if (revision !== 'ccda6229a9451692fb6f1d6d323dd825c2be9dbb') throw new Error('Use the documented pinned revision.');
mkdirSync(output, { mode: 0o700 });
const require = createRequire(import.meta.url);
const { build } = require(resolve(compilerArg));
const compiled = join(output, 'importers.mjs');
await build({
  stdin: { contents: `export {importCodexRollout} from ${JSON.stringify(join(checkout, 'src/services/importers/codex-rollout.ts'))};
export {importClaudeTranscript} from ${JSON.stringify(join(checkout, 'src/services/importers/claude-transcript.ts'))};`, resolveDir: checkout },
  bundle: true, platform: 'node', format: 'esm', outfile: compiled,
  plugins: [{ name: 'capture-storage-boundary', setup(api) {
    api.onResolve({ filter: /trace-service\.js$/ }, () => ({ path: 'capture', namespace: 'probe' }));
    api.onLoad({ filter: /.*/, namespace: 'probe' }, () => ({ contents: 'export function ingestTrace(db,input){return input;}', loader: 'js' }));
  }}],
});
const native = await import(pathToFileURL(compiled).href);
const stamp = n => `2026-02-03T10:00:${String(n).padStart(2, '0')}Z`;
const event = (type, payload, n) => ({ type, payload, timestamp: stamp(n) });
const user = 'Inspect the example cache.';
const correction = 'Correction: the TTL is 30 seconds, not 60.';
const final = 'The example check failed; no deployment is established.';
const longArgument = 'synthetic argument '.repeat(70);
const longOutput = 'synthetic output '.repeat(100);
const codex = [
  event('session_meta', { id: 'synthetic-codex', cwd: '/workspace/example-project' }, 0),
  event('response_item', { type: 'message', role: 'user', content: [{ type: 'input_text', text: user }] }, 1),
  event('response_item', { type: 'function_call', name: 'run_example', arguments: JSON.stringify({ text: longArgument }), call_id: 'synthetic-call-a' }, 2),
  event('response_item', { type: 'function_call_output', output: longOutput, call_id: 'synthetic-call-a' }, 3),
  event('response_item', { type: 'message', role: 'user', content: [{ type: 'input_text', text: correction }] }, 4),
  event('response_item', { type: 'custom_tool_call', name: 'edit_example', input: longArgument, call_id: 'synthetic-call-b' }, 5),
  event('response_item', { type: 'custom_tool_call_output', output: 'Process exited with code 1', call_id: 'synthetic-call-b' }, 6),
  event('response_item', { type: 'message', role: 'assistant', content: [{ type: 'output_text', text: final }] }, 7),
];
const claude = [
  { type: 'user', sessionId: 'synthetic-claude', timestamp: stamp(1), message: { role: 'user', content: user } },
  { type: 'assistant', timestamp: stamp(2), message: { role: 'assistant', content: [{ type: 'tool_use', id: 'synthetic-call-a', name: 'run_example', input: { text: longArgument } }] } },
  { type: 'user', timestamp: stamp(3), message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: 'synthetic-call-a', content: longOutput }] } },
  { type: 'user', timestamp: stamp(4), message: { role: 'user', content: correction } },
  { type: 'assistant', timestamp: stamp(5), message: { role: 'assistant', content: [{ type: 'tool_use', id: 'synthetic-call-b', name: 'edit_example', input: { text: longArgument } }] } },
  { type: 'user', timestamp: stamp(6), message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: 'synthetic-call-b', content: 'Synthetic failure.', is_error: true }] } },
  { type: 'assistant', timestamp: stamp(7), message: { role: 'assistant', content: final } },
];
const reports = {};
for (const [name, records, parse] of [['codex', codex, native.importCodexRollout], ['claude', claude, native.importClaudeTranscript]]) {
  const file = join(output, `synthetic-${name}.jsonl`);
  writeFileSync(file, records.map(r => JSON.stringify(r)).join('\n') + '\n', { mode: 0o600 });
  const report = parse({}, file);
  writeFileSync(join(output, `${name}-payload.json`), JSON.stringify(report, null, 2), { mode: 0o600 });
  const payload = report.trace, serialized = JSON.stringify(payload);
  const calls = payload.steps.filter(step => step.step_type === 'tool_call');
  reports[name] = {
    session_id: payload.session_id, imported: report.imported, skipped: report.skipped,
    prompt_retained: payload.input.prompt === user,
    follow_up_retained: payload.metadata.follow_up_prompts?.includes(correction) ?? false,
    final_retained: payload.output?.text === final,
    tool_calls: calls.length,
    call_ids: calls.map(step => step.metadata?.call_id ?? step.metadata?.tool_use_id),
    complete_argument_retained: calls.every(step => JSON.stringify(step.input).includes(longArgument)),
    complete_long_output_retained: serialized.includes(longOutput),
    error_tool_steps: calls.filter(step => step.error).length,
    follow_up_metadata: payload.metadata.follow_up_prompts,
  };
}
const chronology = {};
for (const [name, records, parse] of [['codex', codex, native.importCodexRollout], ['claude', claude, native.importClaudeTranscript]]) {
  const payloads = {};
  for (const order of ['before', 'after']) {
    const copy = JSON.parse(JSON.stringify(records));
    const isCorrection = row => name === 'codex' ? row.payload?.content?.[0]?.text === correction : row.message?.content === correction;
    const correctionRow = copy.find(isCorrection);
    const others = copy.filter(row => !isCorrection(row));
    const callRow = name === 'codex' ? others.find(row => row.payload?.call_id === 'synthetic-call-b' && row.payload?.type === 'custom_tool_call') :
      others.find(row => row.message?.content?.[0]?.id === 'synthetic-call-b');
    if (name === 'codex') callRow.payload.input = JSON.stringify({ ttl_seconds: 60 });
    else callRow.message.content[0].input = { ttl_seconds: 60 };
    others.at(-1).timestamp = stamp(8);
    correctionRow.timestamp = stamp(order === 'before' ? 4 : 7);
    const callIndex = others.indexOf(callRow);
    others.splice(order === 'before' ? callIndex : others.length - 1, 0, correctionRow);
    const directory = join(output, `${name}-${order}`);
    mkdirSync(directory, { mode: 0o700 });
    const file = join(directory, `synthetic-${name}.jsonl`);
    writeFileSync(file, others.map(row => JSON.stringify(row)).join('\n') + '\n', { mode: 0o600 });
    const parsed = parse({}, file);
    payloads[order] = parsed.trace;
    writeFileSync(join(directory, 'payload.json'), JSON.stringify(parsed.trace, null, 2), { mode: 0o600 });
  }
  chronology[name] = { payloads_identical: JSON.stringify(payloads.before) === JSON.stringify(payloads.after),
    before_follow_up: payloads.before.metadata.follow_up_prompts,
    after_follow_up: payloads.after.metadata.follow_up_prompts };
}
const result = { revision, synthetic_only: true, storage_boundary_stubbed: true, reports, chronology,
  limits: 'Actual parser code only. Persistence, full CLI, automatic grading, replay and private transcripts were not tested.' };
writeFileSync(join(output, 'report.json'), JSON.stringify(result, null, 2), { mode: 0o600 });
console.log(JSON.stringify(result, null, 2));
