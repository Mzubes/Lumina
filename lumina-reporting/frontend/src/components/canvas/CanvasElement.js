import React from 'react';

import { HANDLES } from '../../canvasGeometry';
import { EMPTY_CATALOGUE, previewFor } from '../../bindings';
import { elementClasses } from '../../elementStyles';

// One element, anchored in millimetres inside its band.
//
// The style is the same shape the print template emits
// (`left: 12mm; top: 4mm; width: 40mm; height: 8mm`). Keeping both sides on
// one unit is what makes the canvas WYSIWYG rather than approximately so.

export const ELEMENT_LABELS = {
  text: 'Text', field: 'Field', table: 'Table', chart: 'Chart',
  image: 'Image', line: 'Rule', box: 'Box', page_number: 'Page number',
  people_grid: 'People grid',
};

const CanvasElement = ({
  element, isSelected, catalogue = EMPTY_CATALOGUE, onPointerDown, onHandlePointerDown,
}) => {
  // What this element would actually draw. A bound element shows the value
  // from the catalogue rather than the word "bound", which is the whole
  // point of E4: an author lays out against the real string length.
  const preview = previewFor(element, catalogue);
  const body = preview.text ?? (ELEMENT_LABELS[element.element_type] || element.element_type);

  return (
    <div
      // The same classes the renderer resolves from this element's token
      // and options -- see elementStyles.js. The canvas's own stylesheet
      // gives them screen equivalents, so a heading looks like a heading
      // here for the same reason it does in the PDF.
      className={[
        'canvas-el', `canvas-el-${element.element_type}`,
        ...elementClasses(element),
        isSelected ? 'is-selected' : '',
        element.is_visible === false ? 'is-hidden' : '',
        preview.missing ? 'is-broken' : '',
        // A derived sample is drawn differently so it cannot be mistaken
        // for a number that came out of the warehouse.
        preview.text && !preview.isReal ? 'is-sample' : '',
      ].filter(Boolean).join(' ')}
      style={{
        left: `${element.x_mm}mm`, top: `${element.y_mm}mm`,
        width: `${element.w_mm}mm`, height: `${element.h_mm}mm`,
        zIndex: element.z_index,
      }}
      onPointerDown={(event) => onPointerDown(event, element)}
      role="button"
      tabIndex={0}
      aria-pressed={isSelected}
      aria-label={`${ELEMENT_LABELS[element.element_type] || element.element_type} element`}
      data-element-id={element.id}
    >
      <span className="canvas-el-body" title={preview.note || undefined}>{body}</span>
      {isSelected && HANDLES.map(handle => (
        <span
          key={handle}
          className={`canvas-handle canvas-handle-${handle}`}
          data-handle={handle}
          onPointerDown={(event) => onHandlePointerDown(event, element, handle)}
          aria-hidden="true"
        />
      ))}
    </div>
  );
};

export default CanvasElement;
