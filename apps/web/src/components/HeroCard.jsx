import { Link } from "react-router-dom";
import { buildInvestigationView } from "../lib/investigationMap.js";

export default function HeroCard({ receipt, tabKey }) {
  if (!receipt) {
    return (
      <div className="pe-hero">
        <p className="pe-tab-label">{tabKey}</p>
        <p style={{ color: "var(--text-muted)" }}>No investigations loaded yet. Run an analysis or check the API.</p>
      </div>
    );
  }

  const v = buildInvestigationView(receipt);
  const id = v.receiptId;
  const label =
    tabKey === "politics"
      ? "POLITICS"
      : tabKey === "culture"
        ? "CULTURE"
        : "EVERYTHING ELSE";

  const share = async () => {
    const url = `${window.location.origin}/i/${id}`;
    try {
      if (navigator.share) await navigator.share({ title: "PUBLIC EYE", url });
      else await navigator.clipboard.writeText(url);
    } catch {
      try {
        await navigator.clipboard.writeText(url);
      } catch {
        /* ignore */
      }
    }
  };

  const [know, dis, miss] = [
    v.bullets.confirmed[0] || "",
    v.bullets.disputed[0] || "",
    v.bullets.missing[0] || "",
  ];

  return (
    <div className="pe-hero">
      {v.signed ? <span className="pe-hero-badge">✓ Verified</span> : null}
      <p className="pe-tab-label">TAB LABEL: {label}</p>
      <h1>{v.headline}</h1>
      <ul className="pe-hero-bullets">
        <li>
          <span className="pe-dot pe-dot--cyan" aria-hidden />
          <span>
            <strong style={{ color: "var(--text-primary)" }}>What we know — </strong>
            {know}
          </span>
        </li>
        <li>
          <span className="pe-dot pe-dot--amber" aria-hidden />
          <span>
            <strong style={{ color: "var(--text-primary)" }}>What&apos;s disputed — </strong>
            {dis}
          </span>
        </li>
        <li>
          <span className="pe-dot pe-dot--red" aria-hidden />
          <span>
            <strong style={{ color: "var(--text-primary)" }}>What&apos;s missing — </strong>
            {miss}
          </span>
        </li>
      </ul>
      <div className="pe-hero-actions">
        <Link to={`/i/${id}`} className="pe-btn pe-btn--primary">
          See the investigation →
        </Link>
        <button type="button" className="pe-btn" onClick={share}>
          Share
        </button>
      </div>
    </div>
  );
}
