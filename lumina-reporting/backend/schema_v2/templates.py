"""How a document is laid out: templates, sections, elements.

Today's `ReportTemplate` holds a flat JSON list of components that stack
down the page in order. That is enough for a factsheet body and nothing
else -- there is no way to say "this logo sits 12mm from the top-right
corner of every page", which is most of what a designed document is.

The model here is the one every document-composition tool in this market
converges on, because the problem forces it:

    DocumentTemplate
      └─ TemplateSection     a band down the page
      │                      flow  -> stacks, may repeat per row of a dataset,
      │                               breaks across pages
      │                      fixed -> a fixed-height band whose contents are
      │                               anchored, and which may repeat on every
      │                               page
      └─ TemplateElement     x, y, w, h, z within its section

A template mixes both: a fixed masthead, a flowing body, a fixed footer.
"Free placement anywhere on the page" is just a fixed section the height of
the page.

**Two rules hold everywhere below.**

*Millimetres, not pixels.* A document is a physical artefact. mm converts
cleanly to CSS mm, to PowerPoint's EMU (1mm = 36000 EMU) and to PDF points;
px would bake in a DPI that only one of the three shares.

*Nothing here may encode HTML.* Two renderers consume this tree -- the
WeasyPrint one today and PPTX in Phase G -- so an element carries position,
size, type, binding and a **brand-kit token name**, never a CSS
declaration. That is enforced rather than documented: `style_token` rejects
anything containing a colon or a semicolon, which is what a stylesheet
fragment always contains and a token name never does.
"""

from sqlalchemy import (
    CheckConstraint, Column, ForeignKey, Index, Integer, Numeric, String, Text,
    UniqueConstraint,
)

from .base import Base, TimestampMixin, firm_column
from .structures import _in

# How a section places its contents.
#   flow  -- the band grows to fit, stacks after the previous one, and breaks
#            across pages when it has to. A factsheet body is one of these.
#   fixed -- the band is a declared height and does not grow. A masthead, a
#            footer, or a whole page of free placement.
LAYOUT_MODES = ('flow', 'fixed')

# When a section reappears. Only a fixed section may repeat: a band whose
# height depends on its content cannot be drawn identically on every page.
REPEAT_MODES = ('none', 'every_page', 'first_page', 'except_first_page')

# Page-break behaviour relative to the preceding section.
BREAK_RULES = ('auto', 'page', 'avoid')

ORIENTATIONS = ('portrait', 'landscape')

PAGE_SIZES = ('a4', 'letter', 'legal', 'a3')

# What an element is. Deliberately abstract: each renderer decides how to
# draw a 'line', and neither the word nor the model implies <hr> or a PPTX
# connector.
ELEMENT_TYPES = (
    'text',         # static words -- a heading, a label, boilerplate
    'field',        # one value from a dataset, or one system value
    'table',        # rows from a display spec
    'chart',        # a chart over a display spec
    'image',        # a logo or a photograph, by asset reference
    'line',         # a rule
    'box',          # a filled or stroked rectangle, for banding
    'page_number',  # resolved at layout time, so it cannot be a 'field'
    # A grid of captioned figures -- an investment team, a set of awards.
    # A domain block rather than an HTML one: both renderers can draw it,
    # and a hand-built v2 template can express the same thing as a flow
    # section iterating a spec. It exists because today's templates have
    # one, and the cutover adapter needs somewhere honest to put it.
    'people_grid',
)

# What an element's content is drawn from.
#   none          -- static (text, line, box, image)
#   dataset_field -- one field's value, for a 'field' element
#   display_spec  -- a whole result set, for a 'table' or 'chart'
#   system        -- something the renderer knows: the client name, the
#                    as-of date, the page count. Named by `binding_key`.
BINDING_KINDS = ('none', 'dataset_field', 'display_spec', 'system')

# The system values a binding may name. A closed list, because an open one
# becomes a template language and then an injection surface.
SYSTEM_BINDINGS = (
    'client_name', 'portfolio_name', 'report_title', 'as_of_date',
    'generated_at', 'page_number', 'page_count', 'firm_name',
)


def _mm_column(**kwargs):
    """A millimetre measurement. Numeric rather than Float, for the same
    reason money is: a layout that drifts by a hair per element is a layout
    that does not reproduce."""
    return Column(Numeric(9, 3), **kwargs)


class DocumentTemplate(Base, TimestampMixin):
    """A document's layout, independent of any one report.

    Named DocumentTemplate rather than ReportTemplate on purpose: models.py
    still has a live class by that name, and two SQLAlchemy classes sharing
    a name across two registries is a debugging trap for the whole cutover.
    """

    __tablename__ = 'document_template'
    __table_args__ = (
        UniqueConstraint('firm_id', 'code', 'version', name='uq_document_template_code'),
        CheckConstraint(_in('page_size', PAGE_SIZES), name='ck_document_template_page_size'),
        CheckConstraint(_in('orientation', ORIENTATIONS), name='ck_document_template_orientation'),
        CheckConstraint('margin_top_mm >= 0 AND margin_bottom_mm >= 0 AND '
                        'margin_left_mm >= 0 AND margin_right_mm >= 0',
                        name='ck_document_template_margins'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()

    name = Column(String(200), nullable=False)
    code = Column(String(80), nullable=False)
    description = Column(Text, nullable=True)

    # A published template is immutable; an edit makes version n+1. A pack
    # records which version rendered it, so "why does March look different
    # from April" has an answer.
    version = Column(Integer, nullable=False, default=1)
    is_published = Column(Integer, nullable=False, default=0)

    # Null -> the firm default kit resolves at render time. Binding the kit
    # here rather than copying its values keeps a rebrand to one edit.
    brand_kit_id = Column(Integer, ForeignKey('brand_kit.id'), nullable=True)

    page_size = Column(String(20), nullable=False, default='a4')
    orientation = Column(String(20), nullable=False, default='portrait')
    margin_top_mm = _mm_column(nullable=False, default=26)
    margin_bottom_mm = _mm_column(nullable=False, default=20)
    margin_left_mm = _mm_column(nullable=False, default=16)
    margin_right_mm = _mm_column(nullable=False, default=16)

    is_active = Column(Integer, nullable=False, default=1)


class TemplateSection(Base, TimestampMixin):
    """A band down the page.

    `iterate_display_spec_id` is what makes a repeating block possible: a
    section bound to a spec is drawn once per row of it, which is how "one
    card per holding" or "a page per portfolio" is expressed without the
    template needing a loop construct.
    """

    __tablename__ = 'template_section'
    __table_args__ = (
        UniqueConstraint('template_id', 'ordinal', name='uq_template_section_ordinal'),
        CheckConstraint(_in('layout_mode', LAYOUT_MODES), name='ck_template_section_layout'),
        CheckConstraint(_in('repeat_mode', REPEAT_MODES), name='ck_template_section_repeat'),
        CheckConstraint(_in('break_before', BREAK_RULES), name='ck_template_section_break_before'),
        CheckConstraint(_in('break_after', BREAK_RULES), name='ck_template_section_break_after'),
        # A fixed band has to declare its height -- that is what "fixed"
        # means. A flow band must NOT, because its height is its content's.
        CheckConstraint(
            "(layout_mode = 'fixed' AND height_mm IS NOT NULL) OR "
            "(layout_mode = 'flow' AND height_mm IS NULL)",
            name='ck_template_section_height_matches_mode'),
        # Only a fixed band may repeat. A band whose height depends on its
        # content cannot be drawn identically on every page, and a running
        # header that changes height per page is a broken document.
        CheckConstraint("repeat_mode = 'none' OR layout_mode = 'fixed'",
                        name='ck_template_section_repeat_needs_fixed'),
        # Iteration is a flow behaviour: N rows means N bands, which means a
        # height that is not knowable in advance.
        CheckConstraint("iterate_display_spec_id IS NULL OR layout_mode = 'flow'",
                        name='ck_template_section_iterate_needs_flow'),
        Index('ix_template_section_template', 'firm_id', 'template_id', 'ordinal'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    template_id = Column(Integer, ForeignKey('document_template.id'), nullable=False, index=True)

    ordinal = Column(Integer, nullable=False)
    name = Column(String(200), nullable=True)

    layout_mode = Column(String(20), nullable=False, default='flow')
    height_mm = _mm_column(nullable=True)

    repeat_mode = Column(String(30), nullable=False, default='none')
    break_before = Column(String(20), nullable=False, default='auto')
    break_after = Column(String(20), nullable=False, default='auto')

    # Draw this band once per row of the spec.
    iterate_display_spec_id = Column(Integer, ForeignKey('display_spec.id'), nullable=True)

    # A band the reader never sees but the layout still reserves -- used for
    # a section that only applies to some reports.
    is_visible = Column(Integer, nullable=False, default=1)


class TemplateElement(Base, TimestampMixin):
    """One drawn thing, anchored within its section.

    Position is relative to the section's own top-left corner in both layout
    modes -- the difference between them is where that corner lands, not how
    elements sit inside it. One rule, two behaviours.
    """

    __tablename__ = 'template_element'
    __table_args__ = (
        CheckConstraint(_in('element_type', ELEMENT_TYPES), name='ck_template_element_type'),
        CheckConstraint(_in('binding_kind', BINDING_KINDS), name='ck_template_element_binding_kind'),
        CheckConstraint('x_mm >= 0 AND y_mm >= 0 AND w_mm > 0 AND h_mm > 0',
                        name='ck_template_element_box'),
        # Exactly the binding column the kind names, and no other. Without
        # this a row can claim to be a dataset field while carrying a
        # display spec, and the renderer has to guess.
        CheckConstraint(
            "(binding_kind = 'none' AND dataset_field_id IS NULL "
            "   AND display_spec_id IS NULL AND binding_key IS NULL) OR "
            "(binding_kind = 'dataset_field' AND dataset_field_id IS NOT NULL "
            "   AND display_spec_id IS NULL AND binding_key IS NULL) OR "
            "(binding_kind = 'display_spec' AND display_spec_id IS NOT NULL "
            "   AND dataset_field_id IS NULL AND binding_key IS NULL) OR "
            "(binding_kind = 'system' AND binding_key IS NOT NULL "
            "   AND dataset_field_id IS NULL AND display_spec_id IS NULL)",
            name='ck_template_element_binding_exclusive'),
        CheckConstraint(
            f"binding_key IS NULL OR {_in('binding_key', SYSTEM_BINDINGS)}",
            name='ck_template_element_binding_key'),
        # The renderer-agnostic rule, enforced instead of documented. A
        # brand-kit token is a name ('heading_1', 'accent_rule'); a CSS
        # declaration always carries a colon, and usually a semicolon.
        # Letting one through here is how an HTML-only template gets built
        # by accident and discovered in Phase G.
        CheckConstraint(
            "style_token IS NULL OR "
            "(style_token NOT LIKE '%:%' AND style_token NOT LIKE '%;%')",
            name='ck_template_element_style_is_a_token'),
        Index('ix_template_element_section', 'firm_id', 'section_id', 'z_index'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    section_id = Column(Integer, ForeignKey('template_section.id'), nullable=False, index=True)

    element_type = Column(String(30), nullable=False)

    # Relative to the section's top-left corner, in millimetres.
    x_mm = _mm_column(nullable=False, default=0)
    y_mm = _mm_column(nullable=False, default=0)
    w_mm = _mm_column(nullable=False)
    h_mm = _mm_column(nullable=False)
    # Draw order within the section. Explicit because a PPTX shape tree is
    # ordered and an HTML stacking context is not -- leaving it implicit
    # would make the two renderers disagree about what sits on top.
    z_index = Column(Integer, nullable=False, default=0)

    binding_kind = Column(String(20), nullable=False, default='none')
    dataset_field_id = Column(Integer, ForeignKey('dataset_field.id'), nullable=True)
    display_spec_id = Column(Integer, ForeignKey('display_spec.id'), nullable=True)
    binding_key = Column(String(40), nullable=True)

    # For a 'text' element. Static words, never a template expression --
    # substitution is what a 'system' binding is for.
    static_text = Column(Text, nullable=True)

    # Names a style in the brand kit. Never a CSS declaration; see the
    # check constraint above.
    style_token = Column(String(80), nullable=True)

    # Renderer-agnostic presentation options: chart kind, text alignment,
    # number format override, image fit. JSON because the set differs by
    # element type and a column per option would be mostly null.
    options = Column(Text, nullable=True)

    is_visible = Column(Integer, nullable=False, default=1)
