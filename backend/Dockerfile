FROM python:3.12-slim

# Use Tsinghua (TUNA) mirror for apt (faster/more stable in mainland China); works for both
# the legacy sources.list and the newer deb822 sources.list.d/debian.sources format.
# RUN sed -i \
#     -e 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' \
#     -e 's|security.debian.org|mirrors.tuna.tsinghua.edu.cn/debian-security|g' \
#     /etc/apt/sources.list.d/*.sources 2>/dev/null || true \
#     && sed -i \
#     -e 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' \
#     -e 's|security.debian.org|mirrors.tuna.tsinghua.edu.cn/debian-security|g' \
#     /etc/apt/sources.list 2>/dev/null || true

# Retry flaky downloads instead of failing the whole apt-get on a single dropped connection
# RUN printf 'Acquire::Retries "5";\nAcquire::http::Timeout "30";\nAcquire::https::Timeout "30";\n' \
#     > /etc/apt/apt.conf.d/80-retries

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
    texlive-lang-chinese \
    texlive-science \
    texlive-xetex \
    tipa \
    dvisvgm \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
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

# ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
#     PATH="/app/.venv/bin:$PATH" \
#     UV_DEFAULT_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple/" \
#     UV_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple/" \
#     PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple/" \
#     UV_HTTP_TIMEOUT="120" \
#     npm_config_registry="https://registry.npmmirror.com" \
#     npm_config_fetch_retries="5" \
#     npm_config_fetch_retry_maxtimeout="60000"
