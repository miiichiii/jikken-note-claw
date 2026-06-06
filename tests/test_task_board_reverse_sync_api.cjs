const test = require("node:test");
const assert = require("node:assert/strict");

const {
  compareSecret,
  createSignature,
  classifyIssue,
  parseMarkedJson,
  requireAuth,
  validatePayload,
  REQUEST_MARKER,
  RESULT_MARKER,
  CONFLICT_LABEL,
  SUCCESS_LABEL
} = require("../site-public/api/task-board-reverse-sync/lib");

test("compareSecret rejects missing and mismatched tokens", () => {
  assert.equal(compareSecret("", "abc"), false);
  assert.equal(compareSecret("abc", ""), false);
  assert.equal(compareSecret("abc", "abd"), false);
  assert.equal(compareSecret("abc", "abc"), true);
});

test("requireAuth accepts valid HMAC signature and rejects invalid signature", () => {
  process.env.TASK_BOARD_SYNC_CLIENT_TOKEN = "secret-123";
  const timestamp = String(Date.now());
  const bodyText = JSON.stringify({ taskId: "mtodo-1" });
  const req = {
    method: "POST",
    url: "/api/task-board-reverse-sync/request",
    headers: {}
  };
  req.headers["x-task-board-timestamp"] = timestamp;
  req.headers["x-task-board-signature"] = createSignature(process.env.TASK_BOARD_SYNC_CLIENT_TOKEN, req.method, req.url, timestamp, bodyText);
  assert.doesNotThrow(() => requireAuth(req, { bodyText }));
  req.headers["x-task-board-signature"] = "bad";
  assert.throws(() => requireAuth(req, { bodyText }));
});

test("validatePayload rejects invalid ids and statuses", () => {
  assert.throws(() => validatePayload({ taskId: "?", desiredStatus: "done", expectedCurrentStatus: "todo", clientRequestId: "req-12345678" }));
  assert.throws(() => validatePayload({ taskId: "mtodo-1", desiredStatus: "later", expectedCurrentStatus: "todo", clientRequestId: "req-12345678" }));
  assert.throws(() => validatePayload({ taskId: "mtodo-1", desiredStatus: "done", expectedCurrentStatus: "later", clientRequestId: "req-12345678" }));
});

test("parseMarkedJson extracts request and result payloads", () => {
  const requestText = `${REQUEST_MARKER}\n\`\`\`json\n{"taskId":"mtodo-1"}\n\`\`\``;
  const resultText = `${RESULT_MARKER}\n\`\`\`json\n{"syncState":"synced"}\n\`\`\``;
  assert.deepEqual(parseMarkedJson(requestText, REQUEST_MARKER), { taskId: "mtodo-1" });
  assert.deepEqual(parseMarkedJson(resultText, RESULT_MARKER), { syncState: "synced" });
});

test("classifyIssue maps labels to sync states", () => {
  const synced = classifyIssue({ state: "closed", labels: [{ name: SUCCESS_LABEL }] }, []);
  assert.equal(synced.syncState, "synced");
  const conflict = classifyIssue({ state: "closed", labels: [{ name: CONFLICT_LABEL }] }, []);
  assert.equal(conflict.syncState, "failed_conflict");
});
