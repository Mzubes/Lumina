import React, { useState } from 'react';

const WIDTH = 600;
const HEIGHT = 200;
const PADDING_X = 8;
const PADDING_TOP = 16;
const PADDING_BOTTOM = 12;

// Smooth single-series trend over time -- one hue, one axis (a second axis
// is the #1 dataviz mistake this deliberately avoids), with a soft gradient
// wash under the line rather than a saturated fill. Crosshair + per-point
// hit targets follow the interaction spec: the vertical hairline tracks the
// pointer and snaps to the nearest week, and the readout leads with the
// value (Strong), the label secondary.
const AreaChart = ({ data, title, color = 'var(--brand)' }) => {
  const [hoverIndex, setHoverIndex] = useState(null);
  const values = data.map(row => row.value);
  const maxValue = Math.max(1, ...values);
  const plotWidth = WIDTH - PADDING_X * 2;
  const plotHeight = HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const stepX = data.length > 1 ? plotWidth / (data.length - 1) : 0;

  const pointX = (index) => PADDING_X + index * stepX;
  const pointY = (value) => PADDING_TOP + plotHeight - (value / maxValue) * plotHeight;

  const linePath = data.reduce((path, row, index) => {
    const x = pointX(index);
    const y = pointY(row.value);
    if (index === 0) return `M ${x} ${y}`;
    const prevX = pointX(index - 1);
    const prevY = pointY(data[index - 1].value);
    const midX = (prevX + x) / 2;
    return `${path} C ${midX} ${prevY}, ${midX} ${y}, ${x} ${y}`;
  }, '');

  const baselineY = PADDING_TOP + plotHeight;
  const areaPath = data.length > 0
    ? `${linePath} L ${pointX(data.length - 1)} ${baselineY} L ${pointX(0)} ${baselineY} Z`
    : '';

  const gradientId = `area-chart-fill-${title.replace(/\s+/g, '-')}`;

  return (
    <div className="area-chart" role="img" aria-label={`${title}: ${data.map(row => `${row.label} ${row.value}`).join(', ')}`}>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="area-chart-svg" preserveAspectRatio="none">
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.22" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 0.25, 0.5, 0.75, 1].map(fraction => (
          <line
            key={fraction} x1={PADDING_X} x2={WIDTH - PADDING_X}
            y1={PADDING_TOP + plotHeight * fraction} y2={PADDING_TOP + plotHeight * fraction}
            className="area-chart-gridline"
          />
        ))}
        <path d={areaPath} fill={`url(#${gradientId})`} stroke="none" />
        <path d={linePath} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {hoverIndex !== null && (
          <line x1={pointX(hoverIndex)} x2={pointX(hoverIndex)} y1={PADDING_TOP} y2={baselineY} className="area-chart-crosshair" />
        )}
        {data.map((row, index) => (
          <circle
            key={row.label} cx={pointX(index)} cy={pointY(row.value)} r={hoverIndex === index ? 5 : 3.5}
            fill={color} stroke="var(--panel-bg)" strokeWidth="2" className="area-chart-dot"
          />
        ))}
        {data.map((row, index) => (
          <rect
            key={`hit-${row.label}`}
            x={pointX(index) - Math.max(stepX, 24) / 2} y={PADDING_TOP} width={Math.max(stepX, 24)} height={plotHeight}
            fill="transparent"
            onMouseEnter={() => setHoverIndex(index)}
            onMouseLeave={() => setHoverIndex(current => (current === index ? null : current))}
            onFocus={() => setHoverIndex(index)}
            onBlur={() => setHoverIndex(current => (current === index ? null : current))}
            tabIndex={0}
          />
        ))}
      </svg>
      <div className="area-chart-labels">
        {data.map(row => <span key={row.label}>{row.label}</span>)}
      </div>
      {hoverIndex !== null && data[hoverIndex] && (
        <div className="area-chart-tooltip" style={{ left: `${(pointX(hoverIndex) / WIDTH) * 100}%` }}>
          <strong>{data[hoverIndex].value.toLocaleString()}</strong>
          <span>{data[hoverIndex].label}</span>
        </div>
      )}
    </div>
  );
};

export default AreaChart;
