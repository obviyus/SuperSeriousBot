import {
  answerCallback,
  callbackQuery,
  defineBot,
  every,
  on,
  routes,
} from "telly";

import {
  botCommands,
  commandHandlers,
  type CommandDefinition,
} from "./app/command.ts";
import type { AppDependencies } from "./app/dependencies.ts";
import { replyBlocks, rich } from "./app/rich.ts";
import { basicCommands } from "./features/basic.ts";
import { informationCommands } from "./features/information.ts";
import { moderationCommands } from "./features/moderation.ts";
import { statsCommands } from "./features/stats.ts";
import { storageCommands } from "./features/storage.ts";
import { settingsCallback, settingsCommands } from "./features/settings.ts";
import { summonFeature } from "./features/summon.ts";
import { habitFeature } from "./features/habit.ts";
import { highlightFeature } from "./features/highlight.ts";
import { reminderFeature } from "./features/reminders.ts";
import { trackingHandler } from "./features/tracking.ts";
import { askCommands } from "./features/ask.ts";
import { contentCommands } from "./features/content.ts";
import { catalogCommands } from "./features/catalog.ts";
import { reactionHandler, sedHandler } from "./features/passive.ts";
import { downloadFeature } from "./features/download.ts";
import { cronFeature } from "./features/cron.ts";
import { songCommand } from "./features/song.ts";
import { videoCommand } from "./features/video.ts";
import { footballFeature } from "./features/football.ts";
import { searchFeature } from "./features/search.ts";

export function createSuperSeriousBot(dependencies: AppDependencies) {
  const summon = summonFeature(dependencies);
  const habit = habitFeature(dependencies);
  const highlight = highlightFeature(dependencies);
  const reminders = reminderFeature(dependencies);
  const downloads = downloadFeature(dependencies);
  const cron = cronFeature(dependencies);
  const football = footballFeature(dependencies);
  const search = searchFeature(dependencies);
  const featureCommands = [
    ...basicCommands(dependencies),
    ...informationCommands(dependencies),
    ...moderationCommands(dependencies),
    ...statsCommands(dependencies),
    ...storageCommands(dependencies),
    ...settingsCommands(dependencies),
    ...summon.commands,
    ...habit.commands,
    ...highlight.commands,
    ...reminders.commands,
    ...askCommands(dependencies),
    ...contentCommands(dependencies),
    ...catalogCommands(dependencies),
    ...downloads.commands,
    ...cron.commands,
    songCommand(dependencies),
    videoCommand(dependencies),
    ...football.commands,
    ...search.commands,
  ];
  const help: CommandDefinition = {
    description: "Show every enabled command.",
    example: "/help",
    names: ["help"],
    run: ({ message }) => replyBlocks(message, [
      rich.heading("📺 SuperSeriousBot commands"),
      rich.list(botCommands(featureCommands, dependencies).map((command) => [
        rich.command(`/${command.command}`),
        ` — ${command.description}`,
      ])),
      rich.footer("Only commands enabled by this bot's current integrations are shown."),
    ]),
    usage: "/help",
  };
  const definitions = [help, ...featureCommands];
  return {
    commands: botCommands(definitions, dependencies),
    definitions,
    handler: every(
      defineBot({ commands: commandHandlers(definitions, dependencies) }),
      routes(
        settingsCallback(dependencies),
        summon.callback,
        habit.callback,
        highlight.callback,
        cron.callback,
        football.callback,
        on(callbackQuery(), ({ callbackQuery: query }) =>
          answerCallback(query, { text: "This button expired." })),
      ),
      sedHandler,
      reactionHandler(dependencies),
      trackingHandler(dependencies),
      highlight.handler,
      downloads.handler,
    ),
    workers: {
      cron: cron.worker,
      football: football.workers,
      habit: habit.worker,
      reminders: reminders.worker,
      search: search.workers,
    },
  };
}
