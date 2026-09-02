import * as Semaphore from "effect/Semaphore";
import {
  deleteMessage,
  editMessageText,
  Effect,
  Schema,
  sendMediaGroup,
  type InputMediaAudio,
} from "telly";

import { Ai } from "../app/ai.ts";
import {
  answer,
  type CommandDefinition,
  usage,
} from "../app/command.ts";
import type { AppDependencies } from "../app/dependencies.ts";

const SongPlan = Schema.Struct({
  lyricsLines: Schema.Array(Schema.String),
  style: Schema.String,
  title: Schema.String,
});
const CreateTask = Schema.Struct({
  code: Schema.Number,
  data: Schema.Struct({ taskId: Schema.String }),
  msg: Schema.optionalKey(Schema.String),
});
const Track = Schema.Struct({
  audioUrl: Schema.String,
  title: Schema.optionalKey(Schema.String),
});
const TaskStatus = Schema.Struct({
  code: Schema.Number,
  data: Schema.Struct({
    errorMessage: Schema.optionalKey(Schema.String),
    response: Schema.optionalKey(Schema.Struct({ sunoData: Schema.Array(Track) })),
    status: Schema.String,
  }),
  msg: Schema.optionalKey(Schema.String),
});

const songLock = Semaphore.makeUnsafe(1);

function kieHeaders(dependencies: AppDependencies): HeadersInit {
  return {
    authorization: `Bearer ${dependencies.config.api.kieApiKey ?? ""}`,
    "content-type": "application/json",
  };
}

export function songCommand(dependencies: AppDependencies): CommandDefinition {
  const ai = new Ai(dependencies);
  const definition: CommandDefinition = {
    apiKey: "kieApiKey",
    availability: "whitelist",
    dailyLimit: 8,
    description: "Generate two custom songs from a short prompt.",
    example: "/song everyone at the party is secretly a spreadsheet",
    names: ["song"],
    run: Effect.fn("song")(function* (match) {
      if (match.argText.length === 0) return yield* usage(match.message, definition);
      if (dependencies.config.api.openrouterApiKey === undefined) {
        return yield* answer(match.message, "Song generation is not fully configured.");
      }
      const progress = yield* answer(match.message, "Writing banger lyrics...");
      const program = Effect.gen(function* () {
        const plan = yield* ai.object("song", [
          {
            content: "Write finished custom song inputs. Return a title under 80 characters, lyricsLines with one section tag or sung line per item and at most 5000 total characters, and concise style tags under 1000 characters. Preserve the requested language. Avoid artist names and copyrighted titles.",
            role: "system",
          },
          { content: match.argText, role: "user" },
        ], SongPlan, { extraBody: { provider: { require_parameters: true } } });
        const lyrics = plan.lyricsLines.map((line) => line.trim()).filter(Boolean).join("\n");
        if (
          plan.title.trim().length === 0 || plan.title.length > 80 ||
          lyrics.length === 0 || lyrics.length > 5_000 ||
          plan.style.trim().length === 0 || plan.style.length > 1_000
        ) return yield* Effect.die(new Error("OpenRouter returned an invalid song plan"));
        yield* editMessageText({
          chatId: progress.chat.id,
          messageId: progress.messageId,
          text: "Turning lyrics into songs...",
        });
        const created = yield* dependencies.http.json(
          "kie",
          "https://api.kie.ai/api/v1/generate",
          CreateTask,
          {
            body: JSON.stringify({
              callBackUrl: "https://localhost/kie-callback",
              customMode: true,
              instrumental: false,
              model: "V5",
              negativeTags: "rap, spoken word, mumble rap, long dense verses",
              prompt: lyrics,
              style: plan.style.trim(),
              title: plan.title.trim(),
            }),
            headers: kieHeaders(dependencies),
            method: "POST",
          },
        );
        if (created.status !== 200 || created.data.code !== 200) {
          return yield* Effect.die(new Error(created.data.msg ?? "KIE create failed"));
        }
        let tracks: ReadonlyArray<typeof Track.Type> | undefined;
        for (let attempt = 0; attempt < 96; attempt += 1) {
          const url = new URL("https://api.kie.ai/api/v1/generate/record-info");
          url.searchParams.set("taskId", created.data.data.taskId);
          const status = yield* dependencies.http.json("kie", url, TaskStatus, {
            headers: kieHeaders(dependencies),
          });
          if (status.data.data.status === "SUCCESS") {
            tracks = status.data.data.response?.sunoData;
            break;
          }
          if ([
            "CREATE_TASK_FAILED",
            "GENERATE_AUDIO_FAILED",
            "CALLBACK_EXCEPTION",
            "SENSITIVE_WORD_ERROR",
          ].includes(status.data.data.status)) {
            return yield* Effect.die(new Error(status.data.data.errorMessage ?? "KIE failed"));
          }
          yield* Effect.sleep("5 seconds");
        }
        if (tracks === undefined || tracks.length < 2) {
          return yield* Effect.die(new Error("KIE generated fewer than two songs"));
        }
        const media: ReadonlyArray<InputMediaAudio> = tracks.slice(0, 2).map((track) => ({
          caption: track.title ?? plan.title,
          media: track.audioUrl,
          title: track.title ?? plan.title,
          type: "audio",
        }));
        yield* deleteMessage({ chatId: progress.chat.id, messageId: progress.messageId });
        yield* sendMediaGroup({ chatId: match.message.chat.id, media });
      });
      yield* songLock.withPermits(1)(program).pipe(
        Effect.catch(() => editMessageText({
          chatId: progress.chat.id,
          messageId: progress.messageId,
          text: "Song generation failed. Please try again.",
        })),
      );
    }),
    usage: "/song <prompt>",
  };
  return definition;
}
