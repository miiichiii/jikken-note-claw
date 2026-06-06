const crypto = require("node:crypto");

const REQUEST_MARKER = "<!-- task-board-reverse-sync-request -->";
const RESULT_MARKER = "<!-- task-board-reverse-sync-result -->";
const QUEUE_LABEL = "task-board-reverse-sync";
const PROCESSING_LABEL = "task-board-reverse-sync-processing";
const SUCCESS_LABEL = "task-board-reverse-sync-synced";
const PARTIAL_LABEL = "task-board-reverse-sync-partial";
const FAILED_LABEL = "task-board-reverse-sync-failed";
const CONFLICT_LABEL = "task-board-reverse-sync-conflict";
const DEFAULT_REPO = "miiichiii/jikken-note-claw";
const STATUS_LABELS = [PROCESSING_LABEL, SUCCESS_LABEL, PARTIAL_LABEL, FAILED_LABEL, CONFLICT_LABEL];
const TASK_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{2,160}$/;
const SIGNATURE_WINDOW_MS = 5 * 60 * 1000;

function sendJson(res, statusCode, payload) {
  res.statusCode = statusCode;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.end(JSON.stringify(payload));
}

function compareSecret(provided, expected) {
  const providedBuffer = Buffer.from(String(provided || ""), "utf8");
  const expectedBuffer = Buffer.from(String(expected || ""), "utf8");
  if (!providedBuffer.length || !expectedBuffer.length) return false;
  if (providedBuffer.length !== expectedBuffer.length) return false;
  return crypto.timingSafeEqual(providedBuffer, expectedBuffer);
}

function signaturePayload(method, requestPath, timestamp, bodyText) {
  return [String(method || "").toUpperCase(), String(requestPath || ""), String(timestamp || ""), String(bodyText || "")].join("\n");
}

function createSignature(secret, method, requestPath, timestamp, bodyText = "") {
  return crypto.createHmac("sha256", secret).update(signaturePayload(method, requestPath, timestamp, bodyText)).digest("hex");
}

function requireAuth(req, { bodyText = "" } = {}) {
  const expected = String(process.env.TASK_BOARD_SYNC_CLIENT_TOKEN || "").trim();
  if (!expected) {
    const error = new Error("task-board sync token is not configured");
    error.statusCode = 503;
    error.code = "bridge_not_configured";
    throw error;
  }
  const timestamp = String(req.headers["x-task-board-timestamp"] || "").trim();
  const providedSignature = String(req.headers["x-task-board-signature"] || "").trim();
  const timestampValue = Number(timestamp);
  if (!Number.isFinite(timestampValue)) {
    const error = new Error("missing or invalid signature timestamp");
    error.statusCode = 401;
    error.code = "unauthorized";
    throw error;
  }
  if (Math.abs(Date.now() - timestampValue) > SIGNATURE_WINDOW_MS) {
    const error = new Error("signature expired");
    error.statusCode = 401;
    error.code = "unauthorized";
    throw error;
  }
  const expectedSignature = createSignature(expected, req.method, req.url, timestamp, bodyText);
  if (!compareSecret(providedSignature, expectedSignature)) {
    const error = new Error("invalid sync signature");
    error.statusCode = 401;
    error.code = "unauthorized";
    throw error;
  }
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      try {
        const raw = Buffer.concat(chunks).toString("utf8").trim();
        const payload = raw ? JSON.parse(raw) : {};
        if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
          const error = new Error("request body must be a JSON object");
          error.statusCode = 400;
          error.code = "invalid_json";
          throw error;
        }
        resolve({ raw, payload });
      } catch (error) {
        if (!error.statusCode) {
          error.statusCode = 400;
          error.code = "invalid_json";
          error.message = "request body must be valid JSON";
        }
        reject(error);
      }
    });
    req.on("error", reject);
  });
}

function validatePayload(payload) {
  const taskId = String(payload.taskId || "").trim();
  const desiredStatus = String(payload.desiredStatus || "").trim();
  const expectedCurrentStatus = String(payload.expectedCurrentStatus || "").trim();
  const clientRequestId = String(payload.clientRequestId || "").trim();

  if (!TASK_ID_RE.test(taskId)) {
    const error = new Error("taskId must be a stable mtodo id");
    error.statusCode = 400;
    error.code = "invalid_task_id";
    throw error;
  }
  if (!["todo", "done"].includes(desiredStatus)) {
    const error = new Error("desiredStatus must be todo or done");
    error.statusCode = 400;
    error.code = "invalid_desired_status";
    throw error;
  }
  if (!["todo", "done"].includes(expectedCurrentStatus)) {
    const error = new Error("expectedCurrentStatus must be todo or done");
    error.statusCode = 400;
    error.code = "invalid_expected_status";
    throw error;
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{7,120}$/.test(clientRequestId)) {
    const error = new Error("clientRequestId is required");
    error.statusCode = 400;
    error.code = "invalid_client_request_id";
    throw error;
  }

  return { taskId, desiredStatus, expectedCurrentStatus, clientRequestId };
}

function queueRepo() {
  return String(process.env.TASK_BOARD_SYNC_QUEUE_REPO || DEFAULT_REPO).trim() || DEFAULT_REPO;
}

function githubToken() {
  const token = String(process.env.TASK_BOARD_SYNC_QUEUE_GITHUB_TOKEN || "").trim();
  if (!token) {
    const error = new Error("GitHub queue token is not configured");
    error.statusCode = 503;
    error.code = "queue_not_configured";
    throw error;
  }
  return token;
}

async function githubRequest(path, { method = "GET", body } = {}) {
  const response = await fetch(`https://api.github.com${path}`, {
    method,
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${githubToken()}`,
      "Content-Type": "application/json; charset=utf-8",
      "User-Agent": "task-board-reverse-sync"
    },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  if (!response.ok) {
    const detail = await response.text();
    const error = new Error(`GitHub API ${response.status}: ${detail || response.statusText}`);
    error.statusCode = 502;
    error.code = "github_api_error";
    error.githubStatus = response.status;
    throw error;
  }
  if (response.status === 204) return null;
  return response.json();
}

function requestBody(payload) {
  return [
    REQUEST_MARKER,
    "```json",
    JSON.stringify({
      ...payload,
      queuedAt: new Date().toISOString(),
      source: "site-public/tasks.html"
    }, null, 2),
    "```"
  ].join("\n");
}

function resultComment(result) {
  return [
    RESULT_MARKER,
    "```json",
    JSON.stringify(result, null, 2),
    "```"
  ].join("\n");
}

function parseMarkedJson(text, marker) {
  const source = String(text || "");
  const markerIndex = source.indexOf(marker);
  if (markerIndex === -1) return null;
  const start = source.indexOf("```json", markerIndex);
  if (start === -1) return null;
  const end = source.indexOf("```", start + 7);
  if (end === -1) return null;
  try {
    return JSON.parse(source.slice(start + 7, end).trim());
  } catch {
    return null;
  }
}

function parseRequestIssue(issue) {
  return parseMarkedJson(issue?.body, REQUEST_MARKER);
}

function parseResultComments(comments) {
  for (let index = comments.length - 1; index >= 0; index -= 1) {
    const parsed = parseMarkedJson(comments[index]?.body, RESULT_MARKER);
    if (parsed) return parsed;
  }
  return null;
}

async function ensureLabel(repo, name, color, description) {
  const [owner, repoName] = repo.split("/");
  try {
    await githubRequest(`/repos/${owner}/${repoName}/labels/${encodeURIComponent(name)}`);
  } catch (error) {
    if (error.code !== "github_api_error" || error.githubStatus !== 404) throw error;
    await githubRequest(`/repos/${owner}/${repoName}/labels`, {
      method: "POST",
      body: { name, color, description }
    });
  }
}

async function ensureQueueLabels(repo) {
  await ensureLabel(repo, QUEUE_LABEL, "0e8a16", "Queued task-board reverse-sync requests");
  await ensureLabel(repo, PROCESSING_LABEL, "fbca04", "Task-board reverse-sync request is being processed");
  await ensureLabel(repo, SUCCESS_LABEL, "1d76db", "Task-board reverse-sync completed and republished");
  await ensureLabel(repo, PARTIAL_LABEL, "d4c5f9", "Meta TODO updated but public republish is still pending");
  await ensureLabel(repo, FAILED_LABEL, "d73a4a", "Task-board reverse-sync failed");
  await ensureLabel(repo, CONFLICT_LABEL, "b60205", "Task-board reverse-sync was rejected due to stale/conflict state");
}

async function findQueuedIssueByRequestId(repo, clientRequestId) {
  const [owner, repoName] = repo.split("/");
  const issues = await githubRequest(
    `/repos/${owner}/${repoName}/issues?state=open&labels=${encodeURIComponent(QUEUE_LABEL)}&per_page=100&sort=created&direction=asc`
  );
  return issues.find((issue) => parseRequestIssue(issue)?.clientRequestId === clientRequestId) || null;
}

async function createQueueIssue(payload) {
  const repo = queueRepo();
  const [owner, repoName] = repo.split("/");
  await ensureQueueLabels(repo);
  const existing = await findQueuedIssueByRequestId(repo, payload.clientRequestId);
  if (existing) return existing;
  return githubRequest(`/repos/${owner}/${repoName}/issues`, {
    method: "POST",
    body: {
      title: `[task-board-reverse-sync] ${payload.taskId} -> ${payload.desiredStatus}`,
      body: requestBody(payload),
      labels: [QUEUE_LABEL]
    }
  });
}

function classifyIssue(issue, comments) {
  const labels = new Set((issue.labels || []).map((label) => label.name));
  const result = parseResultComments(comments || []);
  if (labels.has(CONFLICT_LABEL)) {
    return { syncState: "failed_conflict", result };
  }
  if (labels.has(FAILED_LABEL)) {
    return { syncState: "failed", result };
  }
  if (labels.has(PARTIAL_LABEL)) {
    return { syncState: "partial", result };
  }
  if (labels.has(SUCCESS_LABEL)) {
    return { syncState: "synced", result };
  }
  if (labels.has(PROCESSING_LABEL)) {
    return { syncState: "pending", result };
  }
  return { syncState: issue.state === "closed" ? "failed" : "pending", result };
}

async function loadIssueStatus(requestId) {
  const issueNumber = Number(requestId);
  if (!Number.isInteger(issueNumber) || issueNumber <= 0) {
    const error = new Error("requestId must be a positive integer");
    error.statusCode = 400;
    error.code = "invalid_request_id";
    throw error;
  }
  const repo = queueRepo();
  const [owner, repoName] = repo.split("/");
  const issue = await githubRequest(`/repos/${owner}/${repoName}/issues/${issueNumber}`);
  const comments = await githubRequest(`/repos/${owner}/${repoName}/issues/${issueNumber}/comments?per_page=100`);
  const status = classifyIssue(issue, comments);
  return {
    requestId: issue.number,
    issueUrl: issue.html_url,
    taskId: parseRequestIssue(issue)?.taskId || "",
    syncState: status.syncState,
    result: status.result
  };
}

module.exports = {
  CONFLICT_LABEL,
  FAILED_LABEL,
  PARTIAL_LABEL,
  PROCESSING_LABEL,
  QUEUE_LABEL,
  REQUEST_MARKER,
  RESULT_MARKER,
  STATUS_LABELS,
  SUCCESS_LABEL,
  classifyIssue,
  compareSecret,
  createQueueIssue,
  createSignature,
  loadIssueStatus,
  parseMarkedJson,
  parseRequestIssue,
  parseResultComments,
  queueRepo,
  signaturePayload,
  readJson,
  requireAuth,
  sendJson,
  validatePayload
};
