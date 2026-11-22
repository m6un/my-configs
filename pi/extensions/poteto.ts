import { existsSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { getAgentDir, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function poteto(pi: ExtensionAPI) {
  const preference = join(getAgentDir(), "poteto-enabled");
  const enabled = () => existsSync(preference);
  const activeStatus = "🥔 Poteto on";

  pi.registerCommand("poteto", {
    description: "Toggle the sticky pstack router: /poteto on|off|status",
    getArgumentCompletions: (prefix) => ["on", "off", "status"]
      .filter((value) => value.startsWith(prefix)).map((value) => ({ value, label: value })),
    handler: async (args, ctx) => {
      try {
        switch (args.trim()) {
          case "on": writeFileSync(preference, "", { flag: "a", mode: 0o600 }); break;
          case "off": rmSync(preference, { force: true }); break;
          case "status": case "": break;
          default: ctx.ui.notify("Usage: /poteto on|off|status", "warning"); return;
        }
      } catch (error) {
        ctx.ui.notify(`Could not save Poteto mode: ${error instanceof Error ? error.message : String(error)}`, "error");
        return;
      }
      ctx.ui.setStatus("poteto", enabled() ? activeStatus : undefined);
      ctx.ui.notify(`Poteto is ${enabled() ? "on" : "off"} across Pi sessions.`, "info");
    },
  });

  pi.on("session_start", (_event, ctx) => {
    ctx.ui.setStatus("poteto", enabled() ? activeStatus : undefined);
  });

  pi.on("before_agent_start", (event, ctx) => {
    const { sections, skills, selectedTools } = event.systemPromptOptions;
    if (!enabled()) {
      delete sections.poteto;
      ctx.ui.setStatus("poteto", undefined);
      return;
    }
    const mode = skills.find((skill) => skill.name === "poteto-mode");
    if (!mode || !selectedTools.includes("read")) {
      delete sections.poteto;
      ctx.ui.setStatus("poteto", "Poteto unavailable (pstack or read missing)");
      return;
    }
    const playbooks = join(mode.baseDir, "playbooks");
    sections.poteto = [
      "Poteto mode is on. Answer quick questions directly. For substantial work, choose and read one pstack playbook before acting.",
      `Playbooks are in ${playbooks}. Common routes: investigation for read-only analysis, prototype to settle a design question, feature for new behavior, bug-fix for defects, refactoring for behavior-preserving changes, perf-issue for measured slowness.`,
      `Use the playbook named by the user if given. Read ${mode.filePath} for the full routing index only when needed. Read only the supporting skills the task needs.`,
      "Follow the user's scope and local agent instructions. Don't delegate, commit, push, open PRs, or run automations unless requested. Verify on the real thing and say what remains unverified.",
    ].join("\n");
    ctx.ui.setStatus("poteto", activeStatus);
  });
}
