const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const hub = require('../site-public/app-hub.js');
const html = fs.readFileSync(path.join(__dirname, '../site-public/apps.html'), 'utf8');
const tasks = fs.readFileSync(path.join(__dirname, '../site-public/tasks.html'), 'utf8');
const key = 'taskBoardSyncConfigV2';
function storage(seed = {}, denied = false) {
  const values = new Map(Object.entries(seed));
  return { getItem(k) { if (denied) throw new Error('denied'); return values.get(k) ?? null; }, setItem(k,v) { if(denied) throw new Error('denied'); values.set(k,v); } };
}
function browser(hash = '', local = storage(), session = storage()) {
  const calls = [];
  const win = {location:{pathname:'/apps.html',search:'',hash,assign:url=>calls.push(['assign',url])},localStorage:local,sessionStorage:session,history:{replaceState(_s,_t,url){calls.push(['clean',url]);win.location.hash=url.includes('#') ? url.slice(url.indexOf('#')) : '';}}};
  return {win,calls};
}
function taskFunction(name) {
  const start = tasks.search(new RegExp(`^    (?:async )?function ${name}\\(`,'m'));
  assert.ok(start>=0,name);
  const next = tasks.slice(start+1).search(/^    (?:async )?function \w+\(/m);
  return tasks.slice(start,next<0?undefined:start+1+next);
}
function taskContext(win) {
  const context = vm.createContext({localStorage:win.localStorage,sessionStorage:win.sessionStorage,syncConfigKey:key,localStateKey:'state',window:win,miniappMode:true,Date});
  vm.runInContext(['normalizeSyncConfig','readSyncConfig','writeSyncConfig','readLocalState','writeLocalState','openAppHub'].map(taskFunction).join('\n'),context);
  return context;
}
test('setup preserves all settings/auth fields and removes only setup hash before SDK capture', () => {
  const config = {token:'old',googleIdToken:'fixture-google',googleExpiresAt:Date.now()+60000,googleEmail:'fixture@example.invalid',extra:{theme:'paper'}};
  const {win,calls} = browser('#sync-token=fixture-new&tgWebAppVersion=8.0&tgWebAppPlatform=ios',storage({[key]:JSON.stringify(config)}));
  const result=hub.bootstrap(win);
  assert.equal(result.fallbackToken,'');
  assert.deepEqual(JSON.parse(win.localStorage.getItem(key)),{...config,token:'fixture-new'});
  assert.equal(win.location.hash,'#tgWebAppVersion=8.0&tgWebAppPlatform=ios');
  assert.equal(calls[0][0],'clean');
  assert.doesNotMatch(calls[0][1],/fixture-new|sync-token/);
  assert.equal(hub.taskDestination(result),'tasks.html?miniapp=1');
});
test('plain menu does not alter saved credentials or create setup state', () => {
  const saved=JSON.stringify({token:'fixture-existing',extra:true});
  const {win,calls}=browser('',storage({[key]:saved}));
  assert.equal(hub.bootstrap(win).fallbackToken,'');
  assert.equal(win.localStorage.getItem(key),saved);
  assert.equal(calls.length,0);
});
test('explicit persistent logout wins legacy session data during setup', () => {
  const {win}=browser('#sync-token=fixture-new',storage({[key]:'{}'}),storage({[key]:JSON.stringify({googleIdToken:'old-session'})}));
  hub.bootstrap(win);
  assert.deepEqual(JSON.parse(win.localStorage.getItem(key)),{token:'fixture-new'});
});
test('malformed settings recover; malformed/empty credentials are cleared but never stored', () => {
  const {win}=browser('#sync-token=fixture-valid',storage({[key]:'not json'}));
  assert.equal(hub.bootstrap(win).malformed,false);
  assert.equal(JSON.parse(win.localStorage.getItem(key)).token,'fixture-valid');
  for(const hash of ['#sync-token=', '#sync-token=bad%00value', '#sync-token=%FF', `#sync-token=${'x'.repeat(8193)}`]) {
    const {win}=browser(hash);
    assert.equal(hub.bootstrap(win).malformed,true);
    assert.equal(win.location.hash,'');
    assert.equal(win.localStorage.getItem(key),null);
  }
});
test('denied storage uses memory-only same-origin navigation, with no credential in displayed link', () => {
  const {win,calls}=browser('#sync-token=fixture-secret',storage({},true),storage({},true));
  let taskClick;
  const task={addEventListener(_event,callback){taskClick=callback;}};
  const scripts=[];
  const doc={getElementById:id=>id==='taskApp'?task:{},querySelectorAll:()=>[],createElement:()=>({}),head:{appendChild:script=>scripts.push(script)}};
  hub.init(win,doc);
  assert.equal(win.location.hash,'');
  assert.equal(task.href,undefined);
  assert.equal(scripts[0].src,'https://telegram.org/js/telegram-web-app.js');
  let prevented=false;
  taskClick({preventDefault(){prevented=true;}});
  assert.equal(prevented,true);
  assert.deepEqual(calls.at(-1),['assign','tasks.html?miniapp=1#sync-token=fixture-secret']);
});
test('session-only setup remains usable by the taskboard if persistent storage is denied', () => {
  const {win}=browser('#sync-token=fixture-only',storage({},true),storage());
  const result=hub.bootstrap(win);
  assert.equal(result.fallbackToken,'fixture-only');
  const ctx=taskContext(win);
  assert.equal(ctx.readSyncConfig().token,'fixture-only');
});
test('RAM-only task auth and state survive checks, logout and hub round-trip without external sharing', () => {
  const {win,calls}=browser('',storage({},true),storage({},true));
  const ctx=taskContext(win);
  ctx.writeSyncConfig({token:'fixture-secret'});
  assert.equal(ctx.readSyncConfig().token,'fixture-secret');
  ctx.writeLocalState({a:{syncState:'pending',status:'done'}});
  assert.equal(ctx.readLocalState().a.syncState,'pending');
  ctx.openAppHub({preventDefault(){}});
  assert.deepEqual(calls.at(-1),['assign','apps.html#sync-token=fixture-secret']);
  const returned=browser('#sync-token=fixture-secret',storage({},true),storage({},true));
  const next=hub.bootstrap(returned.win);
  assert.equal(hub.taskDestination(next),'tasks.html?miniapp=1#sync-token=fixture-secret');
  ctx.writeSyncConfig({token:''});
  assert.equal(ctx.readSyncConfig().token,'');
  const count=calls.length;
  ctx.openAppHub({preventDefault(){throw Error('unexpected');}});
  assert.equal(calls.length,count);
});
test('normal task config respects persistent precedence and plain backlink', () => {
  const {win,calls}=browser('',storage({[key]:'{}'}),storage({[key]:JSON.stringify({token:'stale'})}));
  const ctx=taskContext(win);
  assert.equal(ctx.readSyncConfig().token,'');
  ctx.writeSyncConfig({token:'fixture-current'});
  ctx.openAppHub({preventDefault(){throw Error('unexpected');}});
  assert.equal(calls.length,0);
});
test('external SDK route is exact, receives no setup token, and uses ordinary anchors if absent/broken', () => {
  const urls=['https://calendar.google.com/calendar/u/0/r','https://miiichiii.github.io/research-fund-dashboard/'];
  for(const url of urls) {
    let opened,prevented=false;
    const win={Telegram:{WebApp:{openLink(u,opts){opened={url:u,opts};}}}};
    assert.equal(hub.openExternal(win,url,{preventDefault(){prevented=true;}}),true);
    assert.equal(opened.url,url);
    assert.equal(opened.opts.try_instant_view,false);
    assert.equal(prevented,true);
    assert.equal(hub.openExternal({},url,{preventDefault(){throw Error('must remain anchor');}}),false);
    assert.equal(hub.openExternal({Telegram:{WebApp:{openLink(){throw Error('old client');}}}},url,{preventDefault(){throw Error('must remain anchor');}}),false);
  }
  assert.equal(hub.openExternal({},'https://calendar.google.com/calendar/u/0/r#sync-token=bad',{}),false);
});
test('launcher has only genuine routes and no mock calendar, iframe, callbacks, AI or data fetching', () => {
  const js=fs.readFileSync(path.join(__dirname,'../site-public/app-hub.js'),'utf8');
  assert.equal((html.match(/class="app-link"/g)||[]).length,3);
  assert.match(html,/href="tasks.html\?miniapp=1"/);
  assert.match(html,/name="referrer" content="no-referrer"/);
  assert.equal((html.match(/rel="noopener noreferrer"/g)||[]).length,2);
  assert.doesNotMatch(html+js,/calendar\.html|iframe|callback_data|initDataUnsafe|\bfetch\(|XMLHttpRequest|api\/|openai|googleEmail/);
  assert.match(tasks,/href="apps.html">‹ アプリへ戻る/);
  assert.match(tasks,/\.miniapp-hub-back \{ display: none;/);
});
test('readable storage with blocked writes retains RAM auth and pending task state', () => {
  const local={getItem:()=>null,setItem:()=>{throw Error('quota denied');}};
  const {win}=browser('',local,storage());
  const ctx=taskContext(win);
  ctx.writeSyncConfig({token:'fixture-quota'});
  assert.equal(ctx.readSyncConfig().token,'fixture-quota');
  ctx.writeLocalState({a:{syncState:'pending'}});
  assert.equal(ctx.readLocalState().a.syncState,'pending');
});
