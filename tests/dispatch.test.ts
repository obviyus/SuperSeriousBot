import { expect, test } from "bun:test";
import { Fiber, Layer, Redacted } from "effect";
import { Bot, Effect, InboxStore, MemoryInbox, pollInboxUpdates, type Update, type UpdateHandler } from "telly";
import { FakeBotApi } from "telly/testing";

import { conversationKey } from "../src/app/dispatch.ts";
import { commandUpdate, token } from "./harness.ts";

function caption(text: string, updateId: number): Update {
  return {
    message: {
      caption: text,
      captionEntities: [{ length: text.indexOf(" "), offset: 0, type: "bot_command" }],
      chat: { id: -1007, type: "supergroup" },
      date: 1_700_000_000,
      from: { firstName: "Ayaan", id: 1, isBot: false },
      messageId: updateId,
      photo: [{ fileId: "p", fileUniqueId: "p", height: 1, width: 1 }],
    },
    updateId,
  };
}

test("slow generation commands leave the chat's ordered lane", () => {
  expect(conversationKey(commandUpdate("/edit a tiny moon", 1))).toBe("chat:-1007:update:1");
  expect(conversationKey(commandUpdate("/EDIT@SuperSeriousBot a tiny moon", 2))).toBe("chat:-1007:update:2");
  expect(conversationKey(caption("/edit restore the colors", 3))).toBe("chat:-1007:update:3");
  expect(conversationKey(commandUpdate("/ask why", 4))).toBe("chat:-1007:update:4");
});

test("other updates keep per-chat ordering", () => {
  expect(conversationKey(commandUpdate("/quote", 5))).toBe("chat:-1007");
  expect(conversationKey(commandUpdate("hello /edit", 6))).toBe("chat:-1007");
  expect(conversationKey({
    callbackQuery: {
      chatInstance: "c",
      from: { firstName: "Ayaan", id: 1, isBot: false },
      id: "q",
      message: { chat: { id: -1007, type: "supergroup" }, date: 1, messageId: 9 },
    },
    updateId: 7,
  })).toBe("chat:-1007");
  expect(conversationKey({ updateId: 8 })).toBe("update:8");
});

const wire = (text: string, updateId: number) => ({
  update_id: updateId,
  message: {
    message_id: updateId,
    date: 1_700_000_000,
    chat: { id: -1007, type: "supergroup" },
    from: { id: 1, first_name: "Tester", is_bot: false },
    text,
    entities: [{ offset: 0, length: text.split(" ")[0]!.length, type: "bot_command" }],
  },
});

async function quoteFinishesBehindHungEdit(key?: (update: Update) => string): Promise<boolean> {
  const fake = FakeBotApi.make({
    token,
    updates: [wire("/edit a tiny moon", 1), wire("/quote", 2)],
  });
  let quoteDone = false;
  const handler: UpdateHandler<never, void> = (update) => update.updateId === 1
    ? Effect.never
    : Effect.sync(() => { quoteDone = true; });
  return Effect.runPromise(Effect.gen(function* () {
    const polling = yield* pollInboxUpdates(handler, { gracePeriodMs: 0, ...(key === undefined ? {} : { conversationKey: key }) })
      .pipe(Effect.forkChild);
    yield* Effect.promise(() => fake.whenCalled("getUpdates", 2));
    yield* Effect.sleep("300 millis");
    yield* Fiber.interrupt(polling);
    return quoteDone;
  }).pipe(
    Effect.provideService(InboxStore, MemoryInbox.make()),
    Effect.provide(Bot.layer({ token: Redacted.make(token), rateLimit: false }).pipe(Layer.provide(fake.layer))),
  ));
}

test("a hung /edit no longer blocks the next message in its chat", async () => {
  expect(await quoteFinishesBehindHungEdit()).toBe(false);
  expect(await quoteFinishesBehindHungEdit(conversationKey)).toBe(true);
});
