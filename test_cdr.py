import sys
import os

# Add src to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from processors.cdr_processor import process_cdr

def main():
    file_path = 'assets/cdr_sample.csv'
    
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return

    print("Processing CDR...")
    results = process_cdr(file_path)
    print("\nCDR Analysis Result:")
    for res in results:
        print(res)

if __name__ == "__main__":
    main()
