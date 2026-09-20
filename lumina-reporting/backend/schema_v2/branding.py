"""Brand kits -- what makes the output marketing quality rather than a dump.

The deliverable is a document someone is willing to put in front of an
institutional client. That is a typographic and layout problem as much as a
data one, and it needs somewhere to live that isn't hardcoded per template.

Two levels, resolved most-specific-first:

    firm default   the house style -- used unless something overrides it
    per client     a client-branded pack (a sub-advised mandate carrying the
                   distributor's logo, a white-labelled statement)

Deliberately not a third level per template: a template that needs to look
different from the house style is a template design choice, and belongs in
the template's own theme_config rather than in a brand kit nobody else uses.
"""

from sqlalchemy import (
    Column, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)

from .base import Base, TimestampMixin, firm_column


class BrandKit(Base, TimestampMixin):
    """A resolved visual identity for generated documents.

    `client_id` null means this is the firm's default. At most one default
    per firm, enforced below, because two defaults is a silent coin toss.
    """

    __tablename__ = 'brand_kit'
    __table_args__ = (
        # One kit per client, and one firm default (client_id NULL). SQLite
        # and Postgres both treat NULLs as distinct in a unique index, so the
        # single-default rule is enforced by is_firm_default instead.
        UniqueConstraint('firm_id', 'client_id', name='uq_brand_kit_firm_client'),
        Index('ix_brand_kit_default', 'firm_id', 'is_firm_default'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    # Null -> the firm default.
    client_id = Column(Integer, ForeignKey('client.id'), nullable=True)
    is_firm_default = Column(Integer, nullable=False, default=0)

    name = Column(String(200), nullable=False)

    # --- assets ----------------------------------------------------------
    # Stored as references, not bytes: a logo belongs in object storage, and
    # a multi-megabyte blob in a row every query touches is a tax on every
    # page load.
    logo_uri = Column(String(500), nullable=True)
    logo_mono_uri = Column(String(500), nullable=True)   # for dark or single-colour covers
    cover_image_uri = Column(String(500), nullable=True)
    watermark_uri = Column(String(500), nullable=True)   # DRAFT / CONFIDENTIAL overlays

    # --- palette ---------------------------------------------------------
    # JSON so a house style can carry as many accents and chart colours as it
    # needs. Expected keys: primary, secondary, accent, ink, muted, surface,
    # positive, negative, chart_series (a list).
    #
    # A categorical chart palette is part of brand identity and has to be
    # colour-vision-deficiency safe -- which is a property of the whole list,
    # not of any one colour, so it is stored and validated as a list.
    colors = Column(Text, nullable=True)

    # --- typography ------------------------------------------------------
    # Expected keys: heading_family, body_family, numeric_family, weights,
    # and a size scale. A separate numeric family matters: figures in a
    # holdings table need tabular (fixed-width) digits or the columns do not
    # line up, and most brand body faces are proportional.
    typography = Column(Text, nullable=True)
    # URIs for the licensed faces, so rendering does not silently substitute
    # a fallback and change the document's look between environments.
    font_asset_uris = Column(Text, nullable=True)

    # --- page furniture --------------------------------------------------
    # Margins, header/footer content, page-number style, paper size.
    page_setup = Column(Text, nullable=True)
    # Boilerplate that must appear on every page of every document under
    # this kit, separate from the per-report Disclosure records.
    footer_text = Column(Text, nullable=True)

    is_active = Column(Integer, nullable=False, default=1)
