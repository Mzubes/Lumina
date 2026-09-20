import React from 'react';

// One element, anchored in millimetres inside its band.
//
// The style here is deliberately the same shape the print template emits
// (`left: 12mm; top: 4mm; width: 40mm; height: 8mm`). Keeping both sides on
// one unit is what makes the canvas WYSIWYG rather than approximately so.

export const ELEMENT_LABELS = {
  text: 'Text', field: 'Field', table: 'Table', chart: 'Chart',
  image: 'Image', line: 'Rule', box: 'Box', page_number: 'Page number',
  people_grid: 'People grid',
};

const preview = (element) => {
  if (element.static_text) return element.static_text;
  if (element.binding_kind === 'system') return `{${element.binding_key}}`;
  if (element.binding_kind === 'display_spec') return 'Bound to a display spec';
  if (element.binding_kind === 'dataset_field') return 'Bound to a field';
  return ELEMENT_LABELS[element.element_type] || element.element_type;
};

const CanvasElement = ({ element, isSelected, onSelect }) => (
  <div
    className={`canvas-el canvas-el-${element.element_type}${isSelected ? ' is-selected' : ''}`}
    style={{
      left: `${element.x_mm}mm`, top: `${element.y_mm}mm`,
      width: `${element.w_mm}mm`, height: `${element.h_mm}mm`,
      zIndex: element.z_index,
    }}
    onMouseDown={(event) => { event.stopPropagation(); if (onSelect) onSelect(element); }}
    role="button"
    tabIndex={0}
    aria-pressed={isSelected}
    aria-label={`${ELEMENT_LABELS[element.element_type] || element.element_type} element`}
  >
    <span className="canvas-el-body">{preview(element)}</span>
  </div>
);

export default CanvasElement;
