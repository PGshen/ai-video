FROM python:3.12-slim

# System deps for manim (cairo/pango rendering + ffmpeg + LaTeX for Tex/MathTex)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    git \
    curl \
    ffmpeg \
    sox \
    libcairo2-dev \
    libpango1.0-dev \
    libgirepository1.0-dev \
    texlive \
    texlive-latex-extra \
    texlive-fonts-extra \
    texlive-science \
    tipa \
    dvisvgm \
    && rm -rf /var/lib/apt/lists/*

# Node.js for the Remotion render engine (worker calls `pnpm`/`remotion` as a subprocess)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && corepack enable \
    && corepack prepare pnpm@10.27.0 --activate \
    && rm -rf /var/lib/apt/lists/*

# Shared libs required by Remotion's headless Chrome (chrome-headless-shell) at runtime
# https://remotion.dev/docs/troubleshooting/browser-launch
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    fonts-liberation \
    libu2f-udev \
    libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"
