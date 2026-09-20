"""Applying a DisplaySpec: filter, sort, group, subtotal, cap.

Every arithmetic bug here produces a convincing table of wrong numbers, so
the reconciliation properties are asserted rather than eyeballed.
"""

import pytest

from display_spec import REMAINDER_KEY, SpecError, aggregate, apply_spec

HOLDINGS = [
    {'name': 'Tate', 'sector': 'Financials', 'weight': 3.4, 'ret': 2.1},
    {'name': 'Greif', 'sector': 'Financials', 'weight': 3.1, 'ret': -1.4},
    {'name': 'Hanwha', 'sector': 'Energy', 'weight': 2.9, 'ret': 0.8},
    {'name': 'Iwatani', 'sector': 'Energy', 'weight': 2.7, 'ret': 1.2},
    {'name': 'Vontier', 'sector': 'Industrials', 'weight': 2.6, 'ret': -0.3},
]
FIELDS = [{'field': 'weight', 'default_aggregation': 'sum'},
          {'field': 'ret', 'default_aggregation': 'none', 'is_precomputed': True}]
COLUMNS = ['name', 'sector', 'weight', 'ret']


def run(spec, rows=None):
    return apply_spec(rows if rows is not None else HOLDINGS, spec, FIELDS, COLUMNS)


def body(result):
    return [row for row in result['rows']
            if not row.get('__subtotal__') and not row.get(REMAINDER_KEY)]


# ---------------------------------------------------------------------------
# The property that makes a table honest
# ---------------------------------------------------------------------------

def test_a_capped_table_still_totals_the_whole_portfolio():
    """The bug this replaced: the grand total was taken over the rows that
    survived the cap, so a top-three table of a five-holding portfolio
    totalled 9.4 of 14.7 -- telling a client two thirds of their money had
    gone missing, in a table that looked entirely normal."""
    result = run({'sort_by': [{'field': 'weight', 'direction': 'desc'}],
                  'row_limit': 3, 'remainder_label': 'Other ({count})',
                  'totals': {'grand_total': True}})
    assert float(result['totals']['weight']) == pytest.approx(14.7)


def test_the_remainder_reconciles_the_cap_to_the_total():
    result = run({'sort_by': [{'field': 'weight', 'direction': 'desc'}],
                  'row_limit': 3, 'remainder_label': 'Other ({count})',
                  'totals': {'grand_total': True}})
    kept = sum(row['weight'] for row in body(result))
    remainder = next(row for row in result['rows'] if row.get(REMAINDER_KEY))
    assert kept + float(remainder['weight']) == pytest.approx(float(result['totals']['weight']))
    assert remainder['name'] == 'Other (2)'


def test_subtotals_are_never_folded_into_the_remainder():
    """The second half of the same bug: capping AFTER grouping put subtotal
    rows in the tail, so the remainder double-counted them and came out
    larger than the grand total."""
    result = run({'sort_by': [{'field': 'weight', 'direction': 'desc'}],
                  'group_by': [{'field': 'sector', 'show_subtotal': True}],
                  'row_limit': 3, 'remainder_label': 'Other',
                  'totals': {'grand_total': True}})
    remainder = next(row for row in result['rows'] if row.get(REMAINDER_KEY))
    assert float(remainder['weight']) < float(result['totals']['weight'])
    assert float(remainder['weight']) == pytest.approx(2.6 + 2.7)


# ---------------------------------------------------------------------------
# The property that keeps a methodology honest
# ---------------------------------------------------------------------------

def test_a_precomputed_measure_is_never_aggregated():
    """Adding two time-weighted returns produces a number that is simply
    wrong and looks entirely plausible. The subtotal cell is left blank."""
    result = run({'group_by': [{'field': 'sector', 'show_subtotal': True}],
                  'totals': {'grand_total': True}})
    subtotals = [row for row in result['rows'] if row.get('__subtotal__')]
    assert subtotals and all(row['ret'] is None for row in subtotals)
    assert result['totals']['ret'] is None
    # The column that MAY be summed still is.
    assert all(row['weight'] is not None for row in subtotals)


def test_an_empty_group_aggregates_to_nothing_rather_than_zero():
    """Zero is a number a reader will believe. Blank is the truth."""
    assert aggregate([], 'weight', 'sum') is None


# ---------------------------------------------------------------------------
# Filtering, sorting, grouping
# ---------------------------------------------------------------------------

def test_filters_narrow_the_rows():
    result = run({'filters': [{'field': 'weight', 'op': 'gte', 'value': 2.9}]})
    assert [row['name'] for row in body(result)] == ['Tate', 'Greif', 'Hanwha']


@pytest.mark.parametrize('op,value,expected', [
    ('eq', 'Energy', 2), ('ne', 'Energy', 3), ('in', ['Energy', 'Industrials'], 3),
    ('not_in', ['Energy'], 3), ('contains', 'nanc', 2),
])
def test_every_operator(op, value, expected):
    result = run({'filters': [{'field': 'sector', 'op': op, 'value': value}]})
    assert len(body(result)) == expected


def test_a_null_does_not_abort_a_sort():
    """Rows come from a warehouse. One null in a numeric column used to
    raise and take the whole render with it; nulls sort last, where a
    reader expects "no data"."""
    rows = HOLDINGS + [{'name': 'Unknown', 'sector': 'Energy', 'weight': None, 'ret': None}]
    result = apply_spec(rows, {'sort_by': [{'field': 'weight', 'direction': 'asc'}]},
                        FIELDS, COLUMNS)
    assert body(result)[-1]['name'] == 'Unknown'


def test_the_first_sort_key_is_the_primary_one():
    result = run({'sort_by': [{'field': 'sector', 'direction': 'asc'},
                              {'field': 'weight', 'direction': 'desc'}]})
    assert [row['name'] for row in body(result)] == \
        ['Hanwha', 'Iwatani', 'Tate', 'Greif', 'Vontier']


def test_groups_can_be_ordered_by_size():
    """What "sectors ordered by size" means."""
    result = run({'group_by': [{'field': 'sector', 'sort': 'size'}]})
    assert [group['label'] for group in result['groups']][0] in ('Financials', 'Energy')
    assert result['groups'][-1]['label'] == 'Industrials'


def test_a_hard_cap_says_how_many_it_dropped():
    """No remainder label means the author wanted a hard cap. The result
    still records the drop, so a caller can say so rather than presenting a
    partial table as complete."""
    result = run({'row_limit': 2})
    assert result['truncation'] == {'dropped': 3}


def test_no_limit_leaves_the_rows_alone():
    assert len(body(run({}))) == len(HOLDINGS)
    assert run({})['truncation'] is None


# ---------------------------------------------------------------------------
# A bad spec fails loudly
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('spec', [
    {'filters': [{'op': 'eq', 'value': 1}]},                 # no field
    {'filters': [{'field': 'weight', 'op': 'roughly'}]},     # unknown operator
    {'filters': [{'field': 'sector', 'op': 'in', 'value': 'Energy'}]},  # not a list
    {'sort_by': [{'direction': 'asc'}]},                     # no field
    {'sort_by': [{'field': 'weight', 'direction': 'sideways'}]},
    {'group_by': [{'sort': 'asc'}]},                         # no field
    {'group_by': [{'field': 'sector', 'sort': 'random'}]},
])
def test_a_malformed_spec_raises(spec):
    """A filter that quietly does nothing shows a client more rows than the
    author intended."""
    with pytest.raises(SpecError):
        run(spec)
