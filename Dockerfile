FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code.
COPY . .

# Run as a non-root user.
RUN useradd --create-home --uid 1000 botuser \
    && chown -R botuser:botuser /app
USER botuser

CMD ["python", "bot.py"]
