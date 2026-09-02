import { spawn } from "node:child_process";
import { resolve4 } from "node:dns/promises";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import net from "node:net";
import { pathToFileURL } from "node:url";

const repository = path.resolve(import.meta.dirname, "../..");
const skillDirectory = process.env.TELEGRAM_E2E_SKILL_DIR ?? path.resolve(
  repository,
  "../telly/.agents/skills/telegram-e2e-userbot",
);
const brokerDirectory = process.env.TELEGRAM_E2E_CONVEX_PROJECT_DIR ?? path.resolve(
  repository,
  "../openclaw/qa/convex-credential-broker",
);
const proofDirectory = path.resolve(
  process.env.TELEGRAM_E2E_PROOF_DIR ?? fs.mkdtempSync(path.join(os.tmpdir(), "superseriousbot-proof-")),
);
const scratch = fs.mkdtempSync(path.join(os.tmpdir(), "superseriousbot-e2e-"));

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (address === null || typeof address === "string") {
        server.close();
        reject(new Error("Could not reserve webhook port"));
        return;
      }
      server.close(() => resolve(address.port));
    });
  });
}

async function waitForDns(url) {
  const hostname = new URL(url).hostname;
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try {
      await resolve4(hostname);
      return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
  throw new Error("Public tunnel DNS did not propagate");
}

const credentialModule = await import(pathToFileURL(path.join(
  skillDirectory,
  "scripts/telegram-test-credential.mjs",
)));
const proxyModule = await import(pathToFileURL(path.join(
  skillDirectory,
  "scripts/telegram-test-api-proxy.mjs",
)));

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: repository,
      env: options.env ?? process.env,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
      if (options.logPath) fs.appendFileSync(options.logPath, chunk);
      options.onStdout?.(String(chunk));
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
      if (options.logPath) fs.appendFileSync(options.logPath, chunk);
    });
    child.once("error", reject);
    child.once("exit", (code, signal) => {
      if (code === 0) resolve({ stderr, stdout });
      else reject(new Error(`${command} exited with ${code ?? signal}: ${stderr.slice(-2_000)}`));
    });
    options.started?.(child);
  });
}

let credential;
let proxy;
let bot;
let tunnel;
let mockAi;
const aiRequests = [];
try {
  fs.mkdirSync(proofDirectory, { recursive: true });
  credential = await credentialModule.acquireTelegramTestCredential({
    convexProjectDir: brokerDirectory,
  });
  proxy = await proxyModule.startTelegramTestApiProxy({
    leaseHealth: {
      assertHealthy: credential.assertLeaseHealthy,
      whenUnhealthy: credential.whenLeaseUnhealthy,
    },
  });
  await proxy.drainUpdates(credential.sutToken);
  const groupMode = process.env.TELEGRAM_E2E_GROUP === "1";
  let chatTarget = `@${credential.sutUsername}`;
  if (groupMode) {
    const ensured = await run("uv", [
      "run",
      "--script",
      path.join(skillDirectory, "scripts/isolated-group.py"),
      "ensure",
    ], { env: { ...process.env, ...credential.driverEnv } });
    const group = JSON.parse(ensured.stdout);
    if (!Number.isSafeInteger(group.chatId)) throw new Error("Isolated Telegram group missing");
    chatTarget = String(group.chatId);
  }

  const webhookMode = process.env.TELEGRAM_E2E_WEBHOOK === "1";
  const aiMode = process.env.TELEGRAM_E2E_AI === "1";
  let openrouterBaseUrl = "";
  if (aiMode) {
    mockAi = Bun.serve({
      hostname: "127.0.0.1",
      port: 0,
      async fetch(request) {
        const body = await request.json();
        aiRequests.push({ body, userAgent: request.headers.get("user-agent") });
        fs.writeFileSync(
          path.join(proofDirectory, "ai-requests.json"),
          `${JSON.stringify(aiRequests, null, 2)}\n`,
        );
        const chunks = [
          { choices: [{ delta: { content: "AI_SDK_E2E_OK", role: "assistant" }, finish_reason: null, index: 0 }], id: "e2e", model: "test/model" },
          { choices: [{ delta: {}, finish_reason: "stop", index: 0 }], id: "e2e", model: "test/model" },
        ];
        return new Response(
          `${chunks.map((chunk) => `data: ${JSON.stringify(chunk)}\n\n`).join("")}data: [DONE]\n\n`,
          { headers: { "content-type": "text/event-stream" } },
        );
      },
    });
    openrouterBaseUrl = `http://127.0.0.1:${mockAi.port}`;
  }
  const webhookPort = webhookMode ? await freePort() : 8_443;
  let webhookUrl = "";
  if (webhookMode) {
    webhookUrl = await new Promise((resolve, reject) => {
      tunnel = spawn("bunx", ["localtunnel@2.0.2", "--port", String(webhookPort)], {
        cwd: repository,
        stdio: ["ignore", "pipe", "pipe"],
      });
      const timer = setTimeout(() => reject(new Error("Public tunnel did not start")), 30_000);
      tunnel.stdout.on("data", (chunk) => {
        fs.appendFileSync(path.join(proofDirectory, "tunnel.log"), chunk);
        const match = String(chunk).match(/https:\/\/[a-z0-9-]+\.loca\.lt/u);
        if (match === null) return;
        clearTimeout(timer);
        resolve(match[0]);
      });
      tunnel.stderr.on("data", (chunk) => fs.appendFileSync(
        path.join(proofDirectory, "tunnel.log"),
        chunk,
      ));
      tunnel.once("error", reject);
      tunnel.once("exit", (code) => {
        if (webhookUrl.length === 0) reject(new Error(`Public tunnel exited with ${code}`));
      });
    });
    await waitForDns(webhookUrl);
  }

  let started;
  const ready = new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("SuperSeriousBot did not start")), 30_000);
    started = (text) => {
      if (!text.includes(webhookMode ? "Webhook listening" : "Started @")) return;
      clearTimeout(timer);
      resolve();
    };
  });
  const botRun = run("bun", ["src/main.ts"], {
    env: {
      ...process.env,
      ADMINS: credential.testerUserId,
      COBALT_URL: "",
      GOODREADS_API_KEY: "",
      KIE_API_KEY: "",
      LOGGING_CHANNEL_ID: "",
      NANO_GPT_API_KEY: "",
      OPENROUTER_API_KEY: aiMode ? "e2e-test" : "",
      OPENROUTER_BASE_URL: openrouterBaseUrl,
      PORT: String(webhookPort),
      QUOTE_CHANNEL_ID: groupMode ? chatTarget : credential.groupId,
      TELEGRAM_API_ROOT: proxy.apiRoot,
      TELEGRAM_TOKEN: credential.sutToken,
      TELLY_STATE_DIRECTORY: path.join(scratch, "state"),
      TURSO_AUTH_TOKEN: "test",
      TURSO_DATABASE_URL: `file:${path.join(scratch, "bot.db")}`,
      UPDATER: webhookMode ? "webhook" : "polling",
      WAQI_API_KEY: "",
      WEATHERAPI_API_KEY: "",
      WEBHOOK_URL: webhookUrl,
      WOLFRAM_APP_ID: "",
    },
    onStdout: (text) => started?.(text),
    logPath: path.join(proofDirectory, "bot.log"),
    started: (child) => {
      bot = child;
    },
  });
  await ready;

  const eventsPath = path.join(proofDirectory, "events.ndjson");
  const summaryPath = path.join(proofDirectory, "summary.json");
  const scenarioPath = path.join(scratch, "scenario.json");
  fs.writeFileSync(scenarioPath, JSON.stringify(aiMode
    ? {
        actions: [
          { atMs: 0, text: "/start", type: "send" },
          { atMs: 750, text: "/thinking high", type: "send" },
          { atMs: 1_500, text: "/ask answer with the test marker", type: "send" },
        ],
      }
    : groupMode
    ? {
        actions: [
          { atMs: 0, text: "/summon alpha", type: "send" },
          { atMs: 1_500, text: "/habit walk 3", type: "send" },
          { atMs: 3_000, buttonText: "📅 Check-in", messageText: "#walk", timeoutMs: 5_000, type: "click" },
          { atMs: 4_500, text: "/football", type: "send" },
        ],
      }
    : {
        actions: [
          { atMs: 0, text: "/start", type: "send" },
          { atMs: 1_000, text: "/ping", type: "send" },
        ],
      }));
  await run("uv", [
    "run",
    "--script",
    path.join(skillDirectory, "scripts/user-record.py"),
    "--chat",
    chatTarget,
    "--scenario",
    scenarioPath,
    "--seconds",
    groupMode ? "15" : "8",
    "--record",
    eventsPath,
    "--output",
    summaryPath,
    "--sut-user-id",
    credential.sutBotId,
  ], { env: { ...process.env, ...credential.driverEnv } });

  const summary = JSON.parse(fs.readFileSync(summaryPath, "utf8"));
  const events = Array.isArray(summary.timeline) ? summary.timeline : [];
  const revisions = Array.isArray(summary.sutRevisionTexts) ? summary.sutRevisionTexts : [];
  const proven = aiMode
    ? revisions.some((text) => text.includes("AI_SDK_E2E_OK")) &&
      revisions.some((text) => text.includes("Thinking level updated")) &&
      aiRequests.length === 1 &&
      aiRequests[0]?.body?.reasoning?.effort === "high" &&
      aiRequests[0]?.userAgent?.includes("ai-sdk/openrouter/3.0.0") === true
    : groupMode
    ? revisions.some((text) => text.includes("[alpha] (1 members)")) &&
      revisions.some((text) => text.includes("Created a new habit #walk")) &&
      revisions.some((text) => text.includes("Football alerts enabled")) &&
      events.some((event) => Array.isArray(event.buttonTexts) && event.buttonTexts.includes("📅 Check-in")) &&
      events.some((event) => event.actionType === "click" && event.status === "completed")
    : revisions.some((text) => text.startsWith("pong ("));
  if (!proven) {
    throw new Error("Telegram timeline did not contain the expected Telly behavior");
  }
  console.log(JSON.stringify({ ok: true, proofDirectory, eventCount: events.length }));
  bot.kill("SIGTERM");
  await botRun;
} finally {
  if (bot?.exitCode === null) bot.kill("SIGTERM");
  if (tunnel?.exitCode === null) tunnel.kill("SIGTERM");
  mockAi?.stop(true);
  await proxy?.close().catch(() => undefined);
  await credential?.release().catch(() => undefined);
  fs.rmSync(scratch, { force: true, recursive: true });
}
