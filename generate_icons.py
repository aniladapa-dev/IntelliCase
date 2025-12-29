import base64
import requests
import os

# The Specific "SaaS Style" Icons - UPDATED PERSON ICON
ICONS = {
    "CASE": "https://img.icons8.com/color/96/police-badge.png",       # 🛡️ Badge
    "PERSON": "https://img.icons8.com/color/96/person-male.png",       # 👤 Single Person (UPDATED)
    "VEHICLE": "https://img.icons8.com/color/96/fiat-500.png",         # 🚗 Car
    "PHONE": "https://img.icons8.com/color/96/iphone.png",             # 📞 Phone
    "LOCATION": "https://img.icons8.com/color/96/marker.png",          # 📍 Red Pin
    "MONEY": "https://img.icons8.com/color/96/money-bag.png",          # 💰 Money Bag
    "CRIME": "https://img.icons8.com/color/96/handcuffs.png",          # 🔗 Crime/Handcuffs
    "DEFAULT": "https://img.icons8.com/color/96/high-priority.png"     # ❗ Alert
}

# Ensure the directory exists
output_dir = "src/utils"
os.makedirs(output_dir, exist_ok=True)
output_file = os.path.join(output_dir, "static_icons.py")

code_content = "# Auto-generated file containing Base64 encoded icons.\n"
code_content += "class StaticIcons:\n"

print("⬇️ Downloading and Converting Icons...")
for name, url in ICONS.items():
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            # Convert image to Base64 String
            b64_str = base64.b64encode(response.content).decode("utf-8")
            full_string = f"data:image/png;base64,{b64_str}"
            # Add to python class
            code_content += f'    {name} = "{full_string}"\n'
            print(f"✅ Encoded {name}")
        else:
            print(f"❌ Failed to download {name} (Status: {response.status_code})")
    except Exception as e:
        print(f"❌ Error encoding {name}: {e}")

# Write the file
with open(output_file, "w", encoding="utf-8") as f:
    f.write(code_content)
print(f"\n🎉 Success! '{output_file}' has been updated with the new icons.")
