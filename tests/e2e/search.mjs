import { spawn } from "node:child_process";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { homedir, tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { Effect } from "telly";
import { Database } from "../../src/app/database.ts";
import { initializeDatabase } from "../../src/app/schema.ts";
import { openRouterEmbeddings, openRouterText } from "../harness.ts";

const repository = resolve(import.meta.dirname, "../..");
const skill = process.env.TELEGRAM_E2E_SKILL_DIR ?? join(homedir(), ".agents/skills/telegram-e2e-userbot");
const load = (file) => import(pathToFileURL(join(skill, "scripts", file)));
const { withTelegramRun } = await load("telegram-run-scope.mjs");
const { acquireTelegramTestCredential } = await load("telegram-test-credential.mjs");
const { checkTelegramTestCredential } = await load("telegram-test-doctor.mjs");
const { startTelegramTestApiProxy } = await load("telegram-test-api-proxy.mjs");
const { runCommand } = await load("run-mock-sut-user-e2e.mjs");
const proof = await mkdtemp(join(tmpdir(), "ssgbot-search-telegram-"));
process.chdir(resolve(repository, "../openclaw"));

const result = await withTelegramRun(async (scope) => {
  const credential = await scope.acquire(acquireTelegramTestCredential({
    signal: scope.signal,
  }));
  scope.observeLease(credential);
  const env = { ...process.env, ...credential.driverEnv, TELEGRAM_E2E_SKILL_DIR: skill };
  const driver = async (args) => {
    const result = await runCommand("uv", ["run", "--script", ...args], { cwd: repository, env, timeoutMs: 60000 });
    if (args[1] === "create" && result.stdout.trim()) chatId = JSON.parse(result.stdout.trim().split("\n")[0]).chatId;
    if (result.status !== 0) throw new Error(result.stderr || result.stdout);
    return result.stdout;
  };
  let chatId;
  let child;
  let provider;
  try {
    const created = await driver([join(import.meta.dirname, "search-group.py"), "create", credential.sutBotId, credential.sutUsername]);
    const group = JSON.parse(created.trim().split("\n").at(-1));
    chatId = group.chatId;
    const readiness = await checkTelegramTestCredential({ credential: { ...credential, groupId: String(chatId) } });
    await writeFile(join(proof, "readiness.json"), JSON.stringify(readiness));
    const proxy = scope.ownProxy(await startTelegramTestApiProxy({ leaseHealth: scope.health }));
    await proxy.drainUpdates(credential.sutToken);
    const calls = [];
    provider = createServer(async (request, response) => {
      const chunks = [];
      for await (const chunk of request) chunks.push(chunk);
      const body = Buffer.concat(chunks).toString();
      calls.push({ url: request.url, body: JSON.parse(body) });
      const reply = request.url.includes("embeddings") ? openRouterEmbeddings(body)
        : openRouterText(JSON.stringify(body.includes("Plan retrieval")
        ? { queries: [], memberIds: [], topics: [] }
        : { answer: "Alice builds satellites. Space nerd, confirmed.", citations: [1] }));
      response.writeHead(reply.status, Object.fromEntries(reply.headers));
      response.end(Buffer.from(await reply.arrayBuffer()));
    });
    await new Promise((resolveListen) => provider.listen(0, "127.0.0.1", resolveListen));
    const providerPort = provider.address().port;
    const databaseUrl = `file:${join(proof, "fixture.db")}`;
    const database = Database.open({ tursoDatabaseUrl: databaseUrl, tursoAuthToken: "test" });
    await Effect.runPromise(initializeDatabase(database));
    await Effect.runPromise(database.batch([
      { sql: "INSERT INTO group_settings (chat_id, fts) VALUES (?, 1)", args: [chatId] },
      { sql: "INSERT INTO chat_stats (chat_id, user_id, message_id, message_text) VALUES (?, ?, ?, ?)", args: [chatId, Number(credential.testerUserId), group.messageId, "Alice builds satellites."] },
      { sql: "INSERT INTO chat_search_windows (chat_id,start_message_id,end_message_id,start_time,end_time,message_count,message_text,embedding,embedding_model,embedding_dimension) VALUES (?,?,?,'2026-09-07','2026-09-07',1,?,vector32(?),'qwen/qwen3-embedding-8b',1024)", args: [chatId, group.messageId, group.messageId, "Alice builds satellites.", JSON.stringify(Array(1024).fill(0.01))] },
    ]));
    database.close();
    const ready = new Promise((resolveReady, reject) => {
      child = spawn("bun", [join(repository, "src", "main.ts")], { cwd: repository, env: {
        ...process.env, TELEGRAM_TOKEN: credential.sutToken, TELEGRAM_API_ROOT: proxy.apiRoot,
        ADMINS: credential.testerUserId, QUOTE_CHANNEL_ID: String(chatId), LOGGING_CHANNEL_ID: "",
        TURSO_DATABASE_URL: databaseUrl, TURSO_AUTH_TOKEN: "test", UPDATER: "polling",
        OPENROUTER_API_KEY: "test", OPENROUTER_BASE_URL: `http://127.0.0.1:${providerPort}`,
        TELLY_STATE_DIRECTORY: join(proof, "state"),
      }, stdio: ["ignore", "pipe", "pipe"] });
      scope.ownChild(child, async (process) => { process.kill("SIGTERM"); });
      const timer = setTimeout(() => reject(new Error("Search test bot did not start")), 30000);
      child.stdout.on("data", (chunk) => { if (String(chunk).includes("Started @")) { clearTimeout(timer); resolveReady(); } });
      child.once("error", reject);
      child.once("exit", () => { clearTimeout(timer); reject(new Error("Search test bot exited before readiness")); });
    });
    await ready;
    const scenario = join(proof, "scenario.json");
    await writeFile(scenario, JSON.stringify({ actions: [{ atMs: 0, type: "send", text: "/search what does Alice do" }] }));
    await driver([join(skill, "scripts/user-record.py"), "--chat", String(chatId), "--scenario", scenario,
      "--seconds", "12", "--record", join(proof, "events.ndjson"), "--output", join(proof, "summary.json"), "--sut-user-id", credential.sutBotId]);
    await writeFile(join(proof, "provider-requests.json"), JSON.stringify(calls));
    const summary = JSON.parse(await readFile(join(proof, "summary.json"), "utf8"));
    if (!summary.sutRevisionTexts.some((text) => text.includes("Alice builds satellites"))) throw new Error("Search answer missing from Telegram timeline");
    return { ok: true, proof, providerRequests: calls.length };
  } finally {
    await scope.stopChild(child);
    if (provider !== undefined) await new Promise((resolveClose) => provider.close(resolveClose));
    if (chatId !== undefined) await driver([join(import.meta.dirname, "search-group.py"), "cleanup", String(chatId)]);
  }
});
console.log(JSON.stringify(result));
