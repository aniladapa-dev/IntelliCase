import pandas as pd

def process_cdr(file_path):
    """
    Process CDR CSV file to extract significant connections.
    
    Args:
        file_path (str): Path to the CDR CSV file.
        
    Returns:
        list: List of dictionaries representing edges.
              Example: [{"source": "...", "target": "...", "weight": 5, "duration": 120}, ...]
    """
    try:
        df = pd.read_csv(file_path)
        
        # Verify required columns
        required_columns = {'source', 'destination', 'duration_sec', 'timestamp'}
        if not required_columns.issubset(df.columns):
            missing = required_columns - set(df.columns)
            raise ValueError(f"Missing columns in CDR file: {missing}")

        # specific logic: Group by source and destination
        # Calculate 'total_duration' and 'call_count'
        grouped = df.groupby(['source', 'destination']).agg(
            call_count=('duration_sec', 'count'),
            total_duration=('duration_sec', 'sum')
        ).reset_index()

        # Filter: Keep only pairs where call_count >= 2 OR total_duration > 60
        filtered = grouped[
            (grouped['call_count'] >= 2) | (grouped['total_duration'] > 60)
        ]

        # Format output
        results = []
        for _, row in filtered.iterrows():
            results.append({
                "source": str(row['source']),
                "target": str(row['destination']),
                "weight": int(row['call_count']),
                "duration": int(row['total_duration'])
            })
            
        return results

    except Exception as e:
        print(f"Error processing CDR: {e}")
        return []
