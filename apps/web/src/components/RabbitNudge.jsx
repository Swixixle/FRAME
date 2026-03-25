/**
 * Inline rabbit hole nudge — invitation to go deeper (spec).
 * @param {string | null} href
 * @param {string} [label]
 * @param {boolean} [absent]
 */
export default function RabbitNudge({ href, label, absent }) {
  const dead = absent === true || href == null || href === "";

  if (dead) {
    return (
      <span className="rabbit-nudge rabbit-nudge--absent" title="No actor ledger row for this name">
        <span className="rabbit-nudge-emoji" aria-hidden="true">
          🐇
        </span>{" "}
        <em className="rabbit-nudge-absent-text">No further verified sourcing available</em>
      </span>
    );
  }

  return (
    <a
      className="rabbit-nudge"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      title="Go deeper — open record"
    >
      <span className="rabbit-nudge-emoji" aria-hidden="true">
        🐇
      </span>
      {label ? <span className="rabbit-nudge-label">{label}</span> : null}
    </a>
  );
}
