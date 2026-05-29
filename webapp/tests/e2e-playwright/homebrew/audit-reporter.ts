import type {
  FullResult,
  Reporter,
  TestCase,
  TestResult,
} from "@playwright/test/reporter";
import {
  recordFinding,
  writeAreaReport,
  writeRollup,
  backupPreviousRollup,
  getCriticalCount,
  previousCriticalCount,
  type Severity,
} from "./findings";

class AuditReporter implements Reporter {
  onTestEnd(test: TestCase, result: TestResult): void {
    // Skip non-final retry attempts that failed — they will be retried.
    if (result.status !== "passed" && result.retry < test.retries) return;

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

  onEnd(
    _result: FullResult
  ): { status: FullResult["status"] } | undefined | void {
    // Snapshot the prior run's rollup BEFORE overwriting
    backupPreviousRollup();

    const prevCrit = previousCriticalCount();

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

    const crit = getCriticalCount();

    // Informative diff line. We store the prior critical count to enable
    // manual run-to-run diffing; the exit gate fires on ANY current critical
    // (target state is zero criticals, whether rising or falling).
    if (prevCrit !== null) {
      console.log(
        `[homebrew-audit] critical findings: previous=${prevCrit} → current=${crit}`
      );
    } else {
      console.log(
        `[homebrew-audit] critical findings: ${crit} (no previous baseline)`
      );
    }

    if (crit > 0) {
      console.error(
        `[homebrew-audit] FAIL: ${crit} critical (🔴/🟠) finding(s). See docs/homebrew-audit/known-issues.md`
      );
      // Belt-and-suspenders for non-Playwright invocations (e.g. ts-node).
      process.exitCode = 1;
      // Authoritative exit gate: Playwright propagates this into a non-zero
      // exit code, overriding the test-run status.
      return { status: "failed" };
    } else {
      console.log(`[homebrew-audit] OK: 0 critical findings.`);
    }
  }
}

export default AuditReporter;
