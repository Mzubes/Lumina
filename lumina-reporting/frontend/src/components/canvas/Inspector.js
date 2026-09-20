import React from 'react';

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

const ElementProperties = ({ element, editor }) => {
  const begin = editor.begin;
  const set = (patch) => editor.setElement(element.id, patch);
  const option = (key) => (value) => editor.setElementOption(element.id, key, value);
  const can = controlsFor(element.element_type);
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

      {can.staticText && (
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

const Inspector = ({ editor, section }) => {
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
        ? <ElementProperties element={selected} editor={editor} />
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
