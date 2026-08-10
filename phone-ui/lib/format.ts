const leadingSymbol = /^(?:[\p{Extended_Pictographic}\uFE0F\u200D]|[✓✔●○—–-])+\s*/u;

export function cleanRelayText(value: string) {
  return value.replace(leadingSymbol, "").trim();
}

export function formatBytes(bytes = 0) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** index;
  return `${value >= 10 || index === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`;
}

export function formatTime(value: Date | string) {
  const date = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(date);
}

export function formatAuditTool(tool: string) {
  const names: Record<string, string> = {
    list_directory: "List directory",
    search_files: "Search files",
    search_file_content: "Search file contents",
    read_file_preview: "Read document",
    fetch_file: "Download file",
    run_command: "Run command",
    run_app_command: "Developer workflow",
    delete_file: "Delete file",
    write_file: "Write file",
    append_to_file: "Update file",
    create_file: "Create file",
    send_email: "Send email",
  };
  return names[tool] ?? tool.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}

export function conciseArgs(args: Record<string, unknown>) {
  const preferred = ["path", "keyword", "query", "command", "template", "to", "subject", "folder"];
  const key = preferred.find((candidate) => candidate in args);
  if (!key) return "No additional details";
  const value = typeof args[key] === "object" ? JSON.stringify(args[key]) : String(args[key]);
  return value.length > 110 ? `${value.slice(0, 107)}…` : value;
}

export function fileKind(name: string, mime = "") {
  if (mime.startsWith("image/")) return "image";
  const ext = name.split(".").pop()?.toLowerCase();
  if (ext === "pdf") return "pdf";
  if (["zip", "tar", "gz", "rar", "7z"].includes(ext ?? "")) return "archive";
  if (["js", "jsx", "ts", "tsx", "py", "go", "rs", "java"].includes(ext ?? "")) return "code";
  return "file";
}
