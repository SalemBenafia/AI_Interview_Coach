import { test, expect } from "../fixtures/auth";
import { findOrCreateCompletedSession } from "../fixtures/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// Item 14: candidate dashboard KPIs (backend/app/modules/interviews/router.py
// get_my_stats) are computed only from COMPLETED sessions -- cross-checks
// the dashboard's rendered numbers against what /interviews/me/stats/
// independently returns for the same candidate. Reuses an existing
// completed session where possible (see findOrCreateCompletedSession) --
// the exact count doesn't matter for verifying the computation is correct,
// only that at least one completed interview exists to compute from.

test("dashboard KPIs match /interviews/me/stats/", async ({ candidatePage }) => {
  await findOrCreateCompletedSession(candidatePage.request, { mode: "mixed", difficulty: "mid" });

  const statsRes = await candidatePage.request.get(`${API_BASE}/interviews/me/stats/`);
  const stats = (await statsRes.json()).data;
  expect(stats.totalCompletedInterviews).toBeGreaterThanOrEqual(1);

  await candidatePage.goto("/candidate/dashboard");
  await expect(candidatePage.getByText("Interviews done")).toBeVisible();
  const interviewsDoneCard = candidatePage.locator(".p-5", { hasText: "Interviews done" });
  await expect(interviewsDoneCard.getByText(String(stats.totalCompletedInterviews), { exact: true })).toBeVisible();

  if (stats.weakestDimension) {
    await expect(candidatePage.getByText(stats.weakestDimension, { exact: true })).toBeVisible();
  }

  // Regression check: the "Recent interviews" heading renders unconditionally
  // regardless of whether the list itself is populated, so asserting on the
  // heading alone previously let a real bug slip through -- the dashboard
  // used the wrong hook (useApiQuery instead of useApiPaginated) for this
  // paginated endpoint, silently discarding real session data via a double
  // .data unwrap and always rendering the empty state. Assert the actual
  // list renders and the empty state does NOT show, given a completed
  // session is known to exist.
  await expect(candidatePage.getByText("Recent interviews")).toBeVisible();
  await expect(candidatePage.getByText("No interviews yet")).not.toBeVisible();
  await expect(candidatePage.getByText("General Interview").first()).toBeVisible();
});
