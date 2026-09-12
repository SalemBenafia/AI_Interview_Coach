import { test, expect } from "../fixtures/auth";
import { findOrCreateCompletedSession } from "../fixtures/api";

// Items 16 and 17: from /candidate/history, clicking a completed interview
// must land on its report; scores/strengths/weaknesses/suggestions must
// render; the "Download PDF" link must resolve to a real, working presigned
// MinIO URL (report generation runs async via Celery -- generate_feedback_report
// -- so this polls rather than assuming it's instant). Reuses an existing
// completed session where possible -- see findOrCreateCompletedSession.

test("history -> click a completed interview -> report renders with a working PDF download", async ({ candidatePage }) => {
  const sessionId = await findOrCreateCompletedSession(candidatePage.request, { mode: "technical", difficulty: "mid" });

  await candidatePage.goto("/candidate/history");
  // Filter to Completed -- today's test run has created many more recent
  // active/abandoned sessions that would otherwise push the reused
  // completed one past page 1 (limit=10, unfiltered, newest first).
  await candidatePage.getByRole("combobox").selectOption("completed");

  const row = candidatePage.locator(`a[href="/candidate/interview/${sessionId}/report"]`);
  await expect(row).toBeVisible({ timeout: 20_000 });
  await row.click();
  await candidatePage.waitForURL(new RegExp(`/candidate/interview/${sessionId}/report`), { timeout: 15_000 });

  // Report generation is async (Celery) -- the page itself retries on 202,
  // so just give it a generous window to land on real content.
  await expect(candidatePage.getByText("Your interview report")).toBeVisible({ timeout: 45_000 });
  await expect(candidatePage.getByText("Strengths")).toBeVisible();
  await expect(candidatePage.getByText("Areas to improve")).toBeVisible();
  await expect(candidatePage.getByText("Suggestions")).toBeVisible();

  const downloadLink = candidatePage.getByRole("link", { name: /download pdf/i });
  await expect(downloadLink).toBeVisible();
  const href = await downloadLink.getAttribute("href");
  expect(href).toBeTruthy();

  const pdfRes = await candidatePage.request.get(href!);
  expect(pdfRes.ok()).toBeTruthy();
  expect(pdfRes.headers()["content-type"]).toContain("pdf");

  // Rating widget actually posts (POST /interviews/sessions/{id}/rating/).
  const ratingRequest = candidatePage.waitForResponse((res) => res.url().includes("/rating/") && res.request().method() === "POST");
  await candidatePage.getByText("Was this feedback helpful?").locator("..").getByRole("button").first().click();
  const ratingResponse = await ratingRequest;
  expect(ratingResponse.ok()).toBeTruthy();
});
