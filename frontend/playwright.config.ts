import { defineConfig } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

// This config loads as an ES module (frontend/package.json has "type":
// "module"), so __dirname isn't available — derive it from import.meta.url.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
// The project root is one level up from this config file (backend.app.* is
// only importable when uvicorn is launched with the project root as cwd).
const projectRoot = path.resolve(__dirname, "..");
const backendPython = path.join(projectRoot, "backend", ".venv", "Scripts", "python.exe");

export default defineConfig({
  use: { baseURL: "http://localhost:5173" },
  testDir: "./e2e",
  // Playwright starts both servers itself for every run (reuseExistingServer
  // is deliberately false, not just for CI) so the E2E suite can force
  // LLM_PROVIDER=mock on the backend it spawns — this must hold regardless
  // of whatever a leftover manually-started server, or the developer's own
  // .env, is configured with. `npx playwright test` alone is the isolation
  // guarantee; it does not depend on how servers were started beforehand.
  webServer: [
    {
      command: `"${backendPython}" -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`,
      cwd: projectRoot,
      url: "http://localhost:8000/api/health",
      reuseExistingServer: false,
      timeout: 30_000,
      env: { ...process.env, LLM_PROVIDER: "mock" },
    },
    {
      command: "npm run dev",
      cwd: __dirname,
      url: "http://localhost:5173",
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
