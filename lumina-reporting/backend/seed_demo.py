import datetime
import json

from database import db_session
from models import (
    Client, Contact, Disclosure, FundData, Holding, PerformanceSnapshot,
    Report, ReportTemplate, User,
)
from renderers import RENDERERS
from report_content import resolve_report_content
from routes.reports import _save_pdf_bytes
from workflow import apply_transition

AS_OF = datetime.date(2026, 7, 31)

STRATEGY_FACTS_ROWS = [
    ['Inception Date', 'April 1, 2021'],
    ['AUM (USD)', '$0.5B'],
    ['Investment Universe', 'MSCI World Small Cap Index'],
    ['# of Positions', 'Generally 40-80'],
    ['Available Vehicles', 'Separate Account'],
]

PORTFOLIO_CHARACTERISTICS_ROWS = [
    ['Price to Normal Earnings', '7.7x', '13.3x'],
    ['Price / Earnings (1 Year Forecast)', '13.0', '15.6'],
    ['Price / Book', '1.1', '2.1'],
    ['Dividend Yield', '2.7%', '1.8%'],
    ['Median Market Cap ($B)', '2.4', '2.3'],
    ['Weighted Average Market Cap ($B)', '3.7', '9.6'],
    ['Active Share', '98.5%', '-'],
    ['Number of Stocks (model portfolio)', '41', '3,877'],
]

SECTOR_WEIGHTS_ROWS = [
    ['Communication Services', '0%', '3%'],
    ['Consumer Discretionary', '22%', '11%'],
    ['Consumer Staples', '8%', '4%'],
    ['Energy', '2%', '5%'],
    ['Financials', '12%', '15%'],
    ['Health Care', '7%', '11%'],
    ['Industrials', '29%', '20%'],
    ['Information Technology', '4%', '14%'],
    ['Materials', '9%', '8%'],
    ['Real Estate', '3%', '8%'],
    ['Utilities', '2%', '1%'],
]

REGION_CONCENTRATION_ROWS = [
    ['North America', '59%', '66%'],
    ['Europe ex U.K.', '17%', '10%'],
    ['United Kingdom', '12%', '5%'],
    ['Japan', '9%', '12%'],
    ['Dev. Asia ex Japan', '3%', '3%'],
    ['Australia/New Zealand', '0%', '3%'],
    ['Dev. Africa/Middle East', '0%', '1%'],
]

MARKET_CAP_ROWS = [
    ['>$75B', '0%', '2%'],
    ['$25-$75B', '0%', '0%'],
    ['$10-$25B', '5%', '2%'],
    ['$2.5-$10B', '69%', '58%'],
    ['<$2.5B', '26%', '38%'],
]

COUNTRY_WEIGHTS_ROWS = [
    ['United States', '57%', '62%'],
    ['United Kingdom', '12%', '5%'],
    ['Japan', '9%', '12%'],
    ['France', '8%', '1%'],
    ['Germany', '3%', '1%'],
    ['Hong Kong', '3%', '1%'],
    ['Ireland', '2%', '0%'],
    ['Finland', '2%', '0%'],
    ['Netherlands', '2%', '1%'],
    ['Others', '2%', '17%'],
]

CALENDAR_YEAR_RETURNS_ROWS = [
    ['Composite - Gross', '-4.1%', '26.3%', '0.4%', '13.8%'],
    ['Composite - Net', '-4.9%', '25.2%', '-0.3%', '12.8%'],
    ['MSCI World Small Cap Index', '-18.8%', '15.8%', '8.2%', '19.9%'],
    ['MSCI World Small Cap Value Index', '-11.8%', '14.1%', '7.2%', '20.5%'],
]

TOP_10_HOLDINGS = [
    ('Spectrum Brands Holdings Inc.', 'Equity', 16_500_000, 3.3),
    ('Advance Auto Parts Inc.', 'Equity', 16_000_000, 3.2),
    ('Teleflex Incorporated', 'Equity', 14_500_000, 2.9),
    ('MasterBrand Inc', 'Equity', 14_000_000, 2.8),
    ('Tokai Carbon Co. Ltd.', 'Equity', 13_500_000, 2.7),
    ('B&M European Value Retail PLC', 'Equity', 13_500_000, 2.7),
    ('Tate & Lyle PLC', 'Equity', 12_500_000, 2.5),
    ('Remy Cointreau SA', 'Equity', 11_000_000, 2.2),
    ('Robert Half Inc.', 'Equity', 11_000_000, 2.2),
    ('ABM Industries Incorporated', 'Equity', 10_500_000, 2.1),
]

PERFORMANCE_ROWS = [
    # period_type, composite gross return %, MSCI World Small Cap Index %
    ('1M', 4.2, -2.6),
    ('QTD', 4.2, -2.4),
    ('YTD', 18.2, 13.9),
    ('1Y', 27.2, 25.5),
    ('3Y', 19.1, 14.8),
    ('5Y', 11.1, 7.1),
    ('SI', 11.2, 7.3),
]

ABOUT_US = (
    "Pzena Investment Management is a global deep value equity manager that uses a "
    "proprietary research process to buy companies we believe are priced significantly "
    "below their long-term earnings potential. A diverse team with deep industry "
    "backgrounds, Pzena is dedicated to meeting client needs as thought leaders in "
    "value investing."
)

PORTFOLIO_COMMENTARY = (
    "Markets advanced strongly during the second quarter, as investors looked past "
    "disruptions in the Middle East and embraced a semiconductor-led rally. Small caps "
    "participated in the advance, though growth meaningfully outperformed value within "
    "the asset class, extending a pattern that has persisted for much of the past year. "
    "Despite the challenging style environment for value-oriented approaches, our "
    "portfolio outperformed the MSCI World Small Cap Value Index for the period, though "
    "it trailed the broad MSCI World Small Cap Index. The industrials, consumer "
    "discretionary, and financials sectors contributed most to absolute performance "
    "during the period, while the energy and utilities sectors detracted from absolute "
    "performance. Portfolio activity remained centered on our value-oriented process: we "
    "initiated four positions in Genpact, VTech Holdings, Doir, and ScanSource during the "
    "period, and added to our existing positions in B&M European Value Retail, "
    "Winnebago Industries, and MillerKnoll on weakness, consistent with our valuation "
    "framework and conviction in our long-term theses."
)

GENERAL_DISCLOSURES = (
    "Pzena Investment Management, LLC (“PIM”) is a U.S.-registered investment adviser "
    "with the United States Securities and Exchange Commission. PIM makes a global deep "
    "value investment approach. All investments involve risk, including loss of "
    "principal. Investments may be in a variety of instruments whose changes in rates of "
    "exchange between currencies may cause the value of investments to decrease or "
    "increase. The price, liquidity, and ability to sell any security or commodity may "
    "be adversely affected by market changes in commodity prices, currency conversion "
    "or availability. Investments in small-cap companies involve additional risks such "
    "as limited liquidity and greater volatility than larger companies. Investments in "
    "foreign securities involve political, economic and currency risks, greater "
    "volatility and differences in accounting methods. These risks are greater for "
    "investments in Emerging Markets. PIM's strategies emphasize a “value” style of "
    "investing, which targets undervalued companies with characteristics for improved "
    "valuations. This style of investing is subject to the risk that the valuations "
    "never improve or that returns on “value” securities may not move in tandem with "
    "the returns on other styles of investing or the stock market in general. Past "
    "performance does not predict future returns, and the past performance of any "
    "account or composite fund managed by PIM does not predict the future returns of "
    "any account or composite fund managed by PIM. Investment return and principal "
    "value of an investment will fluctuate over time, may go down as well as up, and "
    "you may not receive upon redemption the full amount of your original investment."
)


def _get_or_create_user(email, password, role, client_id=None):
    email = email.strip().lower()
    user = db_session.query(User).filter_by(email=email).first()
    if user:
        return user
    user = User(email=email, client_id=client_id, role=role)
    user.set_password(password)
    db_session.add(user)
    db_session.commit()
    return user


def _data_table(title, columns, rows):
    return {
        'id': title.lower().replace(' ', '-'),
        'type': 'data_table',
        'title': title,
        'data_binding': {'columns': columns, 'rows': rows},
    }


def seed_demo():
    """Idempotent demo dataset: a reverse-engineered Pzena Global Small Cap
    Focused Value factsheet, taken end-to-end through the full workflow to
    'distributed'. Safe to run more than once -- exits early once seeded."""
    if db_session.query(FundData).filter_by(ticker='PZFVX').first():
        return False

    admin = _get_or_create_user('admin@lumina.test', 'admin-pass', 'admin')
    _get_or_create_user('editor@lumina.test', 'editor-pass', 'editor')
    compliance = _get_or_create_user('compliance@lumina.test', 'compliance-pass', 'compliance')

    client = db_session.query(Client).filter_by(name='Meridian Pension Partners').first()
    if not client:
        client = Client(name='Meridian Pension Partners', contact_email='dana.whitfield@meridianpp.example')
        db_session.add(client)
        db_session.commit()

    if not db_session.query(Contact).filter_by(client_id=client.id, email='dana.whitfield@meridianpp.example').first():
        db_session.add(Contact(
            client_id=client.id, name='Dana Whitfield', title='Director of Investments',
            email='dana.whitfield@meridianpp.example', phone='+1 (212) 555-0148',
        ))

    _get_or_create_user('client@lumina.test', 'client-pass', 'client', client_id=client.id)
    db_session.commit()

    fund = FundData(
        name='Pzena Global Small Cap Focused Value', asset_class='Equity', ticker='PZFVX',
        inception_date=datetime.date(2021, 4, 1),
        description=ABOUT_US, investment_universe='MSCI World Small Cap Index',
    )
    db_session.add(fund)
    db_session.commit()

    for security_name, asset_class, market_value, weight_pct in TOP_10_HOLDINGS:
        db_session.add(Holding(
            fund_id=fund.id, as_of_date=AS_OF, security_id=security_name[:50],
            security_name=security_name, asset_class=asset_class,
            market_value=market_value, weight_pct=weight_pct,
        ))

    for period_type, return_pct, benchmark_return_pct in PERFORMANCE_ROWS:
        db_session.add(PerformanceSnapshot(
            fund_id=fund.id, as_of_date=AS_OF, period_type=period_type,
            return_pct=return_pct, benchmark_return_pct=benchmark_return_pct,
        ))
    db_session.commit()

    disclosure = Disclosure(
        title='General Disclosures', body=GENERAL_DISCLOSURES, category='Legal', created_by=admin.id,
    )
    db_session.add(disclosure)
    db_session.commit()

    components = [
        _data_table('Strategy Facts', ['Metric', 'Value'], STRATEGY_FACTS_ROWS),
        _data_table('Portfolio Characteristics', ['Metric', 'Strategy', 'Index'], PORTFOLIO_CHARACTERISTICS_ROWS),
        {'id': 'about-us', 'type': 'text_block', 'title': 'About Us', 'data_binding': {'static_text': ABOUT_US}},
        {
            'id': 'portfolio-managers', 'type': 'people_grid', 'title': 'Portfolio Managers',
            'data_binding': {'rows': [
                {'name': 'Evan Fox, CFA', 'title': 'Portfolio Manager', 'detail': 'With Pzena since 2007 · In industry since 2007'},
                {'name': 'Matt Ring', 'title': 'Portfolio Manager', 'detail': 'With Pzena since 2010 · In industry since 2002'},
            ]},
        },
        {
            'id': 'top-10-holdings', 'type': 'holdings_table', 'title': 'Top 10 Holdings',
            'data_binding': {'filters': {'as_of': 'latest'}},
        },
        _data_table('Sector Weights', ['Sector', 'Strategy', 'Index'], SECTOR_WEIGHTS_ROWS),
        _data_table('Region Concentration', ['Region', 'Strategy', 'Index'], REGION_CONCENTRATION_ROWS),
        _data_table('Market Cap (USD)', ['Range', 'Strategy', 'Index'], MARKET_CAP_ROWS),
        _data_table('Country Weights', ['Country', 'Strategy', 'Index'], COUNTRY_WEIGHTS_ROWS),
        {
            'id': 'performance-summary', 'type': 'performance_summary',
            'title': 'Performance Summary (Composite Gross vs. MSCI World Small Cap Index)',
            'data_binding': {'filters': {}},
        },
        _data_table(
            'Calendar Year Returns (USD)',
            ['Series', '2023', '2024', '2025 YTD', 'Since Inception'],
            CALENDAR_YEAR_RETURNS_ROWS,
        ),
        {'id': 'commentary', 'type': 'text_block', 'title': 'Portfolio Commentary', 'data_binding': {'static_text': PORTFOLIO_COMMENTARY}},
    ]

    template = ReportTemplate(
        name='Pzena Global Small Cap Focused Value — Monthly Factsheet',
        description='Reverse-engineered from the real Pzena Global Small Cap Focused Value monthly factsheet.',
        components=json.dumps(components),
        disclosure_ids=json.dumps([disclosure.id]),
        header_config=json.dumps({
            'title': 'Pzena Global Small Cap Focused Value — Monthly Factsheet',
            'subtitle': f'FACTSHEET · Strategy overview as of {AS_OF.strftime("%B %Y")}',
        }),
        footer_config=json.dumps({
            'text': 'Pzena Investment Management, LLC | Confidential — for institutional use only',
        }),
        created_by=admin.id,
    )
    db_session.add(template)
    db_session.commit()

    report = Report(
        title=f'Pzena Global Small Cap Focused Value — Monthly Factsheet ({AS_OF.strftime("%B %Y")})',
        fund_id=fund.id, template_id=template.id, report_type='factsheet',
        status='draft', created_by=admin.id,
    )
    db_session.add(report)
    db_session.commit()

    content = resolve_report_content(report, template)
    report.file_path = _save_pdf_bytes(RENDERERS['pdf'](content), report.id)
    db_session.commit()

    apply_transition(report, 'submit', admin.id)
    apply_transition(report, 'approve', admin.id)
    apply_transition(report, 'certify', compliance.id)
    apply_transition(report, 'distribute', admin.id)

    return True
