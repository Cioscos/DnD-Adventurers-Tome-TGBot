import type { Reporter, TestCase, TestResult } from "@playwright/test/reporter";
import {
  recordFinding,
  writeAreaReport,
  writeRollup,
  type Severity,
} from "./findings";

class AuditReporter implements Reporter {
  onTestEnd(test: TestCase, result: TestResult): void {
    const area = test.parent.title; // the describe() title, e.g. "01-event-coverage"
    const ok = result.status === "passed";

    let severity: Severity = "🟢";
    if (!ok) {
      const firstMessage = result.errors[0]?.message ?? "";
      severity = firstMessage.includes("state mismatch")
        ? "🔴"
        : firstMessage.includes("display")
        ? "🟠"
        : "🔴";
    }

    recordFinding({
      area,
      title: test.title,
      evento: test.annotations.find((a) => a.type === "event")?.description,
      sintomo: ok ? "OK" : (result.errors[0]?.message ?? "Unknown failure"),
      rootCause: ok
        ? undefined
        : result.errors[0]?.stack?.split("\n").slice(0, 3).join(" | "),
      fixProposto: ok
        ? undefined
        : "Investigare lo stack trace per identificare il root cause.",
      severity,
    });
  }

  onEnd(): void {
    const areas = [
      "01-event-coverage",
      "02-action-coverage",
      "03-templates",
      "04-passive-modifiers",
      "05-filters",
      "06-error-cases",
      "07-state-transitions",
    ];
    for (const a of areas) {
      writeAreaReport(a);
    }
    writeRollup();
  }
}

export default AuditReporter;
