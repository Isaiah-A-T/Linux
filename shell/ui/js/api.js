// Thin wrapper over lumend's JSON API.

async function call(method, path, body) {
  const res = await fetch(`/api/${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

export const get = (path) => call("GET", path);
export const post = (path, body = {}) => call("POST", path, body);
