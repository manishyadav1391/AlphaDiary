/**
 * The one place the browser talks to the API.
 *
 * Requests go to `/api/v1/...` on this origin and are rewritten to the
 * FastAPI container (see next.config.ts), which mirrors the Caddy setup in
 * SRS 11.1. Same-origin is what lets the HttpOnly session cookie ride along;
 * calling the API's own host directly would be cross-site and drop it.
 */

import type { ApiErrorBody } from "@/lib/types";

export const API_PREFIX = "/api/v1";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** The session is gone; the caller should send the owner to /login. */
  get isUnauthorized(): boolean {
    return this.status === 401;
  }
}

type Query = Record<string, string | number | boolean | undefined | null | string[]>;

function buildUrl(path: string, query?: Query): string {
  const url = `${API_PREFIX}${path}`;
  if (!query) return url;

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) params.append(key, item);
    } else {
      params.set(key, String(value));
    }
  }
  const search = params.toString();
  return search ? `${url}?${search}` : url;
}

async function toError(response: Response): Promise<ApiError> {
  let code = "http_error";
  let message = `Request failed (${response.status}).`;
  try {
    const body = (await response.json()) as Partial<ApiErrorBody>;
    if (body.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
    }
  } catch {
    // A non-JSON body (a proxy error page, say) keeps the default message.
  }
  return new ApiError(response.status, code, message);
}

function isFormData(body: unknown): body is FormData {
  return typeof FormData !== "undefined" && body instanceof FormData;
}

async function request<T>(
  method: string,
  path: string,
  options: { query?: Query; body?: unknown } = {},
): Promise<T> {
  const form = isFormData(options.body);
  const response = await fetch(buildUrl(path, options.query), {
    method,
    credentials: "same-origin",
    // A multipart body must NOT carry a Content-Type header: only the browser
    // knows the boundary it generated, and naming the type without it leaves
    // the server unable to parse the parts.
    headers:
      options.body === undefined || form
        ? undefined
        : { "Content-Type": "application/json" },
    body:
      options.body === undefined
        ? undefined
        : form
          ? (options.body as FormData)
          : JSON.stringify(options.body),
  });

  if (!response.ok) throw await toError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>("GET", path, { query }),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, { body }),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, { body }),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, { body }),
  /**
   * Multipart POST, for the Console tradebook import (FR-IMP-01). The browser
   * sets Content-Type with its own boundary; see `request`. Errors come back
   * through the same `toError` envelope as every other call, so a 413
   * `file_too_large` or a 422 `invalid_tradebook` arrives as an ApiError with
   * a usable `code`.
   */
  upload: <T>(path: string, form: FormData) => request<T>("POST", path, { body: form }),
};
