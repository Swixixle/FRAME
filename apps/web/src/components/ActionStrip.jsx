import { Link } from "react-router-dom";

export default function ActionStrip({ receiptId }) {
  const permalink = `${window.location.origin}/i/${receiptId}`;

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(permalink);
    } catch {
      /* ignore */
    }
  };

  const compare = () => {
    window.location.href = `/?tab=politics`;
  };

  const seeSources = () => {
    const el = document.getElementById("pe-sources-anchor");
    el?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div className="pe-beat-3" style={{ marginTop: 28, display: "flex", flexWrap: "wrap", gap: 10 }}>
      <button type="button" className="pe-btn" onClick={compare}>
        Compare coverage
      </button>
      <button type="button" className="pe-btn" onClick={seeSources}>
        See sources
      </button>
      <button type="button" className="pe-btn" onClick={copyLink}>
        Copy permalink
      </button>
      <Link to="/analyze" className="pe-btn pe-btn--primary">
        Analyze another →
      </Link>
    </div>
  );
}
