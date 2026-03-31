"""
context.py — Ticker business context layer.

Explains what a business does, where value comes from, what breaks it, and
its capital allocation pattern.  Attaches cleanly to single-ticker output
and alert messages.

Coverage: top S&P 500 holdings by weight.  Returns None for unknown tickers —
callers should treat None as "no context available" and omit the field.
"""

from __future__ import annotations

_CONTEXT: dict[str, dict] = {
    "AAPL": {
        "name": "Apple Inc.",
        "business": "Consumer electronics, software, and digital services",
        "value_driver": "iPhone ecosystem lock-in, App Store margin (~30%), growing Services segment",
        "what_breaks_it": "Smartphone unit decline, China manufacturing/revenue risk, App Store antitrust",
        "capital_pattern": "Capital returner — massive buybacks and dividends, low reinvestment relative to earnings",
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "business": "Cloud (Azure), productivity software (Office 365), gaming, and AI infrastructure",
        "value_driver": "Azure cloud share gains, Office 365 recurring ARR, Copilot AI monetisation",
        "what_breaks_it": "Cloud price wars, enterprise budget cuts, antitrust on Activision/AI bundling",
        "capital_pattern": "Reinvests heavily in cloud infra; also returns capital via buybacks",
    },
    "NVDA": {
        "name": "NVIDIA Corporation",
        "business": "GPU design for AI/data centres, gaming, and automotive",
        "value_driver": "H100/B200 GPU monopoly in AI training, CUDA software moat, data centre pricing power",
        "what_breaks_it": "AMD/custom-chip competition, export restrictions to China, AI capex slowdown",
        "capital_pattern": "Reinvesting aggressively in R&D and supply chain; modest buybacks",
    },
    "GOOGL": {
        "name": "Alphabet Inc. (Class A)",
        "business": "Search advertising, YouTube, Google Cloud, Waymo",
        "value_driver": "Search monopoly (90%+ share), YouTube ad revenue, Cloud growth",
        "what_breaks_it": "AI-disrupted search, antitrust remedies, advertiser spend pullback",
        "capital_pattern": "Large buybacks; selectively reinvests in moonshots (Waymo, DeepMind)",
    },
    "GOOG": {
        "name": "Alphabet Inc. (Class C)",
        "business": "Same as GOOGL — Class C shares (no voting rights)",
        "value_driver": "Search monopoly, YouTube, Cloud",
        "what_breaks_it": "AI-disrupted search, antitrust remedies",
        "capital_pattern": "Large buybacks; moonshot reinvestment",
    },
    "AMZN": {
        "name": "Amazon.com Inc.",
        "business": "E-commerce marketplace, AWS cloud, advertising, logistics",
        "value_driver": "AWS margins subsidising e-commerce, advertising ARPU growth, Prime flywheel",
        "what_breaks_it": "AWS competitive intensity, e-commerce margin pressure, regulatory fragmentation",
        "capital_pattern": "Reinvests heavily; AWS capex expanding rapidly in 2024–25",
    },
    "META": {
        "name": "Meta Platforms Inc.",
        "business": "Social media (Facebook, Instagram, WhatsApp), Reality Labs VR",
        "value_driver": "Advertising targeting via largest social graph; Reels/AI feed engagement",
        "what_breaks_it": "Teen user decline, ad targeting regulation, Reality Labs cash burn",
        "capital_pattern": "Elevated capex (AI infra); large buyback programme",
    },
    "TSLA": {
        "name": "Tesla Inc.",
        "business": "Electric vehicles, energy storage, Full Self-Driving software",
        "value_driver": "FSD software margin potential, energy business growth, brand premium",
        "what_breaks_it": "EV demand slowdown, Chinese competition, CEO distraction risk",
        "capital_pattern": "Reinvesting in Gigafactory expansion and AI/compute; minimal dividends",
    },
    "BRK-B": {
        "name": "Berkshire Hathaway (Class B)",
        "business": "Diversified conglomerate — insurance, rail (BNSF), utilities, equity portfolio",
        "value_driver": "Float-funded insurance underwriting, equity portfolio (AAPL largest holding)",
        "what_breaks_it": "Catastrophic insurance losses, Buffett succession, interest rate sensitivity",
        "capital_pattern": "Deploys free cash flow into acquisitions and equity stakes; selective buybacks",
    },
    "LLY": {
        "name": "Eli Lilly and Company",
        "business": "Pharmaceuticals — GLP-1 drugs (Mounjaro/Zepbound), oncology, diabetes",
        "value_driver": "GLP-1 blockbuster franchise ($50B+ TAM), strong pipeline, manufacturing scale-up",
        "what_breaks_it": "Drug pricing regulation, patent cliffs, manufacturing bottlenecks",
        "capital_pattern": "Reinvesting in manufacturing and R&D; modest dividend",
    },
    "V": {
        "name": "Visa Inc.",
        "business": "Global payment network — card processing and settlement",
        "value_driver": "Network effects, toll-road revenue model, global consumer spend growth",
        "what_breaks_it": "Real-time payment alternatives (FedNow), account-to-account bypass, regulation",
        "capital_pattern": "Capital-light model — large buybacks and dividends",
    },
    "MA": {
        "name": "Mastercard Incorporated",
        "business": "Global payment network — card processing and settlement",
        "value_driver": "Duopoly with Visa, cross-border fee leverage, value-added services growth",
        "what_breaks_it": "Same risks as Visa — A2A bypass, central bank digital currencies",
        "capital_pattern": "Capital-light — consistent buybacks and dividend growth",
    },
    "JPM": {
        "name": "JPMorgan Chase & Co.",
        "business": "Universal bank — investment banking, consumer banking, asset management",
        "value_driver": "Scale advantage, net interest margin, investment banking market share",
        "what_breaks_it": "Credit cycle downturn, net interest margin compression, regulatory capital requirements",
        "capital_pattern": "Returns capital via dividends and buybacks; reinvests in tech modernisation",
    },
    "UNH": {
        "name": "UnitedHealth Group Inc.",
        "business": "Health insurance (UnitedHealthcare) and health services (Optum)",
        "value_driver": "Optum vertical integration, data advantage, Medicare Advantage growth",
        "what_breaks_it": "Medical loss ratio spikes, Medicare rate cuts, government drug pricing",
        "capital_pattern": "Reinvests in Optum acquisitions; also returns capital via buybacks",
    },
    "XOM": {
        "name": "Exxon Mobil Corporation",
        "business": "Integrated oil & gas — upstream production, refining, chemicals",
        "value_driver": "Low-cost Permian production, Pioneer acquisition synergies, refining margin",
        "what_breaks_it": "Oil price decline, energy transition capex pressure, carbon regulation",
        "capital_pattern": "Committed to growing dividend; share buybacks; major Permian reinvestment",
    },
    "JNJ": {
        "name": "Johnson & Johnson",
        "business": "Pharmaceuticals and MedTech (post-Consumer spin-off of Kenvue)",
        "value_driver": "Oncology and immunology portfolio, surgical robot (Ottava), MedTech margin",
        "what_breaks_it": "Talc liability, drug pricing regulation, patent cliff on Stelara",
        "capital_pattern": "Dividend aristocrat; modest buybacks; reinvests in pipeline M&A",
    },
    "COST": {
        "name": "Costco Wholesale Corporation",
        "business": "Membership warehouse retail — bulk merchandise, own-brand Kirkland",
        "value_driver": "Membership fee economics, treasure-hunt format, Kirkland brand loyalty",
        "what_breaks_it": "Membership renewal rate decline, warehouse oversaturation, inflation impact on bulk buying",
        "capital_pattern": "Special dividends supplementing regular; reinvests in new warehouses",
    },
    "AVGO": {
        "name": "Broadcom Inc.",
        "business": "Semiconductor design (networking, storage, wireless) and infrastructure software (VMware)",
        "value_driver": "AI networking ASICs (Google TPU supplier), VMware cash flows, cost-out M&A model",
        "what_breaks_it": "AI custom silicon competition, VMware integration risk, customer concentration",
        "capital_pattern": "Pays large dividend; buybacks; uses debt for acquisitions",
    },
    "HD": {
        "name": "The Home Depot Inc.",
        "business": "Home improvement retail — tools, lumber, appliances, contractor supplies",
        "value_driver": "Pro contractor segment growth, housing stock ageing driving repair spend",
        "what_breaks_it": "Housing activity slowdown, consumer discretionary pullback, SRS acquisition integration",
        "capital_pattern": "Capital returner — consistent buybacks and dividend growth",
    },
    "PG": {
        "name": "Procter & Gamble Co.",
        "business": "Consumer staples — personal care, household products (Tide, Pampers, Gillette)",
        "value_driver": "Portfolio of #1 or #2 market-share brands, pricing power in inflation",
        "what_breaks_it": "Private-label trading down, commodity cost spikes, emerging market FX",
        "capital_pattern": "Dividend aristocrat (67+ years); steady buyback programme",
    },
    "ABBV": {
        "name": "AbbVie Inc.",
        "business": "Pharmaceuticals — immunology (Humira, Skyrizi, Rinvoq), oncology, aesthetics (Botox)",
        "value_driver": "Skyrizi/Rinvoq replacing Humira decline, Botox aesthetic moat",
        "what_breaks_it": "Humira biosimilar erosion steeper than guided, pipeline failures",
        "capital_pattern": "High dividend payer; some buybacks; M&A-driven growth (Allergan)",
    },
    "MRK": {
        "name": "Merck & Co. Inc.",
        "business": "Pharmaceuticals — Keytruda (cancer), vaccines, animal health",
        "value_driver": "Keytruda oncology franchise ($25B+ revenue), vaccine portfolio, pipeline depth",
        "what_breaks_it": "Keytruda IRA pricing impact 2028, patent cliff risk, R&D failures",
        "capital_pattern": "Reinvests in pipeline and bolt-on M&A; pays dividend, modest buybacks",
    },
    "CVX": {
        "name": "Chevron Corporation",
        "business": "Integrated oil & gas — upstream, downstream, chemicals",
        "value_driver": "Kazakhstan (Tengiz) ramp, Permian production, low-cost upstream",
        "what_breaks_it": "Oil price cycle, Hess/Guyana arbitration risk, energy transition capital pressure",
        "capital_pattern": "Committed dividend and buyback programme; capital-disciplined upstream",
    },
    "KO": {
        "name": "The Coca-Cola Company",
        "business": "Beverage brands — Coke, Sprite, Fanta, water, sports drinks, juice",
        "value_driver": "Global brand moat, asset-light franchise bottling model, pricing power",
        "what_breaks_it": "Sugar/obesity regulation, health trend shift, FX headwinds",
        "capital_pattern": "Dividend king (60+ years); modest buybacks",
    },
    "PEP": {
        "name": "PepsiCo Inc.",
        "business": "Beverages and snacks — Pepsi, Gatorade, Lay's, Quaker, Doritos",
        "value_driver": "Snack portfolio diversification, Frito-Lay margin engine, international growth",
        "what_breaks_it": "GLP-1 drug impact on snack demand, volume declines, commodity costs",
        "capital_pattern": "Dividend aristocrat; consistent buyback programme",
    },
    "WMT": {
        "name": "Walmart Inc.",
        "business": "Mass-market retail — supercenters, Sam's Club, Flipkart, e-commerce",
        "value_driver": "Everyday-low-price scale, advertising/data revenue growth, grocery share gains",
        "what_breaks_it": "Margin compression from e-commerce, labour cost inflation",
        "capital_pattern": "Dividend aristocrat; buybacks; investing in e-commerce and automation",
    },
}


def get_ticker_context(ticker: str) -> dict | None:
    """
    Return the business context dict for *ticker*, or None if not available.

    Consumers should check for None and omit the field from their response
    rather than raising an error — coverage is intentionally partial.
    """
    return _CONTEXT.get(ticker.upper().strip())
