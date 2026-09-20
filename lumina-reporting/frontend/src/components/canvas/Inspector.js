import React from 'react';

import {
  BINDING_KINDS, EMPTY_CATALOGUE, bindingPatch, previewFor,
} from '../../bindings';
import {
  BORDERS, BREAK_RULES, CHART_KINDS, FILLS, LAYOUT_MODES, OPTION_VOCABULARIES,
  REPEAT_MODES, STYLE_TOKENS, controlsFor,
} from '../../elementStyles';
import { ELEMENT_LABELS } from './CanvasElement';

// E3: the properties pane.
//
// **It offers only what the renderer honours.** Every control here maps to
// a name in schema_v2/styling.py, which the API validates against and the
// print stylesheet has a rule for. That constraint is the whole design:
// a colour picker would be friendlier and would let an author pin #eb6834
// into a template that then keeps drawing the old brand after a rebrand,
// and would hand Phase G's PPTX renderer CSS to interpret.
//
// So: roles, not literals. The brand kit decides what `accent` looks like.

// A millimetre field. Commits on change rather than on blur so the canvas
// and the number agree at every keystroke; `begin()` fires once per focus,
// so typing "12.5" is one undo step rather than four.
const MmField = ({ label, value, onChange, onBegin, min = 0, step = 0.5 }) => (
  <label className="inspector-field">
    <span>{label}</span>
    <input
      type="number" value={value} min={min} step={step}
      onFocus={onBegin}
      onChange={(event) => {
        const next = Number(event.target.value);
        if (!Number.isNaN(next)) onChange(next);
      }}
    />
    <i>mm</i>
  </label>
);

const Choice = ({ label, value, options, onChange, onBegin, empty = 'Default' }) => (
  <label className="inspector-field">
    <span>{label}</span>
    <select value={value || ''} onFocus={onBegin}
            onChange={(event) => onChange(event.target.value || null)}>
      <option value="">{empty}</option>
      {options.map(option => (
        typeof option === 'string'
          ? <option key={option} value={option}>{option}</option>
          : <option key={option.value} value={option.value}>{option.label}</option>
      ))}
    </select>
  </label>
);

// E4. Which kinds a type can take: a table or a chart reads a whole result
// set, a field reads one value, and a rule reads nothing. Offering
// `display_spec` on a text element would let an author bind a table's worth
// of rows to a box that draws one line.
const kindsFor = (elementType) => {
  if (elementType === 'table' || elementType === 'chart') {
    return BINDING_KINDS.filter(kind => ['none', 'display_spec'].includes(kind.value));
  }
  if (elementType === 'field') {
    return BINDING_KINDS.filter(kind => ['system', 'dataset_field'].includes(kind.value));
  }
  if (elementType === 'text') {
    return BINDING_KINDS.filter(kind => ['none', 'system'].includes(kind.value));
  }
  return null;   // line, box, image, page_number -- nothing to bind
};

const BindingBlock = ({ element, editor, catalogue }) => {
  const kinds = kindsFor(element.element_type);
  if (!kinds) return null;

  const begin = editor.begin;
  const kind = element.binding_kind || 'none';
  const apply = (patch) => { begin(); editor.setElement(element.id, patch); };
  const preview = previewFor(element, catalogue);

  const fields = (catalogue.datasets || []).flatMap(dataset =>
    (dataset.fields || []).map(field => ({
      value: field.id, label: `${dataset.name} · ${field.name}`,
    })));
  const specs = (catalogue.datasets || []).flatMap(dataset =>
    (dataset.display_specs || []).map(spec => ({
      value: spec.id, label: `${dataset.name} · ${spec.name}`,
    })));

  return (
    <>
      <h3 className="inspector-heading">Data</h3>
      <label className="inspector-field">
        <span>Source</span>
        <select value={kind} onFocus={begin}
                onChange={(event) => apply(bindingPatch(event.target.value))}>
          {kinds.map(entry => (
            <option key={entry.value} value={entry.value}>{entry.label}</option>
          ))}
        </select>
      </label>

      {kind === 'system' && (
        <label className="inspector-field">
          <span>Value</span>
          <select value={element.binding_key || ''} onFocus={begin}
                  onChange={(e) => apply(bindingPatch('system', e.target.value || null))}>
            <option value="">Choose…</option>
            {(catalogue.system || []).map(entry => (
              <option key={entry.key} value={entry.key}>{entry.label}</option>
            ))}
          </select>
        </label>
      )}

      {kind === 'dataset_field' && (
        <label className="inspector-field">
          <span>Field</span>
          <select value={element.dataset_field_id || ''} onFocus={begin}
                  onChange={(e) => apply(
                    bindingPatch('dataset_field', Number(e.target.value) || null))}>
            <option value="">Choose…</option>
            {fields.map(entry => (
              <option key={entry.value} value={entry.value}>{entry.label}</option>
            ))}
          </select>
        </label>
      )}

      {kind === 'display_spec' && (
        <label className="inspector-field">
          <span>Spec</span>
          <select value={element.display_spec_id || ''} onFocus={begin}
                  onChange={(e) => apply(
                    bindingPatch('display_spec', Number(e.target.value) || null))}>
            <option value="">Choose…</option>
            {specs.map(entry => (
              <option key={entry.value} value={entry.value}>{entry.label}</option>
            ))}
          </select>
        </label>
      )}

      {kind !== 'none' && preview.text && (
        <p className={`inspector-sample${preview.isReal ? '' : ' is-sample'}`}>
          <strong>{preview.text}</strong>
          {preview.note && <i>{preview.note}</i>}
        </p>
      )}

      {kind !== 'none' && !fields.length && kind === 'dataset_field' && (
        <p className="panel-subtitle">
          No datasets yet — run <code>flask seed-demo</code>, or load one from a
          data source.
        </p>
      )}
    </>
  );
};

const ElementProperties = ({ element, editor, catalogue }) => {
  const begin = editor.begin;
  const set = (patch) => editor.setElement(element.id, patch);
  const option = (key) => (value) => editor.setElementOption(element.id, key, value);
  const can = controlsFor(element.element_type);
  // A bound element draws its binding, not its words, so the text box
  // would be a control with no effect.
  const bound = (element.binding_kind || 'none') !== 'none';
  const options = element.options || {};

  return (
    <>
      <p className="inspector-type">
        {ELEMENT_LABELS[element.element_type] || element.element_type}
        {element.binding_kind !== 'none' && (
          <i> · bound to {element.binding_key || `${element.binding_kind}`}</i>
        )}
      </p>

      <div className="inspector-grid">
        <MmField label="X" value={element.x_mm} onBegin={begin}
                 onChange={(x_mm) => set({ x_mm })} />
        <MmField label="Y" value={element.y_mm} onBegin={begin}
                 onChange={(y_mm) => set({ y_mm })} />
        <MmField label="Width" value={element.w_mm} onBegin={begin}
                 onChange={(w_mm) => set({ w_mm })} />
        <MmField label="Height" value={element.h_mm} onBegin={begin}
                 onChange={(h_mm) => set({ h_mm })} />
      </div>

      <BindingBlock element={element} editor={editor} catalogue={catalogue} />

      {can.staticText && !bound && (
        <label className="inspector-field inspector-field-wide">
          <span>Text</span>
          <textarea
            rows={2} value={element.static_text || ''} onFocus={begin}
            onChange={(event) => set({ static_text: event.target.value })}
          />
        </label>
      )}

      {can.src && (
        <label className="inspector-field inspector-field-wide">
          <span>Image</span>
          <input
            type="text" value={options.src || ''} onFocus={begin}
            placeholder="Asset reference"
            onChange={(event) => option('src')(event.target.value)}
          />
        </label>
      )}

      {can.style && (
        <Choice label="Style" value={element.style_token} options={STYLE_TOKENS}
                onBegin={begin} onChange={(style_token) => set({ style_token })} />
      )}
      {can.align && (
        <Choice label="Align" value={options.align} options={OPTION_VOCABULARIES.align}
                onBegin={begin} onChange={option('align')} />
      )}
      {can.valign && (
        <Choice label="Vertical" value={options.valign} options={OPTION_VOCABULARIES.valign}
                onBegin={begin} onChange={option('valign')} />
      )}
      {can.color && (
        <Choice label="Colour" value={options.color} options={OPTION_VOCABULARIES.color}
                onBegin={begin} onChange={option('color')} />
      )}
      {can.chartKind && (
        <Choice label="Chart" value={options.chart_kind} options={CHART_KINDS}
                onBegin={begin} onChange={option('chart_kind')} />
      )}
      <Choice label="Border" value={options.border} options={BORDERS}
              onBegin={begin} onChange={option('border')} />
      <Choice label="Fill" value={options.fill} options={FILLS}
              onBegin={begin} onChange={option('fill')} />

      <div className="inspector-grid">
        <label className="inspector-field">
          <span>Layer</span>
          <input type="number" value={element.z_index || 0} onFocus={begin}
                 onChange={(event) => set({ z_index: Number(event.target.value) || 0 })} />
        </label>
        <label className="inspector-field inspector-check">
          <input
            type="checkbox" checked={element.is_visible !== false} onChange={() => {
              begin();
              set({ is_visible: element.is_visible === false });
            }}
          />
          <span>Visible</span>
        </label>
      </div>
    </>
  );
};

const SectionProperties = ({ section, editor }) => {
  const begin = editor.begin;
  const set = (patch) => editor.setSection(section.ordinal, patch);

  return (
    <>
      <label className="inspector-field inspector-field-wide">
        <span>Name</span>
        <input type="text" value={section.name || ''} onFocus={begin}
               onChange={(event) => set({ name: event.target.value })} />
      </label>

      <Choice
        label="Layout" value={section.layout_mode} options={LAYOUT_MODES}
        empty="flow" onBegin={begin}
        onChange={(layout_mode) => set(
          // The schema pairs these: a fixed band declares a height and a
          // flow band must not. Changing one without the other is a tree
          // the API refuses, so the pair moves together here.
          layout_mode === 'fixed'
            ? { layout_mode, height_mm: section.height_mm || 24 }
            : { layout_mode: 'flow', height_mm: null, repeat_mode: 'none' })}
      />

      {section.layout_mode === 'fixed' && (
        <>
          <MmField label="Height" value={section.height_mm || 0} onBegin={begin}
                   onChange={(height_mm) => set({ height_mm })} />
          <Choice label="Repeats" value={section.repeat_mode} options={REPEAT_MODES}
                  empty="none" onBegin={begin}
                  onChange={(repeat_mode) => set({ repeat_mode: repeat_mode || 'none' })} />
        </>
      )}

      <Choice label="Break before" value={section.break_before} options={BREAK_RULES}
              empty="auto" onBegin={begin}
              onChange={(rule) => set({ break_before: rule || 'auto' })} />
      <Choice label="Break after" value={section.break_after} options={BREAK_RULES}
              empty="auto" onBegin={begin}
              onChange={(rule) => set({ break_after: rule || 'auto' })} />
    </>
  );
};

const Inspector = ({ editor, section, catalogue = EMPTY_CATALOGUE }) => {
  const { template, selection } = editor;
  const selected = selection.length === 1
    ? template.sections.flatMap(s => s.elements).find(element => element.id === selection[0])
    : null;

  return (
    <div className="inspector">
      <h2 className="panel-title">
        {selected ? 'Element' : selection.length > 1 ? `${selection.length} elements` : 'Band'}
      </h2>

      {selected
        ? <ElementProperties element={selected} editor={editor} catalogue={catalogue} />
        : selection.length > 1
          ? (
            <p className="panel-subtitle">
              {selection.length} elements selected. Drag to move them together, or
              select one to edit its properties.
            </p>
          )
          : section
            ? <SectionProperties section={section} editor={editor} />
            : <p className="panel-subtitle">No band to edit.</p>}
    </div>
  );
};

export default Inspector;
