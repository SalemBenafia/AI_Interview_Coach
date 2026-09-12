import { test, expect } from "../fixtures/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

// Item 5 and part of item 6: flow lifecycle (draft -> publish validation
// gate -> published -> live -> archived) plus the new hard-Delete button
// for drafts. Building the graph itself is done via a direct PATCH (the
// drag-and-drop canvas is exercised structurally by the existing backend
// pytest suite, tests/agents/test_flow_validation.py/test_flow_compiler.py)
// -- this test's job is the admin UI wiring: do the buttons call the right
// endpoints and reflect the right state back.

function validGraphJson() {
  return {
    nodes: [
      { id: "start", type: "start", position: { x: 0, y: 0 }, data: {} },
      { id: "q1", type: "question", position: { x: 250, y: 0 }, data: { agent: "interviewer" } },
      { id: "eval1", type: "evaluation", position: { x: 500, y: 0 }, data: { agent: "evaluator" } },
      { id: "router1", type: "router", position: { x: 750, y: 0 }, data: { agent: "router" } },
      { id: "coach1", type: "coaching", position: { x: 750, y: 200 }, data: { agent: "coach" } },
      { id: "end1", type: "end", position: { x: 1000, y: 0 }, data: {} },
    ],
    edges: [
      { id: "e1", source: "start", target: "q1" },
      { id: "e2", source: "eval1", target: "router1" },
      { id: "e3", source: "router1", target: "q1", data: { action: "ask_followup" } },
      { id: "e4", source: "router1", target: "q1", data: { action: "next_question" } },
      { id: "e5", source: "router1", target: "q1", data: { action: "increase_difficulty" } },
      { id: "e6", source: "router1", target: "coach1", data: { action: "coaching" } },
      { id: "e7", source: "router1", target: "end1", data: { action: "end" } },
    ],
  };
}

test("flow lifecycle: draft, publish validation gate, publish, go live, archive", async ({ adminPage }) => {
  const uniqueName = `E2E Flow ${Date.now()}`;

  // "Set as live" below steals the mode's live-flow slot from whatever was
  // previously live -- other tests (dashboard/session-lifecycle/live-flow)
  // depend on "mixed" mode always having a live flow to create sessions
  // against. Capture the current one so it can be restored, regardless of
  // whether the test passes, fails, or is interrupted partway through.
  const beforeRes = await adminPage.request.get(`${API_BASE}/admin/flows/`, { params: { mode: "mixed", status: "published" } });
  const previouslyLive = (await beforeRes.json()).data.find((f: { isDefault: boolean }) => f.isDefault);

  try {
    await adminPage.goto("/admin/flows");
    // The "New flow" modal resets its name field via a useEffect keyed on the
    // flows-list query result (to recompute modeHasNoLiveFlow) -- wait for
    // that query to settle before opening it, or typed text can be wiped by
    // a late reset.
    await adminPage.waitForLoadState("networkidle");
    await adminPage.getByRole("button", { name: "New flow", exact: true }).click();
    await adminPage.getByLabel("Flow name").fill(uniqueName);
    await adminPage.getByRole("button", { name: "Create" }).click();

    await expect(adminPage).toHaveURL(/\/admin\/flows\/[0-9a-f-]+$/, { timeout: 10_000 });
    const flowIdMatch = adminPage.url().match(/\/admin\/flows\/([0-9a-f-]+)$/);
    const flowId = flowIdMatch![1];

    // Default skeleton (a bare start node) is structurally invalid -- publish
    // must be rejected with real validation errors, not silently accepted.
    // (handlePublish auto-saves first, so a "Flow saved" toast is stacked
    // alongside the error one -- match on text, not role, to avoid ambiguity.)
    await adminPage.getByRole("button", { name: "Publish" }).click();
    await expect(adminPage.getByText(/failed validation/i)).toBeVisible({ timeout: 10_000 });

    // Build a valid graph directly (see file-level comment) and publish.
    const patchRes = await adminPage.request.patch(`${API_BASE}/admin/flows/${flowId}/`, {
      data: { graph_json: validGraphJson() },
    });
    expect(patchRes.ok()).toBeTruthy();

    await adminPage.reload();
    await adminPage.getByRole("button", { name: "Publish" }).click();
    await expect(adminPage.getByText("Flow published")).toBeVisible({ timeout: 10_000 });
    await expect(adminPage.getByText(/^Published/)).toBeVisible();

    // Set as live (flow was created without "make live on publish").
    const setLiveButton = adminPage.getByRole("button", { name: "Set as live" });
    if (await setLiveButton.isVisible()) {
      await setLiveButton.click();
      await expect(adminPage.getByText(/live/i).first()).toBeVisible({ timeout: 10_000 });
      await expect(adminPage.getByText("Live for this mode")).toBeVisible();
    }

    // Archive retires it -- soft, status-only, row retained.
    await adminPage.getByRole("button", { name: "Archive" }).click();
    await expect(adminPage).toHaveURL("/admin/flows", { timeout: 10_000 });
    const getRes = await adminPage.request.get(`${API_BASE}/admin/flows/${flowId}/`);
    expect((await getRes.json()).data.status).toBe("archived");
  } finally {
    if (previouslyLive) {
      await adminPage.request.post(`${API_BASE}/admin/flows/${previouslyLive.id}/set-default/`);
    }
  }
});

test("draft flows can be hard-deleted via the new Delete button; published ones cannot show it", async ({ adminPage }) => {
  await adminPage.goto("/admin/flows");
  await adminPage.waitForLoadState("networkidle");
  await adminPage.getByRole("button", { name: "New flow", exact: true }).click();
  await adminPage.getByLabel("Flow name").fill(`E2E Delete Me ${Date.now()}`);
  await adminPage.getByRole("button", { name: "Create" }).click();
  await expect(adminPage).toHaveURL(/\/admin\/flows\/[0-9a-f-]+$/, { timeout: 10_000 });
  const flowId = adminPage.url().match(/\/admin\/flows\/([0-9a-f-]+)$/)![1];

  const deleteButton = adminPage.getByRole("button", { name: "Delete" });
  await expect(deleteButton).toBeVisible();
  await deleteButton.click();
  await adminPage.getByRole("dialog").getByRole("button", { name: "Delete" }).click();

  await expect(adminPage).toHaveURL("/admin/flows", { timeout: 10_000 });
  const getRes = await adminPage.request.get(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/admin/flows/${flowId}/`);
  expect(getRes.status()).toBe(404);
});
