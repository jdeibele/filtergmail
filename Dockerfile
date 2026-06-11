# Dockerfile — filtergmail.com | v1.0.0 | 2026-06-11
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY filtergmail_web.py gmail_filter.py ./
COPY templates ./templates
RUN mkdir -p /data
ENV PORT=5060
EXPOSE 5060
CMD ["python", "filtergmail_web.py"]
