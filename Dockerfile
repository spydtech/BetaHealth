# Use an official Python image
FROM python:3.9-slim
 
# Set work directory
WORKDIR /BetaHealth/
 
# Copy everything
COPY . .
 
# Install dependencies
RUN pip3 install --no-cache-dir -r requirements.txt
 
# Expose the port Flask runs on
EXPOSE 5001
 
# Run the Flask app
CMD ["python3", "app3.py"]