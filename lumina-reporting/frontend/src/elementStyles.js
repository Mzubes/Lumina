// The canvas's copy of the template vocabulary: what an element may say
// about how it looks, and what a band may say about how it breaks.
//
// The authority is backend/schema_v2/ — styling.py for the style tokens
// and options, templates.py for the band vocabulary. The API refuses
// anything outside them, so an inspector offering a choice the backend
// rejects would be a dead control. `elementStyles.test.js` reads both
// files and asserts the lists match, because a silently-diverged copy is
// exactly the failure this duplication invites.
//
// The canvas shows these as approximate previews, not as the renderer's
// own CSS: the print stylesheet sets points against A4 and the canvas is a
// zoomable screen surface. Both take their meaning from the same token,
// which is what keeps them honest; E6's live preview is what makes them
// pixel-comparable.

export const STYLE_TOKENS = [
  { value: 'heading-1', label: 'Heading 1' },
  { value: 'heading-2', label: 'Heading 2' },
  { value: 'heading-3', label: 'Heading 3' },
  { value: 'body', label: 'Body' },
  { value: 'body-small', label: 'Body small' },
  { value: 'label', label: 'Label' },
  { value: 'figure', label: 'Figure' },
  { value: 'figure-large', label: 'Figure large' },
  { value: 'caption', label: 'Caption' },
  { value: 'disclosure', label: 'Disclosure' },
];

export const COLOR_ROLES = ['ink', 'muted', 'primary', 'accent'];
export const ALIGNMENTS = ['left', 'center', 'right'];
export const VALIGNMENTS = ['top', 'middle', 'bottom'];
export const BORDERS = ['none', 'top', 'bottom', 'box'];
export const FILLS = ['none', 'tint', 'tint-strong', 'accent-tint'];
export const CHART_KINDS = ['bar', 'bar_comparison', 'composition', 'donut', 'line', 'area'];

// --- band vocabulary (schema_v2/templates.py) -------------------------
export const LAYOUT_MODES = ['flow', 'fixed'];
export const REPEAT_MODES = ['none', 'every_page', 'first_page', 'except_first_page'];
export const BREAK_RULES = ['auto', 'page', 'avoid'];

export const OPTION_VOCABULARIES = {
  align: ALIGNMENTS,
  valign: VALIGNMENTS,
  color: COLOR_ROLES,
  border: BORDERS,
  fill: FILLS,
};

// Mirrors CLASS_PREFIXES in styling.py.
const CLASS_PREFIXES = {
  align: 'align', valign: 'va', color: 'color', border: 'border', fill: 'fill',
};

const TOKEN_NAMES = STYLE_TOKENS.map(token => token.value);

// The same resolution the renderer does, so the canvas element carries the
// same class names the PDF's element will.
export const elementClasses = (element) => {
  const classes = [];
  if (TOKEN_NAMES.includes(element.style_token)) classes.push(`st-${element.style_token}`);
  const options = element.options || {};
  for (const [key, prefix] of Object.entries(CLASS_PREFIXES)) {
    const value = options[key];
    if (value && OPTION_VOCABULARIES[key].includes(value)) classes.push(`${prefix}-${value}`);
  }
  return classes;
};

// Which controls an element type can actually use. A `line` has no
// typography and an `image` has no alignment, and offering them anyway
// teaches an author that half the inspector does nothing.
const TEXTUAL = ['text', 'field', 'page_number'];

export const controlsFor = (elementType) => ({
  style: TEXTUAL.includes(elementType),
  align: TEXTUAL.includes(elementType),
  valign: TEXTUAL.includes(elementType),
  color: [...TEXTUAL, 'line', 'box'].includes(elementType),
  border: true,
  fill: true,
  staticText: elementType === 'text',
  src: elementType === 'image',
  chartKind: elementType === 'chart',
});
