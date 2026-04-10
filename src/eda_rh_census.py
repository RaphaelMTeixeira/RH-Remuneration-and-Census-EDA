"""
Exploratory analysis of the RH remuneration dataset joined with municipal census indicators.

This script is designed for portfolio sharing:
- cleans and standardizes both datasets,
- creates a municipality "crosswalk" (de-para),
- builds integrated analytical tables, and
- exports publication-ready charts as PNG images.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from unidecode import unidecode


ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
FIGURES_DIR = ROOT_DIR / "outputs" / "figures"
TABLES_DIR = ROOT_DIR / "outputs" / "tables"
SUMMARY_PATH = ROOT_DIR / "outputs" / "analysis_summary.md"

RH_PATH = RAW_DIR / "TB_RH.csv"
CENSUS_PATH = RAW_DIR / "census.csv"


def ensure_project_folders() -> None:
    """Create output folders to guarantee a reproducible run on any machine."""
    for folder in [PROCESSED_DIR, FIGURES_DIR, TABLES_DIR]:
        folder.mkdir(parents=True, exist_ok=True)


def normalize_city_name(value: object) -> str:
    """
    Normalize municipality names into a stable matching key.

    Why this matters:
    One dataset may use accents/casing differently than the other.
    A normalized key avoids false mismatches during joins.
    """
    if pd.isna(value):
        return ""

    text = str(value).strip()
    if not text:
        return ""

    text = unidecode(text).upper()
    text = " ".join(text.split())
    return text


def normalize_label(value: object) -> str:
    """Normalize labels into lowercase keys for robust column matching."""
    return normalize_city_name(value).lower()


def parse_ptbr_number(series: pd.Series) -> pd.Series:
    """
    Convert pt-BR formatted numeric strings into float.

    Examples handled:
    - "41.039,39" -> 41039.39
    - "98,36 %" -> 98.36
    - "-" -> NaN
    """
    cleaned = (
        series.astype(str)
        .str.replace("\xa0", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.strip()
        .replace({"-": np.nan, "": np.nan, "nan": np.nan, "None": np.nan})
    )

    cleaned = cleaned.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(cleaned, errors="coerce")


def load_rh_data(path: Path) -> pd.DataFrame:
    """Read RH data and prepare key analytical fields."""
    rh = pd.read_csv(path, sep=";", encoding="utf-8", low_memory=False)

    rh = rh.rename(
        columns={
            "municipio": "city_original",
            "ult_remu_bruta": "gross_remuneration_brl",
            "situacao": "employment_status",
            "genero": "gender",
            "ano_nasc": "birth_year",
            "dt_inicio": "start_date",
            "dt_fim": "end_date",
            "atualizado": "snapshot_date",
            "instituicao": "institution",
            "regime": "employment_regime",
            "tipo_cargo": "position_type",
            "quadro_funcional": "workforce_group",
            "quadro_funcional_desc": "workforce_group_description",
        }
    )

    rh["city_original"] = rh["city_original"].astype(str).str.strip()
    rh["city_key"] = rh["city_original"].apply(normalize_city_name)

    rh["gross_remuneration_brl"] = pd.to_numeric(rh["gross_remuneration_brl"], errors="coerce")
    rh.loc[rh["gross_remuneration_brl"] < 0, "gross_remuneration_brl"] = np.nan

    rh["birth_year"] = pd.to_numeric(rh["birth_year"], errors="coerce")
    rh["snapshot_date"] = pd.to_datetime(rh["snapshot_date"], errors="coerce")
    rh["analysis_year"] = rh["snapshot_date"].dt.year.fillna(2026)
    rh["age"] = rh["analysis_year"] - rh["birth_year"]
    rh.loc[(rh["age"] < 14) | (rh["age"] > 100), "age"] = np.nan

    rh["employment_status"] = rh["employment_status"].astype(str).str.upper().str.strip()
    rh["gender"] = rh["gender"].astype(str).str.upper().str.strip()
    rh["institution"] = rh["institution"].astype(str).str.strip()
    rh["is_active"] = rh["employment_status"].eq("ATIVO")

    return rh


def detect_census_columns(census: pd.DataFrame) -> dict[str, str]:
    """
    Detect census columns by meaning, handling possible encoding variations in headers.
    """
    expected_tokens = {
        "city": "municipios",
        "demonym": "gentilico",
        "population_last_census": "populacao no ultimo censo",
        "population_estimated": "populacao estimada",
        "population_density": "densidade demografica",
        "formal_jobs": "pessoal ocupado em postos de trabalho formais",
        "formal_jobs_avg_salary_min_wage": "salario medio mensal dos trabalhadores formais",
        "infant_mortality_per_thousand": "mortalidade infantil",
        "gdp_per_capita_brl": "pib per capita",
        "school_attendance_6_14_pct": "taxa de escolarizacao de 6 a 14 anos de idade",
        "diarrhea_hospitalizations_per_100k": "internacoes por diarreia pelo sus",
    }

    normalized_columns = {col: normalize_label(col) for col in census.columns}
    rename_map: dict[str, str] = {}

    for target, token in expected_tokens.items():
        source_col = next((col for col, norm in normalized_columns.items() if token in norm), None)
        if source_col is None:
            available = ", ".join(census.columns.tolist())
            raise KeyError(f"Could not detect census column '{target}'. Available columns: {available}")
        rename_map[source_col] = target

    return rename_map


def load_census_data(path: Path) -> pd.DataFrame:
    """Read municipal census data and standardize field names and numeric types."""
    census = pd.read_csv(path, sep=";", encoding="latin1")

    rename_map = detect_census_columns(census)
    census = census.rename(columns=rename_map)
    census = census[list(rename_map.values())].copy()

    census["city"] = census["city"].astype(str).str.strip()
    census["city_key"] = census["city"].apply(normalize_city_name)

    numeric_columns = [
        "population_last_census",
        "population_estimated",
        "population_density",
        "formal_jobs",
        "formal_jobs_avg_salary_min_wage",
        "infant_mortality_per_thousand",
        "gdp_per_capita_brl",
        "school_attendance_6_14_pct",
        "diarrhea_hospitalizations_per_100k",
    ]

    for column in numeric_columns:
        census[column] = parse_ptbr_number(census[column])

    return census


def create_city_crosswalk(rh: pd.DataFrame, census: pd.DataFrame) -> pd.DataFrame:
    """
    Build a municipality de-para table from RH names to official census names.

    This table is useful both for auditability and future data maintenance.
    """
    official_city_by_key = census.drop_duplicates("city_key").set_index("city_key")["city"]

    rh["city_official"] = rh["city_key"].map(official_city_by_key)
    rh["city_match_status"] = np.where(rh["city_official"].notna(), "matched", "unmatched")

    crosswalk = (
        rh.groupby(["city_original", "city_key", "city_official", "city_match_status"], dropna=False)
        .size()
        .reset_index(name="records")
        .sort_values(["city_match_status", "records"], ascending=[True, False])
    )

    return crosswalk


def build_city_level_dataset(rh: pd.DataFrame, census: pd.DataFrame) -> pd.DataFrame:
    """Aggregate RH data by municipality and merge with census indicators."""
    matched_rh = rh[rh["city_official"].notna()].copy()

    city_metrics = (
        matched_rh.groupby("city_official", as_index=False)
        .agg(
            rh_records=("cod_vinculo", "size"),
            active_records=("is_active", "sum"),
            average_remuneration_brl=("gross_remuneration_brl", "mean"),
            median_remuneration_brl=("gross_remuneration_brl", "median"),
            p90_remuneration_brl=("gross_remuneration_brl", lambda s: s.quantile(0.90)),
            female_share_pct=("gender", lambda s: s.eq("F").mean() * 100),
            avg_age=("age", "mean"),
        )
        .sort_values("rh_records", ascending=False)
    )

    city_metrics["inactive_records"] = city_metrics["rh_records"] - city_metrics["active_records"]
    city_metrics["active_share_pct"] = np.where(
        city_metrics["rh_records"] > 0,
        (city_metrics["active_records"] / city_metrics["rh_records"]) * 100,
        np.nan,
    )

    merged = city_metrics.merge(
        census,
        left_on="city_official",
        right_on="city",
        how="left",
        validate="one_to_one",
    )

    merged["rh_records_per_1k_est_pop"] = np.where(
        merged["population_estimated"] > 0,
        merged["rh_records"] / merged["population_estimated"] * 1000,
        np.nan,
    )

    return merged


def build_institution_level_dataset(rh: pd.DataFrame) -> pd.DataFrame:
    """Create institution-level metrics for workforce structure analysis."""
    scoped = rh[(rh["institution"].notna()) & (~rh["institution"].isin(["", "****"]))].copy()
    institution_metrics = (
        scoped.groupby("institution", as_index=False)
        .agg(
            rh_records=("cod_vinculo", "size"),
            active_share_pct=("is_active", lambda s: s.mean() * 100),
            average_remuneration_brl=("gross_remuneration_brl", "mean"),
            median_remuneration_brl=("gross_remuneration_brl", "median"),
            female_share_pct=("gender", lambda s: s.eq("F").mean() * 100),
            avg_age=("age", "mean"),
        )
        .sort_values("rh_records", ascending=False)
    )
    return institution_metrics


def build_status_level_dataset(rh: pd.DataFrame) -> pd.DataFrame:
    """Summarize workforce metrics by employment status."""
    status_metrics = (
        rh.groupby("employment_status", as_index=False)
        .agg(
            rh_records=("cod_vinculo", "size"),
            average_remuneration_brl=("gross_remuneration_brl", "mean"),
            median_remuneration_brl=("gross_remuneration_brl", "median"),
            female_share_pct=("gender", lambda s: s.eq("F").mean() * 100),
            avg_age=("age", "mean"),
        )
        .sort_values("rh_records", ascending=False)
    )
    return status_metrics


def style_and_save_chart(filename: str) -> None:
    """Apply final layout and persist chart in high resolution."""
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / filename, dpi=220, bbox_inches="tight")
    plt.close()


def create_figures(
    rh: pd.DataFrame,
    city_merged: pd.DataFrame,
    institution_metrics: pd.DataFrame,
    status_metrics: pd.DataFrame,
) -> None:
    """Generate exploratory visuals as shareable PNG assets."""
    sns.set_theme(style="whitegrid", context="talk")
    plt.rcParams["figure.figsize"] = (12, 7)

    # 1) Top municipalities by RH record volume.
    top_volume = city_merged.nlargest(15, "rh_records").sort_values("rh_records", ascending=True)
    plt.figure()
    bars = plt.barh(top_volume["city_official"], top_volume["rh_records"], color="#1f77b4")
    plt.title("Top 15 Municipalities by RH Record Volume")
    plt.xlabel("Number of RH records")
    plt.ylabel("Municipality")
    for bar in bars:
        width = bar.get_width()
        plt.text(width, bar.get_y() + bar.get_height() / 2, f" {width:,.0f}", va="center", fontsize=8)
    style_and_save_chart("01_top_municipalities_by_records.png")

    # 2) Highest average remuneration among cities with meaningful sample size.
    robust_cities = city_merged[city_merged["rh_records"] >= 300].copy()
    top_salary = robust_cities.nlargest(15, "average_remuneration_brl").sort_values(
        "average_remuneration_brl", ascending=True
    )
    plt.figure()
    bars = plt.barh(top_salary["city_official"], top_salary["average_remuneration_brl"], color="#ff7f0e")
    plt.title("Top 15 Municipalities by Average Gross Remuneration (>=300 RH records)")
    plt.xlabel("Average gross remuneration (BRL)")
    plt.ylabel("Municipality")
    for bar in bars:
        width = bar.get_width()
        plt.text(width, bar.get_y() + bar.get_height() / 2, f" BRL {width:,.0f}", va="center", fontsize=8)
    style_and_save_chart("02_top_municipalities_by_average_salary.png")

    # 3) Salary distribution (trimmed at 99th percentile for legibility).
    p99 = rh["gross_remuneration_brl"].quantile(0.99)
    salary_view = rh["gross_remuneration_brl"].dropna()
    salary_view = salary_view[salary_view <= p99]
    plt.figure()
    sns.histplot(salary_view, bins=70, kde=True, color="#2ca02c")
    plt.title("Gross Remuneration Distribution (trimmed at 99th percentile)")
    plt.xlabel("Gross remuneration (BRL)")
    plt.ylabel("Employee records")
    style_and_save_chart("03_salary_distribution_histogram.png")

    # 4) Active vs inactive workforce by gender.
    status_gender = (
        rh[rh["gender"].isin(["F", "M"])]
        .groupby(["gender", "employment_status"], as_index=False)
        .size()
        .rename(columns={"size": "records"})
    )
    plt.figure()
    sns.barplot(data=status_gender, x="gender", y="records", hue="employment_status", palette="Set2")
    plt.title("Workforce Status by Gender")
    plt.xlabel("Gender")
    plt.ylabel("Number of records")
    plt.legend(title="Employment status")
    style_and_save_chart("04_status_by_gender.png")

    # 5) Population vs remuneration at municipality level.
    scatter_data = city_merged.dropna(subset=["population_estimated", "average_remuneration_brl"]).copy()
    plt.figure()
    sns.scatterplot(
        data=scatter_data,
        x="population_estimated",
        y="average_remuneration_brl",
        size="rh_records",
        sizes=(40, 700),
        alpha=0.7,
        color="#d62728",
        legend=False,
    )
    plt.title("Municipality Size vs Average RH Remuneration")
    plt.xlabel("Estimated population")
    plt.ylabel("Average gross remuneration (BRL)")
    style_and_save_chart("05_population_vs_average_salary_scatter.png")

    # 6) Correlation heatmap for integrated municipal indicators.
    corr_columns = [
        "rh_records",
        "active_share_pct",
        "average_remuneration_brl",
        "female_share_pct",
        "avg_age",
        "population_estimated",
        "population_density",
        "formal_jobs",
        "gdp_per_capita_brl",
        "school_attendance_6_14_pct",
    ]
    corr_data = city_merged[corr_columns].corr(numeric_only=True)
    plt.figure(figsize=(12, 10))
    sns.heatmap(corr_data, annot=True, fmt=".2f", cmap="RdBu_r", center=0, square=True, linewidths=0.5)
    plt.title("Correlation Matrix: RH and Census Indicators")
    style_and_save_chart("06_correlation_heatmap.png")

    # 7) RH record intensity by municipality (top 15).
    top_intensity = city_merged.nlargest(15, "rh_records_per_1k_est_pop").sort_values(
        "rh_records_per_1k_est_pop", ascending=True
    )
    plt.figure()
    bars = plt.barh(top_intensity["city_official"], top_intensity["rh_records_per_1k_est_pop"], color="#9467bd")
    plt.title("Top 15 Municipalities by RH Records per 1,000 Residents")
    plt.xlabel("RH records per 1,000 estimated residents")
    plt.ylabel("Municipality")
    for bar in bars:
        width = bar.get_width()
        plt.text(width, bar.get_y() + bar.get_height() / 2, f" {width:,.1f}", va="center", fontsize=8)
    style_and_save_chart("07_rh_intensity_per_1000_residents.png")

    # 8) Institutional concentration in workforce records.
    top_institutions = institution_metrics.nlargest(15, "rh_records").sort_values("rh_records", ascending=True)
    plt.figure()
    bars = plt.barh(top_institutions["institution"], top_institutions["rh_records"], color="#17becf")
    plt.title("Top 15 Institutions by RH Record Volume")
    plt.xlabel("Number of RH records")
    plt.ylabel("Institution")
    for bar in bars:
        width = bar.get_width()
        plt.text(width, bar.get_y() + bar.get_height() / 2, f" {width:,.0f}", va="center", fontsize=8)
    style_and_save_chart("08_top_institutions_by_records.png")

    # 9) Average salary by employment status for groups with meaningful volume.
    relevant_status = status_metrics[status_metrics["rh_records"] >= 500].copy()
    relevant_status = relevant_status.sort_values("average_remuneration_brl", ascending=False)
    plt.figure()
    sns.barplot(
        data=relevant_status,
        x="average_remuneration_brl",
        y="employment_status",
        hue="employment_status",
        palette="viridis",
        legend=False,
    )
    plt.title("Average Gross Remuneration by Employment Status (>=500 records)")
    plt.xlabel("Average gross remuneration (BRL)")
    plt.ylabel("Employment status")
    style_and_save_chart("09_average_salary_by_employment_status.png")

    # 10) Age profile to describe workforce lifecycle concentration.
    age_view = rh["age"].dropna()
    plt.figure()
    sns.histplot(age_view, bins=35, color="#8c564b")
    plt.title("Workforce Age Distribution")
    plt.xlabel("Age")
    plt.ylabel("Employee records")
    style_and_save_chart("10_age_distribution.png")

    # 11) Institution-level relationship between headcount and average salary.
    institution_scatter = institution_metrics[institution_metrics["rh_records"] >= 1000].copy()
    plt.figure()
    sns.scatterplot(
        data=institution_scatter,
        x="rh_records",
        y="average_remuneration_brl",
        size="active_share_pct",
        sizes=(80, 650),
        alpha=0.75,
        color="#e377c2",
        legend=False,
    )
    plt.title("Institution Size vs Average Remuneration (>=1,000 records)")
    plt.xlabel("RH records")
    plt.ylabel("Average gross remuneration (BRL)")
    style_and_save_chart("11_institution_size_vs_average_salary.png")


def write_outputs(
    rh: pd.DataFrame,
    census: pd.DataFrame,
    crosswalk: pd.DataFrame,
    city_merged: pd.DataFrame,
    institution_metrics: pd.DataFrame,
    status_metrics: pd.DataFrame,
) -> None:
    """Export processed data tables and executive summary metrics."""
    rh.to_csv(PROCESSED_DIR / "rh_cleaned.csv", index=False, encoding="utf-8")
    census.to_csv(PROCESSED_DIR / "census_cleaned.csv", index=False, encoding="utf-8")
    crosswalk.to_csv(TABLES_DIR / "municipality_crosswalk.csv", index=False, encoding="utf-8")
    city_merged.to_csv(TABLES_DIR / "city_level_rh_census_metrics.csv", index=False, encoding="utf-8")
    institution_metrics.to_csv(TABLES_DIR / "institution_level_metrics.csv", index=False, encoding="utf-8")
    status_metrics.to_csv(TABLES_DIR / "employment_status_metrics.csv", index=False, encoding="utf-8")

    summary_table = pd.DataFrame(
        [
            {"metric": "rh_total_records", "value": int(len(rh))},
            {"metric": "rh_unique_municipalities_raw", "value": int(rh["city_original"].nunique())},
            {"metric": "rh_matched_records", "value": int(rh["city_official"].notna().sum())},
            {"metric": "rh_unmatched_records", "value": int(rh["city_official"].isna().sum())},
            {
                "metric": "rh_matched_share_pct",
                "value": float((rh["city_official"].notna().mean()) * 100),
            },
            {
                "metric": "overall_average_remuneration_brl",
                "value": float(rh["gross_remuneration_brl"].mean()),
            },
            {
                "metric": "overall_median_remuneration_brl",
                "value": float(rh["gross_remuneration_brl"].median()),
            },
            {
                "metric": "overall_active_share_pct",
                "value": float((rh["is_active"].mean()) * 100),
            },
            {
                "metric": "overall_female_share_pct",
                "value": float((rh["gender"].eq("F").mean()) * 100),
            },
            {
                "metric": "cities_with_census_match",
                "value": int(city_merged["city_official"].nunique()),
            },
            {"metric": "census_total_municipalities", "value": int(census["city"].nunique())},
            {"metric": "institutions_with_records", "value": int(institution_metrics["institution"].nunique())},
            {"metric": "employment_status_categories", "value": int(status_metrics["employment_status"].nunique())},
        ]
    )
    summary_table.to_csv(TABLES_DIR / "executive_summary_metrics.csv", index=False, encoding="utf-8")

    top_cities = city_merged.nlargest(20, "rh_records")[
        [
            "city_official",
            "rh_records",
            "active_share_pct",
            "average_remuneration_brl",
            "median_remuneration_brl",
            "gdp_per_capita_brl",
            "population_estimated",
        ]
    ]
    top_cities.to_csv(TABLES_DIR / "top_20_cities_by_rh_records.csv", index=False, encoding="utf-8")


def write_markdown_summary(
    rh: pd.DataFrame,
    crosswalk: pd.DataFrame,
    city_merged: pd.DataFrame,
    institution_metrics: pd.DataFrame,
    status_metrics: pd.DataFrame,
) -> None:
    """Create a business-facing summary for quick portfolio review."""
    matched_pct = rh["city_official"].notna().mean() * 100
    unmatched = crosswalk[crosswalk["city_match_status"] == "unmatched"].copy()
    unmatched_preview = unmatched.head(10)[["city_original", "records"]]

    city_filtered = city_merged[city_merged["rh_records"] >= 300].copy()
    top_salary_city = city_filtered.nlargest(1, "average_remuneration_brl").iloc[0]
    top_volume_city = city_merged.nlargest(1, "rh_records").iloc[0]
    top_institution = institution_metrics.nlargest(1, "rh_records").iloc[0]
    top_status_salary = status_metrics[status_metrics["rh_records"] >= 500].nlargest(
        1, "average_remuneration_brl"
    ).iloc[0]

    pop_salary_corr = city_merged["population_estimated"].corr(city_merged["average_remuneration_brl"])
    gdp_salary_corr = city_merged["gdp_per_capita_brl"].corr(city_merged["average_remuneration_brl"])

    lines = [
        "# RH Remuneration + Census Exploratory Analysis",
        "",
        "## Executive Highlights",
        f"- **Record coverage after municipality standardization:** {matched_pct:.2f}% of RH records matched to official census municipalities.",
        f"- **Largest RH record concentration:** {top_volume_city['city_official']} with {int(top_volume_city['rh_records']):,} records.",
        (
            "- **Highest average remuneration (cities with >=300 RH records):** "
            f"{top_salary_city['city_official']} at BRL {top_salary_city['average_remuneration_brl']:,.2f}."
        ),
        (
            "- **Largest institutional footprint:** "
            f"{top_institution['institution']} with {int(top_institution['rh_records']):,} records."
        ),
        (
            "- **Highest-paying status category (>=500 records):** "
            f"{top_status_salary['employment_status']} at BRL {top_status_salary['average_remuneration_brl']:,.2f}."
        ),
        f"- **Correlation (population vs average remuneration):** {pop_salary_corr:.2f}.",
        f"- **Correlation (GDP per capita vs average remuneration):** {gdp_salary_corr:.2f}.",
        "",
        "## Data Quality Notes",
        "- Municipality names were normalized (accent removal + uppercase + whitespace cleanup) to create a robust join key.",
        "- Unmatched municipality labels are preserved in the crosswalk for transparent auditing.",
        "- Gross remuneration values were coerced to numeric and negative values were treated as missing.",
        "",
        "## Unmatched Municipality Labels (Top 10)",
    ]

    if unmatched_preview.empty:
        lines.append("- No unmatched municipality labels were found after normalization.")
    else:
        for _, row in unmatched_preview.iterrows():
            lines.append(f"- {row['city_original']}: {int(row['records']):,} records")

    lines.extend(
        [
            "",
            "## Generated Assets",
            "- Processed datasets: `data/processed/`",
            "- Analytical tables: `outputs/tables/`",
            "- Figures: `outputs/figures/`",
            "- This summary: `outputs/analysis_summary.md`",
        ]
    )

    SUMMARY_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Run the full pipeline from raw data to final portfolio assets."""
    ensure_project_folders()

    rh = load_rh_data(RH_PATH)
    census = load_census_data(CENSUS_PATH)

    crosswalk = create_city_crosswalk(rh, census)
    city_merged = build_city_level_dataset(rh, census)
    institution_metrics = build_institution_level_dataset(rh)
    status_metrics = build_status_level_dataset(rh)

    write_outputs(rh, census, crosswalk, city_merged, institution_metrics, status_metrics)
    create_figures(rh, city_merged, institution_metrics, status_metrics)
    write_markdown_summary(rh, crosswalk, city_merged, institution_metrics, status_metrics)

    print("Analysis pipeline finished successfully.")
    print(f"Processed data: {PROCESSED_DIR}")
    print(f"Charts: {FIGURES_DIR}")
    print(f"Tables: {TABLES_DIR}")
    print(f"Summary report: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
