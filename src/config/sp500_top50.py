"""
S&P 500 Top 50 Stocks by Market Cap

This list is used for ML model training and analysis.
Updated quarterly - last update: Q1 2025

Market cap rankings change frequently. This list represents
an approximation of the top 50 stocks by market capitalization.
"""

# Top 50 S&P 500 stocks by market cap (as of Q1 2025)
SP500_TOP_50 = [
    # Mega-cap Tech
    "AAPL",   # Apple Inc.
    "MSFT",   # Microsoft Corporation
    "GOOGL",  # Alphabet Inc. Class A
    "AMZN",   # Amazon.com Inc.
    "NVDA",   # NVIDIA Corporation
    "META",   # Meta Platforms Inc.
    "TSLA",   # Tesla Inc.
    "AVGO",   # Broadcom Inc.
    "ORCL",   # Oracle Corporation
    "ADBE",   # Adobe Inc.

    # Financials
    "BRK.B",  # Berkshire Hathaway Inc. Class B
    "JPM",    # JPMorgan Chase & Co.
    "V",      # Visa Inc.
    "MA",     # Mastercard Inc.
    "BAC",    # Bank of America Corp
    "WFC",    # Wells Fargo & Company
    "GS",     # Goldman Sachs Group Inc.
    "MS",     # Morgan Stanley
    "AXP",    # American Express Company
    "BLK",    # BlackRock Inc.

    # Healthcare
    "UNH",    # UnitedHealth Group Inc.
    "JNJ",    # Johnson & Johnson
    "LLY",    # Eli Lilly and Company
    "PFE",    # Pfizer Inc.
    "ABBV",   # AbbVie Inc.
    "MRK",    # Merck & Co. Inc.
    "TMO",    # Thermo Fisher Scientific Inc.
    "ABT",    # Abbott Laboratories
    "DHR",    # Danaher Corporation
    "BMY",    # Bristol-Myers Squibb Company

    # Consumer
    "WMT",    # Walmart Inc.
    "PG",     # Procter & Gamble Company
    "KO",     # Coca-Cola Company
    "PEP",    # PepsiCo Inc.
    "COST",   # Costco Wholesale Corporation
    "HD",     # Home Depot Inc.
    "MCD",    # McDonald's Corporation
    "NKE",    # Nike Inc.
    "SBUX",   # Starbucks Corporation
    "TGT",    # Target Corporation

    # Energy & Industrials
    "XOM",    # Exxon Mobil Corporation
    "CVX",    # Chevron Corporation
    "COP",    # ConocoPhillips
    "CAT",    # Caterpillar Inc.
    "UNP",    # Union Pacific Corporation
    "RTX",    # RTX Corporation
    "HON",    # Honeywell International Inc.
    "BA",     # Boeing Company
    "GE",     # General Electric Company
    "LMT",    # Lockheed Martin Corporation
]

# Sector classifications for the top 50
SECTOR_CLASSIFICATIONS = {
    "Technology": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ORCL", "ADBE"],
    "Financials": ["BRK.B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "AXP", "BLK"],
    "Healthcare": ["UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY"],
    "Consumer": ["WMT", "PG", "KO", "PEP", "COST", "HD", "MCD", "NKE", "SBUX", "TGT"],
    "Energy & Industrials": ["XOM", "CVX", "COP", "CAT", "UNP", "RTX", "HON", "BA", "GE", "LMT"]
}


def get_top_50() -> list:
    """Return the list of top 50 S&P 500 stocks"""
    return SP500_TOP_50.copy()


def get_stocks_by_sector(sector: str) -> list:
    """
    Get stocks for a specific sector

    Args:
        sector: One of 'Technology', 'Financials', 'Healthcare', 'Consumer', 'Energy & Industrials'

    Returns:
        List of stock symbols in that sector
    """
    return SECTOR_CLASSIFICATIONS.get(sector, [])


def get_sector_for_stock(symbol: str) -> str:
    """
    Get the sector for a specific stock

    Args:
        symbol: Stock ticker symbol

    Returns:
        Sector name or 'Unknown'
    """
    for sector, stocks in SECTOR_CLASSIFICATIONS.items():
        if symbol.upper() in stocks:
            return sector
    return "Unknown"


# For quick testing - a smaller subset
SP500_TEST_SUBSET = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]


def get_test_subset() -> list:
    """Return a small subset of stocks for testing"""
    return SP500_TEST_SUBSET.copy()


# Extended diverse stock universe for better ML training
DIVERSE_STOCK_UNIVERSE = {
    # Large Cap Tech (from S&P 500)
    "large_cap_tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ORCL", "ADBE", "CRM", "CSCO", "INTC", "AMD", "QCOM"],

    # Large Cap Financials
    "large_cap_finance": ["JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "AXP", "BLK", "C", "SCHW", "USB", "PNC"],

    # Large Cap Healthcare
    "large_cap_health": ["UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY", "AMGN", "GILD", "ISRG", "MDT"],

    # Large Cap Consumer
    "large_cap_consumer": ["WMT", "PG", "KO", "PEP", "COST", "HD", "MCD", "NKE", "SBUX", "TGT", "LOW", "TJX", "BKNG", "CMG"],

    # Large Cap Energy & Industrials
    "large_cap_industrial": ["XOM", "CVX", "COP", "CAT", "UNP", "RTX", "HON", "BA", "GE", "LMT", "DE", "MMM", "UPS", "FDX"],

    # Mid Cap Growth (higher volatility, different patterns)
    "mid_cap_growth": ["CRWD", "DDOG", "NET", "SNOW", "ZS", "OKTA", "TWLO", "MDB", "HUBS", "TTD", "ROKU", "SQ", "SHOP", "MELI"],

    # Small Cap (more volatile, less efficient)
    "small_cap": ["PLUG", "FCEL", "BLNK", "CHPT", "RIVN", "LCID", "SOFI", "HOOD", "AFRM", "UPST"],

    # Sector ETFs (market segments)
    "sector_etfs": ["XLK", "XLF", "XLE", "XLV", "XLI", "XLC", "XLY", "XLP", "XLB", "XLU", "XLRE"],

    # International ADRs (different market dynamics)
    "international": ["TSM", "BABA", "NVO", "ASML", "TM", "SONY", "SAP", "NVS", "SNY", "BP", "SHEL", "RIO", "BHP"],

    # Dividend Aristocrats (stable, income-focused)
    "dividend": ["JNJ", "PG", "KO", "PEP", "MMM", "EMR", "GPC", "SWK", "ITW", "ADP", "AFL", "CINF"],

    # High Beta / Meme stocks (extreme volatility)
    "high_volatility": ["GME", "AMC", "BBBY", "PLTR", "NIO", "XPEV", "COIN", "MARA", "RIOT"],

    # REITs (real estate, different cycles)
    "reits": ["PLD", "AMT", "EQIX", "PSA", "SPG", "O", "WELL", "AVB", "EQR", "DLR"],

    # Biotech (binary events, high risk)
    "biotech": ["MRNA", "BNTX", "REGN", "VRTX", "BIIB", "ILMN", "SGEN", "ALNY"],
}


def get_diverse_universe() -> list:
    """Return the full diverse stock universe"""
    all_stocks = []
    for category, stocks in DIVERSE_STOCK_UNIVERSE.items():
        all_stocks.extend(stocks)
    # Remove duplicates while preserving order
    return list(dict.fromkeys(all_stocks))


def get_stocks_by_category(category: str) -> list:
    """Get stocks for a specific category"""
    return DIVERSE_STOCK_UNIVERSE.get(category, [])


def get_available_categories() -> list:
    """Get list of available stock categories"""
    return list(DIVERSE_STOCK_UNIVERSE.keys())
