import React, { useState } from 'react';

// Part-to-whole rides on a stacked bar, not a donut (dataviz skill: donut
// stays deprioritized). Single horizontal bar, segments sized by flex-grow
// so they always sum to exactly 100% of the track; a 2px surface-color gap
// (via margin) separates touching segments instead of a border.
const CompositionBar = ({ data, title, unitLabel = 'reports' }) => {
  const [hoverIndex, setHoverIndex] = useState(null);
  const segments = data.filter(row => row.value > 0);
  const total = segments.reduce((sum, row) => sum + row.value, 0);

  if (total === 0) {
    return (
      <div className="composition-bar">
        <div className="composition-bar-track composition-bar-empty" />
        <p className="composition-bar-empty-label">No data yet.</p>
      </div>
    );
  }

  return (
    <div className="composition-bar" role="img" aria-label={`${title}: ${segments.map(row => `${row.label} ${row.value}`).join(', ')}`}>
      <div className="composition-bar-track">
        {segments.map((row, index) => (
          <div
            key={row.label}
            className={`composition-bar-segment ${hoverIndex === index ? 'is-hovered' : ''}`}
            style={{ flexGrow: row.value, background: row.color }}
            onMouseEnter={() => setHoverIndex(index)}
            onMouseLeave={() => setHoverIndex(current => (current === index ? null : current))}
          >
            {hoverIndex === index && (
              <div className="composition-bar-tooltip">
                <strong>{row.value.toLocaleString()} {row.value === 1 ? unitLabel.replace(/s$/, '') : unitLabel}</strong>
                <span>{row.label} · {Math.round((row.value / total) * 100)}%</span>
              </div>
            )}
          </div>
        ))}
      </div>
      <ul className="composition-bar-legend">
        {segments.map((row, index) => (
          <li
            key={row.label}
            className={hoverIndex === index ? 'is-hovered' : ''}
            onMouseEnter={() => setHoverIndex(index)}
            onMouseLeave={() => setHoverIndex(current => (current === index ? null : current))}
          >
            <span className="composition-bar-swatch" style={{ background: row.color }} />
            <span className="composition-bar-legend-label">{row.label}</span>
            <span className="composition-bar-legend-value">{row.value.toLocaleString()} · {Math.round((row.value / total) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default CompositionBar;
