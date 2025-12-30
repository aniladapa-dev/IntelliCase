FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for EasyOCR (Updated for Debian Bookworm/Trixie)
RUN apt-get update && apt-get install -y     libgl1     libglib2.0-0     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
