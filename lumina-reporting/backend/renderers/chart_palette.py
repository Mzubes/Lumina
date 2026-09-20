"""Which colours a printed chart may use, and how many series it may have.

Two facts drive everything here.

**Paper is not the screen.** The app's on-screen categorical palette
(`styles.css --cat-1..6`) was validated against a white card in the browser,
but it is a six-hue subset of the reference set in a different order, and on
paper it fails the normal-vision floor: magenta and red sit adjacent at
delta-E 13.2, below the floor of 15. All 120 re-orderings of those six hues
were enumerated against the validator and *none* clears every gate -- the
subset is short the two hues that make the full set work. Print therefore
uses the full eight-hue reference set in its validated order rather than
inheriting the screen palette.

**A printed chart has no hover.** Everything a tooltip would have carried
has to be on the page: a legend for two or more series, direct labels, and
a visible gap between touching fills. That is not decoration here -- three
of these hues sit below 3:1 against paper, which makes visible labels a
requirement rather than a nicety.
"""

from renderers.color_science import InvalidColor, contrast, delta_e, normalise, oklch

# Paper. Not `--page-bg-1`, not the panel white: the ground a printed mark
# actually sits on.
PRINT_SURFACE = '#ffffff'

# The dataviz reference palette, in its validated order. Verified against
# PRINT_SURFACE on the adjacent pairlist: worst CVD delta-E 9.1 (protan),
# worst normal-vision delta-E 19.6, every check passing.
DEFAULT_SERIES = (
    '#2a78d6',  # blue
    '#eb6834',  # orange
    '#1baf7a',  # aqua
    '#eda100',  # yellow
    '#e87ba4',  # magenta
    '#008300',  # green
    '#4a3aa7',  # violet
    '#e34948',  # red
)

# A ninth series is never a generated hue. Past this it folds into "Other".
MAX_SERIES = len(DEFAULT_SERIES)

# Charts whose marks are all mutually adjacent -- scatter, bubble, a map --
# need every pair to separate, not just neighbours, and the full eight
# cannot clear that. Only the first three do.
ALL_PAIRS_MAX_SERIES = 3

# The remainder slot. Deliberately a neutral: "Other" is not an identity,
# and giving it a hue would imply it were one.
OTHER_COLOR = '#6b7280'
OTHER_LABEL = 'Other'

# Thresholds, from the reference validator. Named rather than inlined so a
# failure message can quote the number it missed.
LIGHTNESS_BAND = (0.43, 0.77)
CHROMA_FLOOR = 0.10
CVD_TARGET = 8.0
CVD_FLOOR = 6.0
NORMAL_FLOOR = 15.0
CONTRAST_MIN = 3.0


def _pairs(count, mode):
    if mode == 'all':
        return [(i, j) for i in range(count) for j in range(i + 1, count)]
    return [(i, i + 1) for i in range(count - 1)]


def validate(colors, surface=PRINT_SURFACE, pairs='adjacent'):
    """The reference validator's checks, as data.

    Returns a list of (name, state, detail) where state is 'pass', 'warn' or
    'fail'. 'warn' is the CVD floor band and the sub-3:1 contrast band --
    both legal, but only alongside the secondary encoding this module's
    docstring describes. A 'fail' is not shippable.
    """
    colors = [normalise(color) for color in colors]
    low, high = LIGHTNESS_BAND
    report = []

    offband = [(color, round(oklch(color)[0], 3)) for color in colors
               if not low <= oklch(color)[0] <= high]
    report.append(('Lightness band', 'fail' if offband else 'pass',
                   f'outside band: {offband}' if offband
                   else f'all {len(colors)} inside L {low}-{high}'))

    washed = [(color, round(oklch(color)[1], 3)) for color in colors
              if oklch(color)[1] < CHROMA_FLOOR]
    report.append(('Chroma floor', 'fail' if washed else 'pass',
                   f'below floor (reads gray): {washed}' if washed
                   else f'all {len(colors)} >= {CHROMA_FLOOR}'))

    pairlist = _pairs(len(colors), pairs)
    label = 'all-pairs' if pairs == 'all' else 'adjacent'

    worst = min(
        ((delta_e(colors[i], colors[j], kind), kind, colors[i], colors[j])
         for kind in ('protan', 'deutan') for i, j in pairlist),
        default=(99.0, None, None, None),
    )
    state = 'pass' if worst[0] >= CVD_TARGET else 'warn' if worst[0] >= CVD_FLOOR else 'fail'
    report.append(('CVD separation', state,
                   f'worst {label} {worst[2]}/{worst[3]} dE {worst[0]:.1f} ({worst[1]})'))

    normal = min(((delta_e(colors[i], colors[j]), colors[i], colors[j])
                  for i, j in pairlist), default=(99.0, None, None))
    report.append(('Normal-vision floor', 'pass' if normal[0] >= NORMAL_FLOOR else 'fail',
                   f'worst {label} {normal[1]}/{normal[2]} dE {normal[0]:.1f} (normal)'))

    faint = [(color, round(contrast(color, surface), 2)) for color in colors
             if contrast(color, surface) < CONTRAST_MIN]
    # A warn, never a fail: it obliges visible labels, which printed charts
    # carry anyway because they have no hover layer to fall back on.
    report.append(('Contrast vs surface', 'warn' if faint else 'pass',
                   f'below {CONTRAST_MIN}:1, labels required: {faint}' if faint
                   else f'all {len(colors)} >= {CONTRAST_MIN}:1'))
    return report


def failures(colors, surface=PRINT_SURFACE, pairs='adjacent'):
    """Just the hard failures, for a caller that only wants a yes or no."""
    return [(name, detail) for name, state, detail in validate(colors, surface, pairs)
            if state == 'fail']


def _brand_series(brand_colors):
    """A brand kit's `chart_series`, if it has a usable one.

    A brand kit is data, entered by a person. A malformed or unvalidatable
    palette falls back to the default rather than rendering a document with
    indistinguishable series -- and never raises into the middle of a
    render.
    """
    if not isinstance(brand_colors, dict):
        return None
    series = brand_colors.get('chart_series')
    if not isinstance(series, (list, tuple)) or not series:
        return None
    try:
        return [normalise(color) for color in series]
    except InvalidColor:
        return None


def series_colors(count, brand_colors=None, pairs='adjacent'):
    """`count` colours in fixed slot order.

    Order is never cycled: asking for more than the palette holds is a
    caller error the chart layer prevents by folding to Other first, so
    this raises rather than quietly repeating a hue and making two series
    look like one.
    """
    palette = _brand_series(brand_colors) or list(DEFAULT_SERIES)
    if failures(palette, pairs=pairs):
        palette = list(DEFAULT_SERIES)
    limit = ALL_PAIRS_MAX_SERIES if pairs == 'all' else len(palette)
    if count > limit:
        raise ValueError(
            f'{count} series exceeds the {limit} this palette validates for '
            f'({pairs} pairs). Fold the tail into "{OTHER_LABEL}" first.')
    return palette[:count]


def fold_to_other(rows, pairs='adjacent', label=OTHER_LABEL):
    """Everything past the palette's limit, summed into one remainder row.

    Rows are (label, value). The remainder keeps its place at the end, which
    is also where a reader expects it -- a chart whose last slice is
    "Other" reads as complete; one that silently drops the tail does not.
    """
    limit = ALL_PAIRS_MAX_SERIES if pairs == 'all' else MAX_SERIES
    rows = list(rows)
    if len(rows) <= limit:
        return rows, False
    kept = rows[:limit - 1]
    remainder = sum(value for _, value in rows[limit - 1:])
    return kept + [(label, remainder)], True
