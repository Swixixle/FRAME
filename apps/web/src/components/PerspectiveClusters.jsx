import { useMemo, useState } from "react";

const LABELS = {
  western_anglophone: "Western",
  russian_state: "Russian",
  chinese_state: "Chinese",
  iranian_regional: "Iranian",
  arab_gulf: "Arab Gulf",
  israeli: "Israeli",
  south_asian: "South Asian",
  european: "European",
};

export default function PerspectiveClusters({ globalPerspectives }) {
  const ecosystems = globalPerspectives?.ecosystems || [];
  const [active, setActive] = useState(ecosystems[0]?.id || "");

  const activeEco = useMemo(
    () => ecosystems.find((e) => e.id === active) || ecosystems[0],
    [ecosystems, active],
  );

  if (!ecosystems.length) return null;

  return (
    <section>
      <h2 className="pe-section-title">Global perspectives</h2>
      <div className="pe-clusters">
        <div className="pe-cluster-pills">
          {ecosystems.map((e) => (
            <button
              key={e.id}
              type="button"
              className={`pe-cluster-pill ${active === e.id ? "pe-cluster-pill--active" : ""}`}
              onClick={() => setActive(e.id)}
            >
              {LABELS[e.id] || e.label || e.id}
            </button>
          ))}
        </div>
        {activeEco ? (
          <div className="pe-cluster-body" style={{ maxHeight: 480 }}>
            <p className="pe-outlet-framing" style={{ marginBottom: 12 }}>
              {activeEco.framing}
            </p>
            {(activeEco.outlets || []).length ? (
              <div>
                {(activeEco.outlets || []).map((o) => (
                  <div key={o} className="pe-outlet-row">
                    <div className="pe-outlet-name">{o}</div>
                    <div className="pe-outlet-framing">{activeEco.framing}</div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
