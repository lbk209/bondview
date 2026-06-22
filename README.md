# bondview

`bondview` is a bond ETF decision-support project that combines macroeconomic signals and ETF price data to evaluate bond market conditions and identify ETFs that may be misaligned with the current market view.

## Purpose

The main goal of this project is not to predict short-term ETF prices directly. Instead, it aims to support better bond ETF selection by combining:

* macro regime analysis
* interest-rate and inflation signals
* bond ETF price behavior
* mismatch detection between macro direction and market pricing

## Core Idea

The system first evaluates the macro environment using selected economic indicators, such as rates, inflation, curve movement, credit conditions, and related market signals.

Then it compares the resulting bond market view with current ETF price behavior. If an ETF appears inconsistent with the macro-based view, it may be flagged for further review.

## Main Workflow

1. Collect macro and ETF price data
2. Generate features from raw inputs
3. Evaluate market regime and bond exposure stance
4. Compare ETF price behavior with the macro-based stance
5. Rank or filter ETFs for further investment review

## Project Scope

This is a research and decision-support tool. It is designed to help organize investment logic, test assumptions, and review bond ETF opportunities more systematically.

It is not intended to be a fully automated trading system.

This repository is currently in its initial setup stage.

## Disclaimer

This project is for personal research and educational purposes only.
It does not provide financial advice or investment recommendations.
