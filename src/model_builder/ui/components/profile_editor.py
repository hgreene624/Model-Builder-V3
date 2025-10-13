from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

import streamlit as st

from model_builder.profiles.service import ProfileNotFoundError, ProfilesService
from src.models.contracts import Portfolio

PROFILE_SELECTION_KEY = "model_builder_profile_selected"
CONFIRM_DELETE_KEY = "model_builder_profile_confirm_delete"
DEFAULT_PROFILE_NAME = "New Strategy Profile"

DEFAULT_PARAMETERS: dict[str, Any] = {
    "symbol_count": 5,
    "atr_window": 14,
    "breakout_lookback": 20,
    "breakout_multiplier": 2.0,
    "risk_fraction": 0.02,
    "min_weight": 0.05,
    "max_weight": 0.25,
    "population_size": 9,
    "generations": 3,
    "max_workers": 1,
    "seed": 42,
    "objective_weights": {"cagr": 0.5, "calmar": 0.3, "sharpe": 0.2},
    "bounds": {
        "atr_window": [10, 30],
        "breakout_lookback": [15, 45],
        "breakout_multiplier": [1.5, 3.5],
        "risk_fraction": [0.01, 0.04],
    },
    "max_trade_rate": 50.0,
    "min_hold_days": 2.0,
    "initial_capital": 100_000.0,
    "use_synthetic": False,
}


@dataclass(frozen=True)
class ProfileEditorResult:
    profile: dict[str, Any] | None
    saved: bool = False
    deleted: bool = False
    message: str | None = None


def _default_profile(portfolio_id: str | None) -> dict[str, Any]:
    return {
        "profile_id": None,
        "name": DEFAULT_PROFILE_NAME,
        "description": "",
        "portfolio_id": portfolio_id or "",
        "train_percentage": 0.7,
        "atr_warmup_days": 14,
        "parameters": copy.deepcopy(DEFAULT_PARAMETERS),
    }


def _format_option(value: str, summaries: Dict[str, dict]) -> str:
    if value == "__new__":
        return "➕ Create new profile"
    summary = summaries.get(value)
    if not summary:
        return value
    name = summary.get("name", value)
    portfolio_id = summary.get("portfolio_id", "—")
    updated = summary.get("updated_at", "")
    return f"{name} · {portfolio_id} · {updated}"


def _portfolio_label(portfolio: Portfolio) -> str:
    symbol_count = len(portfolio.tickers or [])
    return f"{portfolio.name} ({symbol_count} symbols)"


def render_profile_editor(
    *,
    service: ProfilesService,
    portfolios: Sequence[Portfolio],
) -> ProfileEditorResult:
    st.subheader("Strategy Profiles")

    if not portfolios:
        st.info("Save a portfolio in the Portfolio Curator page before creating strategy profiles.")
        return ProfileEditorResult(profile=None, message="No portfolios available.")

    portfolio_lookup = {portfolio.portfolio_id: portfolio for portfolio in portfolios}

    summaries = service.list_profiles()
    summary_map = {summary["profile_id"]: summary for summary in summaries}

    selection_state = st.session_state.get(PROFILE_SELECTION_KEY)

    options: List[str] = ["__new__"] + [summary["profile_id"] for summary in summaries]
    if selection_state in options:
        default_index = options.index(selection_state)
    else:
        default_index = 0

    selected_option = st.selectbox(
        "Profile",
        options=options,
        index=default_index,
        format_func=lambda value: _format_option(value, summary_map),
    )
    st.session_state[PROFILE_SELECTION_KEY] = selected_option

    if st.session_state.get(CONFIRM_DELETE_KEY):
        st.session_state[CONFIRM_DELETE_KEY] = False

    if selected_option == "__new__":
        default_portfolio = portfolios[0]
        profile_data = _default_profile(default_portfolio.portfolio_id)
    else:
        try:
            profile_data = service.load_profile(selected_option)
        except ProfileNotFoundError:
            st.warning("Selected profile could not be found. Resetting selection.")
            st.session_state[PROFILE_SELECTION_KEY] = "__new__"
            return ProfileEditorResult(profile=None, message="Profile missing.")

    parameters = dict(profile_data.get("parameters") or {})
    for key, value in DEFAULT_PARAMETERS.items():
        parameters.setdefault(key, copy.deepcopy(value))

    selected_portfolio_id = profile_data.get("portfolio_id") or portfolios[0].portfolio_id
    if selected_portfolio_id not in portfolio_lookup:
        selected_portfolio_id = portfolios[0].portfolio_id
    selected_portfolio = portfolio_lookup[selected_portfolio_id]

    with st.form("profile_form"):
        col_a, col_b = st.columns(2)
        name = col_a.text_input("Profile Name", value=profile_data.get("name", DEFAULT_PROFILE_NAME))
        description = col_b.text_area(
            "Description",
            value=profile_data.get("description") or "",
            height=80,
        )

        portfolio_ids = [portfolio.portfolio_id for portfolio in portfolios]
        portfolio_labels = {portfolio.portfolio_id: _portfolio_label(portfolio) for portfolio in portfolios}
        portfolio_index = portfolio_ids.index(selected_portfolio_id)
        selected_portfolio_id = col_a.selectbox(
            "Portfolio",
            options=portfolio_ids,
            index=portfolio_index,
            format_func=lambda value: portfolio_labels.get(value, value),
        )
        selected_portfolio = portfolio_lookup[selected_portfolio_id]

        train_percentage = col_b.slider(
            "Train Percentage",
            min_value=0.1,
            max_value=0.95,
            step=0.05,
            value=float(profile_data.get("train_percentage", 0.7)),
            help="Fraction of coverage allocated to training. Holdout automatically fills the remaining window.",
        )
        atr_warmup_days = col_a.number_input(
            "ATR Warmup Days",
            min_value=1,
            max_value=90,
            value=int(profile_data.get("atr_warmup_days", 14)),
            help="ATR warmup period applied before the training window. Extends into holdout if coverage is tight.",
        )

        max_symbols = max(1, len(selected_portfolio.tickers or []))
        symbol_count = st.slider(
            "Symbols Sampled Per Run",
            min_value=1,
            max_value=max_symbols,
            value=int(min(parameters.get("symbol_count", 5), max_symbols)),
            help="Controls how many tickers are sampled from the selected portfolio for each optimisation run.",
        )

        col_c, col_d, col_e = st.columns(3)
        atr_window = col_c.number_input(
            "ATR Window",
            min_value=5,
            max_value=100,
            value=int(parameters.get("atr_window", 14)),
        )
        breakout_lookback = col_d.number_input(
            "Breakout Lookback",
            min_value=5,
            max_value=100,
            value=int(parameters.get("breakout_lookback", 20)),
        )
        breakout_multiplier = col_e.number_input(
            "Breakout Multiplier",
            min_value=0.5,
            max_value=5.0,
            value=float(parameters.get("breakout_multiplier", 2.0)),
            step=0.1,
        )

        col_f, col_g, col_h = st.columns(3)
        risk_fraction = col_f.number_input(
            "Risk Fraction",
            min_value=0.001,
            max_value=0.2,
            value=float(parameters.get("risk_fraction", 0.02)),
            step=0.001,
            format="%.3f",
        )
        min_weight = col_g.number_input(
            "Min Position Weight",
            min_value=0.0,
            max_value=1.0,
            value=float(parameters.get("min_weight", 0.05)),
            step=0.01,
        )
        max_weight = col_h.number_input(
            "Max Position Weight",
            min_value=min_weight,
            max_value=1.0,
            value=float(parameters.get("max_weight", 0.25)),
            step=0.01,
        )

        bounds = parameters.get("bounds", {})
        atr_bounds = bounds.get("atr_window", [atr_window - 4, atr_window + 4])
        lookback_bounds = bounds.get("breakout_lookback", [breakout_lookback - 5, breakout_lookback + 5])
        multiplier_bounds = bounds.get("breakout_multiplier", [breakout_multiplier - 0.5, breakout_multiplier + 0.5])
        risk_bounds = bounds.get("risk_fraction", [max(0.001, risk_fraction / 2), min(0.2, risk_fraction * 1.5)])

        col_i, col_j = st.columns(2)
        atr_range = col_i.slider(
            "ATR Window Range",
            min_value=5,
            max_value=100,
            value=(
                int(max(5, min(atr_bounds[0], atr_bounds[1]))),
                int(min(100, max(atr_bounds[0], atr_bounds[1]))),
            ),
        )
        lookback_range = col_j.slider(
            "Breakout Lookback Range",
            min_value=5,
            max_value=100,
            value=(
                int(max(5, min(lookback_bounds[0], lookback_bounds[1]))),
                int(min(100, max(lookback_bounds[0], lookback_bounds[1]))),
            ),
        )

        col_k, col_l = st.columns(2)
        multiplier_range = col_k.slider(
            "Breakout Multiplier Range",
            min_value=0.5,
            max_value=5.0,
            value=(
                float(min(multiplier_bounds[0], multiplier_bounds[1])),
                float(max(multiplier_bounds[0], multiplier_bounds[1])),
            ),
            step=0.1,
        )
        risk_range = col_l.slider(
            "Risk Fraction Range",
            min_value=0.001,
            max_value=0.2,
            value=(
                float(max(0.001, min(risk_bounds[0], risk_bounds[1]))),
                float(min(0.2, max(risk_bounds[0], risk_bounds[1]))),
            ),
            step=0.001,
            format="%.3f",
        )

        col_m, col_n, col_o = st.columns(3)
        population_size = col_m.number_input(
            "Population Size",
            min_value=3,
            max_value=30,
            value=int(parameters.get("population_size", 9)),
        )
        generations = col_n.number_input(
            "Generations",
            min_value=1,
            max_value=20,
            value=int(parameters.get("generations", 3)),
        )
        max_workers = col_o.number_input(
            "Max Workers",
            min_value=1,
            max_value=4,
            value=int(parameters.get("max_workers", 1)),
        )

        seed = st.number_input(
            "Random Seed",
            min_value=0,
            max_value=10_000,
            value=int(parameters.get("seed", 42)),
        )
        objective = parameters.get("objective_weights", {})
        col_p, col_q, col_r = st.columns(3)
        objective_cagr = col_p.number_input(
            "Objective · CAGR",
            min_value=0.0,
            max_value=1.0,
            value=float(objective.get("cagr", 0.5)),
            step=0.05,
        )
        objective_calmar = col_q.number_input(
            "Objective · Calmar",
            min_value=0.0,
            max_value=1.0,
            value=float(objective.get("calmar", 0.3)),
            step=0.05,
        )
        objective_sharpe = col_r.number_input(
            "Objective · Sharpe",
            min_value=0.0,
            max_value=1.0,
            value=float(objective.get("sharpe", 0.2)),
            step=0.05,
        )
        objective_sum = objective_cagr + objective_calmar + objective_sharpe
        if objective_sum <= 0:
            st.warning("Objective weights must sum to a positive value.")

        col_s, col_t = st.columns(2)
        max_trade_rate = col_s.number_input(
            "Constraint · Max Trades / Year",
            min_value=1.0,
            max_value=200.0,
            value=float(parameters.get("max_trade_rate", 50.0)),
            step=1.0,
        )
        min_hold_days = col_t.number_input(
            "Constraint · Min Hold Days",
            min_value=0.5,
            max_value=30.0,
            value=float(parameters.get("min_hold_days", 2.0)),
            step=0.5,
        )

        initial_capital = st.number_input(
            "Initial Capital",
            min_value=10_000.0,
            max_value=5_000_000.0,
            value=float(parameters.get("initial_capital", 100_000.0)),
            step=10_000.0,
        )

        use_synthetic = st.checkbox(
            "Use Synthetic Data Fallback",
            value=bool(parameters.get("use_synthetic", False)),
            help="Force optimisation to use generated OHLCV samples instead of live providers.",
        )

        submitted = st.form_submit_button("Save Profile", type="primary")

    if submitted:
        payload = {
            "profile_id": profile_data.get("profile_id"),
            "name": name.strip() or DEFAULT_PROFILE_NAME,
            "description": description.strip() or None,
            "portfolio_id": selected_portfolio_id,
            "train_percentage": float(train_percentage),
            "atr_warmup_days": int(atr_warmup_days),
            "parameters": {
                "symbol_count": int(symbol_count),
                "atr_window": int(atr_window),
                "breakout_lookback": int(breakout_lookback),
                "breakout_multiplier": float(breakout_multiplier),
                "risk_fraction": float(risk_fraction),
                "min_weight": float(min_weight),
                "max_weight": float(max_weight),
                "population_size": int(population_size),
                "generations": int(generations),
                "max_workers": int(max_workers),
                "seed": int(seed),
                "objective_weights": {
                    "cagr": float(objective_cagr),
                    "calmar": float(objective_calmar),
                    "sharpe": float(objective_sharpe),
                },
                "bounds": {
                    "atr_window": [int(atr_range[0]), int(atr_range[1])],
                    "breakout_lookback": [int(lookback_range[0]), int(lookback_range[1])],
                    "breakout_multiplier": [float(multiplier_range[0]), float(multiplier_range[1])],
                    "risk_fraction": [float(risk_range[0]), float(risk_range[1])],
                },
                "max_trade_rate": float(max_trade_rate),
                "min_hold_days": float(min_hold_days),
                "initial_capital": float(initial_capital),
                "use_synthetic": bool(use_synthetic),
            },
        }
        saved = service.save_profile(payload)
        st.session_state[PROFILE_SELECTION_KEY] = saved["profile_id"]
        st.success(f"Profile '{saved['name']}' saved.")
        return ProfileEditorResult(profile=saved, saved=True, message="Profile saved.")

    profile_id = profile_data.get("profile_id")
    if profile_id:
        confirm_delete = st.session_state.get(CONFIRM_DELETE_KEY, False)
        delete_clicked = st.button("Delete Profile", key="delete_profile")
        if delete_clicked:
            confirm_delete = True
        st.session_state[CONFIRM_DELETE_KEY] = confirm_delete

        if confirm_delete:
            st.warning("This action permanently removes the strategy profile.")
            col_yes, col_no = st.columns(2)
            if col_yes.button("Confirm Delete", key="confirm_delete_profile"):
                service.delete_profile(profile_id)
                st.session_state[PROFILE_SELECTION_KEY] = "__new__"
                st.session_state[CONFIRM_DELETE_KEY] = False
                st.success("Profile deleted.")
                return ProfileEditorResult(profile=None, deleted=True, message="Profile deleted.")
            if col_no.button("Cancel", key="cancel_delete_profile"):
                st.session_state[CONFIRM_DELETE_KEY] = False

    profile_data["parameters"] = parameters
    return ProfileEditorResult(profile=profile_data)


__all__ = ["ProfileEditorResult", "render_profile_editor"]
