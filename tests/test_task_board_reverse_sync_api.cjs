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

test("requireAuth accepts valid HMAC signature and rejects invalid signature", async () => {
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
  await assert.doesNotReject(() => requireAuth(req, { bodyText }));
  req.headers["x-task-board-signature"] = "bad";
  await assert.rejects(() => requireAuth(req, { bodyText }));
});

test("requireAuth accepts allowed Google bearer token", async () => {
  const originalFetch = global.fetch;
  process.env.TASK_BOARD_GOOGLE_CLIENT_ID = "google-client-id.apps.googleusercontent.com";
  process.env.TASK_BOARD_GOOGLE_ALLOWED_EMAILS = "allowed@example.com";
  global.fetch = async () => ({
    ok: true,
    json: async () => ({
      aud: process.env.TASK_BOARD_GOOGLE_CLIENT_ID,
      iss: "https://accounts.google.com",
      email: "allowed@example.com",
      email_verified: "true",
      sub: "1234567890"
    })
  });
  try {
    await assert.doesNotReject(() => requireAuth({
      method: "POST",
      url: "/api/task-board-reverse-sync/request",
      headers: {
        authorization: "Bearer mock-google-id-token"
      }
    }));
  } finally {
    global.fetch = originalFetch;
    delete process.env.TASK_BOARD_GOOGLE_CLIENT_ID;
    delete process.env.TASK_BOARD_GOOGLE_ALLOWED_EMAILS;
  }
});

test("requireAuth rejects disallowed Google bearer token", async () => {
  const originalFetch = global.fetch;
  process.env.TASK_BOARD_GOOGLE_CLIENT_ID = "google-client-id.apps.googleusercontent.com";
  process.env.TASK_BOARD_GOOGLE_ALLOWED_EMAILS = "allowed@example.com";
  global.fetch = async () => ({
    ok: true,
    json: async () => ({
      aud: process.env.TASK_BOARD_GOOGLE_CLIENT_ID,
      iss: "https://accounts.google.com",
      email: "other@example.com",
      email_verified: "true",
      sub: "1234567890"
    })
  });
  try {
    await assert.rejects(() => requireAuth({
      method: "POST",
      url: "/api/task-board-reverse-sync/request",
      headers: {
        authorization: "Bearer mock-google-id-token"
      }
    }));
  } finally {
    global.fetch = originalFetch;
    delete process.env.TASK_BOARD_GOOGLE_CLIENT_ID;
    delete process.env.TASK_BOARD_GOOGLE_ALLOWED_EMAILS;
  }
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
