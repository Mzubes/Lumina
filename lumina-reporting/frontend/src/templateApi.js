// The canvas's half of the template API.
//
// The two shapes are deliberately the same shape: `GET
// /api/document-templates/<id>` returns exactly the tree the canvas edits
// and the renderer draws, so there is no translation layer here -- only the
// defaults the canvas does not track (margins, break rules) and the id
// bookkeeping a wholesale save forces.
//
// **Element ids are not stable across a save.** The API replaces a
// template's bands and elements rather than diffing them, so it hands back
// new row ids. Everything here therefore treats the save response as the
// new truth rather than trying to keep the pre-save ids alive.

import { apiFetch, isDemoMode } from './api';
import { DEFAULT_MARGINS_MM, roundMm } from './paper';

const TEMPLATES = '/api/document-templates';

// What the canvas leaves unset. Sent explicitly rather than relying on the
// server's defaults, so a template that round-trips through the canvas
// cannot quietly pick up a different page box than the one on screen.
const sectionDefaults = {
  layout_mode: 'flow',
  height_mm: null,
  repeat_mode: 'none',
  break_before: 'auto',
  break_after: 'auto',
  iterate_display_spec_id: null,
};

const toApiElement = (element) => ({
  element_type: element.element_type,
  x_mm: roundMm(element.x_mm),
  y_mm: roundMm(element.y_mm),
  w_mm: roundMm(element.w_mm),
  h_mm: roundMm(element.h_mm),
  z_index: element.z_index || 0,
  binding_kind: element.binding_kind || 'none',
  dataset_field_id: element.dataset_field_id ?? null,
  display_spec_id: element.display_spec_id ?? null,
  binding_key: element.binding_key ?? null,
  static_text: element.static_text ?? null,
  style_token: element.style_token ?? null,
  options: element.options ?? null,
  is_visible: element.is_visible !== false,
});

export const toApiTemplate = (template) => ({
  name: template.name,
  code: template.code,
  description: template.description ?? null,
  page: {
    size: template.page.size,
    orientation: template.page.orientation,
    margins: { ...DEFAULT_MARGINS_MM, ...(template.page.margins || {}) },
  },
  sections: template.sections
    .slice()
    .sort((a, b) => a.ordinal - b.ordinal)
    .map((section, index) => ({
      ...sectionDefaults,
      ...section,
      ordinal: index,
      name: section.name ?? null,
      elements: section.elements.map(toApiElement),
    })),
});

// The canvas keys elements by id, so a template with no sections loaded yet
// still needs every element to have one.
export const fromApiTemplate = (payload) => ({
  id: payload.id,
  name: payload.name,
  code: payload.code,
  description: payload.description,
  version: payload.version,
  is_published: payload.is_published,
  page: {
    size: payload.page.size,
    orientation: payload.page.orientation,
    margins: payload.page.margins,
  },
  sections: (payload.sections || []).map(section => ({
    ...section,
    elements: (section.elements || []).map(element => ({
      ...element,
      id: String(element.id),
    })),
  })),
});

export const listTemplates = () => apiFetch(TEMPLATES);

export const loadTemplate = (id) =>
  apiFetch(`${TEMPLATES}/${id}`).then(fromApiTemplate);

export const createTemplate = (template) =>
  apiFetch(TEMPLATES, {
    method: 'POST',
    body: JSON.stringify(toApiTemplate(template)),
  }).then(fromApiTemplate);

export const saveTemplate = (id, template) =>
  apiFetch(`${TEMPLATES}/${id}`, {
    method: 'PUT',
    body: JSON.stringify(toApiTemplate(template)),
  }).then(fromApiTemplate);

export const newVersion = (id) =>
  apiFetch(`${TEMPLATES}/${id}/versions`, { method: 'POST' }).then(fromApiTemplate);

export const publishTemplate = (id) =>
  apiFetch(`${TEMPLATES}/${id}/publish`, { method: 'POST' }).then(fromApiTemplate);

export { isDemoMode };
