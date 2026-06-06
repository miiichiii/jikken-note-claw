const {
  createQueueIssue,
  readJson,
  requireAuth,
  sendJson,
  validatePayload
} = require("./lib");

module.exports = async function handler(req, res) {
  res.setHeader("Allow", "POST");
  if (req.method !== "POST") {
    sendJson(res, 405, { status: "error", code: "method_not_allowed" });
    return;
  }

  try {
    const { raw, payload } = await readJson(req);
    requireAuth(req, { bodyText: raw });
    const validated = validatePayload(payload);
    const issue = await createQueueIssue(validated);
    sendJson(res, 202, {
      status: "queued",
      requestId: issue.number,
      issueUrl: issue.html_url
    });
  } catch (error) {
    sendJson(res, error.statusCode || 500, {
      status: "error",
      code: error.code || "internal_error",
      message: error.message || "unexpected error"
    });
  }
};
