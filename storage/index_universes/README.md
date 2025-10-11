# Index Universe JSON Schema

Index universes drive the portfolio workflow by supplying the candidate symbol set that researchers refine. Each file under this directory MUST follow the structure below and use `snake_case` filenames (`sp500.json`, `nasdaq_100.json`, etc.).

## File Layout

```json
{
  "name": "S&P 500",
  "as_of": "2025-09-30",
  "metadata": {
    "source": "internal-index-service",
    "notes": "Includes ADRs where liquidity meets thresholds"
  },
  "symbols": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "sector": "Information Technology",
      "industry": "Technology Hardware, Storage & Peripherals",
      "market_cap": 2850000000000,
      "list_date": "1980-12-12"
    }
  ]
}
```

### Required Fields

- `name` (string): Human-readable universe label. MUST match selection name in the Streamlit UI and CLI.
- `symbols` (array): Non-empty list of symbol objects. Duplicate tickers are not allowed.

### Optional Fields

- `as_of` (ISO 8601 date string): Snapshot date for the universe membership.
- `metadata` (object): Arbitrary JSON for provenance (source system, methodology notes, etc.).

### Symbol Record Fields

| Field          | Type          | Required | Notes |
|----------------|---------------|----------|-------|
| `ticker`       | string        | ✓        | Uppercase letters/numbers, no spaces. |
| `name`         | string        |          | Company/security display name. |
| `sector`       | string        |          | GICS sector or equivalent taxonomy. |
| `industry`     | string        |          | Secondary classification if available. |
| `market_cap`   | number        |          | Market capitalization in USD. |
| `list_date`    | string (date) |          | Optional IPO/listing date. |

### Validation Checklist

- Files MUST be valid UTF-8 JSON with trailing whitespace ignored.
- Tickers MUST be unique within a universe file.
- Numeric values MUST be non-negative.
- Additional fields are permitted but SHOULD be documented in the `metadata` section.

## Directory Scaffolding

- Place universe files directly in this directory (no nested folders) so loaders can glob by `*.json`.
- Keep large source files (>5 MB) out of the repository; store references or download scripts instead.
