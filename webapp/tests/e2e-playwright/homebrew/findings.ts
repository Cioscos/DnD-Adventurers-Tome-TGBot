import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
// findings.ts lives at webapp/tests/e2e-playwright/homebrew/
// → homebrew → e2e-playwright → tests → webapp → <repo-root>
const AUDIT_DIR = path.resolve(__dirname, "../../../../docs/homebrew-audit");

export type Severity = "🔴" | "🟠" | "🟡" | "🟢";

export interface Finding {
  num: number;       // sequential within area
  area: string;      // e.g. "01-event-coverage"
  title: string;
  evento?: string;
  sintomo: string;
  rootCause?: string;
  fixProposto?: string;
  severity: Severity;
}

const _findings: Finding[] = [];
const _counter = new Map<string, number>();

export function recordFinding(f: Omit<Finding, "num">): void {
  const prev = _counter.get(f.area) ?? 0;
  const num = prev + 1;
  _counter.set(f.area, num);
  _findings.push({ ...f, num });
}

export function getAllFindings(): Finding[] {
  return [..._findings];
}

function formatDate(): string {
  return new Date().toISOString().slice(0, 10);
}

const SEVERITY_ORDER: Severity[] = ["🔴", "🟠", "🟡", "🟢"];

function renderFinding(f: Finding): string {
  const lines: string[] = [];
  lines.push(`### #${f.num} — ${f.title}`);
  lines.push(`**Area:** \`${f.area}.md\`  `);
  if (f.evento !== undefined) {
    lines.push(`**Evento:** ${f.evento}  `);
  }
  lines.push(`**Sintomo:** ${f.sintomo}  `);
  if (f.rootCause !== undefined) {
    lines.push(`**Root cause:** ${f.rootCause}  `);
  }
  if (f.fixProposto !== undefined) {
    lines.push(`**Fix proposto:** ${f.fixProposto}  `);
  }
  return lines.join("\n");
}

export function writeAreaReport(area: string): void {
  fs.mkdirSync(AUDIT_DIR, { recursive: true });

  const areaFindings = _findings.filter((f) => f.area === area);
  const lines: string[] = [];
  lines.push(`# Audit Homebrew Engine — ${area}`);
  lines.push(`Generato: ${formatDate()}`);
  lines.push("");

  for (const sev of SEVERITY_ORDER) {
    const matching = areaFindings.filter((f) => f.severity === sev);
    if (matching.length === 0) continue;
    lines.push(`## ${sev}`);
    lines.push("");
    for (const f of matching) {
      lines.push(renderFinding(f));
      lines.push("");
    }
  }

  const filePath = path.join(AUDIT_DIR, `${area}.md`);
  fs.writeFileSync(filePath, lines.join("\n"), "utf-8");
}

export function writeRollup(): void {
  fs.mkdirSync(AUDIT_DIR, { recursive: true });

  const lines: string[] = [];
  lines.push(`# Known Issues — Homebrew Engine Audit ${formatDate()}`);
  lines.push("");

  // Counts table
  lines.push("## Conteggi");
  lines.push("");
  lines.push("| Severità | Conteggio |");
  lines.push("|----------|-----------|");
  for (const sev of SEVERITY_ORDER) {
    const count = _findings.filter((f) => f.severity === sev).length;
    lines.push(`| ${sev} | ${count} |`);
  }
  lines.push("");
  lines.push("---");
  lines.push("");

  // BUG FUNZIONALI (🔴)
  const redFindings = _findings.filter((f) => f.severity === "🔴");
  if (redFindings.length > 0) {
    lines.push("## 🔴 BUG FUNZIONALI");
    lines.push("");
    for (const f of redFindings) {
      lines.push(renderFinding(f));
      lines.push("");
    }
  }

  // REGRESSIONI VISIVE (🟠)
  const orangeFindings = _findings.filter((f) => f.severity === "🟠");
  if (orangeFindings.length > 0) {
    lines.push("## 🟠 REGRESSIONI VISIVE");
    lines.push("");
    for (const f of orangeFindings) {
      lines.push(renderFinding(f));
      lines.push("");
    }
  }

  const filePath = path.join(AUDIT_DIR, "known-issues.md");
  fs.writeFileSync(filePath, lines.join("\n"), "utf-8");
}
