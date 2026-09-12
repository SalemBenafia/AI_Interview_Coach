const { chromium } = require("@playwright/test");

const FRONTEND = "http://localhost:3000";
const CANDIDATE = { email: "demo@interview-coach.ai", password: "Demo@123456" };
const SESSION_ID = process.argv[2];
const RECORDINGS_DIR = "/app/recordings";

async function main() {
  const browser = await chromium.launch({
    headless: true,
    args: ["--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required"],
  });
  const context = await browser.newContext({
    recordVideo: { dir: RECORDINGS_DIR, size: { width: 1366, height: 768 } },
    viewport: { width: 1366, height: 768 },
  });
  const page = await context.newPage();

  console.log("STEP: login");
  await page.goto(`${FRONTEND}/login`, { waitUntil: "load", timeout: 120000 });
  await page.waitForSelector('input[type="email"]', { timeout: 60000 });
  await page.fill('input[type="email"]', CANDIDATE.email);
  await page.fill('input[type="password"]', CANDIDATE.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/candidate\//, { timeout: 60000 });

  console.log("STEP: goto report");
  await page.goto(`${FRONTEND}/candidate/interview/${SESSION_ID}/report`, {
    waitUntil: "load",
    timeout: 120000,
  });

  console.log("STEP: waiting for real report content (retrying 'Check again' as needed)");
  const deadline = Date.now() + 5 * 60 * 1000;
  let ready = false;
  while (Date.now() < deadline) {
    const heading = await page.getByRole("heading", { name: "Your interview report" }).count();
    if (heading > 0) {
      ready = true;
      break;
    }
    const checkAgain = page.getByRole("button", { name: "Check again" });
    if (await checkAgain.count()) {
      await checkAgain.click().catch(() => {});
    }
    await page.waitForTimeout(5000);
  }

  console.log(ready ? "STEP: report ready" : "STEP: timed out waiting for report");
  await page.waitForTimeout(4000);
  // Scroll through the report slowly so the video actually shows the content.
  await page.mouse.wheel(0, 400);
  await page.waitForTimeout(1500);
  await page.mouse.wheel(0, 600);
  await page.waitForTimeout(2500);

  const videoPath = await page.video().path();
  await context.close();
  await browser.close();
  console.log("VIDEO_PATH:", videoPath);
}

main().catch((err) => {
  console.error("FATAL:", err);
  process.exit(1);
});
