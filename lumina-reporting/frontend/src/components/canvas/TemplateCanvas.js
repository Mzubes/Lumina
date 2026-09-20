import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { ORIENTATIONS, PAGE_SIZES, ZOOM_STEPS, contentBox } from '../../paper';
import {
  createTemplate, isDemoMode, listTemplates, loadTemplate, newVersion,
  publishTemplate, saveTemplate, toApiTemplate,
} from '../../templateApi';
import CanvasElement from './CanvasElement';
import Inspector from './Inspector';
import DEMO_TEMPLATE from './demoTemplate';
import PageSurface from './PageSurface';
import useTemplateEditor from './useTemplateEditor';

// The page surface (E1) with direct manipulation (E2), over the template
// API. Bands stack down the content box in ordinal order; a fixed band
// takes its declared height, a flow band takes the height its contents
// need. Elements sit inside their band, anchored in millimetres.
//
// **A save replaces the tree.** The API does not diff, so it hands back new
// row ids and this loads the response rather than keeping what was on
// screen. That is what makes "what I see" and "what was stored" the same
// thing after every save, including when the server normalised something.
//
// Demo mode (no API configured) keeps the worked example in component
// state and hides the save controls, so the canvas is still reviewable
// without a backend.

const bandHeightMm = (section) => {
  if (section.layout_mode === 'fixed') return section.height_mm;
  // A flow band's height is its content's. Until a real measurement pass
  // exists, the tallest element's extent stands in for it.
  return Math.max(12, ...section.elements.map(el => el.y_mm + el.h_mm));
};

// What the server holds, as a comparable string. Built from the same
// converter the save uses, so "dirty" means "a save would change
// something" rather than "some object identity changed".
const fingerprint = (template) => JSON.stringify(toApiTemplate(template));

const TemplateCanvas = () => {
  const editor = useTemplateEditor(DEMO_TEMPLATE);
  const { template, setTemplate, load, selection, select, setSelection } = editor;
  const [zoom, setZoom] = useState(1);
  const [guides, setGuides] = useState({ x: null, y: null });
  const drag = useRef(null);

  const [catalogue, setCatalogue] = useState([]);
  const [saved, setSaved] = useState(null);
  const [busy, setBusy] = useState(!isDemoMode);
  const [error, setError] = useState('');

  const adopt = useCallback((loaded) => {
    load(loaded);
    setSaved(fingerprint(loaded));
  }, [load]);

  const open = useCallback(async (id) => {
    setBusy(true);
    setError('');
    try {
      adopt(await loadTemplate(id));
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }, [adopt]);

  useEffect(() => {
    if (isDemoMode) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const list = await listTemplates();
        if (cancelled) return;
        setCatalogue(list);
        if (list.length) adopt(await loadTemplate(list[0].id));
      } catch (failure) {
        if (!cancelled) setError(failure.message);
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => { cancelled = true; };
  }, [adopt]);

  // `saved === null` means nothing has been stored yet -- an unsaved worked
  // example, which is dirty by definition.
  const dirty = !isDemoMode && (saved === null || saved !== fingerprint(template));

  const run = useCallback(async (work) => {
    setBusy(true);
    setError('');
    try {
      adopt(await work());
      setCatalogue(await listTemplates());
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }, [adopt]);

  const onSave = () => run(() => (
    template.id ? saveTemplate(template.id, template) : createTemplate(template)));

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

  // Which band the inspector edits when nothing is selected: the one
  // holding the last selected element, else the first. A properties pane
  // that shows nothing at rest wastes the panel it sits in.
  const [bandOrdinal, setBandOrdinal] = useState(0);
  const activeSection = useMemo(() => {
    const owning = template.sections.find(
      section => section.elements.some(element => selection.includes(element.id)));
    return owning
      || template.sections.find(section => section.ordinal === bandOrdinal)
      || template.sections[0]
      || null;
  }, [template.sections, selection, bandOrdinal]);

  const setPage = (patch) => {
    editor.begin();
    setTemplate(current => ({ ...current, page: { ...current.page, ...patch } }));
  };

  return (
    <div className="page">
      <h1>Template canvas</h1>
      <p className="panel-subtitle">
        {template.name}
        {template.version ? ` · v${template.version}` : ''}
        {' · '}{PAGE_SIZES[template.page.size].label} {template.page.orientation}
        {' · '}content area {content.width}×{content.height}mm
        {isDemoMode && ' · demo data, nothing is saved'}
      </p>

      {error && <p className="alert-banner" role="alert">{error}</p>}

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
        {!isDemoMode && catalogue.length > 0 && (
          <label>
            Template
            <select value={template.id || ''} disabled={busy}
                    onChange={(e) => open(Number(e.target.value))}>
              {!template.id && <option value="">Unsaved draft</option>}
              {catalogue.map(item => (
                <option key={item.id} value={item.id}>
                  {item.name} · v{item.version}{item.is_published ? ' (published)' : ''}
                </option>
              ))}
            </select>
          </label>
        )}
        <span className="canvas-toolbar-actions">
          <button type="button" onClick={editor.undo} disabled={!editor.canUndo}>Undo</button>
          <button type="button" onClick={editor.redo} disabled={!editor.canRedo}>Redo</button>
          <button type="button" onClick={() => editor.changeOrder('front')}
                  disabled={!selection.length}>Bring to front</button>
          <button type="button" onClick={() => editor.changeOrder('back')}
                  disabled={!selection.length}>Send to back</button>
        </span>
        {!isDemoMode && (
          <span className="canvas-toolbar-actions">
            {template.is_published ? (
              // A published template is what distributed packs rendered
              // from, so it is not editable in place -- the only forward
              // move is a new version.
              <button type="button" className="btn-primary" disabled={busy}
                      onClick={() => run(() => newVersion(template.id))}>
                New version
              </button>
            ) : (
              <>
                <button type="button" className="btn-primary" disabled={busy || !dirty}
                        onClick={onSave}>
                  {template.id ? 'Save' : 'Save as new template'}
                </button>
                <button type="button" disabled={busy || dirty || !template.id}
                        onClick={() => run(() => publishTemplate(template.id))}>
                  Publish
                </button>
              </>
            )}
            <span className="panel-subtitle" role="status">
              {busy ? 'Working…'
                : template.is_published ? 'Published — read only'
                : dirty ? 'Unsaved changes'
                : 'Saved'}
            </span>
          </span>
        )}
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
                <button
                  type="button"
                  className={`canvas-outline-band${
                    activeSection && activeSection.ordinal === section.ordinal
                      ? ' is-active' : ''}`}
                  onClick={() => { setSelection([]); setBandOrdinal(section.ordinal); }}
                >
                  <strong>{section.name || `Band ${section.ordinal + 1}`}</strong>
                  <span className="panel-subtitle">
                    {section.layout_mode} · {height}mm · {section.elements.length} element
                    {section.elements.length === 1 ? '' : 's'}
                  </span>
                </button>
              </li>
            ))}
          </ol>

          <Inspector editor={editor} section={activeSection} />

          <p className="panel-subtitle canvas-hint">
            Click an element; shift-click to add. Arrow keys nudge, shift-arrow
            nudges finely, Alt suspends snapping.
          </p>
        </aside>
      </div>
    </div>
  );
};

export default TemplateCanvas;
