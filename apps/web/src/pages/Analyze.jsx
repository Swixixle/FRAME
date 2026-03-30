import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AnalyzeLoadingOverlay from "../components/AnalyzeLoadingOverlay.jsx";
import Header from "../components/Header.jsx";
import { analyzeArticle } from "../lib/api.js";

export default function Analyze({ onToast }) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [overlay, setOverlay] = useState(false);
  const nav = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    const u = url.trim();
    if (!u || !u.startsWith("http")) {
      onToast?.("Enter a valid article URL.");
      return;
    }
    setBusy(true);
    setOverlay(true);
    try {
      const data = await analyzeArticle(u);
      const id = data.receipt_id || data.report_id;
      if (!id) throw new Error("No investigation id returned.");
      nav(`/i/${id}`);
    } catch (err) {
      onToast?.(err.message || "Analysis failed.");
      setOverlay(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="pe-app">
      <Header />
      <main className="pe-analyze-page">
        <h1>Analyze an article</h1>
        <p style={{ maxWidth: 520, lineHeight: 1.5 }}>
          Paste a public article URL. Reading sources and signing the receipt usually takes one to two minutes.
        </p>
        <form className="pe-analyze-page-form" onSubmit={submit}>
          <input
            type="url"
            placeholder="https://…"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={busy}
            autoComplete="off"
            autoFocus
          />
          <button type="submit" className="pe-btn pe-btn--primary" disabled={busy}>
            {busy ? "…" : "Analyze →"}
          </button>
        </form>
      </main>
      <AnalyzeLoadingOverlay open={overlay} />
    </div>
  );
}
