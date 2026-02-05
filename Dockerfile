FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create projects directory
RUN mkdir -p projects

# Run the application
CMD ["python", "app.py"]
