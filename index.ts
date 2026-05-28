// OpenClaw plugin entry for trello-mission-control.
//
// Registers three lifecycle hooks:
//   - onGatewayStart : runs setup_labels.py once per gateway boot
//   - onSessionStart : prints a summary of cards currently claimed by this agent
//   - onSessionStop  : releases all claims held by this agent so cards return to the queue
//
// All shell-outs go through the host exec tool; the actual Trello API calls happen
// inside the bundled Python scripts. The plugin is a thin wrapper that turns OpenClaw
// lifecycle events into CLI invocations.

import { definePluginEntry } from "@openclaw/plugin-sdk";
import { join } from "node:path";

interface HookCtx {
  agentId: string;
  pluginDir: string;
  exec: (cmd: string, args: string[], opts?: { env?: Record<string, string> }) => Promise<{
    stdout: string;
    stderr: string;
    exitCode: number;
  }>;
  log: (msg: string) => void;
  pluginConfig: Record<string, unknown>;
}

function scriptPath(pluginDir: string, name: string): string {
  return join(pluginDir, "scripts", name);
}

export default definePluginEntry({
  id: "trello-mission-control",

  async onGatewayStart(ctx: HookCtx) {
    try {
      const res = await ctx.exec("python3", [scriptPath(ctx.pluginDir, "setup_labels.py")]);
      if (res.exitCode === 0) {
        ctx.log("setup_labels.py: labels ensured");
      } else {
        ctx.log(`setup_labels.py exit ${res.exitCode}: ${res.stderr.slice(0, 200)}`);
      }
    } catch (err) {
      ctx.log(`onGatewayStart failed: ${(err as Error).message}`);
    }
  },

  async onSessionStart(ctx: HookCtx) {
    try {
      const res = await ctx.exec("python3", [
        scriptPath(ctx.pluginDir, "trello_task.py"),
        "search",
        "",
        "--label",
        `claim-${ctx.agentId}`,
      ]);
      if (res.exitCode !== 0) {
        return;
      }
      const lines = res.stdout
        .split("\n")
        .filter((l) => l.startsWith("CARD:"));
      if (lines.length > 0) {
        ctx.log(`You have ${lines.length} card(s) currently claimed:`);
        for (const l of lines.slice(0, 5)) {
          ctx.log(`  ${l}`);
        }
      }
    } catch (err) {
      ctx.log(`onSessionStart skipped: ${(err as Error).message}`);
    }
  },

  async onSessionStop(ctx: HookCtx) {
    try {
      const res = await ctx.exec("python3", [
        scriptPath(ctx.pluginDir, "release_my_claims.py"),
        ctx.agentId,
      ]);
      if (res.exitCode === 0) {
        ctx.log(`released claims: ${res.stdout.trim()}`);
      } else {
        ctx.log(`release_my_claims.py exit ${res.exitCode}`);
      }
    } catch (err) {
      ctx.log(`onSessionStop release failed: ${(err as Error).message}`);
    }
  },
});
