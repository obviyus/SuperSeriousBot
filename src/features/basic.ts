import {
  editMessageText,
  Effect,
  respondTo,
  Schema,
  sendAnimation,
  sendMessage,
  sendPhoto,
} from "telly";

import { answer, type CommandDefinition } from "../app/command.ts";
import type { AppDependencies } from "../app/dependencies.ts";

const DogResponse = Schema.Struct({ message: Schema.String });
const FoxResponse = Schema.Struct({ image: Schema.String });
const CatResponse = Schema.Array(Schema.Struct({ url: Schema.String }));
const JokeResponse = Schema.Struct({
  delivery: Schema.optionalKey(Schema.String),
  setup: Schema.optionalKey(Schema.String),
});
const MemeResponse = Schema.Struct({
  nsfw: Schema.optionalKey(Schema.Boolean),
  url: Schema.optionalKey(Schema.String),
});
const InsultResponse = Schema.Struct({ insult: Schema.optionalKey(Schema.String) });

function animalCommand(dependencies: AppDependencies): CommandDefinition {
  return {
    description: "Get a random image of the selected animal.",
    example: "/fox, /shiba, /cat",
    names: ["fox", "shiba", "cat"],
    run: Effect.fn("animal")(function* (match) {
      const imageUrl = yield* (() => {
        switch (match.command) {
          case "shiba":
            return dependencies.http.json(
              "dog.ceo",
              "https://dog.ceo/api/breed/shiba/images/random",
              DogResponse,
            ).pipe(Effect.map((response) => response.data.message));
          case "fox":
            return dependencies.http.json(
              "randomfox",
              "https://randomfox.ca/floof/",
              FoxResponse,
            ).pipe(Effect.map((response) => response.data.image));
          case "cat":
            return dependencies.http.json(
              "thecatapi",
              "https://api.thecatapi.com/v1/images/search",
              CatResponse,
            ).pipe(Effect.flatMap((response) => {
              const first = response.data[0];
              return first === undefined
                ? Effect.fail(new Error("Cat API returned no image"))
                : Effect.succeed(first.url);
            }));
          default:
            return Effect.fail(new Error(`Unknown animal command: ${match.command}`));
        }
      })().pipe(
        Effect.catch(() => answer(
          match.message,
          `Failed to fetch ${match.command} image. Please try again later.`,
        ).pipe(Effect.as(undefined))),
      );
      if (imageUrl === undefined) return;
      yield* sendPhoto({ ...respondTo(match.message), photo: imageUrl });
    }),
    usage: "/fox, /shiba, /cat",
  };
}

export function basicCommands(dependencies: AppDependencies): ReadonlyArray<CommandDefinition> {
  return [
    animalCommand(dependencies),
    {
      description: "Pong.",
      example: "/ping",
      names: ["ping"],
      run: Effect.fn("ping")(function* ({ message }) {
        const start = dependencies.monotonicMilliseconds();
        const probe = yield* answer(message, "⏳ Measuring...");
        const latency = Math.max(0, dependencies.monotonicMilliseconds() - start);
        yield* editMessageText({
          chatId: probe.chat.id,
          messageId: probe.messageId,
          text: `pong (${latency.toFixed(2)}ms)`,
        });
      }),
      usage: "/ping",
    },
    {
      description: "Get a two-part joke.",
      example: "/joke",
      names: ["joke"],
      run: Effect.fn("joke")(function* ({ message }) {
        const joke = yield* dependencies.http.json(
          "jokeapi",
          "https://v2.jokeapi.dev/joke/Any?type=twopart",
          JokeResponse,
        ).pipe(
          Effect.map((response) => response.data),
          Effect.catch(() => Effect.succeed({
            delivery: "(joke delivery unavailable)",
            setup: "Here's a joke...",
          })),
        );
        const setup = joke.setup ?? "Here's a joke...";
        const delivery = (joke.delivery ?? "(joke delivery unavailable)").replace(/[.!?]$/u, "");
        yield* answer(message, setup);
        yield* Effect.sleep("2 seconds");
        yield* sendMessage({ chatId: message.chat.id, text: `${delivery} 😆` });
        if (dependencies.random() < 0.01) {
          yield* Effect.sleep("2 seconds");
          yield* sendMessage({ chatId: message.chat.id, text: "Please don't kick me 👉👈" });
        }
      }),
      usage: "/joke",
    },
    {
      description: "Get a random safe-for-work meme.",
      example: "/meme",
      names: ["meme"],
      run: Effect.fn("meme")(function* ({ message }) {
        let mediaUrl: string | undefined;
        for (let attempt = 0; attempt < 5; attempt += 1) {
          const response = yield* dependencies.http.json(
            "meme-api",
            "https://meme-api.com/gimme",
            MemeResponse,
          ).pipe(Effect.catch(() => Effect.succeed(undefined)));
          if (response === undefined || response.status !== 200) {
            yield* answer(message, "Could not fetch a meme right now.");
            return;
          }
          if (response.data.nsfw === true) continue;
          if (response.data.url !== undefined) {
            mediaUrl = response.data.url;
            break;
          }
        }
        if (mediaUrl === undefined) {
          yield* answer(message, "Could not fetch a safe-for-work meme right now.");
          return;
        }
        if (mediaUrl.toLowerCase().endsWith(".gif")) {
          yield* sendAnimation({ ...respondTo(message), animation: mediaUrl });
          return;
        }
        yield* sendPhoto({ ...respondTo(message), photo: mediaUrl });
      }),
      usage: "/meme",
    },
    {
      description: "Send a random insult. Reply to a person to insult them.",
      example: "/insult",
      names: ["insult"],
      run: Effect.fn("insult")(function* ({ message }) {
        const url = new URL("https://evilinsult.com/generate_insult.php");
        url.search = new URLSearchParams({ lang: "en", type: "json" }).toString();
        const insult = yield* dependencies.http.json(
          "evilinsult",
          url,
          InsultResponse,
        ).pipe(
          Effect.map((response) => response.data.insult ?? "I'm too polite to insult right now."),
          Effect.catch(() => Effect.succeed("I'm too polite to insult right now.")),
        );
        yield* answer(message.replyToMessage ?? message, insult);
      }),
      usage: "/insult",
    },
  ];
}
