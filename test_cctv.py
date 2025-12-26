import sys
import os

# Add src to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from processors.cctv_processor import process_cctv

def main():
    image_path = 'assets/cctv_sample.png'
    
    if not os.path.exists(image_path):
        print(f"Error: File {image_path} not found.")
        return

    print(f"Processing CCTV image: {image_path}...")
    result = process_cctv(image_path)
    print("\nCCTV Analysis Result:")
    print(result)

if __name__ == "__main__":
    main()
