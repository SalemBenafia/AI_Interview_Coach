const { chromium } = require("@playwright/test");
const http = require("http");
const fs = require("fs");
const { execFile } = require("child_process");
const path = require("path");

const FRONTEND = "http://localhost:3000";
const TTS_URL = "http://localhost:5002/synthesize";
const CANDIDATE = { email: "demo@interview-coach.ai", password: "Demo@123456" };
const RECORDINGS_DIR = "/app/recordings";
const CONTROL_PORT = 7799;

fs.mkdirSync(RECORDINGS_DIR, { recursive: true });

function wavFromPcm(pcm, sampleRate) {
  const header = Buffer.alloc(44);
  const dataSize = pcm.length;
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + dataSize, 4);
  header.write("WAVE", 8);
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20); // PCM
  header.writeUInt16LE(1, 22); // mono
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(sampleRate * 2, 28); // byte rate
  header.writeUInt16LE(2, 32); // block align
  header.writeUInt16LE(16, 34); // bits per sample
  header.write("data", 36);
  header.writeUInt32LE(dataSize, 40);
  return Buffer.concat([header, pcm]);
}

async function synthesize(text) {
  const res = await fetch(TTS_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error(`TTS failed: ${res.status} ${await res.text()}`);
  const sampleRate = parseInt(res.headers.get("x-sample-rate"), 10);
  const pcm = Buffer.from(await res.arrayBuffer());
  return wavFromPcm(pcm, sampleRate);
}

function playWav(filePath) {
  return new Promise((resolve, reject) => {
    execFile("paplay", [filePath], (err) => {
      if (err) reject(err);
      else resolve();
    });
  });
}

async function readCaptions(page) {
  return page.evaluate(() => {
    const container = document.querySelector("aside .overflow-y-auto");
    if (!container) return [];
    const nodes = Array.from(container.children).filter(
      (el) => el.textContent && el.textContent.trim().length > 0
    );
    return nodes.map((n) => ({
      speaker: n.className.includes("ml-auto") ? "candidate" : "ai",
      text: n.textContent.trim(),
    }));
  });
}

async function main() {
  const browser = await chromium.launch({
    headless: true,
    args: [
      "--use-fake-ui-for-media-stream",
      "--autoplay-policy=no-user-gesture-required",
    ],
  });

  const context = await browser.newContext({
    recordVideo: { dir: RECORDINGS_DIR, size: { width: 1366, height: 768 } },
    viewport: { width: 1366, height: 768 },
    permissions: ["microphone"],
  });

  const page = await context.newPage();

  console.log("STEP: goto login");
  await page.goto(`${FRONTEND}/login`, { waitUntil: "load", timeout: 120000 });
  await page.waitForSelector('input[type="email"]', { timeout: 60000 });
  await page.fill('input[type="email"]', CANDIDATE.email);
  await page.fill('input[type="password"]', CANDIDATE.password);
  await page.getByRole("button", { name: "Sign in" }).click();

  console.log("STEP: wait for dashboard/shell after login");
  await page.waitForURL(/\/candidate\//, { timeout: 60000 });

  console.log("STEP: goto practice setup");
  await page.goto(`${FRONTEND}/candidate/practice`, { waitUntil: "load", timeout: 120000 });
  await page.getByRole("heading", { name: "Set up your interview" }).waitFor({ timeout: 60000 });
  await page.waitForTimeout(1500);

  console.log("STEP: start interview");
  await page.getByRole("button", { name: "Start the interview" }).click();
  await page.waitForURL(/\/candidate\/interview\//, { timeout: 60000 });

  console.log("STEP: join interview room");
  await page.getByRole("button", { name: "Join the interview" }).waitFor({ timeout: 60000 });
  await page.getByRole("button", { name: "Join the interview" }).click();

  console.log("STEP: wait for live transcript panel");
  await page.getByRole("heading", { name: "Live transcript" }).waitFor({ timeout: 60000 });

  console.log("READY: control server starting on port", CONTROL_PORT);

  const server = http.createServer(async (req, res) => {
    try {
      let body = "";
      req.on("data", (c) => (body += c));
      await new Promise((r) => req.on("end", r));
      const payload = body ? JSON.parse(body) : {};

      if (req.method === "GET" && req.url === "/status") {
        const captions = await readCaptions(page);
        const url = page.url();
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ captions, url }));
        return;
      }

      if (req.method === "POST" && req.url === "/speak") {
        const wav = await synthesize(payload.text);
        const filePath = path.join(RECORDINGS_DIR, `answer-${Date.now()}.wav`);
        fs.writeFileSync(filePath, wav);
        await playWav(filePath);
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true }));
        return;
      }

      if (req.method === "POST" && req.url === "/end") {
        await page.getByRole("button", { name: "End interview" }).click();
        await page.getByRole("dialog").getByRole("button", { name: "End interview" }).click();
        await page.waitForURL(/\/report/, { timeout: 60000 });
        // Wait out the loading skeleton for the real report content.
        await page
          .getByText("Still generating your report")
          .waitFor({ timeout: 5000 })
          .catch(() => {});
        await page
          .getByText(/score|overall|feedback/i)
          .first()
          .waitFor({ timeout: 90000 })
          .catch(() => {});
        await page.waitForTimeout(3000);
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true, url: page.url() }));
        return;
      }

      if (req.method === "POST" && req.url === "/shutdown") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true }));
        server.close();
        await page.waitForTimeout(1000);
        const videoPath = await page.video().path();
        await context.close();
        await browser.close();
        console.log("VIDEO_PATH:", videoPath);
        process.exit(0);
        return;
      }

      if (req.method === "GET" && req.url === "/screenshot") {
        const shotPath = path.join(RECORDINGS_DIR, `shot-${Date.now()}.png`);
        await page.screenshot({ path: shotPath });
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ path: shotPath }));
        return;
      }

      res.writeHead(404);
      res.end("not found");
    } catch (err) {
      console.error("control error:", err);
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: String(err) }));
    }
  });

  server.listen(CONTROL_PORT, () => {
    console.log("CONTROL_SERVER_UP");
  });
}

main().catch((err) => {
  console.error("FATAL:", err);
  process.exit(1);
});
