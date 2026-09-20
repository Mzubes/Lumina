// What an element is bound to, and what it would show.
//
// The catalogue comes from `GET /api/bindings` — datasets with their
// fields, display specs, and the system values the renderer can supply —
// and each entry carries a SAMPLE of what that binding would draw.
//
// **A sample says whether it is real.** Where the dataset cache holds rows
// the sample is a real value; where it does not, the backend derives one
// from the field's data type and flags it. The canvas marks the derived
// ones, because an author who lays a table out against a made-up number
// gets the column widths and the decimal places wrong and does it twice.

import { BINDING_COLUMNS } from './elementStyles';

export const EMPTY_CATALOGUE = { system: [], datasets: [] };

export const BINDING_KINDS = [
  { value: 'none', label: 'Not bound' },
  { value: 'system', label: 'System value' },
  { value: 'dataset_field', label: 'Dataset field' },
  { value: 'display_spec', label: 'Display spec' },
];

const allFields = (catalogue) =>
  (catalogue.datasets || []).flatMap(dataset =>
    (dataset.fields || []).map(field => ({ ...field, dataset })));

const allSpecs = (catalogue) =>
  (catalogue.datasets || []).flatMap(dataset =>
    (dataset.display_specs || []).map(spec => ({ ...spec, dataset })));

export const findField = (catalogue, id) =>
  allFields(catalogue).find(field => field.id === id) || null;

export const findSpec = (catalogue, id) =>
  allSpecs(catalogue).find(spec => spec.id === id) || null;

export const findSystem = (catalogue, key) =>
  (catalogue.system || []).find(entry => entry.key === key) || null;

// The one place a binding kind's columns are set, so switching kind cannot
// leave the previous kind's id behind. The schema refuses an element that
// carries two, and the API now reports it rather than raising an
// IntegrityError, but the canvas should never send one in the first place.
export const bindingPatch = (kind, value = null) => {
  const patch = {
    binding_kind: kind,
    binding_key: null,
    dataset_field_id: null,
    display_spec_id: null,
  };
  const column = BINDING_COLUMNS[kind];
  if (column) patch[column] = value;
  return patch;
};

// What the canvas draws inside a bound element: the sample where there is
// one, a description where the binding names something the catalogue does
// not have (a deleted field, a spec from another firm), and the element's
// own words when it is not bound at all.
export const previewFor = (element, catalogue = EMPTY_CATALOGUE) => {
  const kind = element.binding_kind || 'none';

  if (kind === 'system') {
    const entry = findSystem(catalogue, element.binding_key);
    if (!entry) return { text: `{${element.binding_key || 'system'}}`, isReal: false };
    // Page numbers are resolved by the engine during pagination, so there
    // is no honest value to show here -- only the shape of one.
    return { text: entry.sample, isReal: false, note: entry.resolved_at_layout
      ? 'resolved when the document paginates' : 'example' };
  }

  if (kind === 'dataset_field') {
    const field = findField(catalogue, element.dataset_field_id);
    if (!field) return { text: 'Unknown field', isReal: false, missing: true };
    return {
      text: String(field.sample),
      isReal: field.sample_is_real,
      note: field.sample_is_real
        ? `${field.dataset.name} · ${field.name}`
        : `${field.name} · example, no cached rows`,
    };
  }

  if (kind === 'display_spec') {
    const spec = findSpec(catalogue, element.display_spec_id);
    if (!spec) return { text: 'Unknown display spec', isReal: false, missing: true };
    return { text: spec.name, isReal: true, note: spec.summary };
  }

  if (element.static_text) return { text: element.static_text, isReal: true };
  return { text: null, isReal: false };
};
