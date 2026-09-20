import { useCallback, useMemo, useRef, useState } from 'react';

import { moveBox, nudge, reorder, resizeBox } from '../../canvasGeometry';
import { contentBox, gridStepMm, pxToMm, roundMm } from '../../paper';

// The canvas's state: the template, what is selected, and the undo stack.
//
// History takes a snapshot at the START of a gesture rather than on every
// pointer move. A drag is one undo step, which is what an author means by
// "undo that" -- recording every intermediate position would make Ctrl-Z
// replay the drag frame by frame.

const MAX_HISTORY = 50;

export const useTemplateEditor = (initial) => {
  const [template, setTemplate] = useState(initial);
  const [selection, setSelection] = useState([]);
  const past = useRef([]);
  const future = useRef([]);
  const [depth, setDepth] = useState({ past: 0, future: 0 });

  const sync = () => setDepth({ past: past.current.length, future: future.current.length });

  // Call once at the start of a gesture; everything until the next begin()
  // collapses into one undo step.
  const begin = useCallback(() => {
    past.current = [...past.current.slice(-(MAX_HISTORY - 1)), template];
    future.current = [];
    sync();
  }, [template]);

  const undo = useCallback(() => {
    if (!past.current.length) return;
    const previous = past.current[past.current.length - 1];
    past.current = past.current.slice(0, -1);
    setTemplate(current => { future.current = [current, ...future.current]; return previous; });
    sync();
  }, []);

  const redo = useCallback(() => {
    if (!future.current.length) return;
    const [next, ...rest] = future.current;
    future.current = rest;
    setTemplate(current => { past.current = [...past.current, current]; return next; });
    sync();
  }, []);

  const bounds = useMemo(() => {
    const box = contentBox(template.page);
    return { width: box.width, height: box.height };
  }, [template.page]);

  const elementsById = useMemo(() => {
    const map = new Map();
    for (const section of template.sections) {
      for (const element of section.elements) map.set(element.id, { element, section });
    }
    return map;
  }, [template]);

  const patchElements = useCallback((changes) => {
    setTemplate(current => ({
      ...current,
      sections: current.sections.map(section => ({
        ...section,
        elements: section.elements.map(element =>
          (changes.has(element.id) ? { ...element, ...changes.get(element.id) } : element)),
      })),
    }));
  }, []);

  const select = useCallback((id, additive = false) => {
    setSelection(current => {
      if (!additive) return id ? [id] : [];
      return current.includes(id) ? current.filter(item => item !== id) : [...current, id];
    });
  }, []);

  // A gesture converts pixel deltas to millimetres ONCE, here, dividing by
  // the zoom. Nothing downstream sees pixels, so nothing downstream can be
  // wrong about the scale.
  const gesture = useCallback((zoom, kind, handle) => {
    const startBoxes = new Map(
      selection.map(id => [id, { ...elementsById.get(id).element }]).filter(([, box]) => box));
    let guides = { x: null, y: null };

    return {
      move(dxPx, dyPx, { snap = true } = {}) {
        const dx = pxToMm(dxPx, zoom);
        const dy = pxToMm(dyPx, zoom);
        const gridMm = snap ? gridStepMm(zoom) : 0;
        const changes = new Map();
        for (const [id, start] of startBoxes) {
          const others = [...elementsById.values()]
            .map(entry => entry.element)
            .filter(element => !startBoxes.has(element.id));
          if (kind === 'resize') {
            changes.set(id, resizeBox(start, handle, dx, dy, { bounds, gridMm, snap }));
          } else {
            const result = moveBox(start, dx, dy, { bounds, others, gridMm, snap });
            guides = result.guides;
            changes.set(id, result.box);
          }
        }
        patchElements(changes);
        return guides;
      },
    };
  }, [selection, elementsById, bounds, patchElements]);

  const nudgeSelection = useCallback((key, fine) => {
    if (!selection.length) return false;
    const changes = new Map();
    for (const id of selection) {
      const { element } = elementsById.get(id) || {};
      if (element) changes.set(id, nudge(element, key, { bounds, gridMm: 5, fine }));
    }
    if (!changes.size) return false;
    patchElements(changes);
    return true;
  }, [selection, elementsById, bounds, patchElements]);

  const changeOrder = useCallback((direction) => {
    const changes = new Map();
    for (const id of selection) {
      const entry = elementsById.get(id);
      if (entry) {
        changes.set(id, { z_index: reorder(entry.element, entry.section.elements, direction) });
      }
    }
    if (changes.size) patchElements(changes);
  }, [selection, elementsById, patchElements]);

  const setElement = useCallback((id, patch) => {
    patchElements(new Map([[id, patch]]));
  }, [patchElements]);

  return {
    template, setTemplate, bounds, elementsById,
    selection, select, setSelection,
    begin, undo, redo, canUndo: depth.past > 0, canRedo: depth.future > 0,
    gesture, nudgeSelection, changeOrder, setElement, roundMm,
  };
};

export default useTemplateEditor;
