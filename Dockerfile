# Use an official Python image
FROM python:3.9-slim
 
# Set work directory
WORKDIR /BetaHealth
 
# Install dependencies first (better cache layer)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
 
# Copy app code + static + templates
COPY . .
 
# Expose Flask port
EXPOSE 5001
 
# Run the Flask app
CMD ["python3", "app3.py"]