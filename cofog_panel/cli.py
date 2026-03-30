import typer
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Import refactored functions
from cofog_panel.checks import verify_cofog_format, verify_country_format
from cofog_panel.master_seed import seed_master  # Output has changed
from cofog_panel.etl import split_data
from cofog_panel.aggregate import run_aggregation  # Input has changed


app = typer.Typer(help="COFOG-Panel: Tool for harmonizing IMF GFS COFOG data into reproducible panel datasets.")


DEFAULT_MASTER_FILE_NAME = "COFOG_MASTER_SCHEMA.xlsx"
DEFAULT_OUTPUT_COLS = "DATA_NEW"
DEFAULT_OUTPUT_DIR = Path("./output")
DEFAULT_SPLIT_DIR = Path("./intermediate_splits")
DEFAULT_TRANSFORMATION = "Percent of GDP"  # Set a reasonable default value

VALID_SECTORS = [
    "Budgetary central government", 
    "Central government excluding social security", 
    "Central government including social security",
    "Extrabudgetary central government", 
    "General government",  # Uses legacy logic
    "Local Government", 
    "Social security funds", 
    "State Government"
]


def initialize_google_services() -> bool:
    """Initialize gspread and Drive service. Does NOT use Context."""
    global GC_CLIENT, DRIVE_SERVICE
    
    if GC_CLIENT and DRIVE_SERVICE:
        return True 

    try:
        from google.auth import default
        creds, project = default()
        
        GC_CLIENT = gspread.authorize(creds)
        DRIVE_SERVICE = build('drive', 'v3', credentials=creds)
        
        typer.echo("✅ Google Services Authenticated Successfully.")
        return True
    except Exception as e:
        typer.echo(f"❌ Google Authentication FAILED. Cannot proceed with Drive/Sheet operations. Error: {e}", err=True)
        return False

# Simpler hook: initialize only when explicitly required
def run_with_google_client(func):
    """Decorator to run function only when Google Client is initialized."""
    def wrapper(*args, **kwargs):
        if not initialize_google_services():
            # Abort commands that depend on Google API if auth fails
            typer.echo("Aborting Google API operation.")
            raise typer.Exit(code=1)
        return func(*args, **kwargs)
    return wrapper

# ==============================================================================
# 1. CHECK FORMATS (Local)
# ==============================================================================

@app.command("check-format")
def check_cofog(
    input_file: Path = typer.Option(..., "--source-file", help="Path to the raw COFOG Excel file.")
):
    """Verifies the header structure of the raw COFOG input file (CODE 1)."""
    verify_cofog_format(input_file)

@app.command("check-country-format")
def check_country(
    lookup_file: Path = typer.Option(..., "--lookup-file", help="Path to the Country Code lookup file.")
):
    """Verifies the structure of the required Country Code mapping file (New CODE stage)."""
    verify_country_format(lookup_file)


# ==============================================================================
# 2. SEED MASTER (Output Local XLSX)
# ==============================================================================

@app.command("seed-master")
def seed(
    lookup_file: Path = typer.Option(..., "--lookup-file", help="Verified Country Code file path."),
    output_dir: Path = typer.Option("./output", "--output-dir", help="Directory to save the Master XLSX file."),
    output_name: str = typer.Option(DEFAULT_MASTER_FILE_NAME, "--output-name", help="Name for the new Master XLSX file.")
):
    """Creates the Master XLSX file locally (CODE 2/B1)."""
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Function now returns Path
    master_path, success = seed_master(lookup_file, output_dir, output_name)
    
    if success:
        typer.echo(f"::MASTER_PATH::{master_path}") 
    else:
        raise typer.Exit(code=1)

# ==============================================================================
# 3. SPLIT DATA (unchanged, still requires Drive for intermediate files)
# ==============================================================================
@app.command("split")
def split(
    source_file: Path = typer.Option(..., "--source-file", help="Path to the raw COFOG source file."),
    filter_type: str = typer.Option(DEFAULT_TRANSFORMATION, "--filter-type"),
    # COFOG is now required and accepts only one value
    cofog: str = typer.Option(..., "--cofog", help="The exact COFOG category to process (must match file value)."), 
    output_dir: Path = typer.Option(DEFAULT_SPLIT_DIR, "--output-dir", help="Directory to save intermediate country XLSX files.")
):
    """Filters raw data and saves split data into local XLSX files (CODE 3/B2)."""
    
    # Convert COFOG string into a single-element set for compatibility
    cofog_set = {cofog} 
    
    folder_path, success = split_data(
        source_file, 
        filter_type, 
        cofog_set,
        output_dir
    )
    
    if success:
        typer.echo(f"::SPLIT_PATH::{folder_path}")
    else:
        raise typer.Exit(code=1)

# ==============================================================================
# 4. AGGREGATE (Input Local XLSX, Output Local XLSX)
# ==============================================================================
@app.command("aggregate")
def aggregate(
    master_file_path: Path = typer.Option(..., "--master-file", help="Path to the Master XLSX file to update."),
    folder_path: Path = typer.Option(..., "--folder-path", help="Local path where intermediate country XLSX files are stored."),
    data_col: str = typer.Option("DATA_NEW", "--data-col", help="Target column name in Master file for final data."),
    sector: str = typer.Option(
        "General government", 
        "--sector", 
        help="Aggregation method. Must be one of the specified sector names or 'General government' (default)."
    ),
):
    """Applies the 3-Tier algorithm based on the specified SECTOR logic."""

    def main_aggregate():
        # Pass sector_override
        success = run_aggregation(
            master_file_path,
            folder_path, 
            data_col,
            sector,  # Pass sector here
        )
        if success:
            typer.echo(f"::AGGREGATE_SUCCESS::COMPLETED") 
        else:
            raise typer.Exit(code=1)

    main_aggregate()


# ==============================================================================
# 5. RUN ORCHESTRATOR (adds --sector parameter)
# ==============================================================================
@app.command("run")
def run_pipeline(
    source_file: Path = typer.Option(..., "--source-file", help="Path to the raw COFOG source file."),
    lookup_file: Path = typer.Option(..., "--lookup-file", help="Path to the Country Code lookup file."),
    cofog: str = typer.Option(..., "--cofog", help="Specific COFOG category to process."),
    filter_type: str = typer.Option(DEFAULT_TRANSFORMATION, "--filter-type", help="Transformation type (e.g., Percent of GDP, Domestic currency)."),
    output_dir: Path = typer.Option(DEFAULT_OUTPUT_DIR, "--output-dir", help="Directory for Master XLSX."),
    split_dir: Path = typer.Option(DEFAULT_SPLIT_DIR, "--split-dir", help="Directory to save intermediate country XLSX splits."),
    output_cols: str = typer.Option(DEFAULT_OUTPUT_COLS, "--output-cols", help="Target data column name (e.g., DATA_NEW)."),
    sector: str = typer.Option(
        "General government", 
        "--sector", 
        help="Aggregation method used in the final step."
    ),
):
    """Runs the FULL pipeline sequentially (1 -> 5) using ONLY local files."""
    
    typer.echo("--- Starting FULL LOCAL COFOG Pipeline Orchestration ---")
    
    # --- Step 1 & 2: Validation ---
    typer.echo("\n[Stage 1/5] Checking COFOG Format...")
    if not verify_cofog_format(source_file)[0]: raise typer.Exit(code=1)

    typer.echo("\n[Stage 2/5] Checking Country Code Format...")
    if not verify_country_format(lookup_file)[0]: raise typer.Exit(code=1)

    # --- Step 3: Seed Master (Local XLSX) ---
    typer.echo("\n[Stage 3/5] Seeding Master XLSX...")
    # Call seed function directly and capture master_path
    master_path, success = seed_master(lookup_file, output_dir, DEFAULT_MASTER_FILE_NAME)
    if not success: raise typer.Exit(code=1)
    
    typer.echo(f"Master Path Established: {master_path}")
    
    # --- Step 4: Split Data (Local XLSX) ---
    typer.echo("\n[Stage 4/5] Splitting Data per Country (to Local XLSX)...")
    folder_path, success = split_data(
        source_file, filter_type, {cofog}, split_dir
    )
    if not success: raise typer.Exit(code=1)
        
    # --- Step 5: Aggregate (Read Local XLSX, Write Local XLSX) ---
    typer.echo("\n[Stage 5/5] Running 3-Tier Aggregation...")
    data_col = output_cols
    
    # Call aggregate function with master_path
    success = run_aggregation(
        master_path,         
        folder_path,        
        data_col,
        sector,  # Pass sector
    )
    
    if success:
        typer.echo("\n🎉 FULL PIPELINE COMPLETED SUCCESSFULLY! 🎉")
        typer.echo(f"Final Master XLSX available at: {master_path}")
    else:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()