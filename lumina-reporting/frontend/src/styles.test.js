import fs from 'fs';
import path from 'path';

// A CSS custom property that is never defined fails SILENTLY: the
// declaration using it is dropped at computed-value time and the element
// renders as though the rule were not there. This project has been caught
// by that twice now -- once by deleting the `--cat-*` palette while the
// build stayed green, and once by writing `var(--ink)` for a token
// actually named `--ink-primary`, which made a whole block of canvas
// styling inert while every test and the build passed.
//
// So: every property referenced must be defined somewhere.

const SRC = __dirname;
const CSS = fs.readFileSync(path.join(SRC, 'styles.css'), 'utf8');

// Some properties are set inline from JS -- `style={{ '--status-color': … }}`
// -- which is a real definition even though it is not in the stylesheet.
// The scan has to know about both, or it reports false positives and gets
// switched off, which is worse than not having it.
const jsSources = (function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return walk(full);
    return entry.name.endsWith('.js') ? [fs.readFileSync(full, 'utf8')] : [];
  });
}(SRC)).join('\n');

const defined = new Set([
  ...[...CSS.matchAll(/^\s*(--[\w-]+)\s*:/gm)].map(match => match[1]),
  ...[...jsSources.matchAll(/['"](--[\w-]+)['"]\s*:/g)].map(match => match[1]),
]);

const referenced = [...CSS.matchAll(/var\(\s*(--[\w-]+)/g)].map(match => match[1]);

describe('styles.css', () => {
  test('defines every custom property it references', () => {
    const missing = [...new Set(referenced)].filter(name => !defined.has(name)).sort();
    expect(missing).toEqual([]);
  });

  test('actually defines some properties, so the scan is not vacuous', () => {
    expect(defined.size).toBeGreaterThan(20);
    expect(referenced.length).toBeGreaterThan(100);
  });

  test('the inline-from-JS properties are found, not just the CSS ones', () => {
    // If the JS walk ever stops working, the first test starts passing
    // for the wrong reason.
    expect(defined.has('--status-color')).toBe(true);
  });
});
