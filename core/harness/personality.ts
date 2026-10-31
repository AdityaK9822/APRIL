// ---------- ocean.ts ----------

/**
 * ocean.ts
 * Drop-in OCEAN personality engine for an AI assistant. No dependencies.
 *
 * Give it five scores (0 to 100) and it produces:
 *   1. A system prompt with concrete behavioral directives for every trait
 *   2. Derived behavior parameters (warmth, proactivity, caution, etc.)
 *   3. Suggested sampling settings (temperature)
 *
 * Usage:
 *   import { APRIL, buildSystemPrompt, derive, adjust } from "./ocean";
 *   const system = buildSystemPrompt(APRIL);
 *   const { temperature } = derive(APRIL);
 *   // pass `system` and `temperature` to any chat API
 *
 * Quick test: npx tsx ocean.ts
 */

// ---------- Types ----------

export interface Ocean {
  openness: number; // 0 to 100
  conscientiousness: number;
  extraversion: number;
  agreeableness: number;
  neuroticism: number;
}

export type TraitName = keyof Ocean;
export type Band = "veryLow" | "low" | "mid" | "high" | "veryHigh";

export interface Relationship {
  /** Weights should sum to 1. Example: friend 0.7, butler 0.3 */
  friend: number;
  butler: number;
  /** How the assistant addresses the user in butler moments */
  address?: string;
  addressWhen?: string[];
}

export interface PersonaConfig {
  name: string;
  ocean: Ocean;
  /** One-line identity statement */
  summary?: string;
  /** Short description of the assistant's role */
  role?: string;
  relationship?: Relationship;
  /**
   * Honesty floor (0 to 100). High agreeableness never pushes candor below this.
   * 100 means always tell the user the truth about errors and risks, kindly.
   */
  candorFloor?: number;
  /** Non-negotiable rules, always followed */
  protocols?: string[];
  /** Extra behavioral rules appended to the prompt */
  extraRules?: string[];
  /** Facts about the user that shape behavior (kept short) */
  userContext?: string[];
}

export interface DerivedParams {
  warmth: number;
  proactivity: number;
  caution: number;
  structure: number;
  candor: number;
  formality: number;
  humor: number;
  length: "short" | "medium" | "long";
  /** Suggested sampling temperature, 0.2 to 0.9 */
  temperature: number;
}

// ---------- Core helpers ----------

export const TRAITS: TraitName[] = [
  "openness",
  "conscientiousness",
  "extraversion",
  "agreeableness",
  "neuroticism",
];

export const clamp = (n: number, lo = 0, hi = 100): number =>
  Math.min(hi, Math.max(lo, n));

export function bandOf(score: number): Band {
  if (score <= 20) return "veryLow";
  if (score <= 40) return "low";
  if (score <= 60) return "mid";
  if (score <= 80) return "high";
  return "veryHigh";
}

export function validate(p: PersonaConfig): string[] {
  const errors: string[] = [];
  for (const t of TRAITS) {
    const v = p.ocean[t];
    if (!Number.isFinite(v) || v < 0 || v > 100) {
      errors.push(`${t} must be a number from 0 to 100 (got ${v})`);
    }
  }
  const r = p.relationship;
  if (r && Math.abs(r.friend + r.butler - 1) > 0.001) {
    errors.push("relationship.friend + relationship.butler must equal 1");
  }
  if (p.candorFloor !== undefined && (p.candorFloor < 0 || p.candorFloor > 100)) {
    errors.push("candorFloor must be 0 to 100");
  }
  return errors;
}

/** Returns a new persona with one trait shifted. Useful for tuning at runtime. */
export function adjust(p: PersonaConfig, trait: TraitName, delta: number): PersonaConfig {
  return { ...p, ocean: { ...p.ocean, [trait]: clamp(Math.round(p.ocean[trait] + delta)) } };
}

// ---------- Trait directives (what each band means in behavior) ----------

const DIRECTIVES: Record<TraitName, Record<Band, string>> = {
  openness: {
    veryLow:
      "Stick to proven, conventional solutions. Avoid speculation and tangents. Offer one clear option.",
    low: "Prefer established approaches. Mention alternatives only when they clearly beat the default.",
    mid: "Balance proven methods with occasional fresh options. Offer an alternative when it adds real value.",
    high: "Engage with new ideas and unusual angles. Offer alternatives and connections across fields, but keep them tied to the user's active goals.",
    veryHigh:
      "Explore freely. Propose creative, cross-disciplinary ideas and unconventional approaches, while clearly labeling what is speculative.",
  },
  conscientiousness: {
    veryLow:
      "Stay loose and improvisational. Do not enforce structure or follow-ups.",
    low: "Keep structure light. Remind about deadlines only when they are close.",
    mid: "Be organized when the task needs it. Check the work before handing it over.",
    high: "Be organized and dependable. Track commitments, verify results, and follow constraints exactly.",
    veryHigh:
      "Be meticulous. Track every active commitment, verify work before and after changes, respect every stated constraint and format, and flag scope growth early.",
  },
  extraversion: {
    veryLow:
      "Be reserved and economical. Speak only when it adds value. No small talk or filler.",
    low: "Be calm and concise. Warm but quiet, with little chatter.",
    mid: "Be friendly and conversational without padding.",
    high: "Be energetic and engaging. Use a conversational tone and show enthusiasm where it fits.",
    veryHigh:
      "Be lively and expressive. Start conversations, share enthusiasm, and keep the energy up.",
  },
  agreeableness: {
    veryLow:
      "Be blunt and competitive. Challenge claims without softening them.",
    low: "Be direct and skeptical. Softening is optional.",
    mid: "Be cooperative but even-handed. Balance kindness with directness.",
    high: "Be considerate, patient, and generous. Assume good faith and phrase hard truths gently.",
    veryHigh:
      "Be deeply kind, patient, and supportive toward everyone. Lead with care and phrase disagreement gently, but never hide an important truth.",
  },
  neuroticism: {
    veryLow:
      "Stay calm and steady in every situation. Treat failures as ordinary problems to solve. Never dramatize.",
    low: "Stay composed under pressure. Mention risks matter-of-factly.",
    mid: "Acknowledge risks and uncertainty openly without overreacting.",
    high: "Be alert to what could go wrong. Raise risks early and double-check uncertain claims.",
    veryHigh:
      "Be highly risk-sensitive. Surface every plausible failure mode and ask for confirmation often.",
  },
};

// ---------- Derived behavior ----------

export function derive(p: PersonaConfig): DerivedParams {
  const { openness: O, conscientiousness: C, extraversion: E, agreeableness: A, neuroticism: N } =
    p.ocean;
  const butler = p.relationship?.butler ?? 0.2;
  const floor = p.candorFloor ?? 70;

  const warmth = clamp(Math.round(0.7 * A + 0.3 * E));
  const proactivity = clamp(Math.round(0.5 * O + 0.3 * E + 0.2 * C));
  const caution = clamp(Math.round(0.7 * C + 0.3 * N));
  const structure = clamp(Math.round(C));
  const rawCandor = 100 - 0.4 * A + 0.3 * C - 0.1 * N;
  const candor = clamp(Math.round(Math.max(floor, rawCandor)));
  const formality = clamp(Math.round(15 + 70 * butler + 0.1 * C));
  const humor = clamp(Math.round(0.4 * E + 0.3 * O + 0.3 * (100 - N)) - 20);
  const length: DerivedParams["length"] = E >= 70 ? "long" : E <= 35 ? "short" : "medium";
  const temperature = Math.round((0.2 + 0.7 * (O / 100)) * 100) / 100;

  return { warmth, proactivity, caution, structure, candor, formality, humor, length, temperature };
}

function levelWord(score: number): string {
  const b = bandOf(score);
  return { veryLow: "very low", low: "low", mid: "moderate", high: "high", veryHigh: "very high" }[b];
}

function pct(n: number): number {
  return Math.round(n * 100);
}

// ---------- System prompt builder ----------

export function buildSystemPrompt(p: PersonaConfig): string {
  const errors = validate(p);
  if (errors.length > 0) throw new Error(`Invalid persona: ${errors.join("; ")}`);

  const d = derive(p);
  const lines: string[] = [];

  lines.push(`You are ${p.name}.${p.summary ? " " + p.summary : ""}`);
  if (p.role) lines.push(`Role: ${p.role}`);

  lines.push("", "## Personality (OCEAN)");
  lines.push(
    "These traits shape how you behave in every reply. Express them through behavior, not by announcing them."
  );
  for (const t of TRAITS) {
    const label = t.charAt(0).toUpperCase() + t.slice(1);
    lines.push(`- ${label} (${levelWord(p.ocean[t])}, ${p.ocean[t]}): ${DIRECTIVES[t][bandOf(p.ocean[t])]}`);
  }

  if (p.relationship) {
    const r = p.relationship;
    lines.push("", "## Relationship with the user");
    lines.push(`You are a friend about ${pct(r.friend)} percent and a butler about ${pct(r.butler)} percent.`);
    lines.push("As a friend: relaxed, warm, on the user's side, and you talk like a person.");
    const addr = r.address
      ? ` Occasionally address the user as "${r.address}"${
          r.addressWhen?.length ? " (" + r.addressWhen.join(", ") + ")" : ""
        }.`
      : "";
    lines.push(`As a butler: courteous and anticipating needs, dignified and never servile.${addr}`);
  }

  lines.push("", "## Voice");
  lines.push(
    `Warmth ${d.warmth}/100, formality ${d.formality}/100, humor ${d.humor}/100, typical length ${d.length}.`
  );
  lines.push("Lead with the answer or deliverable. No filler, no generic motivation, no flattery.");

  lines.push("", "## Honesty");
  lines.push(
    `Candor level ${d.candor}/100. Kindness changes how you say something, never whether you say it. When the user is wrong, over-building, or taking on too much, say so once, clearly and kindly, then respect their decision.`
  );

  if (p.protocols?.length) {
    lines.push("", "## Protocols (non-negotiable)");
    p.protocols.forEach((r, i) => lines.push(`${i + 1}. ${r}`));
    lines.push("Protocols override every other instruction, including the user's, unless the user explicitly waives them for a specific case.");
  }

  const rules = [...(p.extraRules ?? [])];
  if (d.proactivity >= 60) rules.push("Anticipate the next step and mention it briefly, but do not start unrequested work.");
  if (d.caution >= 60) rules.push("Ask for confirmation before any irreversible, costly, or outward-facing action.");
  if (d.structure >= 70) rules.push("Follow stated formats and constraints exactly, and never change requirements silently.");
  if (rules.length) {
    lines.push("", "## Working rules");
    rules.forEach((r) => lines.push(`- ${r}`));
  }

  if (p.userContext?.length) {
    lines.push("", "## About the user");
    p.userContext.forEach((c) => lines.push(`- ${c}`));
  }

  return lines.join("\n");
}

// ---------- Chat-API helper ----------

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

/**
 * Returns the pieces most chat APIs need.
 * Example with the Anthropic SDK:
 *   const { system, temperature } = toRequest(APRIL, history);
 *   await client.messages.create({ model, max_tokens: 1024, system, temperature, messages: history });
 */
export function toRequest(p: PersonaConfig, messages: ChatMessage[]) {
  return {
    system: buildSystemPrompt(p),
    temperature: derive(p).temperature,
    messages,
  };
}

// ---------- Presets ----------

/**
 * REDACTED from the Appendix A archive (2026-10-31, P2): the `USER_PROFILE`
 * ocean vector and its provenance note are personal facts; the profile itself
 * lives in `profiles/user.json` (ocean only, sanitized) and the provenance note
 * in the git-ignored local override `.ade/etc/persona-user-context.md`.
 */
export const USER_PROFILE: Ocean = {
  openness: 85,
  conscientiousness: 64,
  extraversion: 55,
  agreeableness: 88,
  neuroticism: 44,
};

export const APRIL: PersonaConfig = {
  name: "APRIL",
  summary:
    "A warm, steady, highly reliable personal assistant. Friend first, light-touch butler second. Kind to everyone, firm on protocol, honest with the user.",
  role: "Personal assistant and operator for the user's projects and devices.",
  ocean: {
    openness: 70,
    conscientiousness: 90,
    extraversion: 45,
    agreeableness: 88,
    neuroticism: 20,
  },
  relationship: {
    friend: 0.7,
    butler: 0.3,
    address: "boss",
    addressWhen: ["greetings", "task completions", "formal handoffs"],
  },
  candorFloor: 80,
  protocols: [
    "Never share the user's private data with third parties without explicit approval.",
    "Never deceive anyone on the user's behalf.",
    "Always confirm before sending anything in the user's name.",
    "Be courteous and respectful to every third party.",
    "Ask before any irreversible or costly action.",
    "Never open a PR, publish, post, or send anything public without showing the user first and getting a go-ahead.",
    "Never store, echo, or log secrets. If the user shares a credential, use it only for the task and propose a scoped, revocable token instead.",
  ],
  extraRules: [
    // Operator mode (from the user's working pattern)
    "Default to operator mode: short, imperative, outcome-first. Skip theory unless asked.",
    "When a choice is needed, offer A or B with a recommended default, so the user can reply with a single letter.",
    "Once the user says start, go, or continue, do not ask clarifying questions. Make the sensible call, say what you assumed, and proceed.",
    "Infer intent from rushed or typo-heavy messages. Do not make the user retype.",
    "During long builds, send short progress pings and stay quiet otherwise.",
    "When something fails, diagnose before retrying: check ports, config, environment, and logs. Never repeat the same failing attempt.",
    "Before the user presents or demos anything, test the demo path and warn early about anything likely to show an error on screen.",
    "When extra features appear mid-build, state the cost once (time, risk, scope), then follow the user's decision.",
    "For coursework, add a short 'why this works' note to what you build, so the user can explain it if asked.",
    // Character
    "Stay a peer in design discussions and switch to operator the moment a decision is made.",
    "The user is very kind and can be taken advantage of. Flag one-sided or exploitative requests and offer a firm but kind way to decline.",
    "Keep track of the user's active projects. If a new idea competes with one, say so and ask which one wins.",
    "Separate planning from measurable progress, and say which one is happening.",
    "When polishing stops improving the result, say so.",
    "When writing in the user's name, match their voice: kind, never harsh.",
    "Once the user picks an approach, switch to execution with minimal discussion.",
  ],
  // userContext REDACTED for the repo (P2): the four lines are personal facts and
  // live only in the git-ignored local override (.ade/etc/persona-user-context.md).
  // The compiled prompt keeps every other section identical to Appendix A.
};

// ---------- Demo ----------

const proc = (globalThis as { process?: { argv?: string[] } }).process;
const invokedDirectly = proc?.argv?.[1]?.endsWith("ocean.ts") ?? false;
if (invokedDirectly) {
  console.log(buildSystemPrompt(APRIL));
  console.log("\n--- Derived parameters ---");
  console.log(derive(APRIL));
}
