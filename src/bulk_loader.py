import os
import zipfile
import shutil
import tempfile
from src.graph_manager import GraphManager
from src.processors.fir_processor import process_fir
from src.processors.cdr_processor import process_cdr
from src.processors.cctv_processor import process_cctv

def load_evidence_db(db_folder="Evidence_DB"):
    """
    Scans the evidence_db folder for ZIP files (representing cases)
    and loads them into Neo4j with a Case ID linkage.
    """
    if not os.path.exists(db_folder):
        return [f"❌ Error: Folder '{db_folder}' not found."]

    gm = GraphManager()
    logs = []
    
    # scan for zip files
    zip_files = [f for f in os.listdir(db_folder) if f.endswith('.zip')]
    
    if not zip_files:
        return ["⚠️ No ZIP case archives found in Evidence_DB."]

    for zip_name in zip_files:
        case_id = os.path.splitext(zip_name)[0]  # Case_2019_Robbery
        zip_path = os.path.join(db_folder, zip_name)
        
        logs.append(f"🔄 Processing Archive: {case_id}...")
        
        # Create temp extraction folder
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Walk through extracted files
                file_count = 0
                for root, _, files in os.walk(temp_dir):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        ext = filename.lower().split('.')[-1]
                        
                        print(f"⏳ [PROCESSING] {filename}...", flush=True)
                        
                        try:
                            # FIR (Text/PDF)
                            if ext in ['txt', 'pdf']:
                                # process_fir now handles file reading internaly (expecting path)
                                data = process_fir(file_path)
                                
                                if "error" not in data:
                                    gm.add_fir_data(data, link_to_case_id=case_id)
                                    file_count += 1
                                    print(f"✅ [SUCCESS] {filename} processed and linked.", flush=True)
                                else:
                                    logs.append(f"   ⚠️ FIR Error in {filename}: {data['error']}")
                                    print(f"⚠️ [WARNING] FIR Error in {filename}: {data['error']}", flush=True)
                                
                            # CSV (Smart Routing)
                            elif ext == 'csv':
                                # Check headers to decide which processor to use
                                import pandas as pd
                                try:
                                    df_head = pd.read_csv(file_path, nrows=1)
                                    # Normalize headers for checking
                                    cols_str = " ".join([str(c).lower() for c in df_head.columns])
                                    
                                    # BANK CHECK
                                    if 'amount' in cols_str or 'credit' in cols_str or 'debit' in cols_str or 'balance' in cols_str:
                                        print(f"   ↳ [INTERNAL] Detected BANK Statement structure...", flush=True)
                                        # Import here to avoid circular dependency if any? (Should be fine at top, but sticking to routine)
                                        from src.processors.bank_processor import process_bank_statement
                                        data = process_bank_statement(file_path)
                                        
                                        # Data is dict: {'account_holder':..., 'transactions': [...]}
                                        txs = data.get('transactions', [])
                                        if txs:
                                            gm.add_bank_data(data, link_to_case_id=case_id)
                                            file_count += 1
                                            print(f"✅ [SUCCESS] {filename} (Bank) processed and linked.", flush=True)
                                        else:
                                            print(f"⚠️ [SKIP] No valid transactions found in {filename}.", flush=True)

                                    # CDR CHECK
                                    elif 'source' in cols_str or 'caller' in cols_str or 'origin' in cols_str or 'from' in cols_str:
                                        print(f"   ↳ [INTERNAL] Detected CDR structure...", flush=True)
                                        data = process_cdr(file_path) # Returns list
                                        if data and len(data) > 0:
                                            gm.add_cdr_data(data, link_to_case_id=case_id)
                                            file_count += 1
                                            print(f"✅ [SUCCESS] {filename} (CDR) processed and linked.", flush=True)
                                        else:
                                            print(f"⚠️ [SKIP] No valid call records found in {filename}.", flush=True)
                                    
                                    else:
                                        print(f"⚠️ [SKIP] Unknown CSV format in {filename}. Skipping.", flush=True)
                                        
                                except Exception as csv_e:
                                    print(f"❌ [ERROR] Analyzying CSV {filename}: {csv_e}", flush=True)
                                
                            # CCTV (Images)
                            elif ext in ['jpg', 'jpeg', 'png']:
                                # process_cctv takes file path
                                data = process_cctv(file_path)
                                gm.add_cctv_data(data, link_to_case_id=case_id)
                                file_count += 1
                                print(f"✅ [SUCCESS] {filename} processed and linked.", flush=True)
                                
                        except Exception as e:
                            logs.append(f"   ❌ Failed file {filename}: {str(e)}")
                            print(f"❌ [ERROR] Failed to process {filename}: {str(e)}", flush=True)
                            
                logs.append(f"✅ Loaded {case_id} ({file_count} files linked).")
                
            except Exception as e:
                logs.append(f"❌ Failed to process zip {zip_name}: {e}")
                
    gm.close()
    return logs
