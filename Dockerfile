# 1. Use the official lightweight Python image
FROM python:3.10-slim

# 2. Set the working directory in the container
WORKDIR /app

# 3. Install system dependencies (Fixed for Debian Bookworm)
# We replace 'libgl1-mesa-glx' with 'libgl1' and 'libglx-mesa0' for modern compatibility
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglx-mesa0 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 4. PRE-INSTALL PYTORCH (CPU VERSION)
# This is the "Magic Step" that keeps your app under 4GB.
# Installing this BEFORE requirements.txt ensures Docling doesn't download the massive GPU version.
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu --no-cache-dir

# 5. Copy requirements and install dependencies
# Docker is at the root, so it grabs requirements.txt directly from here
COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir

# 6. Copy the rest of your application code into the container
COPY . .

# ---> NEW STEP 6.5: CREATE DIRECTORIES AND FIX PERMISSIONS <---
# This ensures the folders exist and Railway has full read/write access to save the PDFs
RUN mkdir -p auto-labor-compliance-agent/data/01_raw \
    && mkdir -p auto-labor-compliance-agent/data/02_intermediate \
    && mkdir -p auto-labor-compliance-agent/data/03_structured \
    && chmod -R 777 auto-labor-compliance-agent/data

# 7. Start the application
# We point Python directly to main.py inside your backend folder
CMD ["python", "auto-labor-compliance-agent/main.py"]