import { test, expect } from "../fixtures/auth";
import { completeInterviewViaDevTurns, createSession, getSession } from "../fixtures/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// Item 1: admin dashboard metric correctness. The dashboard's "overview"
// tile is live SQL aggregation (backend/app/modules/admin/analytics/router.py
// get_overview) -- this cross-checks the rendered stat-card values against
// what the API itself returns, which is correct by construction regardless
// of how much data exists. The 30-day trend chart reads a nightly Celery
// rollup (compute_daily_metrics_snapshot) so same-day activity intentionally
// won't show there yet -- only asserted to render without erroring.
//
// Deliberately does NOT drive a brand-new interview through the dev-turn
// endpoint here: doing so needs ~15-20 real sequential Groq calls, and this
// repo's free-tier key (6000 tokens/min) gets shared across the whole E2E
// suite -- under sustained load that reliably takes minutes rather than
// completing within a reasonable single-test budget. Completion itself is
// separately, directly verified in candidate/session-lifecycle.spec.ts and
// candidate/live-flow-e2e.spec.ts; this test only needs *some* completed
// interview to exist, which prior specs in the suite already guarantee.
// If none exist yet (e.g. run in isolation), it completes exactly one,
// using generous headroom for real-world LLM/rate-limit variance.

test("dashboard stat cards reflect live interview data", async ({ adminPage, candidatePage }) => {
  const overviewRes = await adminPage.request.get(`${API_BASE}/admin/analytics/overview/`);
  let overview = (await overviewRes.json()).data;

  if (overview.completedInterviewsLast30Days === 0) {
    const { sessionId } = await createSession(candidatePage.request, { mode: "mixed", difficulty: "mid" });
    await completeInterviewViaDevTurns(candidatePage.request, sessionId, [
      "I led a project where we cut latency by 40% using caching. Situation: high load. Task: reduce p99. Action: added Redis caching. Result: 40% latency drop.",
      "I collaborate by running weekly syncs and writing clear specs before starting work.",
      "I once missed a deadline and learned to communicate risks earlier.",
      "I debug by reproducing the issue locally, checking logs, and bisecting recent changes.",
    ]);
    await expect(async () => {
      const session = await getSession(candidatePage.request, sessionId);
      expect(session.status).toBe("completed");
    }).toPass({ timeout: 60_000 });

    const refreshed = await adminPage.request.get(`${API_BASE}/admin/analytics/overview/`);
    overview = (await refreshed.json()).data;
  }

  expect(overview.interviewsLast30Days).toBeGreaterThan(0);
  expect(overview.completedInterviewsLast30Days).toBeGreaterThan(0);

  await adminPage.goto("/admin/dashboard");
  await expect(adminPage.getByText("Platform overview")).toBeVisible();
  await expect(adminPage.getByText("Interviews (30d)")).toBeVisible();
  await expect(adminPage.getByText("Interview volume — last 30 days")).toBeVisible();

  // Cross-check the rendered stat-card value against the API response
  // itself, not a hardcoded number.
  const statCard = adminPage.locator(".kpi-card", { hasText: "Interviews (30d)" });
  await expect(statCard.locator("p.text-3xl")).toHaveText(String(overview.interviewsLast30Days));
});
