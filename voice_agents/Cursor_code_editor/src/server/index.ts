import http from "node:http";
import path from "node:path";

import express from "express";
import { WebSocketServer } from "ws";

import { config, missingEnv, providerInfo } from "./config.js";
import { createChatTitleWithNebius } from "./nebius.js";
import { readyMessage, VoiceSession } from "./session.js";

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ noServer: true });
const isProduction = process.env.NODE_ENV === "production";

app.use(express.json({ limit: "64kb" }));

app.get("/api/health", (_request, response) => {
  response.json({
    ok: missingEnv().length === 0,
    missingEnv: missingEnv(),
    workspace: config.codeWorkspace,
    model: config.cursorModel,
    providers: providerInfo()
  });
});

app.post("/api/title", async (request, response) => {
  const text = typeof request.body?.text === "string" ? request.body.text.trim() : "";
  if (!text) {
    response.status(400).json({ error: "Missing text" });
    return;
  }

  try {
    response.json({ title: await createChatTitleWithNebius(text) });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    response.status(502).json({ error: message });
  }
});

server.on("upgrade", (request, socket, head) => {
  if (request.url !== "/voice") {
    socket.destroy();
    return;
  }

  wss.handleUpgrade(request, socket, head, (ws) => {
    const session = new VoiceSession({ browser: ws });
    ws.send(JSON.stringify(readyMessage(config.codeWorkspace)));
    ws.on("message", (data, isBinary) => session.handleBrowserMessage(data, isBinary));
    ws.on("close", () => session.close());
  });
});

if (isProduction) {
  app.use(express.static(path.join(config.projectRoot, "dist/client")));
  app.use((_request, response) => {
    response.sendFile(path.join(config.projectRoot, "dist/client/index.html"));
  });
} else {
  const { createServer } = await import("vite");
  const vite = await createServer({
    root: config.projectRoot,
    server: { middlewareMode: true },
    appType: "spa"
  });
  app.use(vite.middlewares);
}

server.listen(config.port, "127.0.0.1", () => {
  console.log(`VoxCode: http://127.0.0.1:${config.port}`);
  console.log(`Workspace: ${config.codeWorkspace}`);
  const missing = missingEnv();
  if (missing.length > 0) {
    console.log(`Missing env: ${missing.join(", ")}`);
  }
});
