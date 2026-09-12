import { test, expect } from "../fixtures/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// Item 9: the new /admin/analytics page -- previously a 404 despite the
// nav link already existing. AgentExecutionLog rows (with real tokens_used)
// are produced by every agent call across the whole suite, not just full
// interviews -- by the time this spec runs, prior specs have already
// generated plenty, so this doesn't need to drive its own interview.

test("analytics page renders real token usage, agent performance, and sentiment data", async ({ adminPage }) => {
  const tokenRes = await adminPage.request.get(`${API_BASE}/admin/analytics/token-usage/`, { params: { days: 30 } });
  const tokenData = (await tokenRes.json()).data;
  expect(tokenData.byAgent.length).toBeGreaterThan(0);
  expect(tokenData.byAgent.some((a: { totalTokens: number }) => a.totalTokens > 0)).toBe(true);

  // Generous timeouts: this box's dev server can take 30-90s to cold-compile
  // a route under heavy CPU contention (see the broader session's resource
  // constraints), well past Playwright's default 30s navigation timeout.
  await adminPage.goto("/admin/analytics", { timeout: 120_000 });
  await expect(adminPage.getByText("AI analytics")).toBeVisible({ timeout: 30_000 });
  await expect(adminPage.getByText("Tokens used (30d)")).toBeVisible();
  await expect(adminPage.getByText("Agent calls (all-time)")).toBeVisible();

  await expect(async () => {
    const statCard = adminPage.locator(".kpi-card", { hasText: "Tokens used (30d)" });
    const value = await statCard.locator("p.text-3xl").textContent();
    expect(value?.trim()).not.toBe("—");
  }).toPass({ timeout: 15_000 });

  await expect(adminPage.getByText("Token usage by agent")).toBeVisible();
  await expect(adminPage.getByRole("heading", { name: "Per-agent performance" })).toBeVisible();
  await expect(adminPage.getByRole("heading", { name: /Candidate sentiment/ })).toBeVisible();
});
