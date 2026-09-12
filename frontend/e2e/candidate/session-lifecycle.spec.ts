import { test, expect } from "../fixtures/auth";
import { completeInterviewViaDevTurns, createSession, devTurn, getSession } from "../fixtures/api";

// Items 2 and 3/10: exercises Active -> Completed (router "end" decision)
// and Active -> Abandoned (explicit end-interview call) transitions for
// real, plus the "End interview" button driving the same abandon path a
// browser closing the tab would need (regression coverage for the stuck-
// session fix; the webhook/sweep paths themselves are covered by backend
// pytest since Playwright can't easily fire a signed LiveKit webhook or
// wait 45 minutes for the sweep).

test("a session started via a turn becomes Active, then Completed once the router ends it", async ({ candidatePage }) => {
  const { sessionId } = await createSession(candidatePage.request, { mode: "mixed", difficulty: "mid" });

  const afterFirstTurn = await devTurn(candidatePage.request, sessionId, null);
  expect(afterFirstTurn.turnNumber).toBe(1);

  const midSession = await getSession(candidatePage.request, sessionId);
  expect(midSession.status).toBe("active");

  const { lastResult } = await completeInterviewViaDevTurns(
    candidatePage.request,
    sessionId,
    [
      "A concrete example: I redesigned our onboarding flow, situation was high drop-off, task was to reduce it, action was simplifying the form, result was a 25% increase in completion.",
      "I prioritize by urgency and impact, using a simple scoring matrix.",
      "I communicate blockers as soon as I notice them, in writing, with a proposed next step.",
      "I stay calm under pressure by breaking the problem into smaller pieces.",
    ],
    30, // generous headroom -- under sustained rate-limit pressure, many individual
    // devTurn calls fail even after their own internal retries
    afterFirstTurn // reuse turn 1's result -- start_session isn't idempotent, don't re-issue it
  );
  expect(lastResult.shouldEnd).toBe(true);

  const finished = await getSession(candidatePage.request, sessionId);
  expect(finished.status).toBe("completed");
  expect(finished.endedAt).not.toBeNull();
});

test("explicitly ending an interview marks it Abandoned, not Completed", async ({ candidatePage }) => {
  const { sessionId } = await createSession(candidatePage.request, { mode: "behavioral", difficulty: "junior" });
  await devTurn(candidatePage.request, sessionId, null);

  const res = await candidatePage.request.post(
    `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/interviews/sessions/${sessionId}/end/`
  );
  expect(res.ok()).toBeTruthy();

  const ended = await getSession(candidatePage.request, sessionId);
  expect(ended.status).toBe("abandoned");
  expect(ended.endedAt).not.toBeNull();

  // Idempotent: ending an already-terminal session is a no-op, not an error
  // (this is the same guard the webhook/sweep fix relies on to avoid a race).
  const res2 = await candidatePage.request.post(
    `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/interviews/sessions/${sessionId}/end/`
  );
  expect(res2.ok()).toBeTruthy();
  const stillEnded = await getSession(candidatePage.request, sessionId);
  expect(stillEnded.status).toBe("abandoned");
});

test("the in-room 'End interview' control drives the same abandon path", async ({ candidatePage }) => {
  const { sessionId } = await createSession(candidatePage.request, { mode: "technical", difficulty: "mid" });
  await devTurn(candidatePage.request, sessionId, null);

  await candidatePage.goto(`/candidate/interview/${sessionId}`);
  await candidatePage.getByRole("button", { name: /join the interview/i }).click();

  const endButton = candidatePage.getByRole("button", { name: /end/i }).first();
  await endButton.click();

  // InterviewControls' end button opens a confirmation modal ("End this
  // interview?") rather than ending immediately -- confirm it.
  await candidatePage.getByRole("dialog").getByRole("button", { name: "End interview" }).click();

  // Generous timeout: the dev server on this constrained box can take a
  // while to cold-compile a route it hasn't served yet this run.
  await expect(candidatePage).toHaveURL(new RegExp(`/candidate/interview/${sessionId}/report`), { timeout: 60_000 });

  const ended = await getSession(candidatePage.request, sessionId);
  expect(ended.status).toBe("abandoned");
});
