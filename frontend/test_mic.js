const { chromium } = require("@playwright/test");

(async () => {
  const browser = await chromium.launch({
    headless: true,
    args: ["--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required"],
  });
  const context = await browser.newContext();
  await context.grantPermissions(["microphone"]);
  const page = await context.newPage();
  await page.goto("http://localhost:3000/login");

  const devices = await page.evaluate(async () => {
    const list = await navigator.mediaDevices.enumerateDevices();
    return list.map((d) => ({ kind: d.kind, label: d.label, deviceId: d.deviceId }));
  });
  console.log("devices:", JSON.stringify(devices));

  const result = await page.evaluate(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const ctx = new AudioCtx();
    const source = ctx.createMediaStreamSource(stream);
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    let maxAmp = 0;
    let samples = 0;
    source.connect(processor);
    processor.connect(ctx.destination === undefined ? ctx.destination : ctx.destination);
    await new Promise((resolve) => {
      processor.onaudioprocess = (e) => {
        const data = e.inputBuffer.getChannelData(0);
        for (let i = 0; i < data.length; i++) {
          maxAmp = Math.max(maxAmp, Math.abs(data[i]));
        }
        samples += data.length;
      };
      setTimeout(resolve, 4000);
    });
    stream.getTracks().forEach((t) => t.stop());
    return { maxAmp, samples };
  });

  console.log(JSON.stringify(result));
  await browser.close();
})();
