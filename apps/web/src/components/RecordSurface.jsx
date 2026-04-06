/**
 * RECORD — journalist / outlet / absence facts from article_analysis receipt (no scores).
 */

import ProportionalityRecords from "./ProportionalityRecords.jsx";

function formatMoney(n) {
  if (n == null || n === "") return null;
  const x = typeof n === "number" ? n : parseFloat(n);
  if (Number.isNaN(x)) return String(n);
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(x);
}

export default function RecordSurface({ receipt }) {
  if (!receipt) return null;

  const jd = receipt.journalist_dossier;
  const od = receipt.outlet_dossier;
  const abs = receipt.absence_signal;
  const topic = String(receipt.article_topic || "").trim();

  const hasQuoted =
    jd && Array.isArray(jd.quoted_sources) && jd.quoted_sources.length > 0;
  const showJournalist =
    jd &&
    typeof jd === "object" &&
    Object.keys(jd).length > 0 &&
    (Boolean(jd.display_name) || hasQuoted);
  const showOutlet = od && typeof od === "object" && Object.keys(od).length > 0;
  const showAbsence = abs && typeof abs === "object" && (abs.outlets_covering ?? 0) >= 5;
  const propRecords = Array.isArray(receipt.proportionality_records) ? receipt.proportionality_records : [];
  const hasProportionality = propRecords.length > 0;

  if (!showJournalist && !showOutlet && !showAbsence && !hasProportionality) return null;

  return (
    <div className="pe-record-section pe-beat-2">
      <h2 className="pe-record-title">RECORD</h2>

      {showJournalist ? (
        <div>
          <h3 className="pe-record-sub">JOURNALIST</h3>
          {jd.display_name ? (
            <div className="pe-record-row">
              <strong style={{ color: "var(--text-primary)" }}>{jd.display_name}</strong>
              {jd.outlet ? (
                <span style={{ color: "var(--text-muted)" }}> · {jd.outlet}</span>
              ) : null}
            </div>
          ) : hasQuoted ? (
            <div className="pe-record-row" style={{ fontSize: 13, color: "var(--text-muted)" }}>
              Sources named in quotation marks (no byline on file for this pass).
            </div>
          ) : null}
          {jd.display_name ? (
            <div className="pe-record-row">
              {typeof jd.story_count_on_topic === "number"
                ? `${jd.story_count_on_topic} indexed pieces on this topic (approximate; GDELT-assisted).`
                : null}
              {typeof jd.byline_mentions_approx === "number" && jd.byline_mentions_approx > 0 ? (
                <span>
                  {jd.story_count_on_topic != null ? " " : ""}
                  {jd.byline_mentions_approx} byline mentions in a 12-month index window.
                </span>
              ) : null}
            </div>
          ) : null}
          {Array.isArray(jd.beat_history) && jd.beat_history.some((b) => b?.topic) ? (
            <ul style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: 13, color: "var(--text-secondary)" }}>
              {jd.beat_history
                .filter((b) => b?.topic)
                .map((b) => (
                  <li key={b.topic} style={{ marginBottom: 4 }}>
                    {b.topic}
                    {typeof b.approx_article_count === "number" ? ` (~${b.approx_article_count} titles)` : null}
                  </li>
                ))}
            </ul>
          ) : null}
          {jd.display_name && jd.coverage_gap && topic ? (
            <p style={{ margin: "12px 0 0", fontSize: 13, color: "var(--accent-amber)" }}>
              No prior coverage of this topic found in the queried public index for this byline (approximate).
            </p>
          ) : null}
          {Array.isArray(jd.fec_donations) && jd.fec_donations.length > 0 ? (
            <div style={{ marginTop: 12 }}>
              <div className="pe-record-row" style={{ fontSize: 12, color: "var(--text-muted)" }}>
                FEC Schedule A rows (name match — unverified)
              </div>
              {jd.fec_donations.map((row, i) => (
                <div key={i} className="pe-record-receipt-row">
                  {formatMoney(row.amount) ?? "—"} to {row.recipient_committee || "committee unknown"}
                  {row.contribution_date ? ` · ${row.contribution_date}` : ""}
                  <div style={{ marginTop: 4, color: "var(--text-muted)", fontSize: 10 }}>
                    Name match — unverified
                  </div>
                </div>
              ))}
            </div>
          ) : null}
          {hasQuoted ? (
            <div style={{ marginTop: 14 }}>
              <div className="pe-record-row" style={{ fontSize: 12, color: "var(--text-muted)" }}>
                Sources quoted in article — OpenFEC Schedule A (name match — unverified)
              </div>
              {jd.quoted_sources.map((q, i) => (
                <div key={`${q.name}-${i}`} className="pe-record-receipt-row">
                  <strong style={{ color: "var(--text-primary)" }}>{q.name}</strong>
                  {q.fec_match && q.fec_note ? (
                    <div style={{ marginTop: 6 }}>{q.fec_note}</div>
                  ) : (
                    <div style={{ marginTop: 6, color: "var(--text-muted)" }}>No Schedule A rows returned for this name.</div>
                  )}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {showOutlet ? (
        <div>
          <h3 className="pe-record-sub">OUTLET</h3>
          <div className="pe-record-row">
            <strong style={{ color: "var(--text-primary)" }}>{od.outlet || od.domain || "—"}</strong>
            {od.parent_company ? (
              <span style={{ color: "var(--text-secondary)" }}> → {od.parent_company}</span>
            ) : null}
          </div>
          {od.ownership_note ? (
            <p className="pe-record-row" style={{ fontSize: 12 }}>
              {od.ownership_note}
            </p>
          ) : null}
          {od.advertiser_conflict_flag && od.advertiser_conflict_note ? (
            <p style={{ margin: "10px 0 0", fontSize: 13, color: "var(--accent-red)" }}>{od.advertiser_conflict_note}</p>
          ) : null}
          {Array.isArray(od.top_advertisers) && od.top_advertisers.length > 0 ? (
            <ul style={{ margin: "10px 0 0", paddingLeft: 18, fontSize: 12, color: "var(--text-secondary)" }}>
              {od.top_advertisers.map((a, idx) => (
                <li key={`${a.name || "adv"}-${idx}`} style={{ marginBottom: 6 }}>
                  {a.name || "Unknown"}
                  {a.spend_upper_bound_sum_est != null && a.spend_upper_bound_sum_est > 0 ? (
                    <span style={{ color: "var(--text-muted)" }}>
                      {" "}
                      · upper-bound total (Meta political/issue ads): {a.spend_upper_bound_sum_est}
                    </span>
                  ) : a.spend_note ? (
                    <span style={{ color: "var(--text-muted)" }}> · {a.spend_note}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : od.ad_library_status ? (
            <p className="pe-record-row" style={{ fontSize: 12, color: "var(--text-muted)" }}>
              Meta Ad Library: {od.ad_library_status}
            </p>
          ) : null}
        </div>
      ) : null}

      {hasProportionality ? <ProportionalityRecords records={propRecords} outletDossier={od} /> : null}

      {showAbsence ? (
        <div>
          <h3 className="pe-record-sub">ABSENCE</h3>
          <p className="pe-record-row">
            {abs.outlets_covering} outlets appeared in the comparative coverage set for this query.
          </p>
          {abs.sibling_outlet_divergence && od?.parent_company ? (
            <p className="pe-record-row" style={{ color: "var(--text-secondary)" }}>
              Sibling outlets under {od.parent_company} appear in that set; compare those pieces independently.
            </p>
          ) : null}
          {abs.gap_note ? (
            <p className="pe-record-row" style={{ fontSize: 12, color: "var(--text-muted)" }}>
              {abs.gap_note}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
