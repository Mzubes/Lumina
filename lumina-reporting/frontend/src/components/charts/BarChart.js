import React, { useState } from 'react';

// Horizontal bar chart. Mark spec: <=24px thick bars, rounded data-end /
// square baseline, direct value labels at the tip, hover tooltip per-mark.
// Colors are passed in already validated (see styles.css --c-* tokens).
const BarChart = ({ data, title, unitLabel = 'reports' }) => {
  const [hoverIndex, setHoverIndex] = useState(null);
  const maxValue = Math.max(1, ...data.map(row => row.value));

  return (
    <div className="bar-chart" role="img" aria-label={`${title}: ${data.map(row => `${row.label} ${row.valueLabel ?? row.value}`).join(', ')}`}>
      {data.map((row, index) => {
        const pct = row.value > 0 ? Math.max((row.value / maxValue) * 100, 2) : 0;
        return (
          <div
            className="bar-chart-row"
            key={row.label}
            onMouseEnter={() => setHoverIndex(index)}
            onMouseLeave={() => setHoverIndex(current => (current === index ? null : current))}
          >
            <span className="bar-chart-label">{row.label}</span>
            <div className="bar-chart-track" style={{ background: `color-mix(in srgb, ${row.color} 8%, var(--page-bg-1))` }}>
              <div
                className="bar-chart-bar"
                style={{ width: `${pct}%`, background: `linear-gradient(90deg, color-mix(in srgb, ${row.color} 62%, white), ${row.color})` }}
              />
              {hoverIndex === index && (
                <div className="bar-chart-tooltip" style={{ left: `${Math.min(pct, 92)}%` }}>
                  <strong>{row.label}</strong>
                  <span>{row.value.toLocaleString()} {row.value === 1 ? unitLabel.replace(/s$/, '') : unitLabel}</span>
                </div>
              )}
            </div>
            {/* valueLabel lets a caller carry a unit into the tip label
                ("42.7h"); without one the bare number is the label, as before. */}
            <span className="bar-chart-value">{row.valueLabel ?? row.value}</span>
          </div>
        );
      })}
    </div>
  );
};

export default BarChart;
