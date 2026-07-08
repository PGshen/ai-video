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

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"
