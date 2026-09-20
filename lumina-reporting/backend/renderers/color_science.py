"""Colour maths for chart palettes.

A faithful Python port of the arithmetic in the dataviz skill's
`validate_palette.js`. It exists because the node validator cannot run in
production: a brand kit supplying its own chart colours has to be checked
where the colours are used, not only where a developer happens to have node
installed.

The port is pinned to its source by `tests/test_chart_palette.py`, which
asserts the numbers this module produces match the ones the node script
prints for the same palettes. Drifting from the reference implementation
would silently change what counts as an accessible palette, so the
agreement is asserted rather than assumed.
"""

import math
import re

# Machado, Oliveira & Fernandes (2009), severity 1.0, in linear RGB. The
# thresholds in chart_palette.py are calibrated to *this* simulation model --
# swapping in another (Vienot 1999, say) moves borderline pairs and would
# require recalibrating them, so the matrices are not an implementation
# detail to be improved on.
MACHADO = {
    'protan': ((0.152286, 1.052583, -0.204868),
               (0.114503, 0.786281, 0.099216),
               (-0.003882, -0.048116, 1.051998)),
    'deutan': ((0.367322, 0.860646, -0.227968),
               (0.280085, 0.672501, 0.047413),
               (-0.011820, 0.042940, 0.968881)),
    'tritan': ((1.255528, -0.076749, -0.178779),
               (-0.078411, 0.930809, 0.147602),
               (0.004733, 0.691367, 0.303900)),
}

# The shared whitespace set the reference implementation defines: ASCII
# whitespace plus the Unicode spaces both JavaScript's trim() and Python's
# str.strip() agree on. It matters because hex lists get pasted out of
# rendered pages and arrive padded with non-breaking spaces.
_WHITESPACE = ' \t\n\v\f\r        ' \
              '         　'
_HEX = re.compile(r'^#?[0-9a-fA-F]{6}$')


class InvalidColor(ValueError):
    """Raised rather than returning NaN.

    The reference implementation is explicit that an unguarded parse lets
    NaN propagate through every check so the run fails *open* -- an invalid
    colour scoring as accessible. Refusing it at the boundary is the whole
    point.
    """


def normalise(value):
    """A hex string, stripped and lowercased, or InvalidColor."""
    if not isinstance(value, str):
        raise InvalidColor(f'not a colour string: {value!r}')
    cleaned = value.strip(_WHITESPACE)
    if not _HEX.match(cleaned):
        raise InvalidColor(f'not a 6-digit hex colour: {value!r}')
    return '#' + cleaned.lstrip('#').lower()


def to_srgb(value):
    cleaned = normalise(value).lstrip('#')
    return tuple(int(cleaned[index:index + 2], 16) / 255 for index in (0, 2, 4))


def _to_linear(channel):
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def linear(value):
    return tuple(_to_linear(channel) for channel in to_srgb(value))


def relative_luminance(value):
    red, green, blue = linear(value)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first, second):
    """WCAG contrast ratio."""
    high, low = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def oklab_from_linear(rgb):
    red, green, blue = rgb
    long_ = math.cbrt(0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue)
    medium = math.cbrt(0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue)
    short = math.cbrt(0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue)
    return (
        0.2104542553 * long_ + 0.7936177850 * medium - 0.0040720468 * short,
        1.9779984951 * long_ - 2.4285922050 * medium + 0.4505937099 * short,
        0.0259040371 * long_ + 0.7827717662 * medium - 0.8086757660 * short,
    )


def oklab(value):
    return oklab_from_linear(linear(value))


def oklch(value):
    lightness, a, b = oklab(value)
    return lightness, math.hypot(a, b)


def simulate(value, kind):
    """A colour as a reader with `kind` colour-vision deficiency sees it."""
    red, green, blue = linear(value)
    matrix = MACHADO[kind]
    return tuple(
        min(1.0, max(0.0, row[0] * red + row[1] * green + row[2] * blue))
        for row in matrix
    )


def delta_e(first, second, kind=None):
    """Euclidean distance in OKLab, x100. `kind` None means normal vision."""
    a = oklab_from_linear(simulate(first, kind) if kind else linear(first))
    b = oklab_from_linear(simulate(second, kind) if kind else linear(second))
    return 100 * math.dist(a, b)
