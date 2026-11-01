export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export class SessionLostError extends ApiError {
  constructor() {
    super(401, "Your session has ended. Sign in again to continue.");
  }
}
export async function http<T>(
  path: string,
  options: {
    method?: "GET" | "POST" | "PUT" | "DELETE";
    body?: unknown;
    csrf?: string | null;
    signal?: AbortSignal;
  } = {},
): Promise<T> {
  const target = new URL(path, window.location.origin);
  if (
    !path.startsWith("/") ||
    path.startsWith("//") ||
    path.includes("\\") ||
    target.origin !== window.location.origin ||
    !/^\/(api\/v1|auth)\//.test(target.pathname) ||
    target.hash
  )
    throw new Error("Unapproved application route");
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.csrf) headers["X-CSRF-Token"] = options.csrf;
  const response = await fetch(target.pathname + target.search, {
    method: options.method ?? "GET",
    credentials: "same-origin",
    cache: "no-store",
    redirect: "error",
    signal: options.signal,
    headers,
    ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
  });
  if (options.signal?.aborted) throw new DOMException("The request was aborted.", "AbortError");
  if (response.status === 401) {
    window.dispatchEvent(new Event("arbit:session-ended"));
    throw new SessionLostError();
  }
  if (!response.ok)
    throw new ApiError(
      response.status,
      response.status === 409
        ? "Your preferences changed in another window. Review the latest version and try again."
        : response.status === 403
          ? "Your account does not have access to this view."
          : "This information is unavailable right now. Try again shortly.",
    );
  return response.status === 204 ? (undefined as T) : (response.json() as Promise<T>);
}
