import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { ORIENTATIONS, PAGE_SIZES, ZOOM_STEPS, contentBox } from '../../paper';
import CanvasElement, { ELEMENT_LABELS } from './CanvasElement';
import DEMO_TEMPLATE from './demoTemplate';
import PageSurface from './PageSurface';
import useTemplateEditor from './useTemplateEditor';

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
  const editor = useTemplateEditor(DEMO_TEMPLATE);
  const { template, setTemplate, selection, select, setSelection } = editor;
  const [zoom, setZoom] = useState(1);
  const [guides, setGuides] = useState({ x: null, y: null });
  const drag = useRef(null);

  // One pointer gesture, from press to release. Pointer capture keeps the
  // drag alive when the cursor leaves the element -- without it a fast
  // drag drops the box the moment it outruns the pointer.
  const startGesture = useCallback((event, element, kind, handle) => {
    event.stopPropagation();
    event.preventDefault();
    const additive = event.shiftKey;
    const alreadySelected = selection.includes(element.id);
    if (!alreadySelected || additive) select(element.id, additive);

    editor.begin();
    drag.current = {
      kind, handle, x: event.clientX, y: event.clientY,
      gesture: null, alt: event.altKey,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }, [editor, select, selection]);

  useEffect(() => {
    // The gesture needs the selection AFTER the press updated it, so it is
    // created lazily on the first move rather than on pointerdown.
    const onMove = (event) => {
      if (!drag.current) return;
      if (!drag.current.gesture) {
        drag.current.gesture = editor.gesture(zoom, drag.current.kind, drag.current.handle);
      }
      const next = drag.current.gesture.move(
        event.clientX - drag.current.x,
        event.clientY - drag.current.y,
        { snap: !event.altKey },
      );
      setGuides(next || { x: null, y: null });
    };
    const onUp = () => { drag.current = null; setGuides({ x: null, y: null }); };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
  }, [editor, zoom]);

  useEffect(() => {
    const onKey = (event) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName);
      if (typing) return;
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z') {
        event.preventDefault();
        return event.shiftKey ? editor.redo() : editor.undo();
      }
      if (event.key.startsWith('Arrow')) {
        // One history entry per key press, so a held arrow is one undo.
        editor.begin();
        if (editor.nudgeSelection(event.key, event.shiftKey)) event.preventDefault();
      }
      if (event.key === 'Escape') setSelection([]);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [editor, setSelection]);

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

  const selected = selection.length === 1
    ? template.sections.flatMap(section => section.elements)
        .find(element => element.id === selection[0])
    : null;

  const setPage = (patch) => {
    editor.begin();
    setTemplate(current => ({ ...current, page: { ...current.page, ...patch } }));
  };

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
        <span className="canvas-toolbar-actions">
          <button type="button" onClick={editor.undo} disabled={!editor.canUndo}>Undo</button>
          <button type="button" onClick={editor.redo} disabled={!editor.canRedo}>Redo</button>
          <button type="button" onClick={() => editor.changeOrder('front')}
                  disabled={!selection.length}>Bring to front</button>
          <button type="button" onClick={() => editor.changeOrder('back')}
                  disabled={!selection.length}>Send to back</button>
        </span>
        {overflows && (
          <span className="canvas-warning" role="status">
            Bands run past the bottom margin — they would break onto a second page.
          </span>
        )}
      </div>

      <div className="canvas-layout">
        <PageSurface page={template.page} zoom={zoom} guides={guides}
                     onBackgroundClick={() => setSelection([])}>
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
                  isSelected={selection.includes(element.id)}
                  onPointerDown={(event, target) => startGesture(event, target, 'move')}
                  onHandlePointerDown={(event, target, handle) =>
                    startGesture(event, target, 'resize', handle)}
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

          <h2 className="panel-title">
            Selection{selection.length > 1 ? ` · ${selection.length} elements` : ''}
          </h2>
          {selected ? (
            <dl className="canvas-props">
              <dt>Type</dt><dd>{ELEMENT_LABELS[selected.element_type]}</dd>
              <dt>X</dt><dd>{selected.x_mm}mm</dd>
              <dt>Y</dt><dd>{selected.y_mm}mm</dd>
              <dt>Width</dt><dd>{selected.w_mm}mm</dd>
              <dt>Height</dt><dd>{selected.h_mm}mm</dd>
            </dl>
          ) : selection.length > 1 ? (
            <p className="panel-subtitle">
              {selection.length} elements selected — drag to move them together.
            </p>
          ) : (
            <p className="panel-subtitle">
              Nothing selected. Click an element; shift-click to add. Arrow keys nudge,
              shift-arrow nudges finely, Alt suspends snapping.
            </p>
          )}
        </aside>
      </div>
    </div>
  );
};

export default TemplateCanvas;
