import { useEffect, useState } from "react";

const MESSAGES = ["Reading sources…", "Extracting claims…", "Signing receipt…"];

export default function AnalyzeLoadingOverlay({ open }) {
  const [i, setI] = useState(0);

  useEffect(() => {
    if (!open) return undefined;
    setI(0);
    const t = window.setInterval(() => {
      setI((x) => (x + 1) % MESSAGES.length);
    }, 4000);
    return () => window.clearInterval(t);
  }, [open]);

  if (!open) return null;

  return (
    <div className="pe-overlay" role="status" aria-live="polite">
      <div className="pe-overlay-wordmark">PUBLIC EYE</div>
      <div className="pe-overlay-bar" />
      <p className="pe-overlay-msg">{MESSAGES[i]}</p>
    </div>
  );
}
