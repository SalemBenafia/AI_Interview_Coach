import { test, expect } from "../fixtures/auth";

// Item 15: target role lifecycle (draft -> analyzing -> ready, a real
// Groq call via the Knowledge Extraction agent) plus the new hard-Delete
// button wired to the backend's existing (previously UI-unreachable)
// DELETE /target-roles/{id}/.

test("create, add fields, analyze to Ready, then hard-delete a target role", async ({ candidatePage }) => {
  const title = `E2E Target Role ${Date.now()}`;

  await candidatePage.goto("/candidate/target-roles");
  await candidatePage.getByRole("button", { name: "New target role" }).click();
  await candidatePage.getByLabel("Job title").fill(title);
  await candidatePage.getByRole("button", { name: "Create" }).click();

  await expect(candidatePage).toHaveURL(/\/candidate\/target-roles\/[0-9a-f-]+$/, { timeout: 10_000 });
  await expect(candidatePage.getByText("Draft")).toBeVisible();

  await candidatePage.getByLabel("Field title").fill("Experience");
  await candidatePage.getByLabel("Field description").fill(
    "Worked at Acme as a backend developer for 3 years, building payments infrastructure and leading a small team."
  );
  await candidatePage.getByRole("button", { name: "Add field" }).click();
  await expect(candidatePage.getByText("1 field(s) ready to analyze.")).toBeVisible();

  await candidatePage.getByRole("button", { name: "Analyze" }).click();
  await expect(candidatePage.getByText("Analyzing…")).toBeVisible({ timeout: 10_000 });
  await expect(candidatePage.getByText("Ready", { exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(candidatePage.getByText("What the AI learned")).toBeVisible();
  await expect(candidatePage.getByText("This target role is ready to use")).toBeVisible();

  // Hard delete via the new button.
  const targetRoleId = candidatePage.url().match(/\/candidate\/target-roles\/([0-9a-f-]+)$/)![1];
  await candidatePage.getByTitle("Delete this target role").click();
  await candidatePage.getByRole("dialog").getByRole("button", { name: "Delete" }).click();

  await expect(candidatePage).toHaveURL("/candidate/target-roles", { timeout: 10_000 });
  const getRes = await candidatePage.request.get(
    `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/target-roles/${targetRoleId}/`
  );
  expect(getRes.status()).toBe(404);
});
