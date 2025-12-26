import os
import json
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

import warnings
# Suppress Google's deprecation warnings for the Hackathon
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# ... rest of your imports (import os, etc.)


# Build paths inside the project like this: BASE_DIR / 'subdir'.
# This points to the root 'IntelliCase' folder
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    # Debugging: Print where it looked for the file
    print(f"DEBUG: Looking for .env at: {BASE_DIR / '.env'}")
    raise ValueError("GEMINI_API_KEY not found in environment variables.")

genai.configure(api_key=api_key)

def process_fir(file_text):
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables.")
        
    model = genai.GenerativeModel('gemini-flash-latest')
    
    prompt = f"""
    Extract these entities as JSON from the text: suspect_name, vehicle_number, vehicle_model, crime_type, location, date. 
    Return ONLY raw JSON. Do not include markdown formatting like ```json ... ```.
    
    Text:
    {file_text}
    """
    
    response = model.generate_content(prompt)
    
    try:
        # Clean up potential markdown formatting if the model ignores the instruction
        cleaned_text = response.text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
            
        return json.loads(cleaned_text.strip())
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON", "raw_response": response.text}
