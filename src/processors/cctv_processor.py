import easyocr
import warnings
import re

# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

def extract_license_plate(text_list):
    """
    Scans a list of text strings for Indian License Plate patterns.
    Matches formats like: MH02C5555, MH 02 C 5555, TS07UB1234
    """
    # Regex for standard Indian plates (approximate)
    # 2 letters + 2 numbers + 1-2 letters + 4 numbers
    plate_pattern = r'[A-Z]{2}[\s\-]?[0-9]{1,2}[\s\-]?[A-Z]{1,3}[\s\-]?[0-9]{3,4}'
    
    for text in text_list:
        # Normalize: Upper case, remove special chars
        clean_text = text.upper().replace('.', '').strip()
        
        # Check if the whole text block looks like a plate
        if re.search(plate_pattern, clean_text):
            # Return standardized version (remove spaces)
            return re.sub(r'[\s\-]', '', clean_text)
            
    return None

def process_cctv(image_path):
    """
    Process CCTV image to extract text and identify vehicles.
    """
    print(f"   ↳ [INTERNAL] Scanning image for text via OCR: {image_path}...", flush=True)
    
    try:
        # Initialize EasyOCR Reader (using CPU for compatibility)
        reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        
        # Read text from image
        results = reader.readtext(image_path)
        
        detected_text = []
        for (bbox, text, prob) in results:
            if prob > 0.3:
                detected_text.append(text)
        
        # Smart Extraction: Look for a license plate
        plate_number = extract_license_plate(detected_text)
        
        if plate_number:
            print(f"   ✅ [SUCCESS] Vehicle Identified: {plate_number}", flush=True)
            return {
                "vehicle_number": plate_number,
                "raw_text": detected_text,
                "status": "success"
            }
        else:
            print(f"   ⚠️ [INFO] No clear license plate found in {len(detected_text)} text blocks.", flush=True)
            return {
                "vehicle_number": None,
                "raw_text": detected_text,
                "status": "partial_success"
            }
        
    except Exception as e:
        print(f"   ❌ [ERROR] Processing CCTV image: {str(e)}", flush=True)
        return {
            "vehicle_number": None,
            "error": str(e),
            "status": "error"
        }