import { useCallback, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import Landing from "./pages/Landing.jsx";
import Analyze from "./pages/Analyze.jsx";
import Investigation from "./pages/Investigation.jsx";

function ReceiptRedirect() {
  const { receipt_id: receiptId } = useParams();
  return <Navigate to={`/i/${receiptId}`} replace />;
}

function AppShell() {
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (!toast) return undefined;
    const id = window.setTimeout(() => setToast(null), 5000);
    return () => window.clearTimeout(id);
  }, [toast]);

  const onToast = useCallback((msg) => {
    setToast(typeof msg === "string" && msg.trim() ? msg.trim() : "Something went wrong.");
  }, []);

  return (
    <>
      <Routes>
        <Route path="/" element={<Landing onToast={onToast} />} />
        <Route path="/analyze" element={<Analyze onToast={onToast} />} />
        <Route path="/i/:receipt_id" element={<Investigation onToast={onToast} />} />
        <Route path="/r/:receipt_id" element={<ReceiptRedirect />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      {toast ? (
        <div className="pe-toast" role="status">
          {toast}
        </div>
      ) : null}
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}
