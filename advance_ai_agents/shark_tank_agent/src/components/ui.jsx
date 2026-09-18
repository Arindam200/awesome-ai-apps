export function ScorePill({ label, value, active }) {
  return (
    <div className={`score-pill ${active ? "active" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function SegmentedControl({ label, value, options, onChange }) {
  const activeOption = options.find((option) => option.key === value);

  return (
    <div className="segmented-row" aria-label={label}>
      <span title={activeOption?.hint || label}>{label}</span>
      <div>
        {options.map((option) => (
          <button
            key={option.key}
            className={option.key === value ? "active" : ""}
            onClick={() => onChange(option.key)}
            aria-pressed={option.key === value}
            title={option.hint || option.label}
            type="button"
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
