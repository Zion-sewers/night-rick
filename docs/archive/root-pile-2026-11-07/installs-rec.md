הנה הרשימה בפורמט קצר, נקי ומותאם למסך של טלפון — בלי שורות ארוכות שנגללות לצד ובלי תווים מיותרים שמקשים על הקלדה ידנית:
1. תשתיות בסיס (להריץ בטרמינל)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

curl -LsSf https://astral.sh/uv/install.sh | sh

curl -fsSL https://fnm.vercel.app/install | bash

fnm install --lts

curl -fsSL https://bun.sh/install | bash

2. כלי מערכת (Homebrew)
מחולק לפקודות קצרות:
גיט ו-CI:
brew install git gh act pre-commit

אבטחה וסריקה:
brew install gitleaks ruff

אבטחת שרשרת אספקה (Supply Chain):
brew install cosign syft scorecard

ענן, דאטה ודאטהבריקס:
brew install opentofu duckdb

brew install databricks/tap/databricks

מנוע מכולות (קליל ופטור מרישוי):
brew install --cask orbstack

3. כלי Node גלובליים
npm install -g pnpm tsx @biomejs/biome promptfoo

4. חבילות פייתון (פקודות קצרות דרך uv)
מנועי נתונים ודאטהבריקס:
uv pip install polars duckdb pyarrow

uv pip install databricks-sdk dbt-databricks

איכות נתונים וחוזים:
uv pip install "pandera[polars]" great-expectations

uv pip install sqlfluff sqlfluff-templater-dbt

בדיקות:
uv pip install pytest pytest-cov pytest-mock pytest-asyncio

הערכת פרומפטים ו-LLMOps:
uv pip install deepeval ragas instructor pydantic mlflow

קומפיילרים ו-Langfuse:
uv pip install dspy openinference-instrumentation-dspy langfuse

הסקה סיבתית (Causal AI):
uv pip install dowhy econml

אבטחה, PII וסימולציות:
uv pip install presidio-analyzer presidio-anonymizer faker pip-audit cyclonedx-bom

מודל שפה מקומי לטיהור שמות וישויות:
python -m spacy download en_core_web_sm

