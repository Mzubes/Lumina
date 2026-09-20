"""What an element can be bound to, and what it would show.

The canvas's field picker is only as good as the metadata behind it, and
`DatasetField` already carries everything needed to present a value well --
a label, a data type, a format spec, an alignment. This module turns that
into a catalogue the inspector can render, and, crucially, into a SAMPLE of
what each binding would actually draw.

**A sample is labelled as what it is.** Where the dataset cache holds real
rows, the sample is a real value and says so; where it does not, the sample
is derived from the field's own data type and says THAT. Showing a
synthesised number on a canvas without saying it is synthesised is how an
author ends up laying out a factsheet against figures that were never in
the warehouse -- and the layout decisions (column width, decimal places)
are exactly the ones a fake number gets wrong.
"""

import json

from sqlalchemy import select

from schema_v2 import Dataset, DatasetField, DatasetRow, DisplaySpec
from schema_v2.templates import SYSTEM_BINDINGS

# What the renderer can supply for a system binding without a warehouse.
# Two of these are resolved at layout time, not here -- see
# renderers.bindings.LAYOUT_TIME_BINDINGS -- so their sample says so.
SYSTEM_SAMPLES = {
    'client_name': 'Meridian Endowment',
    'portfolio_name': 'Global Small Cap',
    'report_title': 'Quarterly Factsheet',
    'as_of_date': '30 September 2026',
    'generated_at': '1 October 2026',
    'firm_name': 'Lumina Asset Management',
    'page_number': '1',
    'page_count': '8',
}

SYSTEM_LABELS = {
    'client_name': 'Client name',
    'portfolio_name': 'Portfolio name',
    'report_title': 'Report title',
    'as_of_date': 'As-at date',
    'generated_at': 'Generated at',
    'firm_name': 'Firm name',
    'page_number': 'Page number',
    'page_count': 'Page count',
}

# Stand-in values by data type, used only when the cache is empty. Chosen
# to be the WIDEST plausible value rather than a tidy one: an author who
# sizes a column against "1.2%" and then meets "(12,345.67)" has to lay the
# page out twice.
TYPE_SAMPLES = {
    'string': 'Technology',
    'number': '12,345.67',
    'percent': '12.34%',
    'currency': '48,250,000',
    'date': '30 Sep 2026',
    'boolean': 'Yes',
    'basis_points': '-125 bps',
}

# How many rows a display-spec sample carries. Enough to show grouping and
# alignment, few enough that the catalogue stays a page-load rather than a
# data export.
SAMPLE_ROWS = 5


def _loads(value, fallback=None):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _field_json(field, sample, is_real):
    return {
        'id': field.id,
        'name': field.name,
        'short_name': field.short_name,
        'source_column': field.source_column,
        'field_role': field.field_role,
        'data_type': field.data_type,
        'default_aggregation': field.default_aggregation,
        'is_precomputed': bool(field.is_precomputed),
        'alignment': field.alignment,
        'sample': sample,
        # The canvas says "example" next to a derived value. Without this
        # flag it cannot tell the difference, and neither can the author.
        'sample_is_real': is_real,
    }


def _cached_rows(session, dataset_id, limit=SAMPLE_ROWS):
    rows = session.execute(
        select(DatasetRow)
        .where(DatasetRow.dataset_id == dataset_id)
        .order_by(DatasetRow.as_of_date.desc(), DatasetRow.id)
        .limit(limit)).scalars().all()
    return [_loads(row.values, {}) or {} for row in rows]


def _sample_for(field, cached):
    """A field's sample value, preferring a real one.

    Returns (value, is_real). The first cached row that actually carries
    the column wins -- a null in row one is not a reason to fall back to a
    stand-in, because the column may simply be sparse.
    """
    for values in cached:
        if field.source_column in values and values[field.source_column] is not None:
            return values[field.source_column], True
    return TYPE_SAMPLES.get(field.data_type, '—'), False


def _spec_json(spec, fields_by_id):
    """A display spec, described by the fields it names rather than by its
    raw JSON. The inspector shows "grouped by Sector, top 10", which an
    author can check; `{"group_by": [{"field_id": 12}]}` is not."""
    group_by = _loads(spec.group_by, []) or []
    sort_by = _loads(spec.sort_by, []) or []
    filters = _loads(spec.filters, []) or []

    def label(entry):
        field = fields_by_id.get(entry.get('field_id'))
        return field.name if field else f"field {entry.get('field_id')}"

    summary = []
    if group_by:
        summary.append('grouped by ' + ', '.join(label(entry) for entry in group_by))
    if sort_by:
        summary.append('sorted by ' + ', '.join(label(entry) for entry in sort_by))
    if filters:
        summary.append(f'{len(filters)} filter' + ('' if len(filters) == 1 else 's'))
    if spec.row_limit:
        summary.append(f'top {spec.row_limit}')

    return {
        'id': spec.id,
        'name': spec.name,
        'code': spec.code,
        'dataset_id': spec.dataset_id,
        'summary': ' · '.join(summary) or 'every row, unsorted',
        'row_limit': spec.row_limit,
    }


def build_catalogue(session, firm_id):
    """Everything bindable, for one firm.

    One query per table rather than per dataset: the inspector opens this
    on every selection, and N+1 on a firm with forty datasets is a visible
    stall in a drag-and-drop editor.
    """
    datasets = session.execute(
        select(Dataset)
        .where(Dataset.firm_id == firm_id, Dataset.is_active == 1)
        .order_by(Dataset.name)).scalars().all()
    dataset_ids = [dataset.id for dataset in datasets] or [-1]

    fields = session.execute(
        select(DatasetField)
        .where(DatasetField.dataset_id.in_(dataset_ids))
        .order_by(DatasetField.dataset_id, DatasetField.display_order,
                  DatasetField.id)).scalars().all()
    specs = session.execute(
        select(DisplaySpec)
        .where(DisplaySpec.dataset_id.in_(dataset_ids))
        .order_by(DisplaySpec.name)).scalars().all()

    fields_by_id = {field.id: field for field in fields}
    fields_by_dataset = {}
    for field in fields:
        fields_by_dataset.setdefault(field.dataset_id, []).append(field)
    specs_by_dataset = {}
    for spec in specs:
        specs_by_dataset.setdefault(spec.dataset_id, []).append(spec)

    catalogue = []
    for dataset in datasets:
        cached = _cached_rows(session, dataset.id)
        catalogue.append({
            'id': dataset.id,
            'name': dataset.name,
            'code': dataset.code,
            'grain': dataset.grain,
            'description': dataset.description,
            'has_cached_rows': bool(cached),
            'fields': [
                _field_json(field, *_sample_for(field, cached))
                for field in fields_by_dataset.get(dataset.id, [])
            ],
            'display_specs': [
                _spec_json(spec, fields_by_id)
                for spec in specs_by_dataset.get(dataset.id, [])
            ],
        })

    return {
        'system': [
            {
                'key': key,
                'label': SYSTEM_LABELS.get(key, key),
                'sample': SYSTEM_SAMPLES.get(key, ''),
                # These two are resolved by the engine during pagination,
                # never in Python -- so the canvas shows a placeholder and
                # the PDF shows the real count.
                'resolved_at_layout': key in ('page_number', 'page_count'),
            }
            for key in SYSTEM_BINDINGS
        ],
        'datasets': catalogue,
    }
