import React from 'react';

import { contentBox, gridStepMm, pageSize, rulerTicks } from '../../paper';

// The sheet, its margins, the grid and the rulers.
//
// Everything is laid out in CSS `mm` -- the same unit the print renderer
// uses -- so an element at 12mm on this page is at 12mm on the PDF. Zoom is
// a transform on the sheet, not a recalculation of positions, which keeps
// the model in millimetres and the screen the only thing that scales.

const Ruler = ({ lengthMm, zoom, axis }) => {
  const { ticks } = rulerTicks(lengthMm, zoom);
  return (
    <div className={`canvas-ruler canvas-ruler-${axis}`} aria-hidden="true">
      {ticks.map(mm => (
        <span key={mm} className="canvas-ruler-tick"
              style={axis === 'x' ? { left: `${mm}mm` } : { top: `${mm}mm` }}>
          <i>{mm}</i>
        </span>
      ))}
    </div>
  );
};

const PageSurface = ({ page, zoom = 1, children, guides, onBackgroundClick }) => {
  const sheet = pageSize(page.size, page.orientation);
  const content = contentBox(page);
  const step = gridStepMm(zoom);

  return (
    <div className="canvas-viewport">
      {/* The rulers scale with the sheet, so a tick always sits over the
          millimetre it names. */}
      <div className="canvas-rulers" style={{ transform: `scale(${zoom})` }}>
        <Ruler lengthMm={sheet.width} zoom={zoom} axis="x" />
        <Ruler lengthMm={sheet.height} zoom={zoom} axis="y" />
      </div>

      <div
        className="canvas-sheet"
        style={{
          width: `${sheet.width}mm`,
          height: `${sheet.height}mm`,
          transform: `scale(${zoom})`,
        }}
        onMouseDown={(event) => {
          if (event.target === event.currentTarget && onBackgroundClick) onBackgroundClick();
        }}
      >
        {/* Grid first, so every element paints over it. */}
        <div
          className="canvas-grid"
          style={{ backgroundSize: `${step}mm ${step}mm` }}
          aria-hidden="true"
        />

        {/* The margin guides. Not a border on the content area -- a guide,
            drawn outside the printable box so it never sits under an
            element the author is trying to place against the margin. */}
        <div
          className="canvas-margins"
          style={{
            left: `${content.x}mm`, top: `${content.y}mm`,
            width: `${content.width}mm`, height: `${content.height}mm`,
          }}
          aria-hidden="true"
        />

        {/* Bands and elements live in the content box, positioned relative
            to it -- the same origin the renderer anchors to. */}
        <div
          className="canvas-content"
          style={{
            left: `${content.x}mm`, top: `${content.y}mm`,
            width: `${content.width}mm`, height: `${content.height}mm`,
          }}
        >
          {children}

          {/* The alignment guide, drawn only while a drag is snapping to
              it -- a line that stays up after the gesture reads as part of
              the design rather than as feedback. */}
          {guides?.x != null && (
            <span className="canvas-guide canvas-guide-x" style={{ left: `${guides.x}mm` }} />
          )}
          {guides?.y != null && (
            <span className="canvas-guide canvas-guide-y" style={{ top: `${guides.y}mm` }} />
          )}
        </div>
      </div>
    </div>
  );
};

export default PageSurface;
