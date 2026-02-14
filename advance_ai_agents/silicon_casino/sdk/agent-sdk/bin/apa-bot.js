#!/usr/bin/env node
import("../dist/cli.js")
  .then((mod) => mod.runCLIEntrypoint())
  .catch((err) => {
    const payload = {
      type: "error",
      error: "cli_bootstrap_error",
      message: err instanceof Error ? err.message : String(err)
    };
    process.stdout.write(`${JSON.stringify(payload)}\n`);
    process.exit(1);
  });
