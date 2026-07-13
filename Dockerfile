FROM python:3.12-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY the_harness/ the_harness/
COPY demo.py ./

# Install dependencies
RUN pip install --no-cache-dir -e .

# Expose WebUI port
EXPOSE 8000

# Run WebUI server
CMD ["uvicorn", "the_harness.webui:app", "--host", "0.0.0.0", "--port", "8000"]
