# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Set the PYTHONPATH to include the app directory
ENV PYTHONPATH="/app"

# Add the scripts directory to the PATH
ENV PATH="/usr/local/bin:${PATH}"

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY src/ ./src/
COPY alembic.ini .
COPY alembic/ ./alembic/

# Set the user to a non-root user for security
RUN addgroup --system app && adduser --system --group app
USER app

# Run main.py when the container launches
CMD ["python", "-m", "src.main"]
