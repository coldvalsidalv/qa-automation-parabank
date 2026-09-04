# Image version must match the playwright version pinned in uv.lock,
# so the preinstalled browsers are compatible.
FROM mcr.microsoft.com/playwright/python:v1.62.0-noble

WORKDIR /app

# Install locked dependencies first so they cache independently of source changes.
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv export --frozen --no-emit-project --no-hashes -o /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY . .

CMD ["pytest", "-m", "smoke"]
