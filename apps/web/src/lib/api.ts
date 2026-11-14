async function request(path: string, body?: unknown): Promise<Response> {
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
  if (!response.ok) {
    const value = await response.json();
    throw new Error(
      typeof value.detail === "string"
        ? value.detail
        : "Request failed validation",
    );
  }
  return response;
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  return (await request(path, body)).json() as Promise<T>;
}

export async function regressionBundle(
  runId: string,
  entrypoint: string,
): Promise<Blob> {
  const query = new URLSearchParams({ entrypoint });
  return (await request(`/runs/${runId}/regression?${query}`)).blob();
}
