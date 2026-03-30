export default function CoalitionMapSkeleton() {
  return (
    <section className="pe-coalition pe-coalition--skeleton" aria-busy="true" aria-label="Building coalition map">
      <div className="pe-coalition-skel-head">
        <span className="pe-coalition-skel-pulse" />
        <span className="pe-coalition-skel-pulse pe-coalition-skel-pulse--short" />
      </div>
      <div className="pe-coalition-skel-grid">
        <div className="pe-coalition-skel-col">
          <span className="pe-coalition-skel-pulse pe-coalition-skel-pulse--bar" />
          {[1, 2, 3, 4].map((k) => (
            <div key={k} className="pe-coalition-skel-row">
              <span className="pe-coalition-skel-dot" />
              <span className="pe-coalition-skel-pulse pe-coalition-skel-pulse--line" />
            </div>
          ))}
        </div>
        <div className="pe-coalition-skel-col">
          <span className="pe-coalition-skel-pulse pe-coalition-skel-pulse--bar" />
          {[1, 2, 3, 4].map((k) => (
            <div key={k} className="pe-coalition-skel-row">
              <span className="pe-coalition-skel-dot" />
              <span className="pe-coalition-skel-pulse pe-coalition-skel-pulse--line" />
            </div>
          ))}
        </div>
      </div>
      <p className="pe-coalition-skel-caption">Building coalition map…</p>
    </section>
  );
}
