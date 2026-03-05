import { constants as fsConstants } from "node:fs";
import { access, appendFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import type { OpenClawConfig, PluginLogger } from "openclaw/plugin-sdk";
import { runPluginCommandWithTimeout } from "openclaw/plugin-sdk";
import { buildWakatimeCommand } from "./wakatime-command.js";

const DEFAULT_PROJECT = "agent-vibe-coding";
const DEFAULT_CATEGORY = "ai coding";
const DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 120;
const DEFAULT_QUEUE_RETRY_BATCH_SIZE = 50;
const DEFAULT_QUEUE_FLUSH_INTERVAL_SECONDS = 60;
const HEARTBEAT_TIMEOUT_MS = 20_000;

type ProjectHint = {
  channelId?: string;
  action?: string;
  toolName?: string;
  sessionKey?: string;
};

type Heartbeat = {
  entity: string;
  timestamp: number;
  project: string;
  category: string;
  language: string;
  entityType: "file" | "app";
  lines: number;
  lineAdditions: number;
  lineDeletions: number;
  isWrite: boolean;
};

type TrackerOptions = {
  pluginId: string;
  pluginVersion: string;
  openclawConfig: OpenClawConfig;
  logger: PluginLogger;
  config: TrackerConfig;
};

export type TrackerConfig = {
  enabled: boolean;
  project: string;
  category: string;
  useContextProject: boolean;
  wakatimeBin: string;
  heartbeatIntervalSeconds: number;
  queueRetryBatchSize: number;
  queueFlushIntervalSeconds: number;
  trackMessages: boolean;
  trackCommands: boolean;
  trackTools: boolean;
  trackSessions: boolean;
};

type InternalQueueSlice = {
  toProcess: string[];
  remaining: string[];
};

function asTrimmedString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function asBoolean(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function asBoundedInt(value: unknown, fallback: number, min: number, max: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return fallback;
  }
  const rounded = Math.trunc(value);
  if (rounded < min || rounded > max) {
    return fallback;
  }
  return rounded;
}

function isTruthyEnv(value: string | undefined): boolean {
  const lowered = (value ?? "").trim().toLowerCase();
  return lowered === "1" || lowered === "true" || lowered === "yes" || lowered === "on";
}

function normalizeFragment(value: string, fallback = "unknown"): string {
  const cleaned = value.trim().replace(/[^A-Za-z0-9._:-]+/g, "_");
  return cleaned || fallback;
}

function detectLanguageFromEntity(entity: string): string {
  if (entity.startsWith("openclaw://tool/exec") || entity.startsWith("openclaw://tool/shell")) {
    return "Shell";
  }

  const ext = path.extname(entity).toLowerCase();
  switch (ext) {
    case ".py":
      return "Python";
    case ".js":
      return "JavaScript";
    case ".ts":
      return "TypeScript";
    case ".json":
      return "JSON";
    case ".md":
      return "Markdown";
    case ".sh":
    case ".bash":
    case ".zsh":
      return "Shell";
    case ".yaml":
    case ".yml":
      return "YAML";
    case ".toml":
      return "TOML";
    case ".rs":
      return "Rust";
    case ".go":
      return "Go";
    case ".java":
      return "Java";
    case ".sql":
      return "SQL";
    case ".html":
      return "HTML";
    case ".css":
      return "CSS";
    default:
      return "Markdown";
  }
}

function extractOpenClawVersion(config: OpenClawConfig): string {
  const envVersion = asTrimmedString(process.env.OPENCLAW_VERSION);
  if (envVersion) {
    return envVersion;
  }

  const metaValue = (config as { meta?: unknown }).meta;
  if (metaValue && typeof metaValue === "object") {
    const lastTouched = asTrimmedString(
      (metaValue as { lastTouchedVersion?: unknown }).lastTouchedVersion,
    );
    if (lastTouched) {
      const matched = lastTouched.match(/([0-9]+(?:\.[0-9]+)+(?:[-+._][A-Za-z0-9._-]+)?)/);
      if (matched) {
        return matched[1];
      }
      return lastTouched;
    }
  }

  return "unknown";
}

async function isExecutable(filePath: string): Promise<boolean> {
  if (!filePath) {
    return false;
  }
  try {
    await access(filePath, fsConstants.X_OK);
    return true;
  } catch {
    return false;
  }
}

async function resolveExecutableFromPath(names: string[]): Promise<string | null> {
  const pathEnv = asTrimmedString(process.env.PATH);
  if (!pathEnv) {
    return null;
  }

  const dirs = pathEnv
    .split(path.delimiter)
    .map((segment) => segment.trim())
    .filter((segment) => segment.length > 0);
  if (dirs.length === 0) {
    return null;
  }

  const exts =
    process.platform === "win32"
      ? (asTrimmedString(process.env.PATHEXT) || ".EXE;.CMD;.BAT;.COM")
          .split(";")
          .map((ext) => ext.trim())
          .filter((ext) => ext.length > 0)
      : [""];

  for (const dir of dirs) {
    for (const name of names) {
      if (!name) {
        continue;
      }
      for (const ext of exts) {
        const normalizedExt =
          ext && ext.startsWith(".")
            ? ext
            : ext
              ? `.${ext}`
              : "";
        const candidate =
          process.platform === "win32" ? path.join(dir, `${name}${normalizedExt}`) : path.join(dir, name);
        if (await isExecutable(candidate)) {
          return candidate;
        }
      }
    }
  }

  return null;
}

export function loadTrackerConfig(rawConfig: Record<string, unknown> | undefined): TrackerConfig {
  const cfg = rawConfig ?? {};

  const envProject = asTrimmedString(process.env.OPENCLAW_WAKATIME_PROJECT);
  const envCategory = asTrimmedString(process.env.OPENCLAW_WAKATIME_CATEGORY);
  const envBin = asTrimmedString(process.env.OPENCLAW_WAKATIME_BIN);

  const project = asTrimmedString(cfg.project) || envProject || DEFAULT_PROJECT;
  const category = asTrimmedString(cfg.category) || envCategory || DEFAULT_CATEGORY;

  const heartbeatIntervalSeconds = asBoundedInt(
    cfg.heartbeatIntervalSeconds,
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    1,
    3600,
  );

  const queueRetryBatchSize = asBoundedInt(
    cfg.queueRetryBatchSize,
    DEFAULT_QUEUE_RETRY_BATCH_SIZE,
    1,
    500,
  );

  const queueFlushIntervalSeconds = asBoundedInt(
    cfg.queueFlushIntervalSeconds,
    DEFAULT_QUEUE_FLUSH_INTERVAL_SECONDS,
    5,
    3600,
  );

  return {
    enabled: asBoolean(cfg.enabled, true),
    project,
    category,
    useContextProject:
      asBoolean(cfg.useContextProject, false) ||
      isTruthyEnv(process.env.OPENCLAW_WAKATIME_USE_CONTEXT_PROJECT),
    wakatimeBin: asTrimmedString(cfg.wakatimeBin) || envBin,
    heartbeatIntervalSeconds,
    queueRetryBatchSize,
    queueFlushIntervalSeconds,
    trackMessages: asBoolean(cfg.trackMessages, true),
    trackCommands: asBoolean(cfg.trackCommands, true),
    trackTools: asBoolean(cfg.trackTools, true),
    trackSessions: asBoolean(cfg.trackSessions, true),
  };
}

export class WakaTimeTracker {
  private readonly logger: PluginLogger;
  private readonly config: TrackerConfig;
  private readonly defaultProject: string;
  private readonly defaultCategory: string;
  private readonly pluginSignature: string;
  private readonly stateDir: string;
  private readonly queueFile: string;
  private readonly logFile: string;
  private readonly sessionsFile: string;
  private readonly heartbeatIntervalSeconds: number;
  private readonly openclawVersion: string;
  private ioQueue: Promise<void> = Promise.resolve();
  private queueFlushTimer: NodeJS.Timeout | null = null;
  private queueFlushInFlight = false;
  private fileIoEnabled = true;
  private fileIoDisableWarned = false;
  private wakatimeBin: string | null = null;
  private readonly lastHeartbeatByEntity = new Map<string, number>();

  constructor(options: TrackerOptions) {
    this.logger = options.logger;
    this.config = options.config;
    this.defaultProject = options.config.project;
    this.defaultCategory = options.config.category;
    this.openclawVersion = extractOpenClawVersion(options.openclawConfig);
    this.pluginSignature = `OpenClaw/${this.openclawVersion} ${options.pluginId}/${options.pluginVersion}`;

    this.stateDir = path.join(os.homedir(), ".openclaw", "wakatime");
    this.queueFile = path.join(this.stateDir, "queue.jsonl");
    this.logFile = path.join(this.stateDir, "plugin.log");
    this.sessionsFile = path.join(this.stateDir, "sessions.jsonl");
    this.heartbeatIntervalSeconds = options.config.heartbeatIntervalSeconds;
  }

  async init(): Promise<void> {
    try {
      await mkdir(this.stateDir, { recursive: true });
    } catch (error) {
      this.disableFileIo(`failed to prepare state directory: ${this.toErrorText(error)}`);
    }
    this.fileIoEnabled = await this.canWriteStateDir();
    if (!this.fileIoEnabled) {
      this.disableFileIo(`state directory is not writable: ${this.stateDir}`);
    }
    this.wakatimeBin = await this.resolveWakatimeBin();
    await this.log(
      `Tracker initialized: openclaw=${this.openclawVersion} wakatime_bin=${this.wakatimeBin ?? "<missing>"}`,
    );
  }

  startPeriodicQueueFlush(): void {
    if (this.queueFlushTimer || !this.config.enabled) {
      return;
    }
    this.queueFlushTimer = setInterval(() => {
      void this.processQueue(this.config.queueRetryBatchSize);
    }, this.config.queueFlushIntervalSeconds * 1000);
  }

  stopPeriodicQueueFlush(): void {
    if (!this.queueFlushTimer) {
      return;
    }
    clearInterval(this.queueFlushTimer);
    this.queueFlushTimer = null;
  }

  getStatus(): Record<string, unknown> {
    return {
      enabled: this.config.enabled,
      pluginSignature: this.pluginSignature,
      openclawVersion: this.openclawVersion,
      wakatimeBin: this.wakatimeBin ?? "",
      defaultProject: this.defaultProject,
      defaultCategory: this.defaultCategory,
      heartbeatIntervalSeconds: this.heartbeatIntervalSeconds,
      queueFlushIntervalSeconds: this.config.queueFlushIntervalSeconds,
      queueRetryBatchSize: this.config.queueRetryBatchSize,
      stateDir: this.stateDir,
      logFile: this.logFile,
      queueFile: this.queueFile,
      sessionsFile: this.sessionsFile,
    };
  }

  async trackMessage(params: {
    action: string;
    channelId: string;
    conversationId?: string;
    sessionKey?: string;
    messageId?: string;
  }): Promise<void> {
    const safeAction = normalizeFragment(params.action, "unknown");
    const safeChannel = normalizeFragment(params.channelId, "unknown");
    const safeConversation = normalizeFragment(
      params.conversationId || params.sessionKey || params.messageId || "",
      "unknown",
    );

    await this.sendHeartbeat({
      entity: `openclaw://im/${safeChannel}/${safeAction}/${safeConversation}`,
      timestamp: Date.now() / 1000,
      project: this.detectProject({ channelId: safeChannel, action: safeAction }),
      category: this.defaultCategory,
      language: "Markdown",
      entityType: "app",
      lines: 0,
      lineAdditions: 0,
      lineDeletions: 0,
      isWrite: true,
    });
  }

  async trackCommand(params: {
    action: string;
    sessionKey?: string;
    commandSource?: string;
  }): Promise<void> {
    const safeAction = normalizeFragment(params.action, "unknown");
    const safeSession = normalizeFragment(params.sessionKey || "", "unknown");

    await this.sendHeartbeat({
      entity: `openclaw://command/${safeAction}/${safeSession}`,
      timestamp: Date.now() / 1000,
      project: this.detectProject({
        channelId: params.commandSource,
        action: safeAction,
        sessionKey: safeSession,
      }),
      category: this.defaultCategory,
      language: "Markdown",
      entityType: "app",
      lines: 0,
      lineAdditions: 0,
      lineDeletions: 0,
      isWrite: false,
    });
  }

  async trackTool(params: {
    toolName: string;
    sessionKey?: string;
    durationMs?: number;
    runId?: string;
    toolCallId?: string;
    fileEntity?: string;
    isWrite?: boolean;
  }): Promise<void> {
    const safeTool = normalizeFragment(params.toolName, "unknown");
    const fileEntity = asTrimmedString(params.fileEntity);
    const entity = fileEntity || `openclaw://tool/${safeTool}`;
    const entityType: "file" | "app" = fileEntity ? "file" : "app";
    const isWrite = params.isWrite ?? false;

    await this.sendHeartbeat({
      entity,
      timestamp: Date.now() / 1000,
      project: this.detectProject({ toolName: safeTool, sessionKey: params.sessionKey }),
      category: this.defaultCategory,
      language: detectLanguageFromEntity(entity),
      entityType,
      lines: 0,
      lineAdditions: 0,
      lineDeletions: 0,
      isWrite,
    });

    await this.log(
      `Tool tracked: name=${safeTool} entity=${entity} type=${entityType} write=${String(isWrite)} duration_ms=${params.durationMs ?? 0} run_id=${params.runId ?? ""} call_id=${params.toolCallId ?? ""}`,
    );
  }

  async trackSession(params: {
    action: "start" | "end";
    sessionId?: string;
    sessionKey?: string;
    durationMs?: number;
    messageCount?: number;
  }): Promise<void> {
    const sessionRef = normalizeFragment(params.sessionKey || params.sessionId || "", "unknown");

    await this.sendHeartbeat({
      entity: `openclaw://session/${sessionRef}`,
      timestamp: Date.now() / 1000,
      project: this.detectProject({ action: params.action, sessionKey: sessionRef }),
      category: this.defaultCategory,
      language: "Markdown",
      entityType: "app",
      lines: 0,
      lineAdditions: 0,
      lineDeletions: 0,
      isWrite: true,
    });

    if (params.action === "end") {
      const row = {
        sessionId: params.sessionId ?? "",
        sessionKey: params.sessionKey ?? "",
        endedAt: new Date().toISOString(),
        durationMs: params.durationMs ?? 0,
        messageCount: params.messageCount ?? 0,
        project: this.detectProject({ action: "session_end", sessionKey: sessionRef }),
      };
      if (this.fileIoEnabled) {
        await this.queueIo(async () => {
          await appendFile(this.sessionsFile, `${JSON.stringify(row)}\n`, "utf8");
        });
      }
    }
  }

  async processQueue(maxItems: number): Promise<number> {
    if (this.queueFlushInFlight || !this.config.enabled || !this.fileIoEnabled) {
      return 0;
    }
    this.queueFlushInFlight = true;

    try {
      const slice = await this.readQueueSlice(maxItems);
      if (slice.toProcess.length === 0) {
        return 0;
      }

      const failed: string[] = [];
      let attempted = 0;

      for (const line of slice.toProcess) {
        attempted += 1;
        let parsed: Heartbeat;
        try {
          parsed = this.parseQueuedHeartbeat(line);
        } catch (error) {
          await this.log(`Queue parse error: ${this.toErrorText(error)}`);
          continue;
        }

        const ok = await this.sendHeartbeat(parsed, true);
        if (!ok) {
          failed.push(line);
        }
      }

      await this.writeQueue([...failed, ...slice.remaining]);
      return attempted;
    } finally {
      this.queueFlushInFlight = false;
    }
  }

  private parseQueuedHeartbeat(line: string): Heartbeat {
    const parsed = JSON.parse(line) as Partial<Heartbeat>;
    return {
      entity: asTrimmedString(parsed.entity),
      timestamp: typeof parsed.timestamp === "number" ? parsed.timestamp : Date.now() / 1000,
      project: asTrimmedString(parsed.project) || this.defaultProject,
      category: asTrimmedString(parsed.category) || this.defaultCategory,
      language: asTrimmedString(parsed.language) || detectLanguageFromEntity(asTrimmedString(parsed.entity)),
      entityType: parsed.entityType === "file" ? "file" : "app",
      lines: typeof parsed.lines === "number" ? parsed.lines : 0,
      lineAdditions: typeof parsed.lineAdditions === "number" ? parsed.lineAdditions : 0,
      lineDeletions: typeof parsed.lineDeletions === "number" ? parsed.lineDeletions : 0,
      isWrite: Boolean(parsed.isWrite),
    };
  }

  private async sendHeartbeat(heartbeat: Heartbeat, fromQueue = false): Promise<boolean> {
    if (!this.config.enabled) {
      return true;
    }

    if (!fromQueue && !this.shouldSendHeartbeat(heartbeat)) {
      return true;
    }

    if (!this.wakatimeBin) {
      await this.log("ERROR: wakatime binary not found");
      if (!fromQueue) {
        await this.queueHeartbeat(heartbeat);
      }
      return false;
    }

    const command = this.buildCommand(this.wakatimeBin, heartbeat);
    const result = await runPluginCommandWithTimeout({
      argv: command,
      timeoutMs: HEARTBEAT_TIMEOUT_MS,
    });

    if (result.code === 0) {
      this.lastHeartbeatByEntity.set(heartbeat.entity, heartbeat.timestamp);
      if (!fromQueue) {
        void this.processQueue(Math.min(10, this.config.queueRetryBatchSize));
      }
      return true;
    }

    const errorText = (result.stderr || result.stdout || `exit ${result.code}`).trim();
    await this.log(`ERROR sending heartbeat entity=${heartbeat.entity} error=${errorText}`);

    if (!fromQueue) {
      await this.queueHeartbeat(heartbeat);
    }

    return false;
  }

  private shouldSendHeartbeat(heartbeat: Heartbeat): boolean {
    if (heartbeat.isWrite) {
      return true;
    }

    const last = this.lastHeartbeatByEntity.get(heartbeat.entity);
    if (typeof last !== "number") {
      return true;
    }

    return heartbeat.timestamp - last >= this.heartbeatIntervalSeconds;
  }

  private buildCommand(wakaBin: string, heartbeat: Heartbeat): string[] {
    return buildWakatimeCommand({
      wakaBin,
      heartbeat,
      pluginSignature: this.pluginSignature,
    });
  }

  private async resolveWakatimeBin(): Promise<string | null> {
    const configured = asTrimmedString(this.config.wakatimeBin);
    if (configured) {
      return configured;
    }

    const home = os.homedir();
    const homeCandidates = [
      path.join(home, ".local", "bin", "wakatime"),
      path.join(home, ".wakatime", "wakatime-cli"),
      path.join(home, ".wakatime", "wakatime-cli.exe"),
    ];
    for (const candidate of homeCandidates) {
      if (await isExecutable(candidate)) {
        return candidate;
      }
    }

    const fromPath = await resolveExecutableFromPath(["wakatime", "wakatime-cli"]);
    if (fromPath) {
      return fromPath;
    }

    // Let PATH resolution happen at execution time.
    return "wakatime";
  }

  private async queueHeartbeat(heartbeat: Heartbeat): Promise<void> {
    if (!this.fileIoEnabled) {
      return;
    }
    await this.queueIo(async () => {
      await appendFile(this.queueFile, `${JSON.stringify(heartbeat)}\n`, "utf8");
    });
  }

  private async readQueueSlice(maxItems: number): Promise<InternalQueueSlice> {
    if (!this.fileIoEnabled) {
      return { toProcess: [], remaining: [] };
    }
    return await this.queueIo(async () => {
      const lines = await this.readQueueLines();
      return {
        toProcess: lines.slice(0, maxItems),
        remaining: lines.slice(maxItems),
      };
    });
  }

  private async writeQueue(lines: string[]): Promise<void> {
    if (!this.fileIoEnabled) {
      return;
    }
    await this.queueIo(async () => {
      if (lines.length === 0) {
        await rm(this.queueFile, { force: true });
        return;
      }
      await writeFile(this.queueFile, `${lines.join("\n")}\n`, "utf8");
    });
  }

  private async readQueueLines(): Promise<string[]> {
    try {
      const text = await readFile(this.queueFile, "utf8");
      return text
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
    } catch {
      return [];
    }
  }

  private async log(message: string): Promise<void> {
    if (!this.fileIoEnabled) {
      this.logger.debug?.(`[wakatime] ${message}`);
      return;
    }

    const line = `[${new Date().toISOString()}] ${message}\n`;
    try {
      await this.queueIo(async () => {
        await appendFile(this.logFile, line, "utf8");
      });
    } catch (error) {
      if (this.isPermissionError(error)) {
        this.disableFileIo(`failed to write plugin log: ${this.toErrorText(error)}`);
        return;
      }
      this.logger.warn?.(`[wakatime] failed to write plugin log: ${this.toErrorText(error)}`);
    }
    this.logger.debug?.(`[wakatime] ${message}`);
  }

  private async canWriteStateDir(): Promise<boolean> {
    try {
      await access(this.stateDir, fsConstants.W_OK);
      return true;
    } catch {
      return false;
    }
  }

  private detectProject(hint: ProjectHint): string {
    if (!this.config.useContextProject) {
      return this.defaultProject;
    }

    const text = [hint.channelId, hint.action, hint.toolName, hint.sessionKey]
      .map((value) => value ?? "")
      .join(" ")
      .toLowerCase();

    if (text.includes("research") || text.includes("quant") || text.includes("factor")) {
      return "research";
    }
    if (text.includes("exec") || text.includes("shell") || text.includes("tool")) {
      return "coding-agent";
    }
    if (text.includes("config") || text.includes("setup") || text.includes("system")) {
      return "system-admin";
    }
    if (text.includes("openclaw")) {
      return "openclaw";
    }
    return this.defaultProject;
  }

  private toErrorText(error: unknown): string {
    if (error instanceof Error) {
      return error.message;
    }
    return String(error);
  }

  private disableFileIo(reason: string): void {
    this.fileIoEnabled = false;
    if (this.fileIoDisableWarned) {
      return;
    }
    this.fileIoDisableWarned = true;
    this.logger.warn?.(`[wakatime] ${reason}; file-backed queue/log/session persistence disabled`);
  }

  private isPermissionError(error: unknown): boolean {
    if (!error || typeof error !== "object") {
      return false;
    }
    const code = (error as { code?: unknown }).code;
    return code === "EACCES" || code === "EPERM" || code === "EROFS";
  }

  private async queueIo<T>(op: () => Promise<T>): Promise<T> {
    let result: T | undefined;
    let thrown: unknown;

    this.ioQueue = this.ioQueue.then(async () => {
      try {
        result = await op();
      } catch (error) {
        thrown = error;
      }
    });

    await this.ioQueue;

    if (thrown !== undefined) {
      throw thrown;
    }

    return result as T;
  }
}
