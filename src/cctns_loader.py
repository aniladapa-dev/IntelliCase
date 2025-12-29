import os
from src.graph_manager import GraphManager
from src.processors.fir_processor import process_fir

def load_cctns_history():
    """
    Load CCTNS FIR files from the cctns_db folder into the graph database.
    """
    folder_path = "cctns_db"
    
    # Safety Check: Check if folder exists
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print("Created cctns_db folder. Please add FIR files.")
        return
    
    # Initialize Graph Manager
    gm = GraphManager()
    
    # Loop through all files in the folder
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        
        # Process only .txt or .pdf files
        if filename.lower().endswith(('.txt', '.pdf')):
            print(f"Processing {filename}...")
            
            try:
                # Extract data using FIR processor
                extracted_data = process_fir(file_path)
                
                # Add to graph database
                gm.add_fir_data(extracted_data)
                
                # Success message
                print(f"✅ Loaded CCTNS Case: {filename}")
                
            except Exception as e:
                print(f"❌ Error processing {filename}: {str(e)}")
    
    # Close database connection
    gm.close()
