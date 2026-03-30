import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import AnalyzeBar from "../components/AnalyzeBar.jsx";
import AnalyzeLoadingOverlay from "../components/AnalyzeLoadingOverlay.jsx";
import Header from "../components/Header.jsx";
import HeroCard from "../components/HeroCard.jsx";
import InvestigationCard from "../components/InvestigationCard.jsx";
import { fetchReceipt, fetchRecentReceipts } from "../lib/api.js";

export default function Landing({ onToast }) {
  const [search] = useSearchParams();
  const tab = search.get("tab") || "politics";
  const [rows, setRows] = useState([]);
  const [heroReceipt, setHeroReceipt] = useState(null);
  const [byId, setById] = useState({});
  const [gridReady, setGridReady] = useState(false);
  const [loadOverlay, setLoadOverlay] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setGridReady(false);
        const list = await fetchRecentReceipts(14);
        if (cancelled) return;
        setRows(list);
        const firstId = list[0]?.id;
        if (firstId) {
          try {
            const full = await fetchReceipt(firstId);
            if (!cancelled && full) setHeroReceipt(full);
          } catch {
            if (!cancelled) setHeroReceipt(null);
          }
        } else {
          setHeroReceipt(null);
        }
        const top = list.slice(0, 8).filter((r) => r.id);
        const settled = await Promise.all(
          top.map(async (r) => {
            try {
              const full = await fetchReceipt(r.id);
              return [r.id, full];
            } catch {
              return [r.id, null];
            }
          }),
        );
        if (cancelled) return;
        const next = {};
        for (const [id, full] of settled) {
          if (full) next[id] = full;
        }
        setById(next);
        setGridReady(true);
      } catch (e) {
        onToast?.(e.message || "Could not load investigations.");
        setGridReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [onToast]);

  return (
    <div className="pe-app">
      <Header />
      <main className="pe-landing">
        <HeroCard receipt={heroReceipt} tabKey={tab} />
        <h2 className="pe-section-title" style={{ marginBottom: 16 }}>
          Recent investigations
        </h2>
        <div className="pe-grid">
          {rows.map((row) => (
            <InvestigationCard key={row.id} row={row} receipt={byId[row.id]} loading={!gridReady} />
          ))}
        </div>
      </main>
      <AnalyzeBar
        onStart={() => setLoadOverlay(true)}
        onError={(msg) => {
          setLoadOverlay(false);
          onToast?.(msg);
        }}
      />
      <AnalyzeLoadingOverlay open={loadOverlay} />
    </div>
  );
}
