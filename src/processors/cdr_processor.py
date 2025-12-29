import pandas as pd
import re
import sys

def normalize_columns(df):
    """
    Renames columns to standard internal names (source, destination, etc.)
    regardless of what the CSV header says (Source_Number, Caller, etc.).
    """
    # map: { internal_name: [list of possible csv headers] }
    column_map = {
        'source': ['source_number', 'caller', 'origin', 'from', 'source'],
        'destination': ['destination_number', 'receiver', 'to', 'dest', 'destination'],
        'duration_sec': ['duration_sec', 'duration', 'duration_seconds', 'sec', 'length'],
        'tower_location': ['tower_location', 'tower', 'cell_id', 'location', 'site_id'],
        'date': ['date', 'call_date'],
        'time': ['time', 'call_time'],
        'call_type': ['call_type', 'type', 'direction']
    }

    # 1. Normalize current headers to lowercase & strip spaces
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # 2. Rename columns based on map
    rename_dict = {}
    for standard_col, aliases in column_map.items():
        for alias in aliases:
            if alias in df.columns:
                rename_dict[alias] = standard_col
                break # Found a match for this standard col
    
    df.rename(columns=rename_dict, inplace=True)
    return df

def clean_phone_number(num):
    """
    Standardizes phone numbers:
    - Removes spaces, dashes, +91.
    - Returns None if it's a junk number (like '100' or '198').
    """
    if pd.isna(num): return None
    
    # Remove non-digits
    clean_num = re.sub(r'\D', '', str(num))
    
    # Strip leading 91 if present (Indian country code)
    if clean_num.startswith('91') and len(clean_num) > 10:
        clean_num = clean_num[2:]
        
    # Validation: Must be at least 10 digits
    if len(clean_num) < 10:
        return None
        
    # Filter known junk (Service numbers)
    if clean_num in ['100', '101', '112', '198', '199', '121']:
        return None
        
    return clean_num

def process_cdr(file_path):
    print(f"   ↳ [INTERNAL] Processing CDR file: {file_path}...", flush=True)
    
    try:
        # Read CSV (try different encodings just in case)
        try:
            df = pd.read_csv(file_path)
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding='latin1')

        # 1. Normalize Column Names
        df = normalize_columns(df)

        # 2. Handle Timestamp (Merge Date + Time if needed)
        if 'timestamp' not in df.columns:
            if 'date' in df.columns and 'time' in df.columns:
                # Combine Date and Time
                df['timestamp'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str), errors='coerce')
            elif 'date' in df.columns:
                df['timestamp'] = pd.to_datetime(df['date'], errors='coerce')
            else:
                # If absolutely no date info, use generic placeholder or fail
                print("   ⚠️ Warning: No Date/Time found. Using default timestamp.")
                df['timestamp'] = pd.Timestamp.now()

        # 3. Validation: Check if critical columns exist
        required_cols = ['source', 'destination']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            print(f"   ❌ [ERROR] Missing critical columns: {missing}", flush=True)
            return []

        # 4. Data Cleaning (Apply to Source and Destination)
        df['source'] = df['source'].apply(clean_phone_number)
        df['destination'] = df['destination'].apply(clean_phone_number)
        
        # Drop rows where source OR destination became None (invalid numbers)
        original_count = len(df)
        df.dropna(subset=['source', 'destination'], inplace=True)
        dropped_count = original_count - len(df)
        
        if dropped_count > 0:
            print(f"   ℹ️ Filtered out {dropped_count} rows (short numbers/junk).", flush=True)

        # 5. Convert to List of Dictionaries
        # Select only the columns we need
        final_cols = ['source', 'destination', 'timestamp', 'duration_sec', 'tower_location', 'call_type']
        # Only keep columns that actually exist in the dataframe
        existing_cols = [c for c in final_cols if c in df.columns]
        
        data = df[existing_cols].to_dict(orient='records')
        
        print(f"   ✅ [SUCCESS] Extracted {len(data)} valid call records.", flush=True)
        return data

    except Exception as e:
        print(f"   ❌ [ERROR] CDR Processing Failed: {str(e)}", flush=True)
        return []