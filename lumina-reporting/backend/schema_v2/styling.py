"""What an element may say about how it looks.

`style_token` and `options` were the model's two presentation escape
hatches, and until now neither reached the renderer: a template could carry
`style_token = 'heading-1'` and the PDF would draw body text. This module is
the closed vocabulary that closes that gap, in one place, so the schema's
validation, the renderer's stylesheet and the canvas inspector cannot
disagree about what a token means.

**Every value here is a NAME, never a literal.** `colour: 'accent'`, not
`#eb6834`; `border: 'bottom'`, not `1px solid`. The check constraint on
`style_token` already refuses anything with a colon in it, and the same
reasoning applies to the options: the moment an element can carry a literal,
a template stops being renderer-agnostic and Phase G's PPTX renderer has
CSS to interpret. Names resolve to literals per renderer -- to a stylesheet
rule here, to a shape property there.

That also means the list is deliberately short. Anything not in it is a
design decision the brand kit should be making, not an element.
"""

# Typographic roles. The value is the token; the label is what the canvas
# inspector shows. Ordered as an author would scan them.
STYLE_TOKENS = (
    ('heading-1', 'Heading 1'),
    ('heading-2', 'Heading 2'),
    ('heading-3', 'Heading 3'),
    ('body', 'Body'),
    ('body-small', 'Body small'),
    ('label', 'Label'),         # uppercase, letterspaced -- a column head
    ('figure', 'Figure'),       # a single number, set large
    ('figure-large', 'Figure large'),
    ('caption', 'Caption'),
    ('disclosure', 'Disclosure'),
)

STYLE_TOKEN_NAMES = tuple(token for token, _ in STYLE_TOKENS)

# Colour ROLES, resolved from the theme at render time. A role rather than
# a hex because a brand kit is what decides a firm's accent, and an element
# carrying #eb6834 would keep drawing the old brand after a rebrand.
COLOR_ROLES = ('ink', 'muted', 'primary', 'accent')

ALIGNMENTS = ('left', 'center', 'right')
VALIGNMENTS = ('top', 'middle', 'bottom')

# Which edges carry a rule. 'box' is all four.
BORDERS = ('none', 'top', 'bottom', 'box')

# Background. Tints are computed from the theme, so a filled band follows
# the brand rather than a colour someone typed once.
FILLS = ('none', 'tint', 'tint-strong', 'accent-tint')

# The option keys an element may carry, and the closed set each accepts.
# `src` is the exception -- an asset reference, not a vocabulary -- and is
# validated as a shape rather than by membership.
OPTION_VOCABULARIES = {
    'align': ALIGNMENTS,
    'valign': VALIGNMENTS,
    'color': COLOR_ROLES,
    'border': BORDERS,
    'fill': FILLS,
}

# Options that are not vocabularies. Kept explicit so an unknown key is an
# error rather than something that rides along and silently does nothing.
FREE_OPTIONS = ('src', 'chart_kind', 'format')

# Chart kinds, exactly renderers.charts.KINDS. Restated rather than
# imported because schema_v2 must not depend on renderers -- the
# dependency runs the other way -- so a test asserts the two are equal.
# The first draft of this list carried 'column', which nothing can draw,
# and omitted 'bar_comparison', which something can.
CHART_KINDS = ('bar', 'bar_comparison', 'composition', 'donut', 'line', 'area')


# The class prefix each option contributes. Spelled out rather than derived
# from the key, so the stylesheet can be read against this list.
CLASS_PREFIXES = {
    'align': 'align',
    'valign': 'va',
    'color': 'color',
    'border': 'border',
    'fill': 'fill',
}


def option_problems(options, where=''):
    """Everything wrong with an element's options, as a list of messages.

    An unknown key is reported rather than dropped: an author who set
    `alignment` instead of `align` deserves to be told, not to spend an
    afternoon wondering why nothing moved.
    """
    problems = []
    prefix = f'{where}: ' if where else ''
    if options is None:
        return problems
    if not isinstance(options, dict):
        return [f'{prefix}options must be an object']

    for key, value in options.items():
        if key in OPTION_VOCABULARIES:
            if value is not None and value not in OPTION_VOCABULARIES[key]:
                allowed = ', '.join(OPTION_VOCABULARIES[key])
                problems.append(f'{prefix}option {key}={value!r} is not one of {allowed}')
        elif key == 'chart_kind':
            if value is not None and value not in CHART_KINDS:
                problems.append(f'{prefix}option chart_kind={value!r} is not one of '
                                f'{", ".join(CHART_KINDS)}')
        elif key in FREE_OPTIONS:
            if value is not None and not isinstance(value, str):
                problems.append(f'{prefix}option {key} must be text')
        else:
            problems.append(f'{prefix}unknown option {key!r}')
    return problems


def style_problems(token, where=''):
    prefix = f'{where}: ' if where else ''
    if token and token not in STYLE_TOKEN_NAMES:
        return [f'{prefix}unknown style token {token!r}; '
                f'one of {", ".join(STYLE_TOKEN_NAMES)}']
    return []


def element_classes(element):
    """The CSS classes an element's styling resolves to.

    The renderer's half of the vocabulary. Emitted as classes rather than
    inline style so the stylesheet stays the single place a token's meaning
    is written down -- and so a token that has no rule draws nothing rather
    than injecting an unknown declaration.
    """
    classes = []
    token = element.get('style_token')
    if token in STYLE_TOKEN_NAMES:
        classes.append(f'st-{token}')
    options = element.get('options') or {}
    if isinstance(options, dict):
        for key, prefix in CLASS_PREFIXES.items():
            value = options.get(key)
            if value and value in OPTION_VOCABULARIES[key]:
                classes.append(f'{prefix}-{value}')
    return classes
