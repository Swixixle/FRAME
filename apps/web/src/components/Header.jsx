import { Link, useSearchParams } from "react-router-dom";

const TABS = [
  { key: "politics", label: "Politics" },
  { key: "culture", label: "Culture" },
  { key: "everything", label: "Everything Else" },
];

export default function Header() {
  const [search] = useSearchParams();
  const tab = search.get("tab") || "politics";

  return (
    <header className="pe-header">
      <Link to="/" className="pe-wordmark">
        PUBLIC EYE
      </Link>
      <nav className="pe-header-tabs" aria-label="Sections">
        {TABS.map((t) => (
          <Link
            key={t.key}
            to={`/?tab=${t.key}`}
            className={`pe-header-tab ${tab === t.key ? "pe-header-tab--active" : ""}`}
          >
            {t.label}
          </Link>
        ))}
        <a href="/verify" className="pe-header-tab" style={{ marginLeft: 8 }}>
          Verify
        </a>
      </nav>
    </header>
  );
}
