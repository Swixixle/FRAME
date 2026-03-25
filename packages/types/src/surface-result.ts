import type { ConfidenceTier } from "./depth.js";

/** Named entity as surfaced from the input (Layer 1). */
export interface SurfaceNamedActor {
  name: string;
  confidence_tier: ConfidenceTier;
}

/** Earliest datable appearance described in the material. */
export interface SurfaceWhenBlock {
  earliest_appearance: string;
  source: string;
  confidence_tier: ConfidenceTier;
}

/** Timestamped claim from media transcription (Layer 1 extension). */
export interface SurfaceMediaClaim {
  /** Display string HH:MM:SS */
  timestamp_label?: string;
  timestamp_start?: number;
  timestamp_end?: number;
  speaker?: string;
  text?: string;
  /** Maps claim implication_risk to a confidence-style tier for badges. */
  confidence_tier?: ConfidenceTier | string;
}

/**
 * Layer 1 (Surface) extraction — structured fields only; narrative body in `what`,
 * contextual framing in `cultural_substrate` (not a separate claim block).
 */
export interface SurfaceResult {
  what: string;
  what_confidence_tier: ConfidenceTier;
  /**
   * Broader cultural or historical framing for the narrative (not a factual claim line).
   * Null when no defensible context can be stated.
   */
  cultural_substrate: string | null;
  who: SurfaceNamedActor[];
  when: SurfaceWhenBlock;
  /** Present when the request used a URL input; otherwise null. */
  source_url: string | null;
  /** Tier for URL resolution/identity; null when `source_url` is null. */
  source_url_confidence_tier: ConfidenceTier | null;
  /**
   * Keys among: what, who, when, source_url — that could not be inferred at all from the input.
   * Do not list a field merely because confidence is low. Always present; empty when all four were inferred.
   */
  absent_fields: string[];
  /** Provenance of extraction: plain text, fetched HTML, or media/podcast pipeline. */
  source_type?: "text" | "html" | "media";
  /** Populated when `source_type === "media"` (transcription + claim extraction). */
  media_claims?: SurfaceMediaClaim[];
}

export type SurfaceLayerInput =
  | { narrative: string; url?: undefined }
  | { url: string; narrative?: undefined };
