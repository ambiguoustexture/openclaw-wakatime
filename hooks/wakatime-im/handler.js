const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");

const TRACKED_MESSAGE_ACTIONS = new Set(["received", "sent"]);

function toText(value) {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  return String(value);
}

function shouldTrack(event) {
  if (!event || typeof event !== "object") return false;
  if (event.type === "message") return TRACKED_MESSAGE_ACTIONS.has(event.action);
  if (event.type === "command") return true;
  return false;
}

async function appendLog(message) {
  try {
    const baseDir = path.join(os.homedir(), ".openclaw", "wakatime");
    const logFile = path.join(baseDir, "plugin.log");
    await fs.mkdir(baseDir, { recursive: true });
    await fs.appendFile(
      logFile,
      `[${new Date().toISOString()}] [wakatime-im-hook] ${message}\n`,
      "utf-8",
    );
  } catch {
    // ignore log failures to avoid affecting hook flow
  }
}

function buildPythonArgs(event) {
  const context = event.context && typeof event.context === "object" ? event.context : {};
  const args = [
    path.resolve(__dirname, "../../wakatime_openclaw.py"),
    "--track-hook",
    "--event-type",
    toText(event.type),
    "--event-action",
    toText(event.action),
  ];

  if (event.sessionKey) args.push("--session-key", toText(event.sessionKey));
  if (context.channelId) args.push("--channel-id", toText(context.channelId));
  if (context.conversationId) args.push("--conversation-id", toText(context.conversationId));
  if (context.messageId) args.push("--message-id", toText(context.messageId));
  return args;
}

function runTracker(event) {
  const python = toText(process.env.OPENCLAW_WAKATIME_PYTHON || "python3").trim() || "python3";
  const args = buildPythonArgs(event);
  try {
    const child = spawn(python, args, {
      stdio: "ignore",
      detached: false,
    });
    child.on("error", (err) => {
      void appendLog(`spawn error: ${toText(err?.message || err)}`);
    });
    child.unref();
  } catch (err) {
    void appendLog(`runTracker failed: ${toText(err?.message || err)}`);
  }
}

module.exports = function wakatimeImHook(event) {
  if (!shouldTrack(event)) return;
  runTracker(event);
};
