FROM python:3.13-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy dependency specifications and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt gunicorn>=23.0.0

# Copy project source code
COPY . .

# Expose application port
EXPOSE 5000

# Safely initialize database schema then launch Gunicorn WSGI server
CMD ["sh", "-c", "python init_db.py && exec gunicorn --bind 0.0.0.0:5000 --workers 2 --threads 2 --timeout 120 'run:app'"]
