import sys
import os

# Add src to python path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from processors.fir_processor import process_fir

def main():
    file_path = 'assets/fir_sample.txt'
    
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return

    with open(file_path, 'r') as f:
        content = f.read()
        
    print("Processing FIR...")
    result = process_fir(content)
    print("\nExtraction Result:")
    print(result)

if __name__ == "__main__":
    main()
