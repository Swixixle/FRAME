import type { ConfidenceTier } from "./depth.js";

/**
 * Layer 2 (Spread) — heuristic diffusion signals from narrative text only.
 */
export interface SpreadResult {
  /** Recognized platform / outlet names (canonical labels). */
  platforms_mentioned: string[];
  /** Phrases or heuristic tags suggesting lateral syndication or burst spread. */
  spread_indicators: string[];
  /** True when copy implies rapid or simultaneous propagation in a short window. */
  time_compression: boolean;
  confidence_tier: ConfidenceTier;
  /** Schema keys that could not be grounded (empty lists, etc.). */
  absent_fields: string[];
}
