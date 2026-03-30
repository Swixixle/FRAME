function ChainColumn({ title, subtitle, position }) {
  if (!position) return null;
  const chain = Array.isArray(position.chain) ? position.chain : [];

  return (
    <div className="pe-coalition-col">
      <h3 className="pe-coalition-col-title">{title}</h3>
      {subtitle ? <p className="pe-coalition-col-sub">{subtitle}</p> : null}
      {position.summary ? <p className="pe-coalition-summary">{position.summary}</p> : null}
      <ul className="pe-coalition-chain">
        {chain.map((link, i) => (
          <li key={`${link.outlet || "o"}-${i}`} className="pe-coalition-chain-item">
            <div className="pe-coalition-chain-head">
              <span className="pe-coalition-flag" aria-hidden>
                {link.flag || "·"}
              </span>
              <strong>{link.outlet}</strong>
              <span className="pe-coalition-meta">
                {link.country ? `${link.country} · ` : ""}
                {link.outlet_type?.replace(/_/g, " ") || ""}
              </span>
              <span className={`pe-coalition-conf pe-coalition-conf--${link.alignment_confidence || "medium"}`}>
                {link.alignment_confidence || "medium"}
              </span>
            </div>
            {link.alignment_note ? <p className="pe-coalition-note">{link.alignment_note}</p> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function CoalitionMap({ data }) {
  if (!data?.position_a || !data?.position_b) return null;

  const score = typeof data.divergence_score === "number" ? data.divergence_score : null;

  return (
    <section className="pe-coalition" aria-label="Coalition map">
      <div className="pe-coalition-hero">
        <div className="pe-coalition-hero-top">
          <h2 className="pe-coalition-heading">Coalition map</h2>
          {score != null ? (
            <span className="pe-coalition-score" title="Divergence score (0–100)">
              Divergence <strong>{score}</strong>
            </span>
          ) : null}
        </div>
        {data.contested_claim ? (
          <p className="pe-coalition-claim">&ldquo;{data.contested_claim}&rdquo;</p>
        ) : null}
      </div>

      <div className="pe-coalition-split">
        <ChainColumn
          title={data.position_a.label || "Position A"}
          subtitle={(data.position_a.anchor_outlets || []).slice(0, 3).join(" · ")}
          position={data.position_a}
        />
        <ChainColumn
          title={data.position_b.label || "Position B"}
          subtitle={(data.position_b.anchor_outlets || []).slice(0, 3).join(" · ")}
          position={data.position_b}
        />
      </div>

      {data.irreconcilable_gap ? (
        <div className="pe-coalition-gap">
          <h4 className="pe-coalition-gap-label">Irreconcilable gap</h4>
          <p>{data.irreconcilable_gap}</p>
        </div>
      ) : null}

      {Array.isArray(data.what_both_acknowledge) && data.what_both_acknowledge.length ? (
        <div className="pe-coalition-both">
          <h4 className="pe-coalition-both-label">What both acknowledge</h4>
          <ul>
            {data.what_both_acknowledge.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {data.signed ? <p className="pe-coalition-foot">Signed coalition map · verifiable with receipt verification tools.</p> : null}
    </section>
  );
}
