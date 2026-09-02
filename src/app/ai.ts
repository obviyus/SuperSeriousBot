import { createOpenRouter, type OpenRouterProvider } from "@openrouter/ai-sdk-provider";
import {
  APICallError,
  embedMany,
  experimental_generateVideo as generateVideo,
  generateImage,
  generateText,
  Output,
  streamText,
  type ModelMessage,
} from "ai";
import { Effect, Schema } from "telly";

import type { AppDependencies } from "./dependencies.ts";
import { imageDataUrl, type ImageData } from "./media.ts";
import {
  type ModelCommand,
  getModel,
  getThinking,
  normalizeModelName,
} from "../features/settings.ts";

export type AiMessage = ModelMessage;

export class AiError extends Schema.TaggedError<AiError>()("AiError", {
  description: Schema.String,
  operation: Schema.String,
}) {}

interface GenerateOptions {
  readonly extraBody?: Readonly<Record<string, unknown>>;
  readonly maxTokens?: number;
  readonly model?: string;
  readonly temperature?: number;
}

export interface AiStream {
  readonly abort: () => void;
  readonly next: () => Promise<IteratorResult<string>>;
}

const ReasoningLevelSchema = Schema.Literals(["none", "minimal", "low", "medium", "high"]);
type ReasoningLevel = typeof ReasoningLevelSchema.Type;

function description(error: unknown): string {
  if (
    APICallError.isInstance(error) &&
    error.responseBody?.includes("Generated image rejected by content moderation") === true
  ) return "moderation";
  if (APICallError.isInstance(error) && error.responseBody !== undefined) {
    return error.responseBody;
  }
  return error instanceof Error ? error.message : String(error);
}

function failure(operation: string, error: unknown): AiError {
  return error instanceof AiError
    ? error
    : new AiError({ description: description(error), operation });
}

function standardSchema<A>(
  schema: Schema.Codec<A, unknown, never, never>,
) {
  return Schema.toStandardJSONSchemaV1(Schema.toStandardSchemaV1(schema));
}

function prompt(messages: ReadonlyArray<AiMessage>) {
  const instructions = messages.flatMap((message) => message.role === "system"
    ? [message.content]
    : []).join("\n\n");
  const modelMessages = messages.filter((message) => message.role !== "system");
  return {
    ...(instructions.length === 0 ? {} : { instructions }),
    messages: modelMessages,
  };
}

export class Ai {
  private readonly openrouter: OpenRouterProvider | undefined;

  constructor(private readonly dependencies: AppDependencies) {
    const apiKey = dependencies.config.api.openrouterApiKey;
    const providerFetch = Object.assign(
      (input: RequestInfo | URL, init?: RequestInit) => dependencies.http.fetch(input, init),
      { preconnect: globalThis.fetch.preconnect },
    );
    this.openrouter = apiKey === undefined
      ? undefined
      : createOpenRouter({
          apiKey,
          appName: "SuperSeriousBot",
          appUrl: "https://superserio.us",
          ...(dependencies.config.api.openrouterBaseUrl === undefined
            ? {}
            : { baseURL: dependencies.config.api.openrouterBaseUrl }),
          compatibility: "strict",
          fetch: providerFetch,
        });
  }

  complete(
    command: ModelCommand,
    messages: ReadonlyArray<AiMessage>,
    options: GenerateOptions = {},
  ) {
    return this.settings(command, options).pipe(
      Effect.flatMap(({ model, reasoning }) => Effect.tryPromise({
        try: (signal) => generateText({
          abortSignal: signal,
          ...(options.maxTokens === undefined ? {} : { maxOutputTokens: options.maxTokens }),
          ...prompt(messages),
          model: this.languageModel(command, model, options, reasoning),
          ...(options.temperature === undefined ? {} : { temperature: options.temperature }),
        }),
        catch: (error) => failure("complete", error),
      })),
      Effect.map((result) => result.text),
    );
  }

  object<A>(
    command: ModelCommand,
    messages: ReadonlyArray<AiMessage>,
    schema: Schema.Codec<A, unknown, never, never>,
    options: GenerateOptions = {},
  ) {
    return this.settings(command, options).pipe(
      Effect.flatMap(({ model, reasoning }) => Effect.tryPromise({
        try: (signal) => generateText({
          abortSignal: signal,
          ...(options.maxTokens === undefined ? {} : { maxOutputTokens: options.maxTokens }),
          ...prompt(messages),
          model: this.languageModel(command, model, options, reasoning),
          output: Output.object({
            name: `${command}_response`,
            schema: standardSchema(schema),
          }),
          ...(options.temperature === undefined ? {} : { temperature: options.temperature }),
        }),
        catch: (error) => failure("object", error),
      })),
      Effect.map((result) => result.output),
    );
  }

  stream(
    command: ModelCommand,
    messages: ReadonlyArray<AiMessage>,
    options: GenerateOptions = {},
  ) {
    return this.settings(command, options).pipe(
      Effect.flatMap(({ model, reasoning }) => Effect.try({
        try: (): AiStream => {
          const controller = new AbortController();
          let streamFailure: { readonly error: unknown } | undefined;
          const result = streamText({
            abortSignal: controller.signal,
            ...(options.maxTokens === undefined ? {} : { maxOutputTokens: options.maxTokens }),
            ...prompt(messages),
            model: this.languageModel(command, model, options, reasoning),
            onError: ({ error }) => {
              streamFailure = { error };
            },
            ...(options.temperature === undefined ? {} : { temperature: options.temperature }),
          });
          const iterator = result.textStream[Symbol.asyncIterator]();
          return {
            abort: () => {
              controller.abort();
              void iterator.return?.();
            },
            next: async () => {
              const next = await iterator.next();
              if (next.done && streamFailure !== undefined) throw streamFailure.error;
              return next;
            },
          };
        },
        catch: (error) => failure("stream", error),
      })),
    );
  }

  image(prompt: string, source?: ImageData) {
    return getModel(this.dependencies, "edit").pipe(
      Effect.flatMap((model) => Effect.tryPromise({
        try: (signal) => generateImage({
          abortSignal: signal,
          model: this.provider().imageModel(normalizeModelName(model)),
          prompt: source === undefined
            ? `Please generate an image according to the following description: ${prompt}`
            : {
                images: [imageDataUrl(source)],
                text: `Please edit this image according to the following description: ${prompt}`,
              },
        }),
        catch: (error) => failure("image", error),
      })),
      Effect.map((result) => result.image.uint8Array),
    );
  }

  video(
    prompt: string,
    options: {
      readonly aspectRatio: `${number}:${number}`;
      readonly firstFrame?: string;
    },
  ) {
    return Effect.tryPromise({
      try: (signal) => generateVideo({
        abortSignal: signal,
        aspectRatio: options.aspectRatio,
        download: ({ url, abortSignal }) => this.downloadVideo(url, abortSignal),
        duration: 5,
        model: this.provider().videoModel("bytedance/seedance-2.0-mini", {
          extraBody: { resolution: "480p" },
          generateAudio: true,
          maxPollTimeMs: 15 * 60_000,
        }),
        prompt: options.firstFrame === undefined
          ? prompt
          : { image: options.firstFrame, text: prompt },
      }),
      catch: (error) => failure("video", error),
    }).pipe(Effect.map((result) => result.video.uint8Array));
  }

  embeddings(inputs: ReadonlyArray<string>, dimensions: number) {
    return Effect.tryPromise({
      try: (signal) => embedMany({
        abortSignal: signal,
        model: this.provider().textEmbeddingModel("qwen/qwen3-embedding-8b", {
          extraBody: { dimensions },
          provider: { sort: "latency" },
        }),
        values: [...inputs],
      }),
      catch: (error) => failure("embeddings", error),
    }).pipe(
      Effect.flatMap(({ embeddings }) =>
        embeddings.length === inputs.length && embeddings.every((item) =>
            item.length === dimensions)
          ? Effect.succeed(embeddings)
          : Effect.fail(new AiError({
              description: "OpenRouter returned invalid embedding dimensions",
              operation: "embeddings",
            }))
      ),
    );
  }

  private languageModel(
    command: ModelCommand,
    model: string,
    options: GenerateOptions,
    reasoning: ReasoningLevel,
  ) {
    const id = normalizeModelName(model);
    return this.provider()(id, {
      ...(options.extraBody === undefined ? {} : { extraBody: { ...options.extraBody } }),
      ...(command === "ask" && id.startsWith("x-ai/")
        ? { plugins: [{ engine: "native" as const, id: "web" as const, max_results: 20 }] }
        : {}),
      ...(command === "ask" && reasoning !== "none"
        ? { reasoning: { effort: reasoning } }
        : {}),
    });
  }

  private async downloadVideo(
    url: URL,
    abortSignal?: AbortSignal,
  ): Promise<{ readonly data: Uint8Array; readonly mediaType: string | undefined }> {
    const response = await this.dependencies.http.fetch(
      url,
      abortSignal === undefined ? {} : { signal: abortSignal },
    );
    if (!response.ok) throw new Error(`Video download failed with status ${response.status}`);
    const maximumBytes = 50 * 1_024 * 1_024;
    const declared = Number(response.headers.get("content-length"));
    if (Number.isFinite(declared) && declared > maximumBytes) {
      throw new Error("Generated video is too large");
    }
    const buffer = await response.arrayBuffer();
    if (buffer.byteLength > maximumBytes) throw new Error("Generated video is too large");
    return {
      data: new Uint8Array(buffer),
      mediaType: response.headers.get("content-type") ?? undefined,
    };
  }

  private provider(): OpenRouterProvider {
    if (this.openrouter === undefined) {
      throw new AiError({
        description: "OpenRouter is not configured",
        operation: "configure",
      });
    }
    return this.openrouter;
  }

  private settings(command: ModelCommand, options: GenerateOptions) {
    return Effect.all({
      model: options.model === undefined
        ? getModel(this.dependencies, command)
        : Effect.succeed(options.model),
      thinking: command === "ask" ? getThinking(this.dependencies) : Effect.succeed("none"),
    }).pipe(
      Effect.flatMap(({ model, thinking }) =>
        Schema.decodeUnknownEffect(ReasoningLevelSchema)(thinking).pipe(
          Effect.map((reasoning) => ({ model, reasoning })),
          Effect.mapError((error) => new AiError({
            description: error.message,
            operation: "configure",
          })),
        )
      ),
    );
  }
}

export function streamChunk(stream: AiStream) {
  return Effect.tryPromise({
    try: (signal) => {
      const abort = () => stream.abort();
      signal.addEventListener("abort", abort, { once: true });
      return stream.next().finally(() => signal.removeEventListener("abort", abort));
    },
    catch: (error) => failure("stream", error),
  });
}
