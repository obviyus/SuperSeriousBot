import { defineBot, every } from "telly";

import {
  answer,
  botCommands,
  commandHandlers,
  type CommandDefinition,
} from "./app/command.ts";
import type { AppDependencies } from "./app/dependencies.ts";
import { basicCommands } from "./features/basic.ts";
import { informationCommands } from "./features/information.ts";
import { moderationCommands } from "./features/moderation.ts";
import { statsCommands } from "./features/stats.ts";
import { storageCommands } from "./features/storage.ts";
import { trackingHandler } from "./features/tracking.ts";

export function createSuperSeriousBot(dependencies: AppDependencies) {
  const featureCommands = [
    ...basicCommands(dependencies),
    ...informationCommands(dependencies),
    ...moderationCommands(dependencies),
    ...statsCommands(dependencies),
    ...storageCommands(dependencies),
  ];
  const help: CommandDefinition = {
    description: "Show every enabled command.",
    example: "/help",
    names: ["help"],
    run: ({ message }) => answer(message, featureCommands.map((definition) =>
      `/${definition.names[0]} — ${definition.description}`
    ).join("\n")),
    usage: "/help",
  };
  const definitions = [help, ...featureCommands];
  return {
    commands: botCommands(definitions, dependencies),
    definitions,
    handler: every(
      defineBot({ commands: commandHandlers(definitions, dependencies) }),
      trackingHandler(dependencies),
    ),
  };
}
