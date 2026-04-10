# RH Remuneration + Census Exploratory Analysis

## Executive Highlights
- **Record coverage after municipality standardization:** 75.12% of RH records matched to official census municipalities.
- **Largest RH record concentration:** Curitiba with 123,113 records.
- **Highest average remuneration (cities with >=300 RH records):** Maringá at BRL 3,842.53.
- **Largest institutional footprint:** SECRETARIA DA EDUCAÇÃO with 460,929 records.
- **Highest-paying status category (>=500 records):** ATIVO at BRL 9,180.79.
- **Correlation (population vs average remuneration):** 0.42.
- **Correlation (GDP per capita vs average remuneration):** 0.05.

## Data Quality Notes
- Municipality names were normalized (accent removal + uppercase + whitespace cleanup) to create a robust join key.
- Unmatched municipality labels are preserved in the crosswalk for transparent auditing.
- Gross remuneration values were coerced to numeric and negative values were treated as missing.

## Unmatched Municipality Labels (Top 10)
- ****: 222,000 records
- Brasília: 5 records

## Generated Assets
- Processed datasets: `data/processed/`
- Analytical tables: `outputs/tables/`
- Figures: `outputs/figures/`
- This summary: `outputs/analysis_summary.md`