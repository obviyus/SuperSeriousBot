import { Effect, Schema } from "telly";

export class HttpError extends Schema.TaggedError<HttpError>()("HttpError", {
  description: Schema.String,
  service: Schema.String,
}) {}

export interface JsonResponse<A> {
  readonly data: A;
  readonly status: number;
}

export interface TextResponse {
  readonly data: string;
  readonly status: number;
}

export interface BytesResponse {
  readonly contentType?: string;
  readonly data: Uint8Array;
  readonly fileName?: string;
  readonly status: number;
}

export type Fetch = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

function errorDescription(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export class Http {
  constructor(private readonly send: Fetch = fetch) {}

  json<A>(
    service: string,
    url: string | URL,
    schema: Schema.Codec<A, unknown, never, never>,
    init?: RequestInit,
  ): Effect.Effect<JsonResponse<A>, HttpError> {
    return this.request(service, url, init).pipe(
      Effect.flatMap((response) =>
        Effect.tryPromise({
          try: () => response.json(),
          catch: (error) => new HttpError({
            description: errorDescription(error),
            service,
          }),
        }).pipe(
          Effect.flatMap((data) => Schema.decodeUnknownEffect(schema)(data)),
          Effect.mapError((error) => error instanceof HttpError
            ? error
            : new HttpError({ description: error.message, service })),
          Effect.map((data) => ({ data, status: response.status })),
        )
      ),
    );
  }

  text(
    service: string,
    url: string | URL,
    init?: RequestInit,
  ): Effect.Effect<TextResponse, HttpError> {
    return this.request(service, url, init).pipe(
      Effect.flatMap((response) =>
        Effect.tryPromise({
          try: () => response.text(),
          catch: (error) => new HttpError({ description: errorDescription(error), service }),
        }).pipe(Effect.map((data) => ({ data, status: response.status })))
      ),
    );
  }

  bytes(
    service: string,
    url: string | URL,
    maximumBytes: number,
    init?: RequestInit,
  ): Effect.Effect<BytesResponse, HttpError> {
    return this.request(service, url, init).pipe(
      Effect.flatMap((response) => {
        const declared = Number(response.headers.get("content-length"));
        if (Number.isFinite(declared) && declared > maximumBytes) {
          return Effect.fail(new HttpError({ description: "Response is too large", service }));
        }
        return Effect.tryPromise({
          try: () => response.arrayBuffer(),
          catch: (error) => new HttpError({ description: errorDescription(error), service }),
        }).pipe(Effect.flatMap((buffer) => {
          if (buffer.byteLength > maximumBytes) return Effect.fail(new HttpError({
            description: "Response is too large",
            service,
          }));
          const disposition = response.headers.get("content-disposition");
          const fileName = disposition?.match(/filename\*?=(?:UTF-8''|["']?)([^"';]+)/iu)?.[1];
          const contentType = response.headers.get("content-type") ?? undefined;
          return Effect.succeed({
            ...(contentType === undefined ? {} : { contentType }),
            data: new Uint8Array(buffer),
            ...(fileName === undefined ? {} : { fileName: decodeURIComponent(fileName) }),
            status: response.status,
          });
        }));
      }),
    );
  }

  response(
    service: string,
    url: string | URL,
    init?: RequestInit,
  ): Effect.Effect<Response, HttpError> {
    return Effect.tryPromise({
      try: () => this.send(url, { ...init, signal: init?.signal ?? AbortSignal.timeout(60_000) }),
      catch: (error) => new HttpError({ description: errorDescription(error), service }),
    });
  }

  private request(
    service: string,
    url: string | URL,
    init?: RequestInit,
  ): Effect.Effect<Response, HttpError> {
    return this.response(service, url, init);
  }
}
