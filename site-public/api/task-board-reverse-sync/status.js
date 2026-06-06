const {
  loadIssueStatus,
  queueRepo,
  requireAuth,
  sendJson
} = require("./lib");

module.exports = async function handler(req, res) {
  res.setHeader("Allow", "GET");
  if (req.method !== "GET") {
    sendJson(res, 405, { status: "error", code: "method_not_allowed" });
    return;
  }

  try {
    const requestId = String(req.query.requestId || "").trim();
    if (!requestId) {
      sendJson(res, 200, {
        status: "ok",
        bridge: "github-issue-queue",
        repo: queueRepo(),
        authRequired: true,
        queueConfigured: Boolean(process.env.TASK_BOARD_SYNC_CLIENT_TOKEN && process.env.TASK_BOARD_SYNC_QUEUE_GITHUB_TOKEN)
      });
      return;
    }
    requireAuth(req);
    const payload = await loadIssueStatus(requestId);
    sendJson(res, 200, { status: "ok", ...payload });
  } catch (error) {
    sendJson(res, error.statusCode || 500, {
      status: "error",
      code: error.code || "internal_error",
      message: error.message || "unexpected error"
    });
  }
};
