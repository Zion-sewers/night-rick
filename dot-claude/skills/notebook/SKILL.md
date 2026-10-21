---
name: notebook
description: Generate a SOTA 2026 data science Jupyter notebook scaffold, Polars, Plotly, Optuna, SHAP. Use when data files are present, analysis is needed, or agent eval results need statistical analysis.
---

## First principles (bind every use)

1. **Restraint.** Minimize speculative complexity: code, features, dependencies, payload. YAGNI.
2. **Trust boundaries.** Every state change crosses an explicit contract: approval, gate, or verification run.
3. **No vibes.** Claims anchor to runs, diffs, or distributions, never to impressions.

## Trust boundary

The notebook emits and runs code inside the project. Contract: data files are never
committed; new dependencies go to the dev group only; nothing writes outside the project
dir. The executed notebook, re-run top to bottom with no exceptions, is the evidence.


# /notebook

Scaffold a state-of-the-art data science notebook for the current project context.

## Triggers

- Data files detected in project dir (xlsx, csv, parquet)
- User asks to "analyze", "explore", "EDA", or "model" data
- Agent eval results need statistical analysis
- "scaffold run" requested on a dataset
- User mentions coverage metrics, confidence weighting, conformal prediction, or prediction intervals
- Temporal ML context (triggers the purged-CV cell instead of standard CV)

## Usage

```
/notebook [data-file] [--type tabular|timeseries|embedding|eval]
```

- `tabular`: classification or regression with AutoGluon, SHAP, nested CV
- `timeseries`: forecasting with Chronos-2, StatsForecast, combinatorial purged CV
- `embedding`: text to embeddings (sentence-transformers), clustering and similarity, PaCMAP coverage
- `eval`: agent eval results analysis, coverage metric, confidence-weighted score
- Default: auto-detect from the data schema

## Instructions

### Step 1, read the index, not the data file

Check the project index for data file metadata (size, columns if documented, date). If no schema is documented, read the first 5 rows only:

```python
pl.read_csv("file.csv", n_rows=5)  # polars, never pandas
```

### Step 2, create the notebook at `notebooks/<slug>-<date>.ipynb`

Structure every notebook identically:

```python
# Cell 1, metadata
# Project: <name> | Date: <date> | Analyst: agent
# Data: <file> | Type: <tabular|timeseries|embedding|eval>
# Objective: <one sentence>

# Cell 2, imports (SOTA stack only)
import polars as pl
import polars.selectors as cs
import plotly.express as px
import plotly.graph_objects as go
from great_tables import GT
import numpy as np
from numba import jit  # hot numerical loops only

# Cell 3, ingest (Polars, lazy when over 100K rows)
df = pl.scan_csv("file.csv").collect()
# or for xlsx:
df = pl.read_excel("file.xlsx", sheet_name=0)
print(df.shape, df.dtypes)

# Cell 4, EDA
print(df.describe())
null_report = df.null_count()
# distribution plots, plotly only, no matplotlib
for col in df.select(cs.numeric()).columns:
    fig = px.histogram(df.to_pandas(), x=col, title=f"Distribution: {col}")
    fig.show()
# correlation heatmap via plotly.figure_factory

# Cell 5, preprocessing (Polars expressions, always vectorized)
df = df.with_columns([
    pl.col("date").str.strptime(pl.Date, "%Y-%m-%d").alias("date"),
    pl.col("numeric_col").fill_null(strategy="mean"),
])

# Cell 5b, cross-validation strategy
# Temporal data goes to combinatorial purged CV; IID tabular goes to nested CV.
# Conformal prediction: pin mapie to the version that still ships MondrianCP.

# Cell 6, feature engineering
df = df.with_columns([
    pl.col("date").dt.month().alias("month"),
    pl.col("date").dt.weekday().alias("weekday"),
    # domain-specific features here
])

# Cell 7, model selection (by type)
# TABULAR: AutoGluon TabularPredictor with a time limit
# TIME-SERIES: Chronos zero-shot pipeline plus StatsForecast baselines
# EMBEDDING: sentence-transformers embeddings, then clustering and similarity
#   (generative models as narrators are out; embedding probes are allowed)

# Cell 8, hyperparameter optimization (only if fine-tuning)
import optuna
# study over the model params, maximize the target metric

# Cell 9, evaluation
import shap
# TreeExplainer, summary plot, metrics table via Great Tables

# Cell 9b, coverage visualization (PaCMAP, all types)
# PaCMAP beats UMAP for global structure; 2D scatter of the embedding space

# Cell 9c, coverage metric (eval type only)
# confidence-weighted score = mean quality score x coverage fraction

# Cell 10, bottom line (single markdown cell)
# ## Results
# - **Metric**: X (vs baseline Y, delta +Z%)
# - **Key driver**: feature via SHAP
# - **Recommendation**: one sentence
# - **Next step**: one sentence
```

### Step 3, commit the notebook to `notebooks/`

Add `notebooks/` to the project if it does not exist. Never commit data files, they stay in the project dir (gitignored).

## Reflection (mandatory)

After the notebook runs, verify it the way a reader would: every cell executed in order with no exceptions, the metrics table is non-empty, and the plots rendered. Re-run top to bottom once to prove ordering. Preserve the executed notebook as evidence.

## Per-project defaults

| Project | Default type | Target | Notes |
|---------|-------------|--------|-------|
| agenteval-bench | eval | score, pass_rate | coverage metric plus confidence-weighted score; PaCMAP white-gap view |
| policykit | tabular | decision, cost | nested CV; calibration curves |
| agentgate | eval | verdict, abstain_rate | groundedness axes; Mondrian CP per axis |

## Dependencies (add to the dev group when creating a notebook)

```toml
"polars>=1.0",
"plotly>=5.0",
"great-tables>=0.10",
"autogluon.tabular>=1.1",  # tabular only
"shap>=0.45",
"optuna>=3.6",
"pacmap>=0.7",
"hdbscan>=0.8",
"mapie==0.9.0",  # pinned: later versions removed MondrianCP
"numba>=0.60",
# time-series: "statsforecast>=1.7", "neuralforecast>=2.0"
# embedding: "sentence-transformers" (open-source embedding probes)
```
