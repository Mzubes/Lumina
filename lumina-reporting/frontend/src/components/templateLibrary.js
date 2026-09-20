// Pre-built, industry-standard factsheet sections a template author can drag
// onto the canvas -- generalized from the one real reverse-engineered
// factsheet in the app (the seeded Pzena template), not invented from
// scratch. Each buildDefault() returns the SAME internal editor-state shape
// newComponent() in templates.js produces (not the API data_binding shape --
// toApiComponents() is the only translation layer, and it doesn't change).

const base = () => ({
  type: 'holdings_table',
  title: '',
  periodTypes: ['QTD', 'YTD'],
  staticText: '',
  tableColumns: ['Metric', 'Value'],
  tableRows: [['', '']],
  chartType: 'none',
  people: [{ name: '', title: '', detail: '', photoUrl: '' }],
  reviewRole: '',
  reportId: '',
});

const table = (title, columns, rows, chartType = 'none') => () => ({
  ...base(), type: 'data_table', title, tableColumns: columns, tableRows: rows, chartType,
});

export const TEMPLATE_LIBRARY = [
  {
    category: 'Tables & Data',
    presets: [
      { id: 'fund-facts', label: 'Fund / Strategy Facts', description: 'Inception date, AUM, investment universe, vehicles',
        buildDefault: table('Fund / Strategy Facts', ['Metric', 'Value'], [
          ['Inception Date', ''], ['AUM (USD)', ''], ['Investment Universe', ''], ['Available Vehicles', ''],
        ]) },
      { id: 'portfolio-characteristics', label: 'Portfolio Characteristics', description: 'Valuation metrics vs. index',
        buildDefault: table('Portfolio Characteristics', ['Metric', 'Strategy', 'Index'], [
          ['Price / Earnings', '', ''], ['Price / Book', '', ''], ['Dividend Yield', '', ''], ['Weighted Avg Market Cap ($B)', '', ''],
        ]) },
      { id: 'sector-weights', label: 'Sector Weights', description: 'Sector allocation vs. index, with a comparison chart',
        buildDefault: table('Sector Weights', ['Sector', 'Strategy', 'Index'], [
          ['Financials', '', ''], ['Industrials', '', ''], ['Health Care', '', ''], ['Information Technology', '', ''],
        ], 'bar_comparison') },
      { id: 'region-weights', label: 'Region Concentration', description: 'Geographic allocation vs. index, with a comparison chart',
        buildDefault: table('Region Concentration', ['Region', 'Strategy', 'Index'], [
          ['North America', '', ''], ['Europe', '', ''], ['Asia', '', ''],
        ], 'bar_comparison') },
      { id: 'market-cap-breakdown', label: 'Market Cap Breakdown', description: 'Market-cap band allocation, with a comparison chart',
        buildDefault: table('Market Cap Breakdown', ['Range', 'Strategy', 'Index'], [
          ['>$25B', '', ''], ['$10B-$25B', '', ''], ['$2.5B-$10B', '', ''], ['<$2.5B', '', ''],
        ], 'bar_comparison') },
      { id: 'country-weights', label: 'Country Weights', description: 'Country allocation vs. index, with a comparison chart',
        buildDefault: table('Country Weights', ['Country', 'Strategy', 'Index'], [
          ['United States', '', ''], ['United Kingdom', '', ''], ['Japan', '', ''],
        ], 'bar_comparison') },
      { id: 'calendar-year-returns', label: 'Calendar Year Returns', description: 'Strategy vs. benchmark, year by year',
        buildDefault: table('Calendar Year Returns', ['Year', 'Strategy %', 'Benchmark %'], [
          ['2024', '', ''], ['2023', '', ''], ['2022', '', ''], ['Since Inception', '', ''],
        ]) },
    ],
  },
  {
    category: 'Performance',
    presets: [
      { id: 'performance-summary', label: 'Performance Summary', description: 'Trailing-period returns vs. benchmark (data-driven)',
        buildDefault: () => ({ ...base(), type: 'performance_summary', title: 'Performance Summary', periodTypes: ['QTD', 'YTD'] }) },
      { id: 'top-holdings', label: 'Top Holdings', description: 'Largest positions as of the latest date on file (data-driven)',
        buildDefault: () => ({ ...base(), type: 'holdings_table', title: 'Top Holdings' }) },
    ],
  },
  {
    category: 'People',
    presets: [
      { id: 'portfolio-managers', label: 'Portfolio Managers / Team', description: 'Names, titles, and tenure',
        buildDefault: () => ({
          ...base(), type: 'people_grid', title: 'Portfolio Managers',
          people: [{ name: '', title: 'Portfolio Manager', detail: '', photoUrl: '' }, { name: '', title: 'Portfolio Manager', detail: '', photoUrl: '' }],
        }) },
    ],
  },
  {
    category: 'Text',
    presets: [
      { id: 'firm-overview', label: 'Firm Overview / About Us', description: 'A short paragraph describing the firm',
        buildDefault: () => ({ ...base(), type: 'text_block', title: 'About Us' }) },
      { id: 'portfolio-commentary', label: 'Portfolio Commentary', description: 'Market/portfolio commentary -- pre-set to require Compliance sign-off',
        buildDefault: () => ({ ...base(), type: 'text_block', title: 'Portfolio Commentary', reviewRole: 'compliance' }) },
    ],
  },
  {
    category: 'Blank',
    presets: [
      { id: 'blank-holdings-table', label: 'Blank Holdings Table', description: 'Data-driven, no preset title',
        buildDefault: () => ({ ...base(), type: 'holdings_table', title: '' }) },
      { id: 'blank-performance-summary', label: 'Blank Performance Summary', description: 'Data-driven, no preset title',
        buildDefault: () => ({ ...base(), type: 'performance_summary', title: '' }) },
      { id: 'blank-text-block', label: 'Blank Text Block', description: 'Free-form commentary or narrative',
        buildDefault: () => ({ ...base(), type: 'text_block', title: '' }) },
      { id: 'blank-data-table', label: 'Blank Data Table', description: 'Fully custom columns and rows',
        buildDefault: () => ({ ...base(), type: 'data_table', title: '' }) },
      { id: 'blank-people-grid', label: 'Blank People Grid', description: 'Fully custom bios',
        buildDefault: () => ({ ...base(), type: 'people_grid', title: '' }) },
      { id: 'blank-report-reference', label: 'Blank Report Reference', description: "Inlines another report's own components",
        buildDefault: () => ({ ...base(), type: 'report_reference', title: '' }) },
    ],
  },
];

export const ALL_PRESETS = TEMPLATE_LIBRARY.flatMap(group => group.presets);
export const PRESETS_BY_ID = Object.fromEntries(ALL_PRESETS.map(preset => [preset.id, preset]));
