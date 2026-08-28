# Project Notes and Limitations

## What the backtest proves

The 2023-trained ridge models improve mean absolute error over a trailing-3-game average on the full 2024 holdout sample for passing, rushing, and receiving yards.

## What the backtest does not prove

- It does not show profitability against any PrizePicks projection.
- It does not use PrizePicks historical lines or member play data.
- It does not estimate PrizePicks' internal fair value.
- It does not account for payout structure or correlation between lineup selections.
- It is not a wagering system.

## Important Week 18 lesson

Week 18 contains unusual playing-time decisions, rest situations, and role changes. Several large errors in the sample board illustrate why a production pre-match process should not rely on box-score history alone. The operational takeaway is to combine model output with real-time availability, depth-chart, injury, and news information.

## Why ridge regression

Ridge regression was selected as a first model because rolling-performance variables are highly correlated. Regularization stabilizes the coefficients while keeping the model interpretable. A more advanced version should compare ridge against tree-based models and quantile models with walk-forward validation.

## Leakage control

Features for a given week are computed before that week's outcomes are added to player or opponent histories. The 2024 backtest starts from Week 1 with no imported 2024 future information; rows become eligible only after at least three prior games.
