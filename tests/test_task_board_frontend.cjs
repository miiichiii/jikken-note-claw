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
    readSyncConfig:()=>({token:'test-only-placeholder'}),hasGoogleCredential:()=>false,
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

test('unauthenticated checkbox requests login without changing task state or sending request', async () => {
  let queued = 0;
  let prompted = 0;
  let scheduled = 0;
  const classes = new Set();
  const button = {disabled:false};
  const card = {classList:{contains:x=>classes.has(x),add:x=>classes.add(x)},dataset:{task:'a'},querySelector:()=>button};
  const ctx = context([...localFns,'toggleTask'], {
    allTasks:[{id:'a',status:'todo'}],window:{setTimeout:()=>{scheduled++;}},
    readSyncConfig:()=>({token:''}),hasGoogleCredential:()=>false,googleAuthEnabled:()=>true,
    queueReverseSyncTask:async()=>{queued++;},maybePromptGoogleLogin:async()=>{prompted++;},
    refreshSyncChrome:()=>{},updateSyncAuthCard:()=>{},syncAuthMessage:{textContent:''},syncAuthCard:{},
    syncSetupMessage:'',googleAutoPromptAttempted:true
  });
  ctx.writeLocalState({a:{status:'todo',syncState:'failed',desiredStatus:'done',error:'previous unsaved change'}});
  const before = ctx.localStorage.getItem('state');
  await ctx.toggleTask(card);
  assert.equal(ctx.localStorage.getItem('state'),before);
  assert.equal(queued,0);
  assert.equal(scheduled,0);
  assert.equal(prompted,1);
  assert.equal(button.disabled,false);
  assert.equal(classes.size,0);
  assert.match(ctx.syncAuthMessage.textContent,/先に Google ログイン/);
  assert.match(ctx.syncAuthMessage.textContent,/まだ送信していません/);
});

const authChromeFns = ['hasGoogleCredential', 'googleAuthEnabled', 'hasSignedTokenConfig', 'renderGoogleLoginButton', 'maybePromptGoogleLogin', 'updateSyncAuthCard', 'refreshSyncChrome'];
function authChrome(config = {}, signedToken = true, counters = {}) {
  const calls = {identity:0, render:0, prompt:0};
  const ctx = context(authChromeFns, {
    readSyncConfig:()=>config,
    rejectedSyncToken:'',
    syncBridgeStatus:{authModes:{signedToken,google:true},googleAuth:{clientId:'fixture-client'}},
    syncAuthCard:{hidden:false,clientWidth:350},syncAuthMessage:{},syncAuthMeta:{},syncAuthClear:{},
    googleSignInButton:{innerHTML:'fixture-button'},
    syncPill:{classList:{remove:()=>{},add:()=>{}}},syncLabel:{},
    syncCounters:()=>({pending:0,failed:0,partial:0,synced:0,...counters}),
    syncProbeStarted:true,syncBridgeReachable:true,syncSetupMessage:'',googleAutoPromptAttempted:false,
    ensureGoogleIdentityClient:async()=>{calls.identity++;return true;},
    window:{google:{accounts:{id:{renderButton:()=>{calls.render++;},prompt:()=>{calls.prompt++;}}}}}
  });
  return {ctx,calls};
}
test('configured signed-token MiniApp hides Google card and never waits for or prompts Google', async () => {
  const {ctx,calls} = authChrome({token:'fixture-only-credential'});
  ctx.refreshSyncChrome();
  await ctx.renderGoogleLoginButton();
  await ctx.maybePromptGoogleLogin();
  assert.equal(ctx.syncAuthCard.hidden,true);
  assert.equal(ctx.syncLabel.textContent,'接続設定済み');
  assert.equal(ctx.googleSignInButton.innerHTML,'');
  assert.deepEqual(calls,{identity:0,render:0,prompt:0});
});
test('missing, expired Google, or unavailable signed-token auth retains Google login', async () => {
  for (const [config,signedToken] of [
    [{},true],
    [{googleIdToken:'fixture-expired',googleExpiresAt:1},true],
    [{token:'fixture-only-credential'},false]
  ]) {
    const {ctx,calls} = authChrome(config,signedToken);
    ctx.refreshSyncChrome();
    await ctx.maybePromptGoogleLogin();
    // updateSyncAuthCard renders asynchronously; one microtask completes it.
    await Promise.resolve();
    assert.equal(ctx.syncAuthCard.hidden,false);
    assert.equal(ctx.googleSignInButton.hidden,false);
    assert.match(ctx.syncAuthMessage.textContent,/Google ログイン/);
    assert.equal(calls.render,1);
    assert.equal(calls.prompt,1);
  }
});
test('actual signed-token auth rejection keeps failure visible and offers Google fallback', async () => {
  const {ctx,calls} = authChrome({token:'fixture-rejected'},true,{failed:1});
  ctx.clearGoogleCredential=()=>{};
  vm.runInContext(functionSource('handleSyncAuthFailure'),ctx);
  await ctx.handleSyncAuthFailure({syncCode:'unauthorized'});
  assert.equal(ctx.syncAuthCard.hidden,false);
  assert.equal(ctx.syncLabel.textContent,'未反映の変更 1件');
  assert.equal(calls.prompt,1);
  assert.equal(ctx.hasSignedTokenConfig(),false);
});
test('configured auth never masks pending, failed, or partial publication status', () => {
  for (const [counters,label] of [
    [{pending:2},'同期中 2件'],
    [{failed:1},'未反映の変更 1件'],
    [{partial:3},'正本更新済み / 公開待ち 3件']
  ]) {
    const {ctx} = authChrome({token:'fixture-only-credential'},true,counters);
    ctx.refreshSyncChrome();
    assert.equal(ctx.syncLabel.textContent,label);
    assert.equal(ctx.syncAuthCard.hidden,true);
  }
});
test('setup import uses plain connection language and removes credential fragment', () => {
  let cleaned = false;
  let stored;
  const ctx = context(['consumeSyncTokenFromUrl'], {
    syncTokenHashKeys:['sync-token','task-board-sync-token'],URLSearchParams,
    window:{location:{hash:'#sync-token=fixture-only-credential'},setTimeout:()=>{}},
    readSyncConfig:()=>({}),writeSyncConfig:config=>{stored=config;},
    clearUrlHash:()=>{cleaned=true;},syncSetupMessage:'',syncSetupNoticeMs:12000
  });
  ctx.consumeSyncTokenFromUrl();
  assert.equal(stored.token,'fixture-only-credential');
  assert.equal(cleaned,true);
  assert.equal(ctx.syncSetupMessage,'接続設定を読み込みました。');
});

const miniappFns = [...localFns,'isRecentlyDone','jstDayNumber','explicitDayNumber','miniappDateRange','miniappTasks','miniappVisibleTasks'];
const todayJst = Date.parse('2026-10-12T00:00:00+09:00');
function compact(tasks, filter = 'focus') {
  return context(miniappFns, {
    allTasks:tasks.map((task,index)=>({id:`t${index}`,status:'todo',priority:'B',...task})),
    doneHoldMs:3600000,miniappFilter:filter,miniappDay:'',miniappPage:0,miniappPageSize:5,miniappPinnedOrder:[]
  });
}
test('compact task selection uses JST day and inclusive seven-day boundary, never old 今日 wording', () => {
  const ctx = compact([
    {id:'yesterday',title:'2026-10-11 今日: 古いタスク',priority:'A'},
    {id:'today',title:'2026-10-12 今日: 作業'},
    {id:'next7',title:'2026-10-19まで: 作業'},
    {id:'next8',title:'2026-10-20まで: 作業'},
    {id:'urgent',title:'日付なしの作業',priority:'A'},
    {id:'normal',title:'日付なしの作業',priority:'B'},
    {id:'completed',title:'2026-10-12まで: 完了',status:'done'}
  ]);
  assert.equal(ctx.jstDayNumber(todayJst-1),ctx.explicitDayNumber(2026,10,11));
  assert.equal(ctx.jstDayNumber(todayJst),ctx.explicitDayNumber(2026,10,12));
  assert.deepEqual(Array.from(ctx.miniappTasks(todayJst),task=>task.id),['today','next7','urgent']);
  assert.ok(!Array.from(ctx.miniappTasks(todayJst-1),task=>task.id).includes('next7'));
  ctx.miniappFilter='overdue';ctx.miniappPinnedOrder=[];
  assert.deepEqual(Array.from(ctx.miniappTasks(todayJst),task=>task.id),['yesterday']);
  ctx.miniappFilter='all';ctx.miniappPinnedOrder=[];
  assert.equal(ctx.miniappTasks(todayJst).length,7);
  assert.equal(ctx.miniappTasks(todayJst).at(-1).id,'completed');
});
test('explicit task dates reject invalid calendar dates and ignore incidental receipt/URL dates', () => {
  const ctx = compact([]);
  const parse = title=>ctx.miniappDateRange({title});
  assert.equal(parse('2026-02-30 今日: 不正な日付'),false);
  assert.equal(parse('2026-13-01: 不正な月'),false);
  assert.equal(parse('2025-02-29: 不正な閏日'),false);
  assert.equal(parse('2024-02-29まで').start,ctx.explicitDayNumber(2024,2,29));
  assert.equal(parse('申請の準備。2026-10-12受領したメールを参照'),null);
  assert.equal(parse('作業（10/12まで・今日）'),null);
  assert.equal(parse('締切2026-10-12: 申請').start,ctx.explicitDayNumber(2026,10,12));
  const range=parse('**2026-10-12〜10-18（来週中）**: 作業');
  assert.equal(range.start,ctx.explicitDayNumber(2026,10,12));
  assert.equal(range.end,ctx.explicitDayNumber(2026,10,18));
  assert.equal(parse('2026-10-12〜18: 作業').end,ctx.explicitDayNumber(2026,10,18));
  assert.equal(parse('2026-10-12〜32: 不正な日付'),false);
  assert.equal(parse('2026-10-18〜10-12: 逆転した期間'),false);
});
test('dated range remains focused through its end; past planned dates move to overdue', () => {
  const ctx = compact([{id:'range',title:'2026-10-10〜10-18: 作業'}]);
  assert.equal(ctx.miniappTasks(todayJst).length,1);
  assert.equal(ctx.miniappTasks(Date.parse('2026-10-18T23:59:59+09:00')).length,1);
  assert.equal(ctx.miniappTasks(Date.parse('2026-10-19T00:00:00+09:00')).length,0);
  ctx.miniappFilter='overdue';
  assert.equal(ctx.miniappTasks(Date.parse('2026-10-19T00:00:00+09:00')).length,1);
});
test('compact pages contain at most five; all tasks, including completed tasks, remain reachable', () => {
  const tasks=Array.from({length:13},(_,index)=>({id:`item${index}`,title:'日付なし',priority:'A',status:index===12?'done':'todo'}));
  const ctx=compact(tasks,'all');
  const visited=[];
  for(let page=0;page<3;page++) {
    ctx.miniappPage=page;
    const items=ctx.miniappVisibleTasks(todayJst);
    assert.ok(items.length<=5);
    visited.push(...Array.from(items,task=>task.id));
  }
  assert.equal(new Set(visited).size,13);
  assert.ok(visited.includes('item12'));
  ctx.miniappPage=99;
  assert.equal(ctx.miniappVisibleTasks(todayJst).length,3);
  assert.equal(ctx.miniappPage,2);
});
test('completion remains in its page and position for one hour and can be undone', () => {
  const ctx=compact(Array.from({length:7},(_,index)=>({id:`item${index}`,title:'2026-10-12: 作業'})));
  const before=Array.from(ctx.miniappVisibleTasks(todayJst),task=>task.id);
  ctx.allTasks[1].status='done';
  ctx.updateLocalTaskState('item1',{status:'done',syncState:'synced',updatedAt:todayJst});
  assert.deepEqual(Array.from(ctx.miniappVisibleTasks(todayJst+3599999),task=>task.id),before);
  assert.ok(!Array.from(ctx.miniappVisibleTasks(todayJst+3600000),task=>task.id).includes('item1'));
  ctx.miniappFilter='all';ctx.miniappPinnedOrder=[];
  assert.ok(Array.from(ctx.miniappTasks(todayJst+3600000),task=>task.id).includes('item1'));
  ctx.allTasks[1].status='todo';
  ctx.updateLocalTaskState('item1',{status:'todo',syncState:'synced'});
  ctx.miniappFilter='focus';ctx.miniappPinnedOrder=[];
  assert.ok(Array.from(ctx.miniappVisibleTasks(todayJst+3600000),task=>task.id).includes('item1'));
});
test('ordinary board retains full assignee filtering; MiniApp ignores stale ordinary-board filter', () => {
  const ctx=compact(Array.from({length:8},(_,index)=>({id:`item${index}`,title:'日付なし',priority:'A',assignee:index%2?'Bot':'Me'})));
  ctx.miniappMode=false;ctx.activeFilter='all';
  vm.runInContext([functionSource('taskAssignee'),functionSource('visibleTasks')].join('\n'),ctx);
  assert.equal(ctx.visibleTasks().length,8);
  ctx.activeFilter='me';
  assert.equal(ctx.visibleTasks().length,4);
  ctx.miniappMode=true;
  const visible=ctx.visibleTasks();
  assert.equal(visible.length,5);
  assert.ok(Array.from(visible,task=>task.assignee).includes('Bot'));
});
