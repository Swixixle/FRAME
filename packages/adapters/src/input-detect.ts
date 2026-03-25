export type SurfaceInputKind = "text" | "html_url" | "media_url";

const MEDIA_AUDIO_EXT = /\.(mp3|m4a|wav|ogg|opus|webm|flac)(\?|#|$)/i;
const PODCAST_RSS = /\.(rss|xml)(\?|#|$)/i;

const MEDIA_HOST_RE =
  /youtube\.com|youtu\.be|m\.youtube\.com|music\.youtube\.com|spotify\.com|soundcloud\.com|podcasts\.apple\.com|podcasters\.spotify\.com|anchor\.fm|buzzsprout\.com|libsyn\.com|simplecast\.com|megaphone\.fm|cloudfront\.net|cdn\.|feeds\.|traffic\.megaphone|dcs\.redcirc|\bpodcast\b/i;

const CDN_PATH_RE =
  /\/(audio|episode|episodes|media|podcast|podcasts|stream|mp3|m4a)\//i;

/**
 * Classify a string as plain text vs fetchable HTML URL vs media/podcast URL.
 * Call only for strings that look like `http(s):` URLs.
 */
export function detectInputType(input: string): SurfaceInputKind {
  const u = (input || "").trim();
  if (!u.startsWith("http://") && !u.startsWith("https://")) {
    return "text";
  }
  const lowered = u.toLowerCase();
  if (PODCAST_RSS.test(lowered)) {
    return "media_url";
  }
  if (MEDIA_AUDIO_EXT.test(lowered)) {
    return "media_url";
  }
  if (MEDIA_HOST_RE.test(lowered)) {
    return "media_url";
  }
  if (CDN_PATH_RE.test(lowered) && MEDIA_AUDIO_EXT.test(lowered)) {
    return "media_url";
  }
  if (CDN_PATH_RE.test(lowered) && /\.(mp3|m4a|wav)(\?|#|$)/i.test(lowered)) {
    return "media_url";
  }
  return "html_url";
}
