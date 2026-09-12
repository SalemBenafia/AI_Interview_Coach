import { test, expect } from "../fixtures/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// Item 11: audit log correctness, including the coverage gap this project
// fixed -- flow/agent create/publish/delete previously wrote NO audit rows
// despite being the highest-impact admin actions (a publish instantly
// changes every live candidate's interview).

async function latestAuditAction(request: import("@playwright/test").APIRequestContext) {
  const res = await request.get(`${API_BASE}/admin/security/audit-logs/`, { params: { page: 1, limit: 5 } });
  const body = await res.json();
  return body.data as { action: string; resourceType: string | null; resourceId: string | null }[];
}

test("admin account creation writes an audit entry (existing behavior)", async ({ adminPage }) => {
  const email = `e2e-${Date.now()}@interview-coach.ai`;
  await adminPage.goto("/admin/security");
  await adminPage.getByRole("button", { name: "New admin" }).click();
  await adminPage.getByLabel("First name").fill("E2E");
  await adminPage.getByLabel("Last name").fill("Tester");
  await adminPage.getByLabel("Email").fill(email);
  await adminPage.getByLabel("Username").fill(`e2e_${Date.now()}`);
  await adminPage.getByLabel("Temporary password").fill("TempPass123!");
  await adminPage.getByRole("button", { name: "Create" }).click();
  await expect(adminPage.getByText(/admin account created/i)).toBeVisible({ timeout: 10_000 });

  const logs = await latestAuditAction(adminPage.request);
  expect(logs.some((l) => l.action === "admin.create")).toBe(true);
});

test("flow publish and agent clone write new audit entries (the gap this project fixed)", async ({ adminPage }) => {
  const createRes = await adminPage.request.post(`${API_BASE}/admin/flows/`, {
    data: { name: `E2E Audit Flow ${Date.now()}`, mode: "mixed" },
  });
  const { flowId } = (await createRes.json()).data;

  const validGraph = {
    nodes: [
      { id: "start", type: "start", position: { x: 0, y: 0 }, data: {} },
      { id: "q1", type: "question", position: { x: 250, y: 0 }, data: { agent: "interviewer" } },
      { id: "eval1", type: "evaluation", position: { x: 500, y: 0 }, data: { agent: "evaluator" } },
      { id: "router1", type: "router", position: { x: 750, y: 0 }, data: { agent: "router" } },
      { id: "end1", type: "end", position: { x: 1000, y: 0 }, data: {} },
    ],
    edges: [
      { id: "e1", source: "start", target: "q1" },
      { id: "e2", source: "eval1", target: "router1" },
      { id: "e3", source: "router1", target: "q1", data: { action: "ask_followup" } },
      { id: "e4", source: "router1", target: "q1", data: { action: "next_question" } },
      { id: "e5", source: "router1", target: "q1", data: { action: "increase_difficulty" } },
      { id: "e6", source: "router1", target: "q1", data: { action: "coaching" } },
      { id: "e7", source: "router1", target: "end1", data: { action: "end" } },
    ],
  };
  await adminPage.request.patch(`${API_BASE}/admin/flows/${flowId}/`, { data: { graph_json: validGraph } });
  const publishRes = await adminPage.request.post(`${API_BASE}/admin/flows/${flowId}/publish/`);
  expect(publishRes.ok()).toBeTruthy();

  const agentsRes = await adminPage.request.get(`${API_BASE}/admin/agents/?key=coach`);
  const agents = (await agentsRes.json()).data;
  const activeCoach = agents.find((a: { status: string }) => a.status === "active");
  const cloneRes = await adminPage.request.post(`${API_BASE}/admin/agents/${activeCoach.id}/clone/`);
  expect(cloneRes.ok()).toBeTruthy();

  await expect(async () => {
    const logs = await latestAuditAction(adminPage.request);
    expect(logs.some((l) => l.action === "flow.publish" && l.resourceId === flowId)).toBe(true);
    expect(logs.some((l) => l.action === "agent.clone")).toBe(true);
  }).toPass({ timeout: 10_000 });

  await adminPage.goto("/admin/security");
  await adminPage.getByRole("tab", { name: "Audit log" }).click();
  await expect(adminPage.getByText("flow.publish").first()).toBeVisible({ timeout: 10_000 });
});
