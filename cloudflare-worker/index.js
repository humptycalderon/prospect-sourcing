/**
 * ONTO Wallet — ICP Update Bot (Cloudflare Worker)
 *
 * Receives Telegram webhooks. When the user replies APPLY (or a modification),
 * Claude parses the intent, writes approved changes to icp_overrides.json
 * in the GitHub repo via the GitHub API, then triggers workflow_dispatch
 * on the prospect sourcing workflow.
 *
 * Environment variables (set in Cloudflare dashboard → Workers → Settings → Variables):
 *   TELEGRAM_BOT_TOKEN   — your Telegram bot token
 *   TELEGRAM_CHAT_ID     — your Telegram chat ID (with negative sign for group chats)
 *   ANTHROPIC_API_KEY    — your Anthropic API key
 *   GITHUB_TOKEN         — personal access token with repo + workflow scope
 *   GITHUB_OWNER         — humptycalderon
 *   GITHUB_REPO          — prospect-sourcing
 *   GITHUB_WORKFLOW_ID   — weekly-pipeline.yml
 *   BOT_SECRET           — any random string; set as Telegram webhook secret_token
 */

const GITHUB_API = "https://api.github.com";
const ANTHROPIC_API = "https://api.anthropic.com/v1/messages";
const TELEGRAM_API = "https://api.telegram.org";
const OVERRIDES_PATH = "icp_overrides.json";

// ─── Telegram helpers ────────────────────────────────────────────────────────

async function sendTelegram(env, text, chatId = null) {
  // Default to the admin DM for bot replies; channel publishing is handled by the Python scripts
  const target = chatId || env.TELEGRAM_ADMIN_CHAT_ID;
  const url = `${TELEGRAM_API}/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`;
  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: target,
      text,
      parse_mode: "Markdown",
      disable_web_page_preview: true,
    }),
  });
}

// ─── GitHub helpers ──────────────────────────────────────────────────────────

async function getFileWithSha(env, path) {
  const url = `${GITHUB_API}/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${path}`;
  const resp = await fetch(url, {
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  if (!resp.ok) return null;
  const data = await resp.json();
  const content = atob(data.content.replace(/\n/g, ""));
  return { content, sha: data.sha };
}

async function updateFile(env, path, newContent, sha, message) {
  const url = `${GITHUB_API}/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${path}`;
  const encoded = btoa(unescape(encodeURIComponent(newContent)));
  const resp = await fetch(url, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({ message, content: encoded, sha }),
  });
  return resp.ok;
}

async function triggerWorkflow(env) {
  const url = `${GITHUB_API}/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/actions/workflows/${env.GITHUB_WORKFLOW_ID}/dispatches`;
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  return resp.ok;
}

// ─── Claude helper ───────────────────────────────────────────────────────────

async function parseIntent(env, userMessage, currentOverrides) {
  /**
   * Ask Claude to interpret the user's Telegram reply and produce
   * a structured patch to apply to icp_overrides.json.
   *
   * Returns a patch object (may be empty if no action needed) or null on failure.
   */
  const systemPrompt = `You are an assistant managing ICP (ideal customer profile) search criteria for an AI data platform.

The user has received recommended updates to their prospect sourcing search criteria via Telegram.
They are replying to approve, reject, or modify those recommendations.

Current icp_overrides.json contents:
${JSON.stringify(currentOverrides, null, 2)}

Your job: interpret the user's reply and return a JSON patch object with exactly these fields:
{
  "action": "apply" | "skip" | "modify",
  "extra_github_queries": [...],
  "extra_hn_queries": [...],
  "extra_description_keywords": {...},
  "extra_intent_keywords": {...},
  "_update_reason": "string"
}

Rules:
- "apply": user approved the recommendations as-is
- "skip": user wants to skip this week's updates
- "modify": user wants changes — reflect their modifications in the arrays/objects
- All arrays/objects should contain the FINAL desired state (what to ADD to base config)
- Include existing overrides that should be kept, merge new ones in
- _update_reason: keep existing or update with user's stated reason
- Return ONLY valid JSON, nothing else`;

  const resp = await fetch(ANTHROPIC_API, {
    method: "POST",
    headers: {
      "x-api-key": env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: "claude-opus-4-8",
      max_tokens: 1024,
      system: systemPrompt,
      messages: [{ role: "user", content: userMessage }],
    }),
  });

  if (!resp.ok) return null;
  const data = await resp.json();
  const raw = data.content?.find((b) => b.type === "text")?.text?.trim();
  if (!raw) return null;

  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

// ─── Main handler ────────────────────────────────────────────────────────────

export default {
  async fetch(request, env) {
    // Verify Telegram webhook secret
    const secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
    if (secret !== env.BOT_SECRET) {
      return new Response("Unauthorized", { status: 401 });
    }

    if (request.method !== "POST") {
      return new Response("OK");
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return new Response("Bad Request", { status: 400 });
    }

    const message = body?.message;
    if (!message?.text) return new Response("OK");

    // Only respond to commands from the private admin DM
    const chatId = String(message.chat?.id);
    if (chatId !== String(env.TELEGRAM_ADMIN_CHAT_ID)) {
      return new Response("OK");
    }

    const userText = message.text.trim();
    const lowerText = userText.toLowerCase();

    // Quick commands that don't need Claude
    if (lowerText === "/status") {
      const file = await getFileWithSha(env, OVERRIDES_PATH);
      if (file) {
        const ov = JSON.parse(file.content);
        const ghCount = (ov.extra_github_queries || []).length;
        const hnCount = (ov.extra_hn_queries || []).length;
        const kwCount = Object.keys(ov.extra_description_keywords || {}).length;
        const updated = ov._last_updated || "never";
        await sendTelegram(env,
          `📋 *Current Overrides*\nLast updated: ${updated}\n` +
          `GitHub queries: +${ghCount}\nHN queries: +${hnCount}\nKeywords: +${kwCount}\n\n` +
          `_Reason: ${ov._update_reason || "none"}_`
        );
      } else {
        await sendTelegram(env, "Could not read overrides file.");
      }
      return new Response("OK");
    }

    if (lowerText === "/reset") {
      const file = await getFileWithSha(env, OVERRIDES_PATH);
      if (!file) {
        await sendTelegram(env, "Could not read overrides file.");
        return new Response("OK");
      }
      const blank = {
        _comment: "Weekly ICP overrides managed by the Telegram approval bot. Merged with config.py at runtime.",
        _last_updated: new Date().toISOString().split("T")[0],
        _update_reason: "Manual reset via Telegram",
        extra_github_queries: [],
        extra_hn_queries: [],
        extra_description_keywords: {},
        extra_intent_keywords: {},
        min_score_override: null,
      };
      const ok = await updateFile(env, OVERRIDES_PATH, JSON.stringify(blank, null, 2), file.sha, "chore: reset ICP overrides via Telegram bot");
      await sendTelegram(env, ok ? "✅ Overrides reset to empty." : "❌ Failed to reset overrides.");
      return new Response("OK");
    }

    // For APPLY, SKIP, or any freeform modification — pass to Claude
    await sendTelegram(env, "Got it, processing…");

    const file = await getFileWithSha(env, OVERRIDES_PATH);
    if (!file) {
      await sendTelegram(env, "❌ Could not read icp_overrides.json from the repo.");
      return new Response("OK");
    }

    let currentOverrides;
    try {
      currentOverrides = JSON.parse(file.content);
    } catch {
      await sendTelegram(env, "❌ icp_overrides.json is malformed. Use /reset to clear it.");
      return new Response("OK");
    }

    const patch = await parseIntent(env, userText, currentOverrides);
    if (!patch) {
      await sendTelegram(env, "❌ Could not parse your request. Try replying APPLY, SKIP, or describe what to change.");
      return new Response("OK");
    }

    if (patch.action === "skip") {
      await sendTelegram(env, "👍 Skipping updates this week. Prospect sourcing will run with current criteria.");
      // Still trigger sourcing so the pipeline runs on schedule
      await triggerWorkflow(env);
      return new Response("OK");
    }

    // Build updated overrides from patch
    const today = new Date().toISOString().split("T")[0];
    const updated = {
      _comment: currentOverrides._comment,
      _last_updated: today,
      _update_reason: patch._update_reason || currentOverrides._update_reason || "",
      extra_github_queries: patch.extra_github_queries || [],
      extra_hn_queries: patch.extra_hn_queries || [],
      extra_description_keywords: patch.extra_description_keywords || {},
      extra_intent_keywords: patch.extra_intent_keywords || {},
      min_score_override: currentOverrides.min_score_override || null,
    };

    const ok = await updateFile(
      env,
      OVERRIDES_PATH,
      JSON.stringify(updated, null, 2),
      file.sha,
      `feat: update ICP overrides for ${today} — ${updated._update_reason.slice(0, 72)}`
    );

    if (!ok) {
      await sendTelegram(env, "❌ Failed to write changes to the repo. Check GITHUB_TOKEN permissions.");
      return new Response("OK");
    }

    // Confirm what was applied
    const ghAdded = (updated.extra_github_queries || []).length;
    const hnAdded = (updated.extra_hn_queries || []).length;
    const kwAdded = Object.keys(updated.extra_description_keywords || {}).length;
    const intentAdded = Object.keys(updated.extra_intent_keywords || {}).length;

    let summary = `✅ *Overrides saved* (${today})\n`;
    if (ghAdded) summary += `  • ${ghAdded} GitHub quer${ghAdded === 1 ? "y" : "ies"}\n`;
    if (hnAdded) summary += `  • ${hnAdded} HN quer${hnAdded === 1 ? "y" : "ies"}\n`;
    if (kwAdded) summary += `  • ${kwAdded} description keyword${kwAdded === 1 ? "" : "s"}\n`;
    if (intentAdded) summary += `  • ${intentAdded} intent keyword${intentAdded === 1 ? "" : "s"}\n`;
    summary += `\n_Triggering prospect sourcing now…_`;

    await sendTelegram(env, summary);

    const triggered = await triggerWorkflow(env);
    if (triggered) {
      await sendTelegram(env, "🚀 Prospect sourcing workflow started. Results will appear in Notion.");
    } else {
      await sendTelegram(env, "⚠️ Overrides saved but could not trigger the workflow automatically. Run it manually from GitHub Actions.");
    }

    return new Response("OK");
  },
};
