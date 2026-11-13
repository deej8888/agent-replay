export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    `/api/v1${path}`,
    body === undefined
      ? { cache: "no-store" }
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const value = await response.json();
  if (!response.ok)
    throw new Error(
      typeof value.detail === "string"
        ? value.detail
        : "Request failed validation",
    );
  return value as T;
}
