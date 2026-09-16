import React, { useState } from 'react';

const RADIUS = 60;
const STROKE_WIDTH = 22;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
const SEGMENT_GAP = 3; // px, in the surface color -- same spacer idiom as CompositionBar's segment gap

// Ring chart with a center total figure -- a part-to-whole form the bar-first
// dataviz method doesn't reach for by default, but one every reference
// dashboard leaned on for a single total broken into a handful of shares
// (an asset-class or source mix), so it earns a place alongside BarChart/
// CompositionBar for that specific "here's the whole, here's the split" job.
const DonutChart = ({ data, title, centerLabel = 'Total' }) => {
  const [hoverIndex, setHoverIndex] = useState(null);
  const segments = data.filter(row => row.value > 0);
  const total = segments.reduce((sum, row) => sum + row.value, 0);

  if (total === 0) {
    return <p className="donut-chart-empty panel-subtitle">No data yet.</p>;
  }

  let offsetSoFar = 0;

  return (
    <div className="donut-chart" role="img" aria-label={`${title}: ${segments.map(row => `${row.label} ${row.value}`).join(', ')}`}>
      <div className="donut-chart-ring-wrap">
        <svg viewBox="0 0 160 160" className="donut-chart-svg">
          <circle cx="80" cy="80" r={RADIUS} fill="none" stroke="var(--page-bg-1)" strokeWidth={STROKE_WIDTH} />
          <g transform="rotate(-90 80 80)">
            {segments.map((row, index) => {
              const rawLength = (row.value / total) * CIRCUMFERENCE;
              const dashOffset = -offsetSoFar;
              offsetSoFar += rawLength;
              return (
                <circle
                  key={row.label}
                  cx="80" cy="80" r={RADIUS} fill="none"
                  stroke={row.color}
                  strokeWidth={hoverIndex === index ? STROKE_WIDTH + 4 : STROKE_WIDTH}
                  strokeDasharray={`${Math.max(rawLength - SEGMENT_GAP, 0)} ${CIRCUMFERENCE}`}
                  strokeDashoffset={dashOffset}
                  className="donut-chart-segment"
                  style={{ opacity: hoverIndex === null || hoverIndex === index ? 1 : 0.45 }}
                  onMouseEnter={() => setHoverIndex(index)}
                  onMouseLeave={() => setHoverIndex(current => (current === index ? null : current))}
                />
              );
            })}
          </g>
        </svg>
        <div className="donut-chart-center">
          <strong>{total.toLocaleString()}</strong>
          <span>{centerLabel}</span>
        </div>
      </div>
      <ul className="donut-chart-legend">
        {segments.map((row, index) => (
          <li
            key={row.label}
            className={hoverIndex === index ? 'is-hovered' : ''}
            onMouseEnter={() => setHoverIndex(index)}
            onMouseLeave={() => setHoverIndex(current => (current === index ? null : current))}
          >
            <span className="donut-chart-swatch" style={{ background: row.color }} />
            <span className="donut-chart-legend-label">{row.label}</span>
            <span className="donut-chart-legend-value">{row.value.toLocaleString()} · {Math.round((row.value / total) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default DonutChart;
