type BuildCommandEntityType = "file" | "app";

type BuildCommandHeartbeat = {
  entity: string;
  language: string;
  project: string;
  category: string;
  timestamp: number;
  entityType: BuildCommandEntityType;
  isWrite: boolean;
  lines: number;
  lineAdditions: number;
  lineDeletions: number;
};

export function buildWakatimeCommand(params: {
  wakaBin: string;
  heartbeat: BuildCommandHeartbeat;
  pluginSignature: string;
}): string[] {
  const { wakaBin, heartbeat, pluginSignature } = params;
  const argv = [
    wakaBin,
    "--entity",
    heartbeat.entity,
    "--project",
    heartbeat.project,
    "--category",
    heartbeat.category,
    "--time",
    String(heartbeat.timestamp),
    "--plugin",
    pluginSignature,
  ];

  // For file entities, let wakatime-cli auto-detect language.
  if (heartbeat.entityType !== "file") {
    argv.push("--language", heartbeat.language);
  }

  if (heartbeat.entityType !== "file") {
    argv.push("--entity-type", heartbeat.entityType);
  }

  if (heartbeat.isWrite) {
    argv.push("--write");
  }

  if (heartbeat.lines > 0) {
    argv.push("--lines", String(heartbeat.lines));
  }

  if (heartbeat.lineAdditions > 0) {
    argv.push("--line-additions", String(heartbeat.lineAdditions));
  }

  if (heartbeat.lineDeletions > 0) {
    argv.push("--line-deletions", String(heartbeat.lineDeletions));
  }

  return argv;
}
