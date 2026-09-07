import { expect, test } from "bun:test";

import { messageLink } from "../src/app/links.ts";

test("message links use a public username before the private supergroup address", () => {
  expect(messageLink(-100123, 42, "public_group")).toBe("https://t.me/public_group/42");
});

test("private supergroup links retain the message id", () => {
  expect(messageLink(-100123, 42)).toBe("https://t.me/c/123/42");
});

test("private chats and basic groups have no message permalink", () => {
  expect(messageLink(123, 42)).toBeUndefined();
  expect(messageLink(-123, 42)).toBeUndefined();
});
