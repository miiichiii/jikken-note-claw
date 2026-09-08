const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const html = fs.readFileSync(require('node:path').join(__dirname, '../site-public/tasks.html'), 'utf8');
function functionSource(name) {
  const start = html.search(new RegExp(`^    (?:async )?function ${name}\\(`, 'm'));
  assert.ok(start >= 0, name);
  const tail = html.slice(start + 1);
  const end = tail.search(/^    (?:async )?function \w+\(/m);
  return html.slice(start, end < 0 ? undefined : start + 1 + end);
}
function storage(seed = {}) {
  const data = new Map(Object.entries(seed));
  return { getItem: (key) => data.get(key) ?? null, setItem: (key, value) => data.set(key, value) };
}
function context(names, extra = {}) {
  const ctx = vm.createContext({ localStorage: storage(), sessionStorage: storage(), localStateKey: 'state', syncConfigKey: 'config', allTasks: [], Date, ...extra });
  vm.runInContext(names.map(functionSource).join('\n'), ctx);
  return ctx;
}
const localFns = ['readLocalState', 'writeLocalState', 'updateLocalTaskState', 'taskStatus', 'taskLocalState', 'reconcileLocalTaskState', 'syncCounters'];
test('new tab preserves persistent auth; explicit logout does not resurrect session auth', () => {
  const ctx = context(['normalizeSyncConfig', 'readSyncConfig'], { localStorage: storage({ config: JSON.stringify({ token: 'test-only-placeholder' }) }) });
  assert.equal(ctx.readSyncConfig().token, 'test-only-placeholder');
  ctx.localStorage.setItem('config', '{}');
  assert.equal(ctx.readSyncConfig().token, '');
});
test('session-only legacy settings migrate and expired Google credentials are dropped', () => {
  const ctx = context(['normalizeSyncConfig', 'readSyncConfig'], { sessionStorage: storage({ config: JSON.stringify({token:'test-only-placeholder',googleIdToken:'expired-test',googleExpiresAt:1}) }) });
  assert.equal(ctx.readSyncConfig().token, 'test-only-placeholder');
  assert.equal(ctx.readSyncConfig().googleIdToken, undefined);
});
test('canonical snapshot replaces stale synced and resolved legacy failures, retains genuine intent', () => {
  const allTasks = ['synced','resolved','unsaved','explicit','partial','pending'].map(id => ({ id, status:'done' }));
  const ctx = context(localFns, { allTasks });
  ctx.writeLocalState({
    synced:{status:'todo',syncState:'synced'},
    resolved:{status:'todo',syncState:'failed',error:'PermissionError /private/path'},
    unsaved:{status:'done',syncState:'failed',error:'PermissionError /private/path'},
    explicit:{status:'todo',desiredStatus:'todo',syncState:'failed'},
    partial:{status:'todo',syncState:'partial'},
    pending:{status:'todo',syncState:'pending',requestId:'test-request'},
    removed:{status:'todo',syncState:'failed'}
  });
  ctx.reconcileLocalTaskState();
  const state = ctx.readLocalState();
  assert.equal(state.synced, undefined);
  assert.equal(state.resolved, undefined);
  assert.equal(state.removed, undefined);
  assert.equal(state.unsaved.desiredStatus, 'todo');
  assert.equal(state.explicit.desiredStatus, 'todo');
  assert.doesNotMatch(state.unsaved.error, /PermissionError|private/);
  assert.equal(ctx.taskStatus(allTasks[2]), 'done');
  assert.equal(ctx.taskStatus(allTasks[4]), 'todo');
  assert.equal(state.pending.requestId, 'test-request');
  assert.equal(ctx.syncCounters().failed, 2);
  // Repeated reconciliation never changes the retained intent.
  ctx.reconcileLocalTaskState();
  assert.equal(ctx.readLocalState().unsaved.desiredStatus, 'todo');
});
test('published confirmation clears partial override', () => {
  const ctx = context(localFns, { allTasks:[{id:'a',status:'done'}] });
  ctx.writeLocalState({a:{status:'done',syncState:'partial'}});
  ctx.reconcileLocalTaskState();
  assert.equal(ctx.readLocalState().a, undefined);
});
async function simulateToggle({ accepted = true, terminal = false }) {
  let callback;
  const classes = new Set();
  const card = {classList:{contains:x=>classes.has(x),add:x=>classes.add(x),remove:x=>classes.delete(x)},dataset:{task:'a'},querySelector:()=>({disabled:false})};
  const failure = Object.assign(new Error('test transport failure'), {syncCode:'unauthorized',remoteTerminal:terminal});
  const ctx = context([...localFns,'clearSyncRequest','setQueuedTimeoutState','toggleTask'], {
    allTasks:[{id:'a',status:'todo'}],window:{setTimeout: fn=>{callback=fn;}},toggleDelayMs:0,
    queueReverseSyncTask:async()=>{if(!accepted) throw failure; return {requestId:'accepted-id'};},
    waitForSyncResult:async()=>{throw failure;},handleSyncAuthFailure:async()=>{},
    updateCardCompletionState:()=>{},refresh:()=>{},renderTasks:()=>{}
  });
  await ctx.toggleTask(card);
  await callback();
  return ctx.readLocalState().a;
}
test('accepted request survives polling auth/network failure without losing intent', async () => {
  const state = await simulateToggle({accepted:true});
  assert.equal(state.syncState,'pending');
  assert.equal(state.requestId,'accepted-id');
  assert.equal(state.desiredStatus,'done');
  assert.equal(state.baselineStatus,'todo');
});
test('pre-accept failure and terminal rejection remain actionable failures', async () => {
  for(const params of [{accepted:false},{accepted:true,terminal:true}]) {
    const state = await simulateToggle(params);
    assert.equal(state.syncState,'failed');
    assert.equal(state.requestId,'');
    assert.equal(state.status,'todo');
    assert.equal(state.desiredStatus,'done');
  }
});
