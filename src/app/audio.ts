import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { Effect, Schema } from "telly";

export class AudioConversionError extends Schema.TaggedError<AudioConversionError>()(
  "AudioConversionError",
  { description: Schema.String },
) {}

export function transcodeToWav(bytes: Uint8Array, suffix: string) {
  return Effect.tryPromise({
    try: async () => {
      const directory = await mkdtemp(join(tmpdir(), "superseriousbot-audio-"));
      const source = join(directory, `source${suffix}`);
      const destination = join(directory, "audio.wav");
      try {
        await writeFile(source, bytes);
        const process = Bun.spawn([
          "ffmpeg",
          "-y",
          "-i",
          source,
          "-ac",
          "1",
          "-ar",
          "16000",
          destination,
        ], { stderr: "pipe", stdout: "ignore" });
        const status = await process.exited;
        if (status !== 0) {
          throw new Error(`ffmpeg exited with status ${status}`);
        }
        return new Uint8Array(await readFile(destination));
      } finally {
        await rm(directory, { force: true, recursive: true });
      }
    },
    catch: (error) => new AudioConversionError({
      description: error instanceof Error ? error.message : String(error),
    }),
  });
}
