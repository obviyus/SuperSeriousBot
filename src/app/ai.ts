import { createOpenRouter, type OpenRouterProvider } from "@openrouter/ai-sdk-provider";
import {
  APICallError,
  embedMany,
  experimental_generateVideo as generateVideo,
  generateImage,
  generateText,
  Output,
  streamText,
  type LanguageModel,
  type ModelMessage,
} from "ai";
import { Effect, Schema } from "telly";

import type { AppDependencies } from "./dependencies.ts";
import type { HttpError } from "./http.ts";
import { imageDataUrl, type ImageData } from "./media.ts";
import {
  type ModelCommand,
  getModel,
  getBasedModel,
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
}

export type AiStreamChunk =
  | { readonly type: "reasoning"; readonly text: string }
  | { readonly type: "text"; readonly text: string };

export interface AiStream {
  readonly abort: () => void;
  readonly next: () => Promise<IteratorResult<AiStreamChunk>>;
}

function record(value: unknown): Readonly<Record<string, unknown>> | undefined {
  return typeof value === "object" && value !== null
    ? value as Readonly<Record<string, unknown>>
    : undefined;
}

// OpenRouter flattens multi-message output into one text part and the provider
// drops reasoning that follows text. Read reasoning from the raw delta instead,
// so callers can see when the model went back to thinking mid-answer.
function rawReasoning(value: unknown): string | undefined {
  const choices = record(value)?.["choices"];
  const delta = record(Array.isArray(choices) ? record(choices[0])?.["delta"] : undefined);
  // Signatures that ride along with answer text are not a return to thinking.
  if (delta === undefined || (typeof delta["content"] === "string" && delta["content"].length > 0)) {
    return undefined;
  }
  const details = delta["reasoning_details"];
  if (Array.isArray(details) && details.length > 0) {
    return details.map((detail) => {
      const item = record(detail);
      const text = item?.["type"] === "reasoning.summary" ? item["summary"] : item?.["text"];
      return typeof text === "string" ? text : "";
    }).join("");
  }
  const reasoning = delta["reasoning"];
  return typeof reasoning === "string" && reasoning.length > 0 ? reasoning : undefined;
}

const ReasoningLevelSchema = Schema.Literals(["none", "minimal", "low", "medium", "high"]);
type ReasoningLevel = typeof ReasoningLevelSchema.Type;

// NanoGPT rejects reasoning_effort values a model does not list, so /based asks for "high"
// when the catalog advertises it and otherwise the nearest effort, preferring lower ones.
const nanoGptDefaultEffort = "high";
const nanoGptEffortPreference = ["high", "medium", "low", "minimal", "none", "xhigh", "max"];
const nanoGptCatalogTtlMs = 60 * 60_000;
const NanoGptCatalog = Schema.Struct({
  data: Schema.Array(Schema.Struct({
    id: Schema.String,
    reasoning_efforts: Schema.optionalKey(Schema.Array(Schema.String)),
  })),
});

interface NanoGptEfforts {
  readonly fetchedAt: number;
  readonly models: ReadonlyMap<string, ReadonlyArray<string>>;
}

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
  private readonly based: OpenRouterProvider | undefined;
  private readonly openrouter: OpenRouterProvider | undefined;
  private nanoGptEfforts: NanoGptEfforts | undefined;

  constructor(private readonly dependencies: AppDependencies) {
    const apiKey = dependencies.config.api.openrouterApiKey;
    const providerFetch = Object.assign(
      (input: RequestInfo | URL, init?: RequestInit) => dependencies.http.fetch(input, init),
      { preconnect: globalThis.fetch.preconnect },
    );
    const based = dependencies.config.api.based;
    this.based = based === undefined ? undefined : createOpenRouter({
      apiKey: based.apiKey ?? "local-only",
      baseURL: based.baseUrl,
      compatibility: "strict",
      fetch: providerFetch,
    });
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
        }),
        catch: (error) => failure("object", error),
      })),
      Effect.map((result) => result.output),
    );
  }

  stream(
    command: ModelCommand | "based",
    messages: ReadonlyArray<AiMessage>,
    options: GenerateOptions = {},
  ) {
    const based = this.based;
    const basedConfig = this.dependencies.config.api.based;
    const model = command === "based"
      ? based === undefined || basedConfig === undefined
        ? Effect.fail(new AiError({ description: "Based provider is not configured", operation: "configure" }))
        : getBasedModel(this.dependencies, basedConfig.model).pipe(
            Effect.flatMap((id) => basedConfig.provider === "nanogpt"
              ? this.nanoGptReasoningEffort(basedConfig.baseUrl, id).pipe(
                  Effect.map((effort): LanguageModel => based.chat(id, {
                    extraBody: effort === undefined ? {} : { reasoning_effort: effort },
                  })),
                )
              : Effect.succeed<LanguageModel>(based.chat(id, {
                  extraBody: { chat_template_kwargs: { enable_thinking: false } },
                }))),
          )
      : this.settings(command, options).pipe(
          Effect.flatMap(({ model, reasoning }) => Effect.try({
            try: () => this.languageModel(command, model, options, reasoning),
            catch: (error) => failure("stream", error),
          })),
        );
    return model.pipe(
      Effect.flatMap((model) => Effect.try({
        try: (): AiStream => {
          const controller = new AbortController();
          const abortSignal = command === "based"
            ? AbortSignal.any([controller.signal, AbortSignal.timeout(120_000)])
            : controller.signal;
          let streamFailure: { readonly error: unknown } | undefined;
          const result = streamText({
            abortSignal,
            includeRawChunks: true,
            ...(command === "based" ? { maxOutputTokens: 1_024, maxRetries: 0 } : {}),
            ...(options.maxTokens === undefined ? {} : { maxOutputTokens: options.maxTokens }),
            ...prompt(messages),
            model,
            onError: ({ error }) => {
              streamFailure = { error };
            },
          });
          const iterator = (async function* (): AsyncGenerator<AiStreamChunk> {
            for await (const part of result.fullStream) {
              if (part.type === "text-delta") {
                if (part.text.length > 0) yield { text: part.text, type: "text" };
              } else if (part.type === "raw") {
                const text = rawReasoning(part.rawValue);
                if (text !== undefined) yield { text, type: "reasoning" };
              }
            }
          })();
          return {
            abort: () => {
              controller.abort();
              void iterator.return(undefined);
            },
            next: async () => {
              const next = await iterator.next();
              if (next.done && streamFailure !== undefined) throw streamFailure.error;
              if (next.done && command === "based") abortSignal.throwIfAborted();
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
    return getModel(this.dependencies, "video").pipe(
      Effect.flatMap((model) => Effect.tryPromise({
        try: (signal) => generateVideo({
          abortSignal: signal,
          aspectRatio: options.aspectRatio,
          download: ({ url, abortSignal }) => this.downloadVideo(url, abortSignal),
          duration: 5,
          model: this.provider().videoModel(normalizeModelName(model), {
            extraBody: { resolution: "480p" },
            generateAudio: true,
            maxPollTimeMs: 15 * 60_000,
          }),
          prompt: options.firstFrame === undefined
            ? prompt
            : { image: options.firstFrame, text: prompt },
        }),
        catch: (error) => failure("video", error),
      })),
      Effect.map((result) => result.video.uint8Array),
      Effect.mapError((error) => failure("video", error)),
    );
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
  ): LanguageModel {
    const id = normalizeModelName(model);
    return this.provider()(id, {
      ...(options.extraBody === undefined ? {} : { extraBody: { ...options.extraBody } }),
      ...(command === "ask"
        ? { plugins: [{ id: "web" as const, max_results: 20 }] }
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

  private nanoGptReasoningEffort(
    baseUrl: string,
    model: string,
  ): Effect.Effect<string | undefined> {
    const cached = this.nanoGptEfforts;
    const catalog: Effect.Effect<ReadonlyMap<string, ReadonlyArray<string>>, HttpError> = cached !== undefined &&
        this.dependencies.monotonicMilliseconds() - cached.fetchedAt < nanoGptCatalogTtlMs
      ? Effect.succeed(cached.models)
      : this.dependencies.http.json(
          "nano-gpt-models",
          `${baseUrl}/models?detailed=true`,
          NanoGptCatalog,
          { signal: AbortSignal.timeout(10_000) },
        ).pipe(
          Effect.map(({ data }) => {
            const models = new Map(data.data.flatMap((entry) => entry.reasoning_efforts === undefined
              ? []
              : [[entry.id, entry.reasoning_efforts] as const]));
            this.nanoGptEfforts = { fetchedAt: this.dependencies.monotonicMilliseconds(), models };
            return models;
          }),
        );
    return catalog.pipe(
      Effect.map((models) => {
        const supported = models.get(model);
        return supported === undefined
          ? undefined
          : nanoGptEffortPreference.find((effort) => supported.includes(effort));
      }),
      Effect.catch((error) => Effect.logWarning("NanoGPT reasoning lookup failed").pipe(
        Effect.annotateLogs({ error: error.description }),
        Effect.as<string | undefined>(nanoGptDefaultEffort),
      )),
    );
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
