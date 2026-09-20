"""Applying a DisplaySpec to rows: filter, sort, group, subtotal, cap.

This is the flexibility requirement made mechanical. "Top 10 holdings by
weight", "holdings grouped by sector with subtotals, sectors ordered by
size", "everything over 1%, sorted by country then name" are three specs
over one dataset, and none of them is a new query.

**Display aggregation only.** A subtotal here sums what is on the page. It
does not compute anything a methodology owns -- a field marked
`is_precomputed` (a return, an attribution effect, a yield) is never
aggregated, because adding two time-weighted returns together produces a
number that is simply wrong and looks entirely plausible. The schema
forbids such a field from carrying an aggregation; this module renders a
blank in its subtotal cell rather than guessing.

Pure functions over plain rows -- no ORM, no session, no database. The spec
and the field descriptors arrive as dicts, so a caller can use this against
warehouse rows, a fixture, or a test list without ceremony.
"""

import datetime
from decimal import Decimal, InvalidOperation

# Comparison operators a filter may use. Closed, because a filter arrives
# from a saved spec and an open operator set is an expression language.
OPERATORS = ('eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in', 'not_in', 'contains',
             'is_null', 'is_not_null')

# What a subtotal may do. 'none' means the column is left blank in subtotal
# and total rows -- the honest answer for anything carrying a methodology.
AGGREGATIONS = ('none', 'sum', 'count', 'count_distinct', 'min', 'max', 'avg')

REMAINDER_KEY = '__remainder__'


class SpecError(ValueError):
    """A spec that cannot be applied. Raised rather than silently ignored:
    a filter that quietly does nothing shows a client more rows than the
    author intended."""


def _numeric(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    try:
        return Decimal(str(value).strip().replace(',', ''))
    except (InvalidOperation, AttributeError, ValueError):
        return None


def _sortable(value):
    """A key that orders mixed types without raising.

    Rows come from a warehouse; one null in a numeric column would
    otherwise abort the whole render. Nulls sort last in ascending order,
    which is where a reader expects "no data" to sit.
    """
    if value is None:
        return (2, 0, '')
    number = _numeric(value)
    if number is not None:
        return (0, number, '')
    if isinstance(value, (datetime.date, datetime.datetime)):
        return (0, Decimal(value.toordinal()), '')
    return (1, 0, str(value).casefold())


def _matches(row, condition):
    field = condition.get('field')
    if not field:
        raise SpecError(f'filter with no field: {condition!r}')
    operator = condition.get('op', 'eq')
    if operator not in OPERATORS:
        raise SpecError(f'unknown filter operator {operator!r}')

    actual = row.get(field)
    expected = condition.get('value')

    if operator == 'is_null':
        return actual is None
    if operator == 'is_not_null':
        return actual is not None
    if operator in ('in', 'not_in'):
        if not isinstance(expected, (list, tuple, set)):
            raise SpecError(f"operator {operator!r} needs a list of values")
        hit = actual in expected
        return hit if operator == 'in' else not hit
    if operator == 'contains':
        return expected is not None and str(expected).casefold() in str(actual or '').casefold()

    left, right = _numeric(actual), _numeric(expected)
    if left is None or right is None:
        # Not comparable as numbers -- fall back to text, so a filter on a
        # string column still works.
        left, right = str(actual or ''), str(expected or '')
    return {
        'eq': left == right, 'ne': left != right,
        'gt': left > right, 'gte': left >= right,
        'lt': left < right, 'lte': left <= right,
    }[operator]


def apply_filters(rows, filters):
    for condition in filters or []:
        rows = [row for row in rows if _matches(row, condition)]
    return rows


def apply_sort(rows, sort_by):
    """Stable, applied last key first, so the first key in the spec is the
    primary one -- which is how a person reading the spec expects it."""
    for term in reversed(sort_by or []):
        field = term.get('field')
        if not field:
            raise SpecError(f'sort term with no field: {term!r}')
        direction = term.get('direction', 'asc')
        if direction not in ('asc', 'desc'):
            raise SpecError(f'unknown sort direction {direction!r}')
        rows = sorted(rows, key=lambda row: _sortable(row.get(field)),
                      reverse=direction == 'desc')
    return rows


def aggregate(rows, field, how):
    """One subtotal cell.

    `None` means "leave it blank", which is the right answer for a column
    whose methodology forbids re-aggregation -- and for an empty group.
    """
    if how in (None, 'none'):
        return None
    values = [row.get(field) for row in rows]
    present = [value for value in values if value is not None]
    if how == 'count':
        return len(present)
    if how == 'count_distinct':
        return len({str(value) for value in present})
    numbers = [number for number in (_numeric(value) for value in present)
               if number is not None]
    if not numbers:
        return None
    if how == 'sum':
        return sum(numbers)
    if how == 'min':
        return min(numbers)
    if how == 'max':
        return max(numbers)
    if how == 'avg':
        return sum(numbers) / len(numbers)
    raise SpecError(f'unknown aggregation {how!r}')


def _aggregation_for(field, fields):
    """What this column may do in a subtotal row.

    A pre-computed measure returns 'none' whatever the spec asks for.
    Summing two time-weighted returns is arithmetic nobody can defend, and
    the result looks entirely plausible on the page.
    """
    descriptor = fields.get(field) or {}
    if descriptor.get('is_precomputed'):
        return 'none'
    how = descriptor.get('default_aggregation', 'none')
    if how not in AGGREGATIONS:
        raise SpecError(f'unknown aggregation {how!r} on field {field!r}')
    return how


def _subtotal_row(rows, columns, fields, label_field, label):
    row = {field: None for field in columns}
    row[label_field] = label
    for field in columns:
        if field == label_field:
            continue
        row[field] = aggregate(rows, field, _aggregation_for(field, fields))
    return row


def apply_limit(rows, columns, fields, row_limit, remainder_label):
    """Top-N with an honest tail.

    The remainder is SUMMED into one row rather than dropped, and labelled,
    so a truncated table says it is truncated. A table that silently shows
    the top ten of forty and totals to 100% is a misrepresentation.
    """
    if not row_limit or len(rows) <= row_limit:
        return rows, None
    kept, tail = rows[:row_limit], rows[row_limit:]
    if not remainder_label:
        # No label means the author asked for a hard cap. Say how many were
        # dropped rather than pretending the table is complete.
        return kept, {'dropped': len(tail)}
    label_field = columns[0]
    remainder = _subtotal_row(tail, columns, fields, label_field,
                              remainder_label.format(count=len(tail))
                              if '{count}' in remainder_label else remainder_label)
    remainder[REMAINDER_KEY] = True
    return kept + [remainder], {'dropped': 0, 'folded': len(tail)}


def apply_spec(rows, spec, fields=None, columns=None):
    """Filter, sort, group, subtotal and cap, in that order.

    Returns {'columns', 'rows', 'groups', 'totals', 'truncation'}. Rows are
    plain dicts; a subtotal or remainder row carries a marker key so the
    renderer can style it without re-deriving which rows are which.
    """
    spec = spec or {}
    fields = {descriptor['field']: descriptor for descriptor in (fields or [])}
    rows = [dict(row) for row in rows or []]
    columns = list(columns or (rows[0].keys() if rows else []))

    rows = apply_filters(rows, spec.get('filters'))
    rows = apply_sort(rows, spec.get('sort_by'))

    # The grand total is taken over everything that survived the FILTER,
    # before the row limit -- so a "top ten" table still totals the whole
    # portfolio. Totalling only the rows that fit would tell a client their
    # portfolio is 30% invested, which is a misrepresentation rather than a
    # rounding issue. The remainder row reconciles the difference.
    filtered = list(rows)

    # Limit BEFORE grouping. The first cut did it after, so the tail that
    # got folded into "Other" contained subtotal rows and double-counted
    # them -- the remainder came out larger than the grand total, which is
    # how the bug announced itself.
    rows, truncation = apply_limit(rows, columns, fields,
                                   spec.get('row_limit'), spec.get('remainder_label'))
    remainder = None
    if rows and rows[-1].get(REMAINDER_KEY):
        rows, remainder = rows[:-1], rows[-1]

    group_by = spec.get('group_by') or []
    groups = []
    if group_by:
        rows, groups = _group(rows, group_by, columns, fields)
    if remainder is not None:
        rows = rows + [remainder]

    totals = None
    totals_spec = spec.get('totals') or {}
    if totals_spec.get('grand_total'):
        totals = _subtotal_row(filtered, columns, fields, columns[0],
                               totals_spec.get('label', 'Total'))

    return {'columns': columns, 'rows': rows, 'groups': groups,
            'totals': totals, 'truncation': truncation}


def _group(rows, group_by, columns, fields):
    """One level of grouping, with an optional subtotal per group.

    Deliberately one level: two would need a nested row model, and no real
    factsheet in this domain has asked for it. The spec's shape allows more
    later without a migration.
    """
    term = group_by[0]
    field = term.get('field')
    if not field:
        raise SpecError(f'group term with no field: {term!r}')

    buckets = {}
    for row in rows:
        buckets.setdefault(row.get(field), []).append(row)

    order = term.get('sort', 'asc')
    if order in ('asc', 'desc'):
        keys = sorted(buckets, key=_sortable, reverse=order == 'desc')
    elif order == 'size':
        # Biggest group first -- what "sectors ordered by size" means.
        keys = sorted(buckets, key=lambda key: -len(buckets[key]))
    else:
        raise SpecError(f'unknown group sort {order!r}')

    out, groups = [], []
    for key in keys:
        members = buckets[key]
        start = len(out)
        out.extend(members)
        if term.get('show_subtotal'):
            subtotal = _subtotal_row(members, columns, fields, columns[0],
                                     f'{key} total' if key is not None else 'Total')
            subtotal['__subtotal__'] = True
            out.append(subtotal)
        groups.append({'key': key, 'label': '' if key is None else str(key),
                       'start': start, 'count': len(members)})
    return out, groups
