import { useState } from "react";
import { fetchProportionalityWithGeo } from "../lib/api.js";

const TRIGGER_LABELS = {
  parent_company_legal: "documented legal finding",
  ad_buy: "political advertising",
  journalist_fec: "campaign contribution — name match, unverified",
};

function pick(obj, ...keys) {
  if (!obj || typeof obj !== "object") return null;
  for (const k of keys) {
    if (obj[k] != null && obj[k] !== "") return obj[k];
  }
  return null;
}

function formatMoney(n) {
  if (n == null || n === "") return null;
  const x = typeof n === "number" ? n : parseFloat(n);
  if (Number.isNaN(x)) return String(n);
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(x);
}

function QualifierLine({ record, od }) {
  if (record.trigger === "parent_company_legal") {
    const parent = record.parent_company || record.subject;
    const outlet = record.outlet_name || od?.outlet || "";
    if (!parent) return null;
    return (
      <p className="pe-prop-qualifier">
        This finding applies to {parent}
        {outlet ? `, owner of ${outlet}` : ""}.
      </p>
    );
  }
  if (record.trigger === "journalist_fec") {
    return <p className="pe-prop-qualifier">Individual contribution record — name match only, not verified.</p>;
  }
  if (record.trigger === "ad_buy") {
    return <p className="pe-prop-qualifier">Political advertising spend — documented via Meta Ad Library.</p>;
  }
  return null;
}

function PacketBody({ packet }) {
  if (!packet || typeof packet !== "object") {
    return (
      <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "8px 0 0" }}>
        Proportionality context was not returned for this record.
      </p>
    );
  }

  const applicable = pick(packet, "applicable_law", "applicableLaw");
  const code =
    typeof applicable === "object"
      ? pick(applicable, "code", "statute_code", "statuteCode", "citation")
      : typeof applicable === "string"
        ? applicable
        : null;
  const desc =
    typeof applicable === "object" ? pick(applicable, "description", "title", "summary") : pick(packet, "description");
  const maxPen = pick(packet, "maximum_penalty_years", "maximumPenaltyYears", "maximum_penalty", "max_penalty_years");
  const uscode = pick(packet, "uscode_url", "uscodeUrl", "us_code_url");

  const fc = pick(packet, "for_context", "forContext") || {};
  const compOff = pick(fc, "comparison_offense", "comparisonOffense");
  const medSent = pick(fc, "median_sentence_months", "medianSentenceMonths", "median_federal_sentence_months");
  const medAmt = pick(fc, "median_amount", "medianAmountInvolved", "median_amount_involved");
  const src = pick(fc, "source", "data_source", "dataSource");

  const amtRec = pick(packet, "amount_in_record", "amountInRecord") || {};
  const amtInv =
    pick(amtRec, "amount_involved", "amountInvolved") ?? pick(packet, "amount_involved", "amountInvolved");
  const mult = pick(amtRec, "multiple_of_median", "multipleOfMedian");

  const fac = pick(packet, "nearest_federal_facility", "nearestFederalFacility") || {};
  const facName = pick(fac, "facility_name", "facilityName", "name");
  const dist = pick(fac, "distance_miles", "distanceMiles");
  const sec = pick(fac, "security_level", "securityLevel");
  const pop = pick(fac, "population_total", "populationTotal", "population");
  const bop = pick(fac, "bop_url", "bopUrl", "bureau_of_prisons_url");

  const hasLaw = code || desc || maxPen;
  const hasContext = compOff || medSent != null || medAmt != null || src;
  const hasAmount = amtInv != null || mult != null;
  const hasFac = facName || dist != null;

  if (!hasLaw && !hasContext && !hasAmount && !hasFac) {
    return (
      <pre
        style={{
          marginTop: 10,
          fontSize: 11,
          fontFamily: "var(--font-mono)",
          color: "var(--text-secondary)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {JSON.stringify(packet, null, 2)}
      </pre>
    );
  }

  return (
    <div className="pe-prop-packet">
      {hasLaw ? (
        <div className="pe-prop-block">
          <div className="pe-prop-block-title">APPLICABLE LAW</div>
          {code || desc ? (
            <p className="pe-prop-line">
              {code ? <strong>{code}</strong> : null}
              {code && desc ? " — " : null}
              {desc || null}
            </p>
          ) : null}
          {maxPen != null ? (
            <p className="pe-prop-line">Maximum penalty: {maxPen} years per count</p>
          ) : null}
          {uscode ? (
            <a href={uscode} target="_blank" rel="noopener noreferrer" className="pe-prop-link">
              uscode.house.gov ↗
            </a>
          ) : (
            <a
              href="https://uscode.house.gov/"
              target="_blank"
              rel="noopener noreferrer"
              className="pe-prop-link"
            >
              uscode.house.gov ↗
            </a>
          )}
        </div>
      ) : null}

      {hasContext ? (
        <div className="pe-prop-block">
          <div className="pe-prop-block-title">FOR CONTEXT</div>
          {compOff && medSent != null ? (
            <p className="pe-prop-line">
              Median federal sentence for {compOff}: {medSent} months
            </p>
          ) : compOff ? (
            <p className="pe-prop-line">Comparison offense: {compOff}</p>
          ) : null}
          {medAmt != null ? <p className="pe-prop-line">Median amount involved: {formatMoney(medAmt)}</p> : null}
          {src ? <p className="pe-prop-line muted">— {src}</p> : null}
        </div>
      ) : null}

      {hasAmount ? (
        <div className="pe-prop-block">
          <div className="pe-prop-block-title">AMOUNT IN RECORD</div>
          {amtInv != null ? <p className="pe-prop-line">Amount involved: {formatMoney(amtInv)}</p> : null}
          {mult != null ? <p className="pe-prop-line">≈ {mult}x the median</p> : null}
        </div>
      ) : null}

      {hasFac ? (
        <div className="pe-prop-block">
          <div className="pe-prop-block-title">NEAREST FEDERAL FACILITY</div>
          {facName && dist != null ? (
            <p className="pe-prop-line">
              {facName} · {dist} miles
            </p>
          ) : (
            <p className="pe-prop-line">{facName || `${dist != null ? `${dist} miles` : ""}`}</p>
          )}
          {sec ? <p className="pe-prop-line">Security level: {sec}</p> : null}
          {pop != null ? <p className="pe-prop-line">Population: {pop}</p> : null}
          <a
            href={bop || "https://www.bop.gov/locations/"}
            target="_blank"
            rel="noopener noreferrer"
            className="pe-prop-link"
          >
            Bureau of Prisons ↗
          </a>
        </div>
      ) : null}
    </div>
  );
}

export default function ProportionalityRecords({ records, outletDossier }) {
  const [geoPackets, setGeoPackets] = useState({});

  if (!Array.isArray(records) || records.length === 0) return null;

  const requestGeo = (idx, fetchParams) => {
    if (!fetchParams || typeof fetchParams !== "object" || !navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const pkt = await fetchProportionalityWithGeo({
            ...fetchParams,
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
          });
          if (pkt && typeof pkt === "object") {
            setGeoPackets((g) => ({ ...g, [idx]: pkt }));
          }
        } catch {
          /* silent */
        }
      },
      () => {},
      { maximumAge: 600000, timeout: 10000 },
    );
  };

  return (
    <div>
      <h3 className="pe-record-sub">LEGAL &amp; FINANCIAL RECORD</h3>
      {records.map((rec, idx) => {
        if (!rec || typeof rec !== "object") return null;
        const label = TRIGGER_LABELS[rec.trigger] || rec.trigger || "record";
        const headerSubject = rec.subject || "—";
        const pkt = geoPackets[idx] ?? rec.packet;

        return (
          <div key={`prop-${idx}-${rec.trigger}`} className="pe-prop-record">
            <div className="pe-record-row" style={{ marginBottom: 6 }}>
              <strong style={{ color: "var(--text-primary)" }}>{headerSubject}</strong>
              <span style={{ color: "var(--text-muted)" }}> · {label}</span>
            </div>
            {rec.trigger === "journalist_fec" && rec.fec_match_confidence ? (
              <p className="pe-prop-qualifier" style={{ fontSize: 11 }}>
                Match confidence: {rec.fec_match_confidence}
              </p>
            ) : null}
            <QualifierLine record={rec} od={outletDossier} />
            <PacketBody packet={pkt} />
            {rec.fetch_params ? (
              <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 10 }}>
                <button
                  type="button"
                  className="pe-prop-geo-btn"
                  onClick={() => requestGeo(idx, rec.fetch_params)}
                >
                  Use approximate location for nearest federal facility context
                </button>
              </p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
