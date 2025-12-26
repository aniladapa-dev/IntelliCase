import easyocr
import warnings

# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

def process_cctv(image_path):
    """
    Process CCTV image to extract text using OCR.
    
    Args:
        image_path (str): Path to the image file.
        
    Returns:
        dict: Dictionary containing detected text and status.
    """
    try:
        # Initialize EasyOCR Reader (using CPU)
        reader = easyocr.Reader(['en'], gpu=False)
        
        # Read text from image
        results = reader.readtext(image_path)
        
        detected_text = []
        for (bbox, text, prob) in results:
            if prob > 0.3:
                detected_text.append(text)
                
        return {
            "detected_text": detected_text,
            "status": "success"
        }
        
    except Exception as e:
        print(f"Error processing CCTV image: {e}")
        return {
            "detected_text": [],
            "status": "error",
            "message": str(e)
        }
