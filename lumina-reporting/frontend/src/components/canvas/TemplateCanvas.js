import React, { useMemo, useState } from 'react';

import { ORIENTATIONS, PAGE_SIZES, ZOOM_STEPS, contentBox } from '../../paper';
import CanvasElement, { ELEMENT_LABELS } from './CanvasElement';
import DEMO_TEMPLATE from './demoTemplate';
import PageSurface from './PageSurface';

// E1: the page surface. Bands stack down the content box in ordinal order;
// a fixed band takes its declared height, a flow band takes the height its
// contents need. Elements sit inside their band, anchored in millimetres.
//
// What this does NOT do yet is E2: nothing is draggable, and selection is
// the only interaction. That is deliberate -- the surface has to be right
// in the unit that matters before anything moves on it.

const bandHeightMm = (section) => {
  if (section.layout_mode === 'fixed') return section.height_mm;
  // A flow band's height is its content's. Until a real measurement pass
  // exists, the tallest element's extent stands in for it.
  return Math.max(12, ...section.elements.map(el => el.y_mm + el.h_mm));
};

const TemplateCanvas = () => {
  const [template, setTemplate] = useState(DEMO_TEMPLATE);
  const [zoom, setZoom] = useState(1);
  const [selectedId, setSelectedId] = useState(null);

  const content = contentBox(template.page);
  const bands = useMemo(() => {
    let cursor = 0;
    return [...template.sections].sort((a, b) => a.ordinal - b.ordinal).map(section => {
      const height = bandHeightMm(section);
      const band = { section, top: cursor, height };
      cursor += height + 6;   // the 6mm gutter the print stylesheet uses
      return band;
    });
  }, [template]);

  const overflows = bands.length
    ? bands[bands.length - 1].top + bands[bands.length - 1].height > content.height
    : false;

  const selected = template.sections
    .flatMap(section => section.elements)
    .find(element => element.id === selectedId);

  const setPage = (patch) => setTemplate(current => ({ ...current, page: { ...current.page, ...patch } }));

  return (
    <div className="page">
      <h1>Template canvas</h1>
      <p className="panel-subtitle">
        {template.name} · {PAGE_SIZES[template.page.size].label} {template.page.orientation}
        {' · '}content area {content.width}×{content.height}mm
      </p>

      <div className="canvas-toolbar">
        <label>
          Page size
          <select value={template.page.size} onChange={(e) => setPage({ size: e.target.value })}>
            {Object.entries(PAGE_SIZES).map(([key, size]) => (
              <option key={key} value={key}>{size.label}</option>
            ))}
          </select>
        </label>
        <label>
          Orientation
          <select value={template.page.orientation}
                  onChange={(e) => setPage({ orientation: e.target.value })}>
            {ORIENTATIONS.map(value => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          Zoom
          <select value={zoom} onChange={(e) => setZoom(Number(e.target.value))}>
            {ZOOM_STEPS.map(step => (
              <option key={step} value={step}>{Math.round(step * 100)}%</option>
            ))}
          </select>
        </label>
        {overflows && (
          <span className="canvas-warning" role="status">
            Bands run past the bottom margin — they would break onto a second page.
          </span>
        )}
      </div>

      <div className="canvas-layout">
        <PageSurface page={template.page} zoom={zoom} onBackgroundClick={() => setSelectedId(null)}>
          {bands.map(({ section, top, height }) => (
            <div
              key={section.ordinal}
              className={`canvas-band canvas-band-${section.layout_mode}`}
              style={{ top: `${top}mm`, height: `${height}mm` }}
            >
              <span className="canvas-band-label">
                {section.name}
                {section.repeat_mode !== 'none' && <i> · repeats</i>}
              </span>
              {section.elements.map(element => (
                <CanvasElement
                  key={element.id}
                  element={element}
                  isSelected={element.id === selectedId}
                  onSelect={() => setSelectedId(element.id)}
                />
              ))}
            </div>
          ))}
        </PageSurface>

        <aside className="canvas-outline panel">
          <h2 className="panel-title">Sections</h2>
          <ol className="canvas-outline-list">
            {bands.map(({ section, height }) => (
              <li key={section.ordinal}>
                <strong>{section.name}</strong>
                <span className="panel-subtitle">
                  {section.layout_mode} · {height}mm · {section.elements.length} element
                  {section.elements.length === 1 ? '' : 's'}
                </span>
              </li>
            ))}
          </ol>

          <h2 className="panel-title">Selection</h2>
          {selected ? (
            <dl className="canvas-props">
              <dt>Type</dt><dd>{ELEMENT_LABELS[selected.element_type]}</dd>
              <dt>X</dt><dd>{selected.x_mm}mm</dd>
              <dt>Y</dt><dd>{selected.y_mm}mm</dd>
              <dt>Width</dt><dd>{selected.w_mm}mm</dd>
              <dt>Height</dt><dd>{selected.h_mm}mm</dd>
            </dl>
          ) : (
            <p className="panel-subtitle">Nothing selected.</p>
          )}
        </aside>
      </div>
    </div>
  );
};

export default TemplateCanvas;
