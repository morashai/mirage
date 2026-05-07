# Mirage `serve` command guide

`mirage serve` runs Mirage in headless server mode so other tools/scripts can call it over HTTP.

## What it does

When running, Mirage starts an HTTP server and exposes:

- `GET /health`
- `POST /run`

Default bind:

- `hostname`: `127.0.0.1`
- `port`: `4096`

Start it:

```bash
mirage serve
```

Custom host/port:

```bash
mirage serve --hostname 0.0.0.0 --port 5050
```

## Endpoints

### `GET /health`

Use for readiness/liveness checks.

Example:

```bash
curl http://127.0.0.1:4096/health
```

Response:

```json
{"ok":true}
```

### `POST /run`

Run one non-interactive Mirage task.

Request JSON fields:

- `message` (string, required): prompt/task text
- `provider` (string, optional): provider key (for example `openai`)
- `model` (string, optional): model id (for example `gpt-4.1-mini`)
- `thread_id` (string, optional): explicit thread id

If `provider`/`model` are omitted, Mirage uses configured defaults.

Example request:

```bash
curl -X POST http://127.0.0.1:4096/run \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Summarize this repository architecture\"}"
```

Example with explicit model and thread:

```bash
curl -X POST http://127.0.0.1:4096/run \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Generate release notes\",\"provider\":\"openai\",\"model\":\"gpt-4.1-mini\",\"thread_id\":\"session-api-1\"}"
```

Success response:

```json
{"ok": true, "thread_id": "session-api-1"}
```

Failure behavior:

- `400` for malformed JSON request
- `404` for unknown paths
- `500` for execution-time errors

## Practical usage pattern

Terminal 1 (server):

```bash
mirage serve
```

Terminal 2 (client script/curl):

```bash
curl -X POST http://127.0.0.1:4096/run \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"List major modules and responsibilities\"}"
```

## Current limitations

The current `serve` implementation is intentionally minimal:

- no streaming response channel
- no authentication layer
- no websocket protocol
- no advanced session API beyond `thread_id` input/output

For local automation and integration smoke-tests, it is ready to use.
