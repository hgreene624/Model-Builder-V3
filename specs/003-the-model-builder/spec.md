# Feature Specification: Model Builder Strategy Profiles

**Feature Branch**: `[003-the-model-builder]`  
**Created**: 2025-10-11  
**Status**: Draft  
**Input**: User description: "The Model Builder page lets you load, save and delete strategy profiles that define all the user input parameters for model training. The page also defines the percent of the time window of a given portfolio that is used for training and testing. Optimization is to be run on the training window and holdout stats are to be run on the testing window. Testing requires an ATR warmup period from outside the testing date range in order to start training at the beginning of the test period. This should be sized so that according to the warmup needed for a given strategy. As the evolutionary run proceeds, you get a rolling \"Live evaluations\" of holdout performance as a table that never loses history, plus a \"Best candidate\" callout with the top score, its score delta, and the full parameter payload. Train and holdout windows come straight from your portfolio coverage, with the train percentage slider enforcing at least one day of holdout; those dates drive every downstream holdout check. Once a leader appears, the page recomputes its holdout equity curve, rolling-return heatmap, and trade timeline, and pins them in session so they survive reruns. The heatmap highlights 5/10/20/60-day annualized momentum with an interpretive blurb, while the trade timeline plots every holdout trade-color-coded by P&L and sized by funded notional-so you can line it up with the equity curve and spot what actually drove the result."

## Clarifications

### Session 2025-10-11

- Q: Who can access and modify a saved strategy profile by default? → A: Strategy profiles are open to everyone without authentication.
- Q: How long should the live evaluations table retain candidate history? → A: Reset at the start of each evolutionary run.
- Q: If the ATR warmup period cannot be satisfied because insufficient pre-testing data exists, how should the system respond? → A: Extend into the testing window to gather enough warmup data.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure Strategy Profile And Run Training (Priority: P1)

Quant researchers load an existing strategy profile, adjust training and testing windows, and launch an optimization run using the training portion of the portfolio coverage.

**Why this priority**: Without the ability to configure and execute training runs, the Model Builder cannot deliver value to portfolio modeling workflows.

**Independent Test**: Load, edit, and save a profile, then start an optimization run while verifying train and test dates plus warmup placement are applied as configured.

**Acceptance Scenarios**:

1. **Given** a saved strategy profile, **When** a user loads it, adjusts the user configurable parameters present on the page, and saves, **Then** the updated profile parameters persist and are reapplied on reload.
2. **Given** a portfolio coverage range, **When** the user starts optimization, **Then** the system uses the derived training window and earmarks the testing window for downstream holdout stats.

---

### User Story 2 - Monitor Live Holdout Evaluations (Priority: P2)

During an evolutionary run, the researcher monitors a rolling table of live holdout evaluations that records every candidate assessed on the testing window without losing prior entries.

**Why this priority**: Visibility into evolving holdout performance lets users decide when to stop runs or adjust parameters, directly impacting productivity.

**Independent Test**: Trigger an evolutionary run that emits candidate scores and confirm the table captures each entry, shows timestamps and scores, and remains intact after subsequent candidates arrive.

**Acceptance Scenarios**:

1. **Given** an active run producing candidate scores, **When** a new candidate is evaluated, **Then** the live evaluations table appends the result with score, delta, timestamp, and configuration snapshot without clearing prior rows.

---

### User Story 3 - Review Best Candidate Insights (Priority: P3)

Once a leader emerges, the researcher reviews a best candidate callout alongside refreshed visual diagnostics (equity curve, rolling-return heatmap, trade timeline) that persist for the session.

**Why this priority**: Consolidated insights help users understand why a candidate leads and support downstream decision-making or communication.

**Independent Test**: Promote a candidate to the top score and confirm the callout details, charts, and timeline refresh immediately and remain available after rerunning the evolutionary process.

**Acceptance Scenarios**:

1. **Given** a candidate surpasses the previous best score, **When** the system promotes it, **Then** the best candidate module displays the new score, delta, and parameter payload while charts regenerate with holdout data.

---

### Edge Cases

- Portfolio coverage spans fewer days than the minimum holdout plus warmup requirement.
- Train percentage slider is moved to 100 percent, leaving no holdout days available.
- Warmup period extends beyond available pre-testing data.
- User deletes the only stored profile while an optimization run is in progress.
- Live evaluations feed produces duplicate candidate identifiers or arrives out of chronological order.

## Assumptions

- Strategy profiles already include fields for ATR lookback and other warmup-sensitive settings, defaulting to 14 calendar days when unspecified.
- Portfolio coverage data is continuous at the trading-day granularity required for holdout calculations.
- Sessions refer to a single signed-in browser session; clearing the session cache resets pinned visuals.
- Strategy profiles are accessible for viewing, editing, and deletion without authentication or access controls.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow users to load any saved strategy profile and view its full parameter set.
- **FR-002**: The system MUST support creating and saving strategy profiles, including training percentage, testing percentage.
- **FR-003**: The system MUST require confirmation before deleting a strategy profile and remove it from the profile list once confirmed.
- **FR-004**: The system MUST derive training and holdout date ranges from the selected portfolio coverage and user-defined train percentage.
- **FR-005**: The system MUST enforce at least one trading day in the holdout window and prevent runs that violate this rule.
- **FR-006**: The system MUST ensure the ATR warmup period is sourced from dates preceding the testing window and extends far enough to satisfy the strategy warmup setting; if insufficient pre-testing data exists, the system extends into the testing window to complete the warmup before running holdout statistics.
- **FR-007**: The system MUST execute optimization routines solely on the training window for the active strategy profile.
- **FR-008**: The system MUST compute holdout statistics using only the designated testing window.
- **FR-009**: The system MUST display a live evaluations table that resets at the start of each evolutionary run and, during an active run, appends each candidate result—including score, delta versus the prior best, timestamp, and parameter payload—while retaining earlier rows from that run.
- **FR-010**: The system MUST surface a best candidate callout showing the top score, score delta, and complete parameter payload.
- **FR-011**: The system MUST refresh the best candidate callout and associated visuals at the end of generation simulation when a new leader is identified.
- **FR-012**: The system MUST regenerate the holdout equity curve, rolling-return heatmap, and trade timeline each time the leading candidate changes.
- **FR-013**: The system MUST ensure the rolling-return heatmap visualizes 5-, 10-, 20-, and 60-day annualized momentum with an interpretive summary.
- **FR-014**: The system MUST render the trade timeline with each holdout trade color-coded by profit or loss and sized by funded notional, aligned to the equity curve timeline.
- **FR-015**: The system MUST persist the latest best candidate visuals for the duration of the user session so they remain available after rerunning the evolutionary process.
- **FR-016**: The system MUST log the all details necessary to replay a training in another module. this include portfolio details. user input parameters, and results of each round of simulation


### Key Entities *(include if feature involves data)*

- **Strategy Profile**: Defines the configurable parameters for a strategy run, including identifiers, training percentage, testing percentage, ATR warmup, and strategy-specific settings.
- **Portfolio Coverage Window**: Represents the available historical time span for the selected portfolio, expressed as start and end dates plus day count.
- **Candidate Evaluation**: Captures the result of evaluating a candidate strategy on the holdout window, storing score, delta, timestamp, and parameter payload.
- **Best Candidate Summary**: Holds the current leading candidate metrics and references to associated visual artifacts such as equity curve, heatmap, and trade timeline.
- **EA Log**: provides a record of the simulation so that it can be read and recreated without the need to resimulate. 

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 95 percent of saved strategy profiles reload with identical parameters across sessions during UAT validation.
- **SC-002**: Users can adjust the train percentage and launch a new optimization run within 2 minutes in moderated usability testing.
- **SC-003**: New candidate evaluations appear in the live table within 10 seconds of scoring completion in performance testing.
- **SC-004**: 90 percent of pilot users report that the best candidate visualizations clearly explain the leader performance in post-session surveys.
