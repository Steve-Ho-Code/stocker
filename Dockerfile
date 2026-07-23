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

# Create the non-root user that runs the application
RUN addgroup --system app && adduser --system --group app
RUN mkdir -p /app/logs && chown app:app /app/logs

# Copy runtime files with ownership for the non-root application user.
COPY --chown=app:app src/ ./src/
COPY --chown=app:app alembic.ini .
COPY --chown=app:app alembic/ ./alembic/

USER app

# Run main.py when the container launches
CMD ["python", "-m", "src.main"]
