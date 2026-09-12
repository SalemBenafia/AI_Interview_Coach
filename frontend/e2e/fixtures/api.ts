import type { APIRequestContext } from "@playwright/test";
import { API_BASE_URL } from "./auth";

/**
 * Direct-API helpers so tests can set up state (sessions, target roles,
 * completed interviews) without clicking through multi-step UI flows just
 * to reach a starting point. `request` must belong to an authenticated
 * browser context (see fixtures/auth.ts).
 */

export async function createSession(
  request: APIRequestContext,
  opts: { mode?: string; difficulty?: string; targetRoleId?: string } = {}
): Promise<{ sessionId: string; livekitRoomName: string }> {
  const res = await request.post(`${API_BASE_URL}/interviews/sessions/`, {
    data: {
      mode: opts.mode ?? "mixed",
      difficulty: opts.difficulty ?? "mid",
      target_role_id: opts.targetRoleId,
    },
  });
  if (!res.ok()) throw new Error(`createSession failed: ${res.status()} ${await res.text()}`);
  const body = await res.json();
  return body.data;
}

export type DevTurnResult = {
  aiMessage: string;
  hint: string | null;
  shouldEnd: boolean;
  endReason: string | null;
  difficulty: string;
  turnNumber: number;
  stage: string;
};

/**
 * Drives one turn via the dev-only text-turn endpoint (answer=null starts
 * the session). Small models occasionally emit malformed JSON; the real
 * production voice pipeline (app/voice_worker/llm_plugin.py) doesn't retry
 * this either -- it just tells the candidate to try again, which in
 * practice means speaking the answer again invokes submit_answer fresh.
 * Retrying here mirrors that real-world "just try again" recovery path
 * rather than working around a genuine LLM reliability characteristic.
 */
export async function devTurn(
  request: APIRequestContext,
  sessionId: string,
  answer: string | null = null,
  retriesLeft = 6
): Promise<DevTurnResult> {
  const res = await request.post(`${API_BASE_URL}/dev/interviews/sessions/${sessionId}/turn/`, {
    data: { answer },
  });
  if (res.status() === 503 && retriesLeft > 0) {
    // Groq's free-tier per-minute token limit gets shared (and easily
    // exhausted) across this whole suite -- a short pause before retrying
    // gives the window a chance to partially refill instead of immediately
    // re-hitting the same limit.
    await new Promise((resolve) => setTimeout(resolve, 3000));
    return devTurn(request, sessionId, answer, retriesLeft - 1);
  }
  if (!res.ok()) throw new Error(`devTurn failed: ${res.status()} ${await res.text()}`);
  const body = await res.json();
  return body.data;
}

/**
 * Drives a full interview to completion via the dev-turn endpoint, returns
 * turn count. `alreadyStarted` lets a caller that already issued the
 * `answer: null` start-session turn itself pass its result in, rather than
 * this function re-issuing it -- start_session is not idempotent (it always
 * inserts a fresh turn_number=1 row), so calling it twice for the same
 * session is a genuine duplicate-key error, not something to retry through.
 */
export async function completeInterviewViaDevTurns(
  request: APIRequestContext,
  sessionId: string,
  answers: string[],
  maxTurns = 15,
  alreadyStarted?: DevTurnResult
): Promise<{ turnCount: number; lastResult: DevTurnResult }> {
  let result = alreadyStarted ?? (await devTurn(request, sessionId, null));
  let turnCount = 1;
  let answerIndex = 0;
  while (!result.shouldEnd && turnCount < maxTurns) {
    const answer = answers[answerIndex % answers.length];
    result = await devTurn(request, sessionId, answer);
    answerIndex += 1;
    turnCount += 1;
  }
  return { turnCount, lastResult: result };
}

export async function createTargetRole(
  request: APIRequestContext,
  title: string,
  description?: string
): Promise<string> {
  const res = await request.post(`${API_BASE_URL}/target-roles/`, { data: { title, description } });
  if (!res.ok()) throw new Error(`createTargetRole failed: ${res.status()} ${await res.text()}`);
  const body = await res.json();
  return body.data.targetRoleId;
}

export async function addTargetRoleField(
  request: APIRequestContext,
  targetRoleId: string,
  fieldTitle: string,
  fieldDescription: string
): Promise<string> {
  const res = await request.post(`${API_BASE_URL}/target-roles/${targetRoleId}/fields/`, {
    data: { field_title: fieldTitle, field_description: fieldDescription },
  });
  if (!res.ok()) throw new Error(`addTargetRoleField failed: ${res.status()} ${await res.text()}`);
  const body = await res.json();
  return body.data.fieldId;
}

export async function getSession(request: APIRequestContext, sessionId: string) {
  const res = await request.get(`${API_BASE_URL}/interviews/sessions/${sessionId}/`);
  if (!res.ok()) throw new Error(`getSession failed: ${res.status()} ${await res.text()}`);
  const body = await res.json();
  return body.data;
}

/**
 * Returns an existing completed session for this candidate if one exists,
 * otherwise drives a fresh one to completion. Driving a full interview
 * needs ~15-20 real sequential Groq calls; this repo's free-tier key
 * (6000 tokens/min) is shared across the whole E2E suite, so reusing
 * already-completed sessions (which earlier specs in the run typically
 * produce) avoids redundant expensive/rate-limited work for tests that
 * only need *some* completed interview to exist, not to test completion
 * itself (that's covered directly by session-lifecycle.spec.ts and
 * live-flow-e2e.spec.ts).
 */
export async function findOrCreateCompletedSession(
  request: APIRequestContext,
  opts: { mode?: string; difficulty?: string } = {}
): Promise<string> {
  const listRes = await request.get(`${API_BASE_URL}/interviews/sessions/`, {
    params: { page: 1, limit: 5, status: "completed" },
  });
  const existing = (await listRes.json()).data as { id: string }[];
  if (existing.length > 0) return existing[0].id;

  const { sessionId } = await createSession(request, opts);
  await completeInterviewViaDevTurns(request, sessionId, [
    "I led a project that improved reliability by adding better monitoring and alerting.",
    "I collaborate by writing clear specs and running short weekly syncs.",
    "I once underestimated a task's scope; I now pad estimates and flag unknowns early.",
    "I debug by reproducing locally, checking logs, then bisecting recent changes.",
  ]);
  return sessionId;
}
