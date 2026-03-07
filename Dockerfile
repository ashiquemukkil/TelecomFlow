# Use lightweight Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements first (better caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Chainlit default port
EXPOSE 8000

# Run Chainlit
CMD ["chainlit", "run", "ui.py", "--host", "0.0.0.0", "--port", "8000"]