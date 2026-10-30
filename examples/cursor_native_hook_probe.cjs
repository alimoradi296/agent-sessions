// Exercise a pinned installed component with synthetic inputs. Never launch main.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const Module = require('node:module');
const { spawn } = require('node:child_process');

const EXPECTED = 'c5e700595b697092a3d462a855f7c0c4de9a62373e7e1a0afa229151602a69c3';
const TAIL = 'var __webpack_exports__=__webpack_require__("./src/main.tsx")})();';

async function evaluate(source) {
  source = fs.realpathSync(source);
  const names = ['index.js', ...fs.readdirSync(source).filter(n => /^\d+\.index\.js$/.test(n))].sort();
  const scripts = new Map(names.map(name => [name, fs.readFileSync(path.join(source, name))]));
  const digest = crypto.createHash('sha256');
  for (const name of names) digest.update(name + '\0').update(scripts.get(name)).update('\0');
  if (names.length !== 80 || digest.digest('hex') !== EXPECTED) throw Error('Unpinned bundle; import refused.');
  if (process.version !== 'v22.23.2') throw Error('Use the documented Node 22.23.2 runtime.');
  const original = scripts.get('index.js').toString('utf8');
  if (!original.trimEnd().endsWith(TAIL)) throw Error('Unexpected entry point; import refused.');
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'agent-sessions-synthetic-native-hook-'));
  fs.chmodSync(root, 0o700);
  try {
    for (const name of ['home', 'cache', 'project', 'receipts']) fs.mkdirSync(path.join(root, name), { mode: 0o700 });
    // This is a standalone experiment process; remove inherited account state.
    for (const key of Object.keys(process.env)) delete process.env[key];
    Object.assign(process.env, { HOME: path.join(root, 'home'), XDG_CACHE_HOME: path.join(root, 'cache'),
      PATH: '/usr/bin:/bin', LANG: 'C.UTF-8', DO_NOT_TRACK: '1' });
    const logger = path.join(root, 'logger.cjs');
    fs.writeFileSync(logger, `const fs=require('node:fs'),crypto=require('node:crypto');let body='';
process.stdin.setEncoding('utf8');process.stdin.on('data',x=>body+=x);process.stdin.on('end',()=>{
JSON.parse(body);fs.writeFileSync(process.argv[2]+'/'+crypto.randomUUID()+'.json',body,{mode:0o600,flag:'wx'});process.stdout.write('{}');});`, { mode: 0o600 });
    // Register the original factories, replacing only the application entry point.
    // The installed files remain untouched. This is an instrumented component test.
    const compiled = new Module(path.join(source, 'component-probe.cjs'));
    compiled.filename = path.join(source, 'component-probe.cjs');
    compiled.paths = Module._nodeModulePaths(source);
    compiled._compile(original.replace(TAIL, 'module.exports=__webpack_require__})();'), compiled.filename);
    const loader = compiled.exports;
    for (const name of names.filter(n => n !== 'index.js')) {
      const chunk = new Module(path.join(source, name));
      chunk.filename = path.join(source, name);
      chunk.paths = Module._nodeModulePaths(source);
      chunk._compile(scripts.get(name).toString('utf8'), chunk.filename);
      Object.assign(loader.m, chunk.exports.modules);
    }
    const NativeExecutor = loader('../hooks-exec/dist/index.js').WL;
    const shell = { async *execute(context, command, options) {
      const child = spawn('/bin/sh', ['-c', command], { cwd: options.workingDirectory,
        env: { ...process.env, ...options.env }, signal: options.signal, stdio: ['pipe', 'pipe', 'pipe'] });
      const stdout = [], stderr = [];
      child.stdout.on('data', b => stdout.push(b));
      child.stderr.on('data', b => stderr.push(b));
      const done = new Promise((resolve, reject) => { child.on('error', reject); child.on('close', resolve); });
      try {
        if (options.pipeStdin) yield { type: 'stdin_ready', stdin: child.stdin };
        else child.stdin.end();
        const code = await done;
        yield { type: 'stdout', data: Buffer.concat(stdout) };
        yield { type: 'stderr', data: Buffer.concat(stderr) };
        yield { type: 'exit', code };
      } finally { if (child.exitCode === null && child.signalCode === null) child.kill(); }
    } };
    // Paths come only from this temporary directory and the running executable.
    const quote = s => "'" + s.replaceAll("'", "'\\''") + "'";
    const command = [process.execPath, logger, path.join(root, 'receipts')].map(quote).join(' ');
    const observations = [], failures = [];
    const config = { userHooks: { version: 1, hooks: {
      postToolUse: [{ command, timeout: 5 }], postToolUseFailure: [{ command, timeout: 5 }],
    } } };
    const executor = new NativeExecutor(config, path.join(root, 'project'),
      { cursor_version: 'synthetic-component-test' }, shell, undefined, undefined,
      item => observations.push(item), { commandHookPayloadTransport: 'stdin' });
    const base = { conversation_id: 'synthetic-conversation', generation_id: 'synthetic-generation-a',
      tool_name: 'Shell', tool_input: { command: 'fictional-check' }, duration: 1, tool_use_id: 'synthetic-shared-id' };
    const inputs = [
      { ...base, hook_event_name: 'postToolUse', tool_output: '{"exitCode":0,"stdout":"SYNTHETIC_INNER_ERROR: inconclusive"}' },
      { ...base, generation_id: 'synthetic-generation-b', hook_event_name: 'postToolUseFailure',
        error_message: 'SYNTHETIC_TIMEOUT', failure_type: 'timeout', is_interrupt: false },
      { ...base, tool_name: 'MCP:fictional-check', tool_use_id: 'synthetic-mcp', hook_event_name: 'postToolUse',
        tool_output: '{"isError":true,"content":[{"type":"text","text":"SYNTHETIC_BACKEND_ERROR"}]}' },
    ];
    inputs.push({ ...inputs[0] }); // Repeated delivery must not overwrite either record.
    await Promise.all(inputs.map(input => executor.executeHookForStep(input.hook_event_name, input,
      { onCommandFailure: failure => failures.push({ exitCode: failure.exitCode, errorMessage: failure.errorMessage }) })));
    if (failures.length || observations.length !== 4 || observations.some(x => x.status !== 'success'))
      throw Error('Native component check failed: ' + JSON.stringify({ failures, observations }));
    const receipts = fs.readdirSync(path.join(root, 'receipts')).map(name =>
      JSON.parse(fs.readFileSync(path.join(root, 'receipts', name), 'utf8')));
    const remaining = [...receipts];
    for (const input of inputs) {
      const i = remaining.findIndex(saved => Object.entries(input).every(([k, v]) => JSON.stringify(saved[k]) === JSON.stringify(v)));
      if (i < 0) throw Error('An input event was omitted or changed.');
      remaining.splice(i, 1);
    }
    if (remaining.length) throw Error('Unexpected captured records.');
    return { synthetic_only: true, source_bundle_sha256: EXPECTED, source_files: names.length,
      instrumented_loader: true, native_hook_executor: true, shell_transport_adapter: 'node_child_process',
      real_shell_logger: true, normal_agent_session: false, repeated_delivery_retained: true,
      shared_id_across_generations_retained: true, observations, receipts,
      limits: 'Synthetic inputs invoke the pinned native component with an instrumented loader and a shell transport adapter. No normal agent session, live service outcome, native transcript merge, or complete event delivery established.' };
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
}

if (process.argv.length !== 3) { console.error('Usage: node cursor_native_hook_probe.cjs /path/to/pinned/installed/client'); process.exitCode = 1; }
else evaluate(process.argv[2]).then(result => console.log(JSON.stringify(result, null, 2))).catch(error => {
  console.error(error.message); process.exitCode = 1;
});
