import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { analyzeArticle } from "../lib/api.js";

export default function AnalyzeBar({ onStart, onError }) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();

  const submit = async (e) => {
    e?.preventDefault();
    const u = url.trim();
    if (!u || !u.startsWith("http")) {
      onError?.("Enter a valid article URL.");
      return;
    }
    setBusy(true);
    onStart?.();
    try {
      const data = await analyzeArticle(u);
      const id = data.receipt_id || data.report_id;
      if (!id) throw new Error("No investigation id returned.");
      nav(`/i/${id}`);
    } catch (err) {
      onError?.(err.message || "Analysis failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="pe-analyze-bar">
      <form className="pe-analyze-bar-inner" onSubmit={submit}>
        <input
          type="url"
          placeholder="Paste any article URL here…"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={busy}
          autoComplete="off"
        />
        <button type="submit" className="pe-btn pe-btn--primary" disabled={busy}>
          {busy ? "…" : "Analyze →"}
        </button>
      </form>
    </div>
  );
}
