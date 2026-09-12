import { defineConfig, devices } from "@playwright/test";

/**
 * Runs against the already-up docker-compose dev stack (make docker-up +
 * make db-seed) -- this config does not start its own webServer. See
 * e2e/fixtures/auth.ts for how admin/candidate sessions are authenticated
 * (HttpOnly cookies, not localStorage, since auth.server.ts mirrors
 * FastAPI's Set-Cookie via Next.js Server Actions).
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  // Several specs drive a full interview through the dev-turn endpoint,
  // meaning multiple sequential real Groq calls per test. On the free
  // tier, heavy same-account E2E usage can also trip the 6000
  // tokens/minute rate limit, which chat_completion() retries/falls back
  // through -- both add real wall-clock time, so this stays generous.
  timeout: 600_000,
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // HEADED=1 renders onto the container's Xvfb :99 display (started
        // ad hoc for this session -- Xvfb + x11vnc + websockify, see
        // http://localhost:6080/vnc.html) so the run can be watched live
        // instead of just read from terminal output.
        headless: process.env.HEADED !== "1",
        // The candidate interview room requests mic access (LiveKit
        // WebRTC) -- fake devices avoid a real-hardware dependency in CI,
        // and this pairs with context.grantPermissions(["microphone"]) in
        // e2e/fixtures/auth.ts's candidatePage fixture.
        launchOptions: {
          args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"],
          // Only slow down when actually being watched over VNC -- makes
          // clicks/typing visible instead of flashing by; headless/CI runs
          // stay at full speed.
          slowMo: process.env.HEADED === "1" ? 250 : 0,
        },
      },
    },
  ],
});
