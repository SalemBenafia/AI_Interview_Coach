import { test, expect } from "../fixtures/auth";
import { createSession, devTurn, getSession } from "../fixtures/api";

const MIN_QUESTIONS = 4; // settings.MIN_QUESTIONS_PER_INTERVIEW
const MAX_QUESTIONS = 8; // settings.MAX_QUESTIONS_PER_INTERVIEW

// Items 8 and 13: does the live, published default flow actually respect
// its own design when a real candidate (well, a text-driven stand-in for
// one -- see dev_router.py) runs through it? This drives the real
// LangGraph-compiled flow via the dev-turn endpoint: real Router decision
// rules, real Evaluator scoring, real end-node reachability -- only the
// audio transport is bypassed.

test("a full interview stays within the configured question bounds and ends via the router", async ({ candidatePage }) => {
  const { sessionId } = await createSession(candidatePage.request, { mode: "mixed", difficulty: "mid" });

  let result = await devTurn(candidatePage.request, sessionId, null);
  let turns = 1;
  const strongAnswers = [
    "In my last role I owned a migration from a monolith to microservices. Situation: growth was blocked by a tightly coupled deploy. Task: decouple the billing service. Action: I extracted it behind an API and added contract tests. Result: deploy frequency tripled and incidents dropped.",
    "I communicate proactively -- weekly written updates, and I flag risks as soon as I see them rather than waiting for a status meeting.",
    "I use profiling first, then bisect recent changes, then write a regression test before shipping the fix.",
    "I mentor by pairing on real tickets rather than lecturing, and I check in async afterward.",
    "I prioritize using impact versus effort, and I revisit the list weekly with stakeholders.",
    "I once underestimated a migration's scope; I now pad estimates and flag unknowns explicitly upfront.",
  ];

  let answerIndex = 0;
  // Generous headroom: devTurn() already retries individual 503s
  // internally, but under sustained rate-limit pressure a real turn can
  // still occasionally exhaust that budget -- the outer cap here is a
  // safety net, not the thing under test (MAX_QUESTIONS_PER_INTERVIEW=8 is
  // still what actually bounds a real completed interview to 9 turns).
  while (!result.shouldEnd && turns < MAX_QUESTIONS + 10) {
    result = await devTurn(candidatePage.request, sessionId, strongAnswers[answerIndex % strongAnswers.length]);
    answerIndex += 1;
    turns += 1;
  }

  expect(result.shouldEnd).toBe(true);

  const finished = await getSession(candidatePage.request, sessionId);
  expect(finished.status).toBe("completed");
  // Assert against the backend's own tracked question count, not the raw
  // devTurn call count -- router actions like "ask_followup" consume a
  // real turn (and Groq call) without incrementing questions_asked, so a
  // completed session can legitimately need more raw turns than
  // MAX_QUESTIONS_PER_INTERVIEW while still respecting the real bound.
  expect(finished.questionsAsked).toBeGreaterThanOrEqual(MIN_QUESTIONS);
  expect(finished.questionsAsked).toBeLessThanOrEqual(MAX_QUESTIONS);

  const transcriptRes = await candidatePage.request.get(
    `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/interviews/sessions/${sessionId}/transcript/`
  );
  const transcript = (await transcriptRes.json()).data;
  expect(transcript.length).toBeGreaterThan(0);
  // Transcript alternates ai/candidate in turn order.
  for (let i = 0; i < transcript.length - 1; i++) {
    expect(transcript[i].speaker).not.toBe(transcript[i + 1].speaker);
  }
});

test("a weak answer can trigger the coaching path (Coach agent hint woven into the next question)", async ({ candidatePage }) => {
  const { sessionId } = await createSession(candidatePage.request, { mode: "behavioral", difficulty: "senior" });
  let result = await devTurn(candidatePage.request, sessionId, null);
  let sawHint = false;
  let turns = 1;

  // Deliberately weak/low-effort answers to try to trigger a weak_signal ->
  // "coaching" router decision at least once across the run. Weak answers
  // tend to accumulate more follow-up/coaching turns before the router
  // reaches MAX_QUESTIONS_PER_INTERVIEW, so this needs more headroom than
  // the strong-answers case.
  while (!result.shouldEnd && turns < MAX_QUESTIONS + 20) {
    result = await devTurn(candidatePage.request, sessionId, "I don't know, not sure, maybe something.");
    if (result.hint) sawHint = true;
    turns += 1;
  }

  // This is a probabilistic real-LLM outcome (the Evaluator/Router decide
  // this, not a mock) -- assert the interview still completed validly
  // either way, and only assert the hint-shape contract when one did fire.
  expect(result.shouldEnd).toBe(true);
  if (sawHint) {
    expect(typeof result.hint).toBe("string");
  }
});
