import os from "node:os";
import path from "node:path";
import type { InternalHookEvent, OpenClawPluginApi } from "openclaw/plugin-sdk";
import { WakaTimeTracker, loadTrackerConfig } from "./src/wakatime-tracker.js";

const PLUGIN_ID = "openclaw-wakatime";
const PLUGIN_VERSION = "0.9.10";
const FILE_PATH_TOOLS = new Set(["read", "edit", "write"]);
const WRITE_FILE_TOOLS = new Set(["edit", "write"]);

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function readMetadataValue(metadata: unknown, key: string): string {
  if (!metadata || typeof metadata !== "object") {
    return "";
  }
  return asString((metadata as Record<string, unknown>)[key]);
}

function normalizeTrackedPath(rawPath: string): string {
  const trimmed = rawPath.trim().replace(/^["']|["']$/g, "");
  if (!trimmed) {
    return "";
  }

  const withoutAtPrefix = trimmed.startsWith("@") ? trimmed.slice(1) : trimmed;
  if (withoutAtPrefix.startsWith("~/")) {
    return path.join(os.homedir(), withoutAtPrefix.slice(2));
  }
  return path.normalize(withoutAtPrefix);
}

function extractPathFromRecord(record: Record<string, unknown>, depth: number): string {
  const candidateKeys = [
    "path",
    "file_path",
    "filePath",
    "filepath",
    "file",
    "target_path",
    "targetPath",
    "filename",
  ];

  for (const key of candidateKeys) {
    const candidate = normalizeTrackedPath(asString(record[key]));
    if (candidate) {
      return candidate;
    }
  }

  if (depth <= 0) {
    return "";
  }

  for (const value of Object.values(record)) {
    if (Array.isArray(value)) {
      for (const item of value) {
        const nested = asRecord(item);
        if (!nested) {
          continue;
        }
        const found = extractPathFromRecord(nested, depth - 1);
        if (found) {
          return found;
        }
      }
      continue;
    }

    const nested = asRecord(value);
    if (!nested) {
      continue;
    }
    const found = extractPathFromRecord(nested, depth - 1);
    if (found) {
      return found;
    }
  }

  return "";
}

function extractFileEntity(toolName: string, params: unknown): string {
  if (!FILE_PATH_TOOLS.has(toolName)) {
    return "";
  }

  const record = asRecord(params);
  if (!record) {
    return "";
  }

  return extractPathFromRecord(record, 3);
}

function isWriteTool(toolName: string): boolean {
  return WRITE_FILE_TOOLS.has(toolName);
}

const plugin = {
  id: PLUGIN_ID,
  name: "WakaTime",
  description: "Track OpenClaw activity in WakaTime via official plugin API",

  async register(api: OpenClawPluginApi) {
    const config = loadTrackerConfig(api.pluginConfig);
    const tracker = new WakaTimeTracker({
      pluginId: PLUGIN_ID,
      pluginVersion: PLUGIN_VERSION,
      openclawConfig: api.config,
      logger: api.logger,
      config,
    });

    await tracker.init();

    if (!config.enabled) {
      api.logger.info("wakatime: plugin is disabled by config (plugins.entries.openclaw-wakatime.config.enabled)");
      return;
    }

    void tracker.processQueue(config.queueRetryBatchSize);

    api.on("gateway_start", async () => {
      tracker.startPeriodicQueueFlush();
      await tracker.processQueue(config.queueRetryBatchSize);
    });

    api.on("gateway_stop", async () => {
      tracker.stopPeriodicQueueFlush();
      await tracker.processQueue(config.queueRetryBatchSize);
    });

    api.on("session_start", async (event) => {
      if (!config.trackSessions) {
        return;
      }

      await tracker.trackSession({
        action: "start",
        sessionId: event.sessionId,
        sessionKey: event.sessionKey,
      });
    });

    api.on("session_end", async (event) => {
      if (!config.trackSessions) {
        return;
      }

      await tracker.trackSession({
        action: "end",
        sessionId: event.sessionId,
        sessionKey: event.sessionKey,
        durationMs: event.durationMs,
        messageCount: event.messageCount,
      });
    });

    api.on("message_received", async (event, ctx) => {
      if (!config.trackMessages) {
        return;
      }

      await tracker.trackMessage({
        action: "received",
        channelId: ctx.channelId,
        conversationId: ctx.conversationId,
        sessionKey: ctx.conversationId,
        messageId: readMetadataValue(event.metadata, "messageId"),
      });
    });

    api.on("message_sent", async (event, ctx) => {
      if (!config.trackMessages) {
        return;
      }

      await tracker.trackMessage({
        action: "sent",
        channelId: ctx.channelId,
        conversationId: ctx.conversationId,
        sessionKey: ctx.conversationId,
        messageId: readMetadataValue((event as { metadata?: unknown }).metadata, "messageId"),
      });
    });

    api.on("after_tool_call", async (event, ctx) => {
      if (!config.trackTools) {
        return;
      }

      const fileEntity = extractFileEntity(event.toolName, event.params);
      await tracker.trackTool({
        toolName: event.toolName,
        sessionKey: ctx.sessionKey,
        durationMs: event.durationMs,
        runId: event.runId,
        toolCallId: event.toolCallId,
        fileEntity,
        isWrite: isWriteTool(event.toolName),
      });
    });

    api.registerHook(
      "command",
      async (event: InternalHookEvent) => {
        if (!config.trackCommands) {
          return;
        }

        const commandSource = asString(
          (event.context as Record<string, unknown> | undefined)?.commandSource,
        );

        await tracker.trackCommand({
          action: event.action,
          sessionKey: event.sessionKey,
          commandSource,
        });
      },
      {
        register: true,
        name: "wakatime-command-tracker",
        description: "Track command:* internal events in WakaTime",
      },
    );

    api.registerCommand({
      name: "waka-status",
      description: "Show current WakaTime plugin runtime status",
      acceptsArgs: false,
      requireAuth: true,
      handler: async () => {
        const status = tracker.getStatus();
        return {
          text: [
            "WakaTime plugin status",
            "```json",
            JSON.stringify(status, null, 2),
            "```",
          ].join("\n"),
        };
      },
    });

    api.logger.info("wakatime: plugin registered");
  },
};

export default plugin;
