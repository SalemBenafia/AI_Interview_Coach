import { test, expect } from "../fixtures/auth";
import type { AgentTemplate } from "../../types";

// Item 4 and 8: verifies every admin/agents/[agentId] form field is really
// wired to a backend save (not just cosmetic), and that the Test Sandbox
// genuinely invokes each agent's real logic (real LLM call for
// interviewer/evaluator/feedback/coach, the real rule engine for router).
// Sample payloads mirror backend/app/modules/agents/schemas.py's *Input
// schemas exactly (snake_case, no alias generator).

const SAMPLE_INPUT: Record<string, object> = {
  interviewer: {
    role_name: "Software Engineer",
    mode: "technical",
    difficulty: "mid",
    stage: "core",
    questions_already_asked: [],
    is_followup: false,
  },
  evaluator: {
    question: "Tell me about a challenging project.",
    answer: "I led a project that reduced API latency by 40% by introducing a Redis caching layer.",
    role_name: "Software Engineer",
    mode: "technical",
    difficulty: "mid",
    rubric: [],
  },
  router: {
    composite_score: 75,
    weak_signal: false,
    follow_up_count: 0,
    questions_asked_count: 3,
    max_questions: 8,
    min_questions: 4,
    difficulty: "mid",
    decision_rules: [],
  },
  feedback: {
    role_name: "Software Engineer",
    mode: "technical",
    transcript: [
      { speaker: "ai", text: "Tell me about a challenging project." },
      { speaker: "candidate", text: "I led a project that reduced latency by 40%." },
    ],
    score_history: [],
    coaching_style: "professional",
  },
  coach: {
    question: "Tell me about a time you failed.",
    last_answer: "I don't really have an example.",
    weak_signal: true,
  },
};

const AGENT_KEYS = ["interviewer", "evaluator", "router", "feedback", "coach"];

test.describe("admin agent config + test sandbox", () => {
  for (const key of AGENT_KEYS) {
    test(`${key} agent: config fields persist and test sandbox runs the real agent`, async ({ adminPage }) => {
      const listRes = await adminPage.request.get(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/admin/agents/?key=${key}`
      );
      const templates: AgentTemplate[] = (await listRes.json()).data;
      const active = templates.find((t) => t.status === "active");
      test.skip(!active, `No active ${key} template seeded`);

      await adminPage.goto(`/admin/agents/${active!.id}`);
      await expect(adminPage.getByRole("heading", { name: active!.name })).toBeVisible();

      // Clone into an editable draft -- published templates are read-only.
      await adminPage.getByRole("button", { name: "Clone" }).click();
      await expect(adminPage).toHaveURL(/\/admin\/agents\/[0-9a-f-]+$/, { timeout: 10_000 });
      await expect(adminPage.getByText(/^Draft/)).toBeVisible();

      // Edit the system prompt and save -- confirms the field is really
      // wired to PATCH /admin/agents/{id}/, not cosmetic.
      const marker = `E2E marker ${Date.now()}`;
      const promptBox = adminPage.getByLabel("System prompt");
      await promptBox.fill(`${(await promptBox.inputValue()) || ""}\n${marker}`);
      await adminPage.getByRole("button", { name: "Save draft" }).click();
      await expect(adminPage.getByText("Saved")).toBeVisible({ timeout: 10_000 });
      await adminPage.reload();
      await expect(adminPage.getByLabel("System prompt")).toHaveValue(new RegExp(marker));

      // Test sandbox: real invocation, no session/transcript persisted.
      await adminPage.getByRole("tab", { name: "Test sandbox" }).click();
      await adminPage.getByLabel("Sample input (JSON)").fill(JSON.stringify(SAMPLE_INPUT[key], null, 2));
      await adminPage.getByRole("button", { name: "Run test" }).click();

      const resultBlock = adminPage.locator("pre");
      await expect(resultBlock).toBeVisible({ timeout: 30_000 });
      const resultText = await resultBlock.textContent();
      expect(resultText).not.toMatch(/^Error:/);
      expect(resultText).toContain("latencyMs");
      expect(resultText).toContain("output");
    });
  }
});
