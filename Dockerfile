FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
# desktop-only packages (flaskwebgui, pyinstaller) are not needed on the server
RUN grep -viE '^(flaskwebgui|pyinstaller)' requirements.txt > req.txt \
 && pip install --no-cache-dir -r req.txt && rm req.txt
COPY . .
RUN useradd -r -u 1001 app && mkdir -p /data /app/instance && chown app /data /app/instance
USER app
EXPOSE 8000
# port is only published on 127.0.0.1, so nginx is the only client and its X-Forwarded-Proto can be trusted
CMD ["sh", "-c", "python deploy/init_prod.py && exec gunicorn -w 3 -b 0.0.0.0:8000 --forwarded-allow-ips='*' 'app:create_app()'"]
