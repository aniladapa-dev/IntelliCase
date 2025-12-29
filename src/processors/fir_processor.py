import os
import json
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
import warnings

# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Load Environment Variables
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables.")

genai.configure(api_key=api_key)

def read_file_content(file_path):
    """Helper to read text from file path."""
    try:
        if str(file_path).endswith('.pdf'):
            # Basic PDF text extraction (requires pypdf, falls back if not found)
            try:
                from pypdf import PdfReader
                reader = PdfReader(file_path)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                return text
            except ImportError:
                return "Error: PDF found but 'pypdf' library not installed. Please install pypdf."
        else:
            # Assume text file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def process_fir(file_path):
    # Robust Input Handling: Check if input is a Path or Text
    import os
    file_text = ""
    path_str = str(file_path)
    
    # Heuristic: If it looks like a path and exists, read it. Else treat as text.
    if len(path_str) < 300 and (os.path.exists(path_str) or "assets/" in path_str or "/tmp/" in path_str):
        print(f"   ↳ [INTERNAL] Processing FIR file path: {path_str}...", flush=True)
        file_text = read_file_content(path_str)
    else:
        print(f"   ↳ [INTERNAL] Processing FIR text content (len={len(path_str)})...", flush=True)
        file_text = path_str
    
    if not file_text or "Error" in file_text[:20]:
         return {"error": "File read failed"}

    print(f"   ↳ [INTERNAL] Sending to Gemini...", flush=True)
    model = genai.GenerativeModel('gemini-flash-latest')
    
    prompt = f"""
    Analyze this Police FIR (First Information Report) text.
    Extract the following fields into a pure JSON object:
    - suspect_name (String, or "Unknown")
    - suspect_phone (String, or null)
    - victim_name (String, or "Unknown")
    - victim_phone (String, or null)
    - vehicle_number (String, standardized uppercase, no spaces e.g. "MH02C5555")
    - vehicle_model (String)
    - crime_type (String)
    - location (String)
    - date (String, YYYY-MM-DD format if possible)

    Text:
    {file_text}
    
    Return ONLY valid JSON. No markdown formatting.
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip()
        if cleaned_text.startswith("```json"): cleaned_text = cleaned_text[7:]
        if cleaned_text.startswith("```"): cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith("```"): cleaned_text = cleaned_text[:-3]
        
        data = json.loads(cleaned_text.strip())
        print(f"   ✅ [SUCCESS] Extracted FIR details for {data.get('suspect_name')}", flush=True)
        return data

    except Exception as e:
        print(f"   ❌ [ERROR] LLM Extraction Failed: {str(e)}", flush=True)
        return {"error": str(e)}