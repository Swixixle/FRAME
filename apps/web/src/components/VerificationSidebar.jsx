import { useState } from "react";
import { rawJsonUrl } from "../lib/api.js";
import { formatUtc } from "../lib/formatTime.js";

function CopyId({ fullId }) {
  const [done, setDone] = useState(false);
  const short = fullId ? `${fullId.slice(0, 8)}…` : "—";
  const copy = async () => {
    if (!fullId) return;
    try {
      await navigator.clipboard.writeText(fullId);
      setDone(true);
      window.setTimeout(() => setDone(false), 2000);
    } catch {
      /* ignore */
    }
  };
  return (
    <div className="pe-id-row">
      <span title={fullId}>{short}</span>
      <button type="button" className="pe-copy-btn" onClick={copy} aria-label="Copy full id">
        {done ? "✓" : "⎘"}
      </button>
    </div>
  );
}

export default function VerificationSidebar({
  receiptId,
  receiptType,
  signed,
  generatedAt,
  className,
  style,
}) {
  const [openSigned, setOpenSigned] = useState(false);

  return (
    <aside className={className} style={style}>
      <h2>Verification</h2>
      <div className="pe-verify-row">
        <span style={{ color: "var(--text-muted)" }}>Receipt ID</span>
        <div>
          <CopyId fullId={receiptId} />
        </div>
      </div>
      <div className="pe-verify-row">
        <span style={{ color: "var(--text-muted)" }}>Type</span>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>
          {receiptType?.replace(/_/g, " ") || "—"}
        </div>
      </div>
      <div className="pe-verify-row">
        <span style={{ color: "var(--text-muted)" }}>Signed</span>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{signed ? "✓ Yes" : "No"}</div>
      </div>
      <div className="pe-verify-row">
        <span style={{ color: "var(--text-muted)" }}>Timestamp</span>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{formatUtc(generatedAt)}</div>
      </div>
      <div className="pe-sidebar-links">
        <a href={rawJsonUrl(receiptId)} target="_blank" rel="noopener noreferrer">
          View raw JSON ↗
        </a>
        <button type="button" onClick={() => setOpenSigned((v) => !v)}>
          What does &quot;signed&quot; mean?
        </button>
      </div>
      {openSigned ? (
        <div className="pe-signed-drawer">
          PUBLIC EYE hashes the receipt body with JCS (canonical JSON) and signs the digest with Ed25519.
          Anyone can verify the signature using the embedded public key — it proves the payload was not
          altered after signing.
        </div>
      ) : null}
    </aside>
  );
}
