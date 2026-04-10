# RH Remuneration and Census EDA (Parana Municipal Analysis)

This project delivers an end-to-end exploratory analysis that combines:
- RH remuneration records (`TB_RH.csv`)
- Municipal census indicators (`census.csv`)

The integration key between both datasets is the municipality name.  
Because naming formats were inconsistent (accents/casing/placeholder values), the pipeline applies a full municipality standardization step and exports a transparent crosswalk table.

## Business Objective

Provide a municipality-level view of workforce remuneration patterns and connect them to demographic and socioeconomic indicators, enabling data-driven discussions around:
- remuneration concentration,
- workforce composition,
- municipal context (population, GDP per capita, formal jobs, education indicators).

## What Is Included

### 1. Reproducible analysis pipeline
- Script: `src/eda_rh_census.py`
- Fully commented in English for portfolio/client readability.

### 2. Processed datasets
- `data/processed/rh_cleaned.csv`
- `data/processed/census_cleaned.csv`

### 3. Analytical tables
- `outputs/tables/municipality_crosswalk.csv`
- `outputs/tables/city_level_rh_census_metrics.csv`
- `outputs/tables/institution_level_metrics.csv`
- `outputs/tables/employment_status_metrics.csv`
- `outputs/tables/executive_summary_metrics.csv`
- `outputs/tables/top_20_cities_by_rh_records.csv`

### 4. Visual assets (PNG)
- `outputs/figures/01_top_municipalities_by_records.png`
- `outputs/figures/02_top_municipalities_by_average_salary.png`
- `outputs/figures/03_salary_distribution_histogram.png`
- `outputs/figures/04_status_by_gender.png`
- `outputs/figures/05_population_vs_average_salary_scatter.png`
- `outputs/figures/06_correlation_heatmap.png`
- `outputs/figures/07_rh_intensity_per_1000_residents.png`
- `outputs/figures/08_top_institutions_by_records.png`
- `outputs/figures/09_average_salary_by_employment_status.png`
- `outputs/figures/10_age_distribution.png`
- `outputs/figures/11_institution_size_vs_average_salary.png`

### 5. Executive narrative
- `outputs/analysis_summary.md`

## Key Data Engineering Decisions

- Municipality normalization key:
  - remove accents,
  - convert to uppercase,
  - trim and collapse whitespace.
- Maintain unmatched municipality labels in the crosswalk for auditability.
- Coerce remuneration and census numeric fields to valid numeric types.
- Treat negative remuneration values as missing.

## How to Run

From this `project` folder:

```bash
py -3 -m pip install -r requirements.txt
py -3 src/eda_rh_census.py
```

## Current High-Level Findings

Based on the latest pipeline run:
- ~75.12% of RH records were matched to official census municipalities.
- Main unmatched label is `****` (placeholder/missing city), which should be treated as a data quality issue.
- Curitiba has the largest RH record concentration.
- The largest institutional concentration is in the Education Secretariat.
- `ATIVO` is the highest-paying status category among statuses with significant volume.
- Population and average remuneration show a moderate positive relationship at city level.

## Portfolio Notes

This repository structure is ready to be uploaded as a portfolio project, with:
- raw data snapshot,
- reproducible code,
- processed outputs,
- static chart assets,
- business-facing documentation.
