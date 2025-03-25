# Use official Python image
FROM python:3.9

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Copy the Flask app
COPY . .

# Set environment variables (Cloud Run injects secrets)
ENV PORT=8080

# Start Flask with Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
