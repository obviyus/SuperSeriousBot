import { Effect, Schema } from "telly";

import type { AppDependencies } from "./dependencies.ts";
import { type ModelCommand, getModel, getThinking, normalizeModelName } from "../features/settings.ts";

export type AiMessage = {
  readonly content: string | ReadonlyArray<
    | { readonly text: string; readonly type: "text" }
    | { readonly image_url: { readonly url: string }; readonly type: "image_url" }
    | {
      readonly input_audio: { readonly data: string; readonly format: string };
      readonly type: "input_audio";
    }
  >;
  readonly role: "assistant" | "system" | "user";
};

export class AiError extends Schema.TaggedError<AiError>()("AiError", {
  description: Schema.String,
  operation: Schema.String,
}) {}

const CompletionResponse = Schema.Struct({
  choices: Schema.Array(Schema.Struct({
    message: Schema.Struct({ content: Schema.String }),
  })),
});
const StreamResponse = Schema.Struct({
  choices: Schema.Array(Schema.Struct({
    delta: Schema.Struct({ content: Schema.optionalKey(Schema.String) }),
  })),
});
const ImageResponse = Schema.Struct({
  data: Schema.Array(Schema.Struct({ b64_json: Schema.String })),
});
const EmbeddingResponse = Schema.Struct({
  data: Schema.Array(Schema.Struct({ embedding: Schema.Array(Schema.Number) })),
});

interface GenerateOptions {
  readonly extraBody?: Readonly<Record<string, unknown>>;
  readonly maxTokens?: number;
  readonly model?: string;
  readonly temperature?: number;
}

function description(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function apiKey(dependencies: AppDependencies): string {
  const value = dependencies.config.api.openrouterApiKey;
  if (value === undefined) throw new AiError({
    description: "OpenRouter is not configured",
    operation: "configure",
  });
  return value;
}

function headers(dependencies: AppDependencies): HeadersInit {
  return {
    authorization: `Bearer ${apiKey(dependencies)}`,
    "content-type": "application/json",
    "http-referer": "https://superserio.us",
    "x-title": "SuperSeriousBot",
  };
}

function firstContent(response: typeof CompletionResponse.Type): string {
  const content = response.choices[0]?.message.content;
  if (content === undefined) throw new AiError({
    description: "OpenRouter returned no content",
    operation: "complete",
  });
  return content;
}

export class Ai {
  constructor(private readonly dependencies: AppDependencies) {}

  complete(
    command: ModelCommand,
    messages: ReadonlyArray<AiMessage>,
    options: GenerateOptions = {},
  ): Effect.Effect<string, AiError | import("./database.ts").DatabaseError> {
    return this.body(command, messages, options).pipe(
      Effect.flatMap((body) => this.dependencies.http.json(
        "openrouter",
        "https://openrouter.ai/api/v1/chat/completions",
        CompletionResponse,
        { body: JSON.stringify(body), headers: headers(this.dependencies), method: "POST" },
      )),
      Effect.flatMap((response) => response.status >= 200 && response.status < 300
        ? Effect.try({
            try: () => firstContent(response.data),
            catch: (error) => error instanceof AiError
              ? error
              : new AiError({ description: description(error), operation: "complete" }),
          })
        : Effect.fail(new AiError({
            description: `OpenRouter rejected the request with status ${response.status}`,
            operation: "complete",
          }))),
      Effect.mapError((error) => error._tag === "DatabaseError"
        ? error
        : error instanceof AiError
        ? error
        : new AiError({ description: error.description, operation: "complete" })),
    );
  }

  object<A>(
    command: ModelCommand,
    messages: ReadonlyArray<AiMessage>,
    schema: Schema.Codec<A, unknown, never, never>,
    options: GenerateOptions = {},
  ) {
    const document = Schema.toJsonSchemaDocument(schema);
    return this.complete(command, messages, {
      ...options,
      extraBody: {
        ...options.extraBody,
        response_format: {
          json_schema: { name: `${command}_response`, schema: document, strict: true },
          type: "json_schema",
        },
      },
    }).pipe(
      Effect.flatMap((content) => Effect.try({
        try: () => JSON.parse(content),
        catch: (error) => new AiError({ description: description(error), operation: "decode" }),
      })),
      Effect.flatMap((value) => Schema.decodeUnknownEffect(schema)(value)),
      Effect.mapError((error) => error instanceof AiError || error._tag === "DatabaseError"
        ? error
        : new AiError({ description: error.message, operation: "decode" })),
    );
  }

  stream(
    command: ModelCommand,
    messages: ReadonlyArray<AiMessage>,
    options: GenerateOptions = {},
  ) {
    return this.body(command, messages, options).pipe(
      Effect.flatMap((body) => this.dependencies.http.response(
        "openrouter",
        "https://openrouter.ai/api/v1/chat/completions",
        {
          body: JSON.stringify({ ...body, stream: true }),
          headers: headers(this.dependencies),
          method: "POST",
        },
      )),
      Effect.flatMap((response) => {
        if (!response.ok || response.body === null) return Effect.fail(new AiError({
          description: `OpenRouter stream failed with status ${response.status}`,
          operation: "stream",
        }));
        return Effect.succeed(readStream(response.body));
      }),
      Effect.mapError((error) => error._tag === "DatabaseError"
        ? error
        : error instanceof AiError
        ? error
        : new AiError({ description: error.description, operation: "stream" })),
    );
  }

  image(prompt: string, sourceImage?: string) {
    return getModel(this.dependencies, "edit").pipe(
      Effect.flatMap((model) => this.dependencies.http.response(
        "openrouter-images",
        "https://openrouter.ai/api/v1/images",
        {
          body: JSON.stringify({
            ...(sourceImage === undefined
              ? {}
              : { input_references: [{ image_url: { url: sourceImage }, type: "image_url" }] }),
            model: normalizeModelName(model),
            prompt: sourceImage === undefined
              ? `Please generate an image according to the following description: ${prompt}`
              : `Please edit this image according to the following description: ${prompt}`,
          }),
          headers: headers(this.dependencies),
          method: "POST",
        },
      )),
      Effect.flatMap((response) => Effect.tryPromise({
        try: () => response.text(),
        catch: (error) => new AiError({ description: description(error), operation: "image" }),
      }).pipe(Effect.flatMap((body) => {
        if (!response.ok) return Effect.fail(new AiError({
          description: body.includes("Generated image rejected by content moderation")
            ? "moderation"
            : `OpenRouter image failed with status ${response.status}`,
          operation: "image",
        }));
        return Effect.try({
          try: () => {
            const parsed = Schema.decodeUnknownSync(ImageResponse)(JSON.parse(body));
            const encoded = parsed.data[0]?.b64_json;
            if (encoded === undefined) throw new Error("OpenRouter returned no image");
            return Uint8Array.from(Buffer.from(encoded, "base64"));
          },
          catch: (error) => new AiError({ description: description(error), operation: "image" }),
        });
      }))),
      Effect.mapError((error) => error._tag === "DatabaseError" || error instanceof AiError
        ? error
        : new AiError({ description: error.description, operation: "image" })),
    );
  }

  embeddings(inputs: ReadonlyArray<string>, dimensions: number) {
    return this.dependencies.http.json(
      "openrouter-embeddings",
      "https://openrouter.ai/api/v1/embeddings",
      EmbeddingResponse,
      {
        body: JSON.stringify({
          dimensions,
          input: inputs,
          model: "qwen/qwen3-embedding-8b",
          provider: { sort: "latency" },
        }),
        headers: headers(this.dependencies),
        method: "POST",
      },
    ).pipe(
      Effect.flatMap((response) => {
        const embeddings = response.data.data.map((item) => item.embedding);
        return embeddings.length === inputs.length && embeddings.every((item) =>
          item.length === dimensions)
          ? Effect.succeed(embeddings)
          : Effect.fail(new AiError({
              description: "OpenRouter returned invalid embedding dimensions",
              operation: "embeddings",
            }));
      }),
      Effect.mapError((error) => error instanceof AiError
        ? error
        : new AiError({ description: error.description, operation: "embeddings" })),
    );
  }

  private body(
    command: ModelCommand,
    messages: ReadonlyArray<AiMessage>,
    options: GenerateOptions,
  ) {
    return Effect.all({
      model: options.model === undefined
        ? getModel(this.dependencies, command)
        : Effect.succeed(options.model),
      thinking: command === "ask" ? getThinking(this.dependencies) : Effect.succeed("none"),
    }).pipe(Effect.map(({ model, thinking }) => ({
      ...options.extraBody,
      messages,
      model: normalizeModelName(model),
      ...(options.maxTokens === undefined ? {} : { max_tokens: options.maxTokens }),
      ...(options.temperature === undefined ? {} : { temperature: options.temperature }),
      ...(command === "ask" && normalizeModelName(model).startsWith("x-ai/")
        ? {
            tools: [{
              parameters: { engine: "native", max_total_results: 20 },
              type: "openrouter:web_search",
            }],
          }
        : {}),
      ...(command === "ask" && thinking !== "none"
        ? { reasoning: { effort: thinking } }
        : {}),
    })));
  }
}

async function* readStream(body: ReadableStream<Uint8Array>): AsyncGenerator<string> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  try {
    while (true) {
      const next = await reader.read();
      pending += decoder.decode(next.value, { stream: !next.done });
      const events = pending.split("\n\n");
      pending = events.pop() ?? "";
      for (const event of events) {
        for (const line of event.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6);
          if (data === "[DONE]") return;
          const decoded = Schema.decodeUnknownSync(StreamResponse)(JSON.parse(data));
          const content = decoded.choices[0]?.delta.content;
          if (content !== undefined) yield content;
        }
      }
      if (next.done) return;
    }
  } finally {
    reader.releaseLock();
  }
}

export function streamChunk(stream: AsyncGenerator<string>) {
  return Effect.tryPromise({
    try: () => stream.next(),
    catch: (error) => new AiError({ description: description(error), operation: "stream" }),
  });
}
