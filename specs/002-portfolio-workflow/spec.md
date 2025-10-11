# Feature Specification: Portfolio Workflow Overhaul

**Feature Branch**: `[002-portfolio-workflow]`  
**Created**: 2025-??-??  
**Status**: Draft  

## Problem Statement

Researchers need a single Streamlit flow that starts with a broad index universe, lets them prune it interactively, surfaces liquidity context, and persists the curated results together with enough metadata for downstream modeling. The current MVP portfolio builder lacks indexing support, per-symbol coverage insight, selective adds, and the ability to manage saved universes.

## Clarifications

### Session 2025-10-11
- Q: When saving a portfolio, how should we establish its identifier so later saves/deletes target the right artifact? → A: Overwrite on name collision.

## User Story — Curate and Manage Portfolios (Priority: P1)

As a researcher, I want to open the Portfolios page, choose an index universe, refine it with search/filters/size limits, inspect liquidity and coverage, cherry-pick final symbols, and save or delete portfolios so that modeling pages can reuse the curated set without repeating the prep work.

### Why This Matters

Portfolio curation is the first step in every workflow. Researchers will iterate often, so the page must feel responsive, remember context, and reduce friction when moving from a large index to a precise working list.

### Independent Test

1. Boot the Portfolios page with supplied index JSON files.  
2. Select an index, apply search/sector filters, and set a numeric max cap to trim the universe (table previews the filtered universe immediately).  
3. Configure liquidity and coverage thresholds, choose the fetch date range, click “Fetch data,” and confirm the same table refreshes with liquidity metrics, coverage flags, and threshold-based filtering.  
4. Add tickers from the updated table to the draft portfolio, review the draft summary table, save with provenance, and verify the saved artifact contains the priors window, liquidity stats, and storage hints.  
5. Delete an existing saved portfolio and confirm removal from Home and list views.

## Acceptance Scenarios

1. **Given** the page loads with available index files, **When** I pick “S&P 500,” **Then** the working universe populates from disk and remains cached for subsequent interactions.
2. **Given** a working list, **When** I apply text search, multi-select sectors, and set a numeric max symbol cap, **Then** the table updates immediately and stamps the priors window (start/end) used for context.
3. **Given** the liquidity controls and fetch dates are set, **When** I click “Fetch data,” **Then** the existing table augments each row with liquidity metrics, applies thresholds, and flags coverage gaps.
4. **Given** the refreshed table is visible, **When** I add symbols from it to the draft portfolio, **Then** they appear in the draft controls and the draft summary table below reflects the current selection.
5. **Given** a draft portfolio, **When** I save, **Then** the artifact includes normalized tickers, filters applied, priors window, shard hints (cached file metadata), and creation timestamp.
6. **Given** saved portfolios exist, **When** I choose “Delete” on one, **Then** the portfolio JSON is removed from storage and the UI updates without requiring a manual refresh.
7. **Given** I attempt to save a portfolio with a name that already exists, **When** I confirm the save, **Then** the previous artifact is overwritten so the latest configuration is preserved without duplicates.

## Functional Requirements

- Load index universes from `storage/index_universes/<name>.json` (or similar) and cache them in Streamlit session state.
- Filtering must support text search, multiple sectors/industries, and numeric max symbol counts, with draft selection gated on the single unified table that updates after the liquidity fetch.
- Draft portfolio controls must display the current selections in a dedicated table beneath the controls.
- Liquidity fetch warms the OHLCV cache and records per-symbol coverage windows and shard metadata.
- Threshold inputs (median price, median dollar volume) filter the working table before selection.
- Draft portfolio supports add/remove of individual symbols; duplicates are prevented.
- Saved portfolio schema extends existing Portfolio contract with new metadata fields as needed.
- Provide delete controls for existing portfolios with confirmation.
- Saving a portfolio with a previously used name overwrites the existing artifact to ensure subsequent edits target the latest version.
- CLI parity: `portfolio curate` gains options for universe pick and thresholds; `portfolio delete` CLI removes saved artifacts.
- Tests cover loader utilities, filtering, liquidity aggregation, selection logic, artifact persistence, and CLI flows.

## Non-Functional Requirements

- Streamlit interactions should avoid extra network calls by relying on session state where practical.
- Liquidity fetch must surface user-friendly errors when data providers are unavailable.
- Persisted artifacts remain backward-compatible (bump schema_version when adding fields).
- Page-level operations should remain responsive for universes up to ~1000 symbols.

## Dependencies & Assumptions

- Index JSON files will be supplied separately; scaffolding must handle missing files gracefully.
- Alpaca/Yahoo data providers remain the primary data sources.
- No brokerage integration or optimization triggers are in scope.
