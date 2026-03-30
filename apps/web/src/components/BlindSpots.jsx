export default function BlindSpots({ items }) {
  if (!items?.length) return null;
  return (
    <div className="pe-blind-card">
      <h3>What nobody is covering</h3>
      <ul>
        {items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </div>
  );
}
