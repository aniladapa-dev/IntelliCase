import pandas as pd
import os

def process_bank_statement(file_path):
    """
    Process Bank Statement CSV.
    Expected Columns: Date, Description, Amount, (optional: Type, Balance)
    """
    print(f"   ↳ [INTERNAL] Analyzing bank statement...", flush=True)
    try:
        df = pd.read_csv(file_path)
        
        # Normalize headers: strip whitespace, title case might be risky, let's just strip
        df.columns = [str(c).strip() for c in df.columns]
        
        transactions = []
        
        # identified columns
        col_map = {}
        for c in df.columns:
            if 'date' in c.lower(): col_map['date'] = c
            elif 'desc' in c.lower() or 'particular' in c.lower(): col_map['desc'] = c
            elif 'amount' in c.lower() or 'credit' in c.lower() or 'debit' in c.lower(): col_map['amount'] = c
            
        if 'amount' not in col_map:
             return {"error": "No Amount column found"}

        for _, row in df.iterrows():
            amt = row[col_map['amount']]
            # Only process if amount is valid
            if pd.notnull(amt) and str(amt).strip() != '':
                t = {
                    "date": str(row.get(col_map.get('date', 'Unknown'), '')),
                    "description": str(row.get(col_map.get('desc', 'Unknown'), '')),
                    "amount": str(amt)
                }
                transactions.append(t)
                
        return {"account_holder": "Unknown", "transactions": transactions}

    except Exception as e:
        return {"error": f"Bank Processing Failed: {str(e)}"}
