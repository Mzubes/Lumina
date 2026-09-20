// A worked template for the canvas, in the shape the backend's layout tree
// uses (schema_v2/templates.py): bands with a layout mode, elements
// anchored in millimetres inside them.
//
// It exists so the canvas is reachable and reviewable before the template
// API lands. Every position here is a real millimetre measurement against
// A4's 178mm content width, so what the canvas shows is what the renderer
// would draw.

export const DEMO_TEMPLATE = {
  name: 'Monthly Factsheet',
  page: { size: 'a4', orientation: 'portrait' },
  sections: [
    {
      ordinal: 0,
      name: 'Masthead',
      layout_mode: 'fixed',
      height_mm: 24,
      repeat_mode: 'every_page',
      elements: [
        { id: 'e1', element_type: 'field', binding_kind: 'system',
          binding_key: 'client_name', x_mm: 0, y_mm: 2, w_mm: 110, h_mm: 7, z_index: 1 },
        { id: 'e2', element_type: 'text', binding_kind: 'none',
          static_text: 'Global Small Cap', x_mm: 0, y_mm: 10, w_mm: 110, h_mm: 6, z_index: 1 },
        { id: 'e3', element_type: 'page_number', binding_kind: 'system',
          binding_key: 'page_number', x_mm: 150, y_mm: 2, w_mm: 28, h_mm: 6, z_index: 1 },
        { id: 'e4', element_type: 'box', binding_kind: 'none',
          x_mm: 0, y_mm: 20, w_mm: 178, h_mm: 1.2, z_index: 0 },
      ],
    },
    {
      ordinal: 1,
      name: 'Commentary',
      layout_mode: 'flow',
      height_mm: null,
      repeat_mode: 'none',
      elements: [
        { id: 'e5', element_type: 'text', binding_kind: 'none',
          static_text: 'Investment approach', x_mm: 0, y_mm: 0, w_mm: 178, h_mm: 7, z_index: 0 },
      ],
    },
    {
      ordinal: 2,
      name: 'Sector Weights',
      layout_mode: 'flow',
      height_mm: null,
      repeat_mode: 'none',
      elements: [
        { id: 'e6', element_type: 'table', binding_kind: 'display_spec',
          display_spec_id: 1, x_mm: 0, y_mm: 0, w_mm: 110, h_mm: 60, z_index: 0 },
        { id: 'e7', element_type: 'chart', binding_kind: 'display_spec',
          display_spec_id: 1, x_mm: 114, y_mm: 0, w_mm: 64, h_mm: 60, z_index: 0 },
      ],
    },
  ],
};

export default DEMO_TEMPLATE;
