import pandas as pd
import openpyxl
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from decimal import Decimal, InvalidOperation, getcontext

# Configure Decimal precision
getcontext().prec = 50

# --- HELPER FUNCTIONS ---

def _to_decimal_safe(val: Any) -> Optional[Decimal]:
    """Safely convert a value to Decimal."""
    if val is None or pd.isna(val): 
        return None
        
    s = str(val).strip()
    if not s: 
        return None
        
    # Strict check for NaN/None strings
    if s.upper() in ('NAN', 'NONE', ''):
        return None
        
    try:
        return Decimal(s)
    except InvalidOperation:
        # If conversion fails (e.g., invalid string), return None
        return None

# --- MAIN FUNCTION FOR aggregate COMMAND ---

def run_aggregation(
    master_file_path: Path,  
    source_folder_path: Path, 
    data_col_out: str,
    sector_override: Optional[str] = None,
) -> bool:
    
    MASTER_TAB_NAME = "MasterData"
    print(f"\n--- AGGREGATE STAGE: Processing files in {source_folder_path.name} ---")

    # --- STEP 1: LOAD MASTER XLSX INTO MEMORY ---
    try:
        df_master = pd.read_excel(master_file_path, sheet_name=MASTER_TAB_NAME, dtype=str)

        if 'SortKey' not in df_master.columns: 
            print("❌ Initialization Error: Master XLSX missing 'SortKey' column.")
            return False

        df_master[data_col_out] = "" 
        original_cols = df_master.columns.tolist()
        
        print(f"✅ Master XLSX loaded: {len(df_master)} rows.")
    except Exception as e:
        print(f"❌ Initialization Error reading Master XLSX: {e}")
        return False

    # --- STEP 2: SCAN AND PROCESS EACH COUNTRY FILE ---
    updates_map: Dict[str, str] = {}  # { 'SortKey': ValueString }
    
    country_files = list(source_folder_path.glob("*.xlsx")) 
    print(f"📂 Found {len(country_files)} intermediate country XLSX files in {source_folder_path}.")

    for idx, file_path in enumerate(country_files):
        country_code = file_path.stem  # Filename (without extension) is the 3-digit country code
        
        print(f"[{idx+1}/{len(country_files)}] Processing {country_code}", end=" ")

        try:
            df = pd.read_excel(file_path) 
            
            # CAST TO STRING BEFORE USING .strip() (fix float issues)
            for col in df.columns:
                if col in ["COFOG", "SECTOR"] or (isinstance(col, str) and not col.isdigit()):
                    df[col] = df[col].astype(str).str.strip()
            
            # Normalize Sector
            col_sector = 'SECTOR' if 'SECTOR' in df.columns else df.columns[4]
            df['SECTOR_NORM'] = df[col_sector].astype(str).str.lower().str.strip()

            year_cols = [c for c in df.columns if str(c).isdigit() and df.columns.get_loc(c) >= 5]
            found_updates = 0

# ... (Code before the for year_str loop: unchanged) ...

            for year_str in year_cols:
                sort_key = f"{country_code}{year_str}"
                
                # Helper to safely get Decimal value (unchanged)
                def get_dec_value(sector_name, year_col):
                    # ... (Same implementation: returns Decimal or None) ...
                    sector_data = df[df['SECTOR_NORM'] == sector_name]
                    if sector_data.empty: return None
                    raw_val = sector_data[year_col].iloc[0] 
                    return _to_decimal_safe(raw_val)

                final_val_str = None
                
                # --- NEW PRIORITY LOGIC BASED ON SECTOR OVERRIDE ---
                
                if sector_override == "General government":
                    # *** UPDATED T1/T2/T3 LOGIC ***
                    
                    # Get T1 value
                    dec_t1 = get_dec_value('general government', year_str)
                    # Get RAW value (before Decimal conversion) to preserve original string
                    raw_t1_val = df[df['SECTOR_NORM'] == 'general government'][year_str].iloc[0]

                    
                    # T1: General government != 0 AND != NULL
                    if dec_t1 is not None and dec_t1 != Decimal(0):
                        final_val_str = str(raw_t1_val).strip() 
                    
                    else:
                        # T2 Trigger Check: Central Gov (incl. SS)
                        dec_central_main = get_dec_value('central government including social security', year_str)
                        
                        # T2: Central Gov (incl. SS) != 0 AND != NULL
                        if dec_central_main is not None and dec_central_main != Decimal(0):
                            
                            def get_dec_or_zero(sector_name, year_col):
                                dec = get_dec_value(sector_name, year_col)
                                return dec if dec is not None else Decimal(0)

                            total = (get_dec_or_zero('central government including social security', year_str) +
                                     get_dec_or_zero('state government', year_str) +
                                     get_dec_or_zero('local government', year_str))
                            
                            final_val_str = str(total)
                        
                        # T3: Fallback (when Central Gov (incl. SS) is 0 OR NULL)
                        elif dec_central_main is None or dec_central_main == Decimal(0):
                            
                            sectors_t3 = [
                                'budgetary central government', 
                                'extrabudgetary central government',
                                'social security funds', 
                                'state government', 
                                'local government'
                            ]
                            
                            decimals_t3 = []
                            for sec in sectors_t3:
                                dec_val = get_dec_value(sec, year_str)
                                decimals_t3.append(dec_val)
                            
                            # If at least one value exists (including 0) in T3 group
                            if any(d is not None for d in decimals_t3):
                                total = sum(d or Decimal(0) for d in decimals_t3)
                                final_val_str = str(total)


                # *** Other scenarios (sector_override != "General government") remain unchanged ***
                elif sector_override == "Central government including social security":

                    CGSS_SECTOR_NAME = 'central government including social security' 

                    dec_central_main = get_dec_value(CGSS_SECTOR_NAME, year_str)

                    if dec_central_main is not None and dec_central_main != Decimal(0):
                        # Priority 1: main value (use cleaned original string)
                        raw_val = df[df['SECTOR_NORM'] == CGSS_SECTOR_NAME][year_str].iloc[0]
                        final_val_str = str(raw_val).strip()
                    else:
                        # Fallback: Budgetary + Extrabudgetary + Social Security funds
                        sectors_fallback = [
                            'budgetary central government', 
                            'extrabudgetary central government', 
                            'social security funds'
                        ]
                        
                        decimals_fb = []
                        for sec in sectors_fallback:
                            decimals_fb.append(_to_decimal_safe(
                                str(df[df['SECTOR_NORM'] == sec][year_str].iloc[0]).strip() if not df[df['SECTOR_NORM'] == sec].empty else None
                            ))
                        if any(d is not None for d in decimals_fb):
                            total = sum(d or Decimal(0) for d in decimals_fb)

                            if total >= Decimal(0):
                                final_val_str = str(total)


                elif sector_override in [
                    "Budgetary central government", "Extrabudgetary central government", 
                    "Local Government", "Social security funds", "State Government", "Central government excluding social security"
                ]:
                    # Scenario 3: Directly select value from specified sector
                    dec_sector = get_dec_value(sector_override.lower(), year_str)
                    if dec_sector is not None:
                        final_val_str = str(df[df['SECTOR_NORM'] == sector_override.lower()][year_str].iloc[0]).strip()
                        
                # --- STORE RESULT ---
                if final_val_str is not None:
                    updates_map[sort_key] = final_val_str 
                    found_updates += 1
                else:
                    # If no valid value found, store empty string
                    updates_map[sort_key] = ""
            
            print(f"-> OK ({found_updates} updates)")

        except Exception as e:
            print(f"⚠️ Processing Error: {e}")
            
    # --- STEP 3: MAP RESULTS AND WRITE MASTER XLSX ---
    
    print("\n💾 Mapping results back to Master DataFrame and writing XLSX...")
    
    final_data_updates = []
    update_count = 0

    for idx, row in df_master.iterrows():
        sk = str(row['SortKey']).strip()

        if sk in updates_map:
            v = updates_map[sk]
            final_data_updates.append([v])
            update_count += 1
        else:
            final_data_updates.append([""]) 

    try:
        df_master[data_col_out] = [item[0] for item in final_data_updates]
        
        # --- COLUMN ORDER HANDLING ---
        new_cols_order = ['SortKey', 'Country', 'Year', data_col_out]
        if 'CODE_NEW' in original_cols:
             new_cols_order.append('CODE_NEW')
        
        final_cols_to_write = [col for col in new_cols_order if col in df_master.columns]
        df_master = df_master[final_cols_to_write] 
        
        # --- SAFEST WRITE METHOD (use Pandas Writer to control headers) ---
        
        # Convert types and replace 'nan'/'None' with empty string ""
        df_to_write = df_master.astype(str).replace('nan', '').replace('None', '')

        with pd.ExcelWriter(master_file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_to_write.to_excel(writer, sheet_name=MASTER_TAB_NAME, index=False)
            
        print(f"✅ SUCCESS! Updated {update_count} records in Master XLSX file.")
        return True
        
    except Exception as e:
        print(f"❌ FAILED TO WRITE TO MASTER XLSX FILE: {e}")
        return False
