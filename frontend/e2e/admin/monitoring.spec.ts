import { test, expect } from "../fixtures/auth";
import { createSession, devTurn } from "../fixtures/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// Item 10: monitoring metrics correctness, plus a regression check for the
// stuck-session fix -- a properly-ended session must actually disappear
// from "live sessions" (before the webhook/sweep fix, nothing but the
// candidate's own explicit "End interview" click ever cleared this).

test("system health panel renders all monitored services", async ({ adminPage }) => {
  await adminPage.goto("/admin/monitoring");
  await expect(adminPage.getByText("System health")).toBeVisible();
  for (const service of ["redis", "groq", "whisper", "piper", "sentiment", "livekit"]) {
    await expect(adminPage.getByText(new RegExp(service, "i"))).toBeVisible({ timeout: 15_000 });
  }
});

test("an active session appears in live sessions, then disappears once ended", async ({ adminPage, candidatePage }) => {
  const { sessionId } = await createSession(candidatePage.request, { mode: "mixed", difficulty: "mid" });
  await devTurn(candidatePage.request, sessionId, null); // turn 1 -> status becomes ACTIVE

  await adminPage.goto("/admin/monitoring");
  await expect(async () => {
    const res = await adminPage.request.get(`${API_BASE}/admin/monitoring/live-sessions/`);
    const sessions = (await res.json()).data;
    expect(sessions.some((s: { id: string }) => s.id === sessionId)).toBe(true);
  }).toPass({ timeout: 15_000 });

  await candidatePage.request.post(`${API_BASE}/interviews/sessions/${sessionId}/end/`);

  await expect(async () => {
    const res = await adminPage.request.get(`${API_BASE}/admin/monitoring/live-sessions/`);
    const sessions = (await res.json()).data;
    expect(sessions.some((s: { id: string }) => s.id === sessionId)).toBe(false);
  }).toPass({ timeout: 15_000 });
});
