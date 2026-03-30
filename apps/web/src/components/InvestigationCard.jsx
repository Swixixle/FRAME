import { useNavigate } from "react-router-dom";
import { relativeTime } from "../lib/formatTime.js";
import { cardSummaryFromReceipt } from "../lib/investigationMap.js";

export default function InvestigationCard({ receipt, row, loading }) {
  const nav = useNavigate();

  if (loading) {
    return (
      <div className="pe-inv-card" style={{ opacity: 0.6 }}>
        <h3>…</h3>
        <p>Loading…</p>
      </div>
    );
  }

  const id = row?.id || receipt?.receipt_id || receipt?.report_id;
  if (!id) return null;

  const summary = receipt ? cardSummaryFromReceipt(receipt) : { title: row.query || row.source_url || "Investigation", takeaway: row.receipt_type || "", sourceCount: 0, signed: false };

  const onClick = () => nav(`/i/${id}`);

  return (
    <button type="button" className="pe-inv-card" onClick={onClick}>
      <h3>{summary.title}</h3>
      <p>{summary.takeaway}</p>
      <div className="pe-inv-card-meta">
        {summary.sourceCount > 0 ? (
          <span className="pe-pill">{summary.sourceCount} sources</span>
        ) : (
          <span>{row.receipt_type?.replace(/_/g, " ") || "investigation"}</span>
        )}
        {summary.signed ? <span className="pe-pill">✓ Verified</span> : null}
        <span>{relativeTime(row.created_at)}</span>
      </div>
    </button>
  );
}
