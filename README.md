
# COFOG-Panel: Harmonizing IMF GFS COFOG Data into Reproducible Panel Datasets

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Ready%20for%20Publishing-brightgreen.svg)](https://github.com/yourusername/COFOG-Panel)

This repository contains the Python pipeline designed to ingest raw Government Finance Statistics (GFS) data organized by COFOG (Classification of the Functions of Government), harmonize it, and output a clean, reproducible panel dataset suitable for econometric analysis.

## 1. Overview and Architecture

COFOG-Panel operates as a modular CLI tool, allowing users to execute individual ETL stages or run the full pipeline sequentially. The entire process is **Local-First**, relying solely on local file inputs and generating output XLSX files to ensure maximum reproducibility.

The core pipeline stages are mapped to specific CLI commands.

## 2. Installation and Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/COFOG-Panel.git
    cd COFOG-Panel
    ```
2.  **Set up Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use: .\venv\Scripts\activate
    ```
3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Install Dependencies (Editable Mode):**
    To use the CLI commands (e.g., `cofog-panel`), install the package in editable mode. **This requires a `setup.py` or `pyproject.toml` file in the root directory.**
    ```bash
    pip install -e .
    ```
    *(Ensure your `requirements.txt` is referenced correctly in your setup file.)*

## 3. Command Line Interface (CLI) Reference

All operations are executed via the primary command: `cofog-panel`.

### A. Validation Commands (Stages 1 & 2)

| Command | Purpose | Key Options | Example |
| :--- | :--- | :--- | :--- |
| `check-format` | Verifies the header structure of the main COFOG source Excel file (Stage 1). | `--source-file`: Required path to the raw data Excel file. | `cofog-panel check-format --source-file ./data/gfs_raw_data.xlsx` |
| `check-country-format` | Verifies the structure of the required Country Code mapping file. | `--lookup-file`: Required path to country code lookup file. | `cofog-panel check-country-format --lookup-file ./data/country_codes.xlsx` |

### B. Stage 3: Seeding the Master Schema (B1)

Creates the base file that will hold the final panel dataset.

| Command | Purpose | Key Options | Example |
| :--- | :--- | :--- | :--- |
| `seed-master` | Creates the `COFOG_MASTER_SCHEMA.xlsx` locally based on country codes. | `--lookup-file`: Required path to country code lookup file. | `cofog-panel seed-master --lookup-file ./data/country_codes.xlsx` |
| | | `--output-dir`: Directory to save the master file (Default: `./output`). | |

### C. Stage 4: ETL and Data Splitting (B2)

Filters the raw data and saves country-specific subsets as local XLSX files.

| Command | Purpose | Key Options | Example |
| :--- | :--- | :--- | :--- |
| `split` | Filters raw data by COFOG and Transformation Type, splitting outputs into country-specific XLSX files. | `--source-file`: Required path to the raw data Excel file. | `cofog-panel split --source-file ./data/gfs_raw_data.xlsx --cofog "Defence" --filter-type "Percent of GDP"` |
| | | `--cofog`: **Required**. The specific COFOG category to process (e.g., "Defence"). | |
| | | `--filter-type`: Transformation type filter (Default: "Percent of GDP"). | |
| | | `--output-dir`: Directory to store split XLSX files (Default: `./intermediate_splits`). | |

### D. Stage 5: Harmonization and Aggregation (B3)

Applies the advanced 3-Tier Harmonization Algorithm to combine sector data and updates the Master File.

| Command | Purpose | Key Options | Example |
| :--- | :--- | :--- | :--- |
| `aggregate` | Runs the 3-Tier algorithm based on the specified sector logic and updates the Master File. | `--master-file`: Required path to the Master XLSX file. | `cofog-panel aggregate --master-file ./output/COFOG_MASTER_SCHEMA.xlsx --folder-path ./intermediate_splits --data-col "DATA_DEFENCE" --sector "Local Government"` |
| | | `--folder-path`: Required path to the directory containing split XLSX files. | |
| | | `--data-col`: **Required**. The name of the new column to populate in the Master File. | |
| | | `--sector`: Controls the harmonization rule (Default: `"General government"`). | |

### E. Orchestrator Command (Full Pipeline)

This command automates Stages 1 through 5 sequentially, ensuring all paths and parameters flow correctly.

| Command | Purpose | Key Options | Example |
| :--- | :--- | :--- | :--- |
| `run` | Executes the full, reproducible pipeline in sequence using only local files. | `--source-file`, `--lookup-file`: Required input files. | `cofog-panel run --source-file ./data/gfs_raw_data.xlsx --lookup-file ./data/country_codes.xlsx --cofog "Defence" --sector "General government"` |
| | | `--cofog`, `--filter-type`, `--sector`: Parameters carried through the pipeline. | |
| | | `--output-cols`: Column name for the final result in the Master File. | |

## 4. Data Format Requirements

For the pipeline to run successfully, ensure your input files adhere to the expected structure:

*   **Raw Data (`--source-file`):** Must contain columns named `SERIES_CODE`, `TYPE_OF_TRANSFORMATION`, `COFOG`, `SECTOR`, and subsequent columns representing Years (e.g., 1990, 2023).
*   **Lookup File (`--lookup-file`):** Must contain columns named `name` and `alpha-3`.

---
*Developed for submission to SoftwareX, Elsevier.*