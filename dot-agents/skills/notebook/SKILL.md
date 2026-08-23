---
name: notebook
description: Generate a SOTA 2026 data science Jupyter notebook scaffold — Polars, Numba, Plotly, AutoGluon/Chronos-2, Optuna, SHAP. Use when data files are present or analysis is needed.
---

# /notebook

Scaffold a SOTA data science notebook for the current project context.

## Triggers

- Data files detected in project dir (xlsx, csv, parquet)
- User asks to "analyze", "explore", "EDA", "model" data
- Agent eval result needs statistical analysis
- "scaffold run" requested on a dataset
- User says "coverage metric", "GD coverage", "CWS", "confidence-weighted"
- User says "conformal prediction", "prediction intervals", "Mondrian"
- Temporal or financial ML context (triggers CPCV cell instead of standard CV)

## Usage

```
/notebook [data-file] [--type tabular|timeseries|embedding|eval]
```

- `tabular`: Classification/regression with AutoGluon + SHAP + Nested CV
- `timeseries`: FTD/call forecasting with Chronos-2 + StatsForecast + CPCV
- `embedding`: Text → OpenAI embeddings → clustering/similarity + PaCMAP coverage
- `eval`: Agent eval results analysis + GD Coverage Metric + CWS
- Default: auto-detect from data schema

## Instructions

### Step 1 — Read INDEX.md, not the data file

Check `INDEX.md` for the data file metadata (size, columns if documented, date).
If no schema documented: read first 5 rows only via:
```python
pl.read_csv("file.csv", n_rows=5)  # polars, never pandas
```

### Step 2 — Create notebook at `notebooks/<slug>-<date>.ipynb`

Structure every notebook identically:

```python
# Cell 1 — Metadata
# Project: <name> | Date: <date> | Analyst: Codex
# Data: <file> | Type: <tabular|timeseries|embedding|eval>
# Objective: <one sentence>

# Cell 2 — Imports (SOTA stack only)
import polars as pl
import polars.selectors as cs
import plotly.express as px
import plotly.graph_objects as go
from great_tables import GT           # SOTA table display
import numpy as np
from numba import jit                  # for hot numerical loops only

# Cell 3 — Ingest (Polars, lazy when >100K rows)
df = pl.scan_csv("file.csv").collect()   # lazy → collect
# OR for xlsx:
df = pl.read_excel("file.xlsx", sheet_name=0)
print(df.shape, df.dtypes)

# Cell 4 — EDA
# Schema + nulls + basic stats
print(df.describe())
null_report = df.null_count()

# Distribution plots (plotly only — no matplotlib)
for col in df.select(cs.numeric()).columns:
    fig = px.histogram(df.to_pandas(), x=col, title=f"Distribution: {col}")
    fig.show()

# Correlation heatmap
import plotly.figure_factory as ff

# Cell 5 — Preprocessing
# Polars expressions > pandas apply — always vectorized
df = df.with_columns([
    pl.col("date").str.strptime(pl.Date, "%Y-%m-%d").alias("date"),
    pl.col("numeric_col").fill_null(strategy="mean"),
])

# Cell 6 — Feature Engineering
df = df.with_columns([
    pl.col("date").dt.month().alias("month"),
    pl.col("date").dt.weekday().alias("weekday"),
    # domain-specific FE here
])

# Cell 7 — Model Selection (by type)
# TABULAR:
from autogluon.tabular import TabularPredictor
predictor = TabularPredictor(label="target").fit(df.to_pandas(), time_limit=120)

# TIME-SERIES (zero-shot forecasting pattern):
# from chronos import ChronosPipeline  # zero-shot, no training
# pipeline = ChronosPipeline.from_pretrained("amazon/chronos-t5-small")
# from statsforecast import StatsForecast
# from statsforecast.models import AutoARIMA, AutoETS

# EMBEDDING:
# from openai import AzureOpenAI
# client = AzureOpenAI(azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"], ...)
# embeddings = client.embeddings.create(input=texts, model="text-embedding-3-large")

# Cell 8 — Hyperparameter Optimization (if fine-tuning needed)
import optuna
def objective(trial):
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "learning_rate": trial.suggest_float("learning_rate", 1e-4, 0.3, log=True),
    }
    # ... train and return metric
study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=50)

# Cell 5b — Cross-Validation Strategy (insert after Cell 5)
# Temporal data (FTD, financial) → CPCV; IID tabular → Nested CV
# from mlfinlab.cross_validation import CombinatorialPurgedCV
# cv = CombinatorialPurgedCV(n_splits=6, n_test_splits=2, purge_pct=0.01, embargo_pct=0.005)
# Conformal prediction: pin "mapie==0.9.0" (v1 removed MondrianCP)
# from mapie.mondrian import MondrianCP

# Cell 9 — Evaluation
import shap
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)
shap.summary_plot(shap_values, X_test)

# Metrics table (Great Tables)
metrics_df = pl.DataFrame({"metric": [...], "value": [...], "vs_baseline": [...]})
GT(metrics_df.to_pandas()).tab_header(title="Evaluation Results").show()

# Cell 9b — Coverage Visualization (PaCMAP, all types)
# from pacmap import PaCMAP
# reducer = PaCMAP(n_components=2, n_neighbors=10, random_state=42)
# X_2d = reducer.fit_transform(embeddings_3072)  # 3072-dim → 2D
# fig = px.scatter(x=X_2d[:,0], y=X_2d[:,1], color=y_pred.astype(str),
#                  title="Coverage Map (PaCMAP)", labels={"x":"Sem Dim 1","y":"Sem Dim 2"})

# Cell 9c — GD Coverage Metric (eval type only)
# CWS = GD_score × coverage_pct  (see ~/Documents/SOTA_DS_Methods_Research_20260415/02-coverage-metrics.md)
# from sklearn.metrics.pairwise import cosine_distances
# dists = cosine_distances(user_embeddings, gd_embeddings)  # (M, N)
# coverage_mask = dists.min(axis=1) <= 0.25  # COVERAGE_RADIUS
# cws = gd_scores.mean() * coverage_mask.mean()

# Cell 10 — Bottom Line
# Single markdown cell:
# ## Results
# - **Metric**: X (vs baseline Y, delta +Z%)
# - **Key driver**: feature via SHAP
# - **Recommendation**: one sentence
# - **Next step**: one sentence
```

### Step 3 — Commit notebook to `notebooks/` dir

Add `notebooks/` to the project if it doesn't exist.
Never commit data files — they stay in the project dir (gitignored).

## Per-project defaults

Add one row per project you actually run notebooks in, named after that
project's own folder. Example rows, showing the pattern:

| Project | Default type | Target column | Notes |
|---------|-------------|---------------|-------|
| `<campaign-scoring-project>` | timeseries + tabular | e.g. a conversion-event count, a conversion rate | CPCV for CV (event count = temporal labels); Chronos-2 forecast; GD Coverage Metric |
| `<qa-eval-project>` | eval | score, pass_rate | GD Coverage Metric + CWS; PaCMAP white-gap view |
| `<agent-eval-project>` | eval | escalation_rate, accuracy | GD Coverage Metric + CWS; Mondrian CP per topic |
| `<embedding-clustering-project>` | embedding | candidate_text | PaCMAP clustering; no temporal CV needed |

## Dependencies (add to pyproject.toml dev group when creating notebook)

```toml
"polars>=1.0",
"plotly>=5.0",
"great-tables>=0.10",
"autogluon.tabular>=1.1",  # tabular only
"shap>=0.45",
"optuna>=3.6",
"pacmap>=0.7",             # coverage visualization (PaCMAP > UMAP for global structure)
"hdbscan>=0.8",            # clustering for Tier 3 eval
"mapie==0.9.0",            # Mondrian CP (pinned — v1 removed MondrianCP)
# mlfinlab>=1.0            # CPCV — commercial license required; or implement manually
"numba>=0.60",
# time-series: "statsforecast>=1.7", "neuralforecast>=2.0"
# embedding: already have openai client
```
