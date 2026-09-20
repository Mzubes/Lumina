import {
  EMPTY_CATALOGUE, bindingPatch, findField, findSpec, previewFor,
} from './bindings';

const CATALOGUE = {
  system: [
    { key: 'client_name', label: 'Client name', sample: 'Meridian Endowment',
      resolved_at_layout: false },
    { key: 'page_number', label: 'Page number', sample: '1', resolved_at_layout: true },
  ],
  datasets: [{
    id: 1, name: 'Holdings', grain: 'portfolio_position', has_cached_rows: true,
    fields: [
      { id: 10, name: 'Market value', data_type: 'currency',
        sample: 16500000, sample_is_real: true },
      { id: 11, name: 'Quantity', data_type: 'number',
        sample: '12,345.67', sample_is_real: false },
    ],
    display_specs: [
      { id: 5, name: 'Top 10 holdings', summary: 'sorted by Weight · top 10' },
    ],
  }],
};

describe('bindingPatch', () => {
  test('sets the kind’s own column and clears the others', () => {
    expect(bindingPatch('dataset_field', 10)).toEqual({
      binding_kind: 'dataset_field', binding_key: null,
      dataset_field_id: 10, display_spec_id: null,
    });
  });

  test('switching kind never leaves the previous id behind', () => {
    // The schema refuses an element carrying two binding columns. The
    // canvas must not be able to construct one at all.
    const patch = bindingPatch('system', 'client_name');
    expect(patch.dataset_field_id).toBeNull();
    expect(patch.display_spec_id).toBeNull();
    expect(patch.binding_key).toBe('client_name');
  });

  test('unbinding clears everything', () => {
    expect(bindingPatch('none')).toEqual({
      binding_kind: 'none', binding_key: null,
      dataset_field_id: null, display_spec_id: null,
    });
  });
});

describe('lookup', () => {
  test('finds a field and a spec across datasets', () => {
    expect(findField(CATALOGUE, 10).name).toBe('Market value');
    expect(findSpec(CATALOGUE, 5).name).toBe('Top 10 holdings');
  });

  test('returns null rather than throwing for an id that is gone', () => {
    expect(findField(CATALOGUE, 999)).toBeNull();
    expect(findField(EMPTY_CATALOGUE, 10)).toBeNull();
  });
});

describe('previewFor', () => {
  test('a real cached value is marked real', () => {
    const preview = previewFor(
      { binding_kind: 'dataset_field', dataset_field_id: 10 }, CATALOGUE);
    expect(preview.text).toBe('16500000');
    expect(preview.isReal).toBe(true);
    expect(preview.note).toContain('Holdings');
  });

  test('a derived value says so', () => {
    // The distinction that matters: an author sizing a column against a
    // made-up number lays the page out twice.
    const preview = previewFor(
      { binding_kind: 'dataset_field', dataset_field_id: 11 }, CATALOGUE);
    expect(preview.isReal).toBe(false);
    expect(preview.note).toContain('example');
  });

  test('a page number is never presented as a real value', () => {
    const preview = previewFor(
      { binding_kind: 'system', binding_key: 'page_number' }, CATALOGUE);
    expect(preview.isReal).toBe(false);
    expect(preview.note).toContain('paginates');
  });

  test('a binding whose target is gone is flagged, not blank', () => {
    const preview = previewFor(
      { binding_kind: 'dataset_field', dataset_field_id: 999 }, CATALOGUE);
    expect(preview.missing).toBe(true);
    expect(preview.text).toBe('Unknown field');
  });

  test('an unbound element shows its own words', () => {
    expect(previewFor({ binding_kind: 'none', static_text: 'Performance' }, CATALOGUE))
      .toEqual({ text: 'Performance', isReal: true });
  });

  test('an empty catalogue degrades to the binding key, not a crash', () => {
    const preview = previewFor(
      { binding_kind: 'system', binding_key: 'client_name' }, EMPTY_CATALOGUE);
    expect(preview.text).toBe('{client_name}');
  });
});
