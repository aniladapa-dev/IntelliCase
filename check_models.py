import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ Error: API Key not found in .env")
else:
    genai.configure(api_key=api_key)
    print("🔍 Checking available models for your API key...")
    
    try:
        # List all models
        models = genai.list_models()
        found_any = False
        for m in models:
            if 'generateContent' in m.supported_generation_methods:
                print(f"✅ Available: {m.name}")
                found_any = True
        
        if not found_any:
            print("⚠️ No models found with 'generateContent' capability.")
            
    except Exception as e:
        print(f"❌ Error listing models: {e}")