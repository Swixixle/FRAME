import { useEffect, useState } from "react";
import { fetchEntityProfile } from "../lib/api.js";

function ProfileSkeleton() {
  return (
    <div className="pe-sa-skeleton" aria-busy="true" aria-label="Loading entity profile">
      <div className="pe-sa-skel-line pe-sa-skel-w90" />
      <div className="pe-sa-skel-line pe-sa-skel-w70" />
      <div className="pe-sa-skel-line pe-sa-skel-w50" />
    </div>
  );
}

function integrityBadge(integrity) {
  if (!integrity || integrity === "insufficient_data") {
    return { label: "INSUFFICIENT DATA", color: "var(--text-muted)" };
  }
  const m = {
    strong: "var(--accent-cyan)",
    acceptable: "var(--accent-cyan)",
    questionable: "var(--accent-amber)",
    compromised: "var(--accent-red)",
  };
  return { label: integrity.toUpperCase().replace(/_/g, " "), color: m[integrity] || "var(--text-secondary)" };
}

function PolitifactLine({ factcheck }) {
  if (!factcheck || typeof factcheck !== "object") return null;
  const c = factcheck.counts || {};
  const parts = [];
  if (c.false) parts.push(`${c.false} false`);
  if (c.pants_on_fire) parts.push(`${c.pants_on_fire} pants on fire`);
  if (c.mostly_false) parts.push(`${c.mostly_false} mostly false`);
  if (c.half_true) parts.push(`${c.half_true} half true`);
  if (c.mostly_true) parts.push(`${c.mostly_true} mostly true`);
  if (c.true) parts.push(`${c.true} true`);
  if (parts.length === 0) return null;
  return (
    <p className="pe-sa-line">
      PolitiFact (name search): {parts.join(" · ")}
      {typeof factcheck.total === "number" ? ` · ${factcheck.total} rated statements` : null}
      {factcheck.false_rate != null ? ` · false-ish rate ${(factcheck.false_rate * 100).toFixed(0)}%` : null}
    </p>
  );
}

export default function SourcesAndActors({ receipt }) {
  const [jProf, setJProf] = useState(null);
  const [oProf, setOProf] = useState(null);

  const jSlug = receipt?.journalist_entity_slug;
  const oSlug = receipt?.outlet_entity_slug;
  const jd = receipt?.journalist_dossier;
  const od = receipt?.outlet_dossier;
  const art = receipt?.article;

  useEffect(() => {
    if (!jSlug) {
      setJProf(null);
      return undefined;
    }
    let cancel = false;
    let timer;
    const tick = async () => {
      try {
        const p = await fetchEntityProfile(jSlug);
        if (cancel) return;
        setJProf(p && typeof p === "object" ? p : { status: "pending", entity_slug: jSlug });
        if (p?.status === "pending") timer = setTimeout(tick, 2500);
      } catch {
        if (!cancel) {
          setJProf({ status: "pending", entity_slug: jSlug });
          timer = setTimeout(tick, 4000);
        }
      }
    };
    setJProf({ status: "pending", entity_slug: jSlug });
    tick();
    return () => {
      cancel = true;
      if (timer) clearTimeout(timer);
    };
  }, [jSlug]);

  useEffect(() => {
    if (!oSlug) {
      setOProf(null);
      return undefined;
    }
    let cancel = false;
    let timer;
    const tick = async () => {
      try {
        const p = await fetchEntityProfile(oSlug);
        if (cancel) return;
        setOProf(p && typeof p === "object" ? p : { status: "pending", entity_slug: oSlug });
        if (p?.status === "pending") timer = setTimeout(tick, 2500);
      } catch {
        if (!cancel) {
          setOProf({ status: "pending", entity_slug: oSlug });
          timer = setTimeout(tick, 4000);
        }
      }
    };
    setOProf({ status: "pending", entity_slug: oSlug });
    tick();
    return () => {
      cancel = true;
      if (timer) clearTimeout(timer);
    };
  }, [oSlug]);

  const showAuthor =
    Boolean(art?.author || jd?.display_name || jSlug || (jd && Object.keys(jd).length > 0));
  const showOutlet = Boolean(od && Object.keys(od).length > 0) || Boolean(oSlug || art?.publication);

  if (!showAuthor && !showOutlet) return null;

  const authorName = jd?.display_name || art?.author || "Unknown byline";
  const outletName = od?.outlet || od?.domain || art?.publication || "Outlet";

  const jReady = jProf?.status === "ready";
  const oReady = oProf?.status === "ready";
  const jPending = Boolean(jSlug && jProf?.status === "pending");
  const oPending = Boolean(oSlug && oProf?.status === "pending");
  const jBadge = integrityBadge(jReady ? jProf?.overall_integrity : null);
  const oBadge = integrityBadge(oReady ? oProf?.overall_integrity : null);

  return (
    <section className="pe-sa-section pe-beat-2">
      <h2 className="pe-record-title">SOURCES &amp; ACTORS</h2>

      {showAuthor ? (
        <div className="pe-sa-block">
          <div className="pe-sa-header">
            <span className="pe-sa-role">AUTHOR</span>
            <span className="pe-sa-name">{authorName}</span>
            {jReady && jProf?.overall_integrity ? (
              <span className="pe-sa-badge" style={{ color: jBadge.color }}>
                ● {jBadge.label}
              </span>
            ) : null}
          </div>
          {jPending ? <ProfileSkeleton /> : null}
          {jReady && jProf?.generated_headline ? (
            <p className="pe-sa-headline">{jProf.generated_headline}</p>
          ) : null}
          {jReady && jProf?.the_gap ? <p className="pe-sa-gap">{jProf.the_gap}</p> : null}
          {jReady ? <PolitifactLine factcheck={jProf?.factcheck_json} /> : null}
          {!jReady && jd?.fec_donations?.length ? (
            <p className="pe-sa-line muted">
              {jd.fec_donations.length} OpenFEC Schedule A row(s) on this pass (name match — unverified).
            </p>
          ) : null}
          {jSlug ? (
            <p className="pe-sa-meta">
              Entity slug: <code className="pe-sa-code">{jSlug}</code> — profile updates after investigations
              accumulate.
            </p>
          ) : null}
        </div>
      ) : null}

      {showOutlet ? (
        <div className="pe-sa-block">
          <div className="pe-sa-header">
            <span className="pe-sa-role">OUTLET</span>
            <span className="pe-sa-name">{outletName}</span>
            {oReady && oProf?.overall_integrity ? (
              <span className="pe-sa-badge" style={{ color: oBadge.color }}>
                ● {oBadge.label}
              </span>
            ) : null}
          </div>
          {oPending ? <ProfileSkeleton /> : null}
          {od?.parent_company ? (
            <p className="pe-sa-line">
              Parent: <strong>{od.parent_company}</strong>
            </p>
          ) : null}
          {oReady && oProf?.generated_headline ? (
            <p className="pe-sa-headline">{oProf.generated_headline}</p>
          ) : null}
          {oReady && oProf?.the_gap ? <p className="pe-sa-gap">{oProf.the_gap}</p> : null}
          {od?.advertiser_conflict_flag && od?.advertiser_conflict_note ? (
            <p className="pe-sa-line" style={{ color: "var(--accent-red)" }}>
              {od.advertiser_conflict_note}
            </p>
          ) : null}
          {oSlug ? (
            <p className="pe-sa-meta">
              Entity slug: <code className="pe-sa-code">{oSlug}</code>
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
