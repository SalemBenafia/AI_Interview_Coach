import { test as base, type BrowserContext, type Page } from "@playwright/test";

// Auth is HttpOnly cookies set directly by FastAPI (app/modules/auth/router.py
// login()), not localStorage -- context.request.post() stores the response's
// Set-Cookie in that browser context's own cookie jar automatically, and
// every subsequent page.goto()/page.request call in the same context carries
// it. Seeded users, see backend/seed.py.
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export const ADMIN_CREDENTIALS = { email: "admin@interview-coach.ai", password: "Admin@123456" };
export const CANDIDATE_CREDENTIALS = { email: "demo@interview-coach.ai", password: "Demo@123456" };

async function loginAs(context: BrowserContext, email: string, password: string): Promise<void> {
  const response = await context.request.post(`${API_BASE_URL}/auth/login/`, {
    data: { email, password },
  });
  if (!response.ok()) {
    throw new Error(`Login failed for ${email}: ${response.status()} ${await response.text()}`);
  }
}

type Fixtures = {
  adminPage: Page;
  candidatePage: Page;
};

export const test = base.extend<Fixtures>({
  // eslint-disable-next-line no-empty-pattern
  adminPage: async ({ browser }, use) => {
    const context = await browser.newContext();
    await loginAs(context, ADMIN_CREDENTIALS.email, ADMIN_CREDENTIALS.password);
    const page = await context.newPage();
    await use(page);
    await context.close();
  },
  // eslint-disable-next-line no-empty-pattern
  candidatePage: async ({ browser }, use) => {
    // Candidate pages may join the live interview room (LiveKit WebRTC),
    // which requests mic access -- grant it up front so that flow never
    // blocks on a permission prompt (fake-device args are set in
    // playwright.config.ts).
    const context = await browser.newContext({ permissions: ["microphone"] });
    await loginAs(context, CANDIDATE_CREDENTIALS.email, CANDIDATE_CREDENTIALS.password);
    const page = await context.newPage();
    await use(page);
    await context.close();
  },
});

export { expect } from "@playwright/test";
