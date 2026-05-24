FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ── System packages ────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3-pip \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Make python3.11 the default python3
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

WORKDIR /app

# ── Python dependencies ────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# ── Application code ───────────────────────────────────────────────────────────
COPY . .

# ── Nginx config ───────────────────────────────────────────────────────────────
COPY nginx.conf /etc/nginx/sites-available/wavroom
RUN ln -sf /etc/nginx/sites-available/wavroom /etc/nginx/sites-enabled/wavroom \
    && rm -f /etc/nginx/sites-enabled/default

# ── Supervisor config ──────────────────────────────────────────────────────────
COPY supervisord.conf /etc/supervisor/conf.d/wavroom.conf

# ── Collect static files ───────────────────────────────────────────────────────
RUN python3 manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 80

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]

# Testing Script 