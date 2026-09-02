import {
  answerCallback,
  callbackData,
  callbackTarget,
  editMessageText,
  Effect,
  getChatAdministrators,
  html,
  Schema,
} from "telly";

import { isAdmin } from "../app/admin.ts";
import { callbackRoute, ignoreUnchangedMessage } from "../app/callback.ts";
import {
  answer,
  type CommandDefinition,
} from "../app/command.ts";
import { rowString } from "../app/database.ts";
import type { AppDependencies } from "../app/dependencies.ts";
import { replyBlocks, rich } from "../app/rich.ts";

export const defaultModels = {
  ask: "openrouter/x-ai/grok-4.3",
  cron: "openrouter/x-ai/grok-4.3",
  edit: "openrouter/google/gemini-3.1-flash-image-preview",
  search: "openrouter/openai/gpt-5.6-luna",
  song: "openrouter/x-ai/grok-4.3",
  tldr: "openrouter/google/gemini-3-flash-preview",
  tr: "google/gemini-2.5-flash",
} as const;

export type ModelCommand = keyof typeof defaultModels;

const modelCommands = Object.keys(defaultModels) as ReadonlyArray<ModelCommand>;
const modelColumns: Readonly<Record<ModelCommand, string>> = {
  ask: "ask_model",
  cron: "cron_model",
  edit: "edit_model",
  search: "search_model",
  song: "song_model",
  tldr: "tldr_model",
  tr: "tr_model",
};
const thinkingLevels = ["none", "minimal", "low", "medium", "high"] as const;

const toggleDefinitions = [
  { key: "fts", label: "Message search", table: "group_settings", value: "fts" },
  { key: "auto_dl", label: "Auto download", table: "group_settings", value: "auto_dl" },
  { key: "ask", label: "/ask", table: "command_whitelist", value: "ask" },
  { key: "edit", label: "/edit", table: "command_whitelist", value: "edit" },
  { key: "video", label: "/video", table: "command_whitelist", value: "video" },
  { key: "tr", label: "/tr", table: "command_whitelist", value: "tr" },
  { key: "tldr", label: "/tldr", table: "command_whitelist", value: "tldr" },
  { key: "search", label: "/search", table: "command_whitelist", value: "search" },
  { key: "cron", label: "/cron", table: "command_whitelist", value: "cron" },
  { key: "song", label: "/song", table: "command_whitelist", value: "song" },
] as const;

type ToggleKey = (typeof toggleDefinitions)[number]["key"];

const SettingsCallback = callbackData("settings", Schema.Struct({
  chatId: Schema.Int,
  key: Schema.Literals(toggleDefinitions.map((toggle) => toggle.key)),
}));

function modelName(value: string): ModelCommand | undefined {
  return modelCommands.find((name) => name === value);
}

export function normalizeModelName(value: string): string {
  return value.replace(/^openrouter\//u, "");
}

export function getModel(dependencies: AppDependencies, command: ModelCommand) {
  return dependencies.database.one(
    `SELECT ${modelColumns[command]} AS model FROM group_settings WHERE chat_id = -1`,
  ).pipe(Effect.map((row) => row === undefined || row["model"] === null
    ? defaultModels[command]
    : rowString(row, "model")));
}

export function getThinking(dependencies: AppDependencies) {
  return dependencies.database.one(
    "SELECT ask_thinking FROM group_settings WHERE chat_id = -1",
  ).pipe(Effect.map((row) => row === undefined || row["ask_thinking"] === null
    ? "none"
    : rowString(row, "ask_thinking")));
}

function modelCommand(dependencies: AppDependencies): CommandDefinition {
  return {
    description: "Set AI models for commands: ask, cron, edit, search, song, tr, tldr.",
    example: "/model ask openrouter/x-ai/grok-4.3",
    names: ["model"],
    run: Effect.fn("modelSettings")(function* (match) {
      if (!isAdmin(dependencies, match.message.from?.id ?? "")) {
        return yield* answer(match.message, "❌ This command is only available to admins.");
      }
      if (match.args.length === 0) {
        const models = yield* Effect.all(Object.fromEntries(
          modelCommands.map((name) => [name, getModel(dependencies, name)]),
        ));
        const table = rich.table([
          ["Command", "Model"],
          ...modelCommands.map((name) => [
            rich.command(`/${name}`),
            rich.code(models[name] ?? defaultModels[name]),
          ]),
        ], { header: true });
        return yield* replyBlocks(match.message, [
          rich.heading("📋 Current AI models"),
          { ...table, isBordered: true, isCompact: true },
          rich.footer(["Usage: ", rich.code("/model <command> <model_name>")]),
        ]);
      }
      const requested = match.args[0]?.toLowerCase();
      const targets = requested === "all"
        ? modelCommands
        : requested === undefined
        ? []
        : [modelName(requested)].filter((value): value is ModelCommand => value !== undefined);
      const nextModel = match.args.slice(1).join(" ").trim();
      if (targets.length === 0 || nextModel.length === 0) {
        return yield* answer(
          match.message,
          "❌ Specify a valid command and model name. Commands: ask, cron, edit, search, song, tr, tldr, all",
        );
      }
      const columns = targets.map((target) => modelColumns[target]);
      yield* dependencies.database.execute(
        `INSERT INTO group_settings (chat_id, ${columns.join(", ")})
         VALUES (-1, ${columns.map(() => "?").join(", ")})
         ON CONFLICT(chat_id) DO UPDATE SET ${columns.map((column) => `${column} = excluded.${column}`).join(", ")}`,
        targets.map(() => nextModel),
      );
      return yield* answer(match.message, {
        parseMode: "HTML",
        text: requested === "all"
          ? `✅ All command models updated to: <code>${html.escape(nextModel)}</code>`
          : `✅ Model for <b>/${targets[0]}</b> updated to: <code>${html.escape(nextModel)}</code>`,
      });
    }),
    usage: "/model [command] [model_name]",
  };
}

function thinkingCommand(dependencies: AppDependencies): CommandDefinition {
  return {
    description: "Set reasoning effort for /ask.",
    example: "/thinking high",
    names: ["thinking"],
    run: Effect.fn("thinkingSettings")(function* (match) {
      if (!isAdmin(dependencies, match.message.from?.id ?? "")) {
        return yield* answer(match.message, "❌ This command is only available to admins.");
      }
      const level = match.args[0]?.toLowerCase();
      if (level === undefined) {
        const current = yield* getThinking(dependencies);
        return yield* replyBlocks(match.message, [
          rich.heading("🧠 AI thinking level"),
          rich.paragraph(["Current level: ", rich.code(current)]),
          rich.list(thinkingLevels.map((candidate) => rich.code(candidate))),
          rich.footer(["Usage: ", rich.code("/thinking <level>")]),
        ]);
      }
      if (!thinkingLevels.some((candidate) => candidate === level)) {
        return yield* answer(match.message, `❌ Invalid thinking level: ${level}`);
      }
      yield* dependencies.database.execute(
        `INSERT INTO group_settings (chat_id, ask_thinking) VALUES (-1, ?)
         ON CONFLICT(chat_id) DO UPDATE SET ask_thinking = excluded.ask_thinking`,
        [level],
      );
      return yield* answer(match.message, {
        parseMode: "HTML",
        text: `✅ Thinking level updated to: <code>${level}</code>`,
      });
    }),
    usage: "/thinking [level]",
  };
}

function canManage(dependencies: AppDependencies, chatId: number, userId: number) {
  if (isAdmin(dependencies, userId)) return Effect.succeed(true);
  return getChatAdministrators({ chatId }).pipe(
    Effect.map((members) => members.some((member) => member.user.id === userId)),
  );
}

function settingStates(dependencies: AppDependencies, chatId: number) {
  return Effect.gen(function* () {
    const states: Record<ToggleKey, boolean> = {
      ask: false,
      auto_dl: false,
      cron: false,
      edit: false,
      fts: false,
      search: false,
      song: false,
      tldr: false,
      tr: false,
      video: false,
    };
    const setting = yield* dependencies.database.one(
      "SELECT fts, auto_dl FROM group_settings WHERE chat_id = ?",
      [chatId],
    );
    states.fts = setting?.["fts"] === 1;
    states.auto_dl = setting?.["auto_dl"] === 1;
    const rows = yield* dependencies.database.all(
      `SELECT command FROM command_whitelist
       WHERE whitelist_type = 'chat' AND whitelist_id = ?`,
      [chatId],
    );
    for (const row of rows) {
      const command = rowString(row, "command");
      if (toggleDefinitions.some((toggle) => toggle.key === command)) {
        states[command as ToggleKey] = true;
      }
    }
    return states;
  });
}

function keyboard(chatId: number, states: Readonly<Record<ToggleKey, boolean>>) {
  return {
    inlineKeyboard: toggleDefinitions.map((toggle) => [SettingsCallback.button(
      `${states[toggle.key] ? "On" : "Off"} - ${toggle.label}`,
      { chatId, key: toggle.key },
    )]),
  };
}

function settingsBlocks(chatId: number) {
  return [
    rich.heading("⚙️ Group settings"),
    rich.paragraph(["Chat: ", rich.code(String(chatId))]),
    rich.footer("Use the buttons below to enable or disable each feature."),
  ];
}

function settingsCommand(dependencies: AppDependencies): CommandDefinition {
  return {
    description: "Manage this group's bot settings.",
    example: "/settings",
    names: ["settings"],
    run: Effect.fn("settings")(function* (match) {
      const user = match.message.from;
      if (match.message.chat.type === "private") {
        return yield* answer(match.message, "Use /settings inside a group.");
      }
      if (user === undefined || !(yield* canManage(dependencies, match.message.chat.id, user.id))) {
        return yield* answer(match.message, "Only group admins can change settings.");
      }
      const states = yield* settingStates(dependencies, match.message.chat.id);
      return yield* replyBlocks(match.message, settingsBlocks(match.message.chat.id), {
        replyMarkup: keyboard(match.message.chat.id, states),
      });
    }),
    usage: "/settings",
  };
}

function setToggle(dependencies: AppDependencies, chatId: number, key: ToggleKey, enabled: boolean) {
  const toggle = toggleDefinitions.find((candidate) => candidate.key === key);
  if (toggle === undefined) return Effect.die(new Error(`Unknown setting: ${key}`));
  if (toggle.table === "group_settings") {
    return dependencies.database.execute(
      `INSERT INTO group_settings (chat_id, ${toggle.value}) VALUES (?, ?)
       ON CONFLICT(chat_id) DO UPDATE SET ${toggle.value} = excluded.${toggle.value}`,
      [chatId, enabled],
    );
  }
  return enabled
    ? dependencies.database.execute(
        `INSERT OR IGNORE INTO command_whitelist (command, whitelist_type, whitelist_id)
         VALUES (?, 'chat', ?)`,
        [toggle.value, chatId],
      )
    : dependencies.database.execute(
        `DELETE FROM command_whitelist
         WHERE command = ? AND whitelist_type = 'chat' AND whitelist_id = ?`,
        [toggle.value, chatId],
      );
}

export function settingsCallback(dependencies: AppDependencies) {
  return callbackRoute("settings", SettingsCallback, Effect.fn("settingsCallback")(function* ({
    callbackQuery,
    data,
  }) {
    const message = callbackQuery.message;
    if (message === undefined || message.chat.id !== data.chatId) {
      return yield* answerCallback(callbackQuery, { text: "Open settings in this group." });
    }
    if (!(yield* canManage(dependencies, data.chatId, callbackQuery.from.id))) {
      return yield* answerCallback(callbackQuery, {
        text: "Only group admins can change settings.",
      });
    }
    const states = yield* settingStates(dependencies, data.chatId);
    const enabled = !states[data.key];
    yield* setToggle(dependencies, data.chatId, data.key, enabled);
    const next = yield* settingStates(dependencies, data.chatId);
    yield* answerCallback(callbackQuery, {
      text: `${toggleDefinitions.find((toggle) => toggle.key === data.key)?.label}: ${enabled ? "on" : "off"}`,
    });
    const target = callbackTarget(callbackQuery);
    if ("ephemeralMessageId" in target) return;
    yield* ignoreUnchangedMessage(editMessageText({
      ...target,
      richMessage: { blocks: settingsBlocks(data.chatId) },
      replyMarkup: keyboard(data.chatId, next),
    }));
  }));
}

export function settingsCommands(dependencies: AppDependencies): ReadonlyArray<CommandDefinition> {
  return [modelCommand(dependencies), thinkingCommand(dependencies), settingsCommand(dependencies)];
}
