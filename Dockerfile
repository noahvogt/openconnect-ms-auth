FROM python:3.14.8-slim AS runner

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /usr/local/bin/uv

# Env
ENV IS_DOCKER=true
# renovate: datasource=github-releases depName=mozilla/geckodriver
ENV GECKO_DRIVER_VERSION='v0.37.1'
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=never
ENV PATH="/app/.venv/bin:$PATH"

# install VPN utils
RUN apt-get update \
  && apt-get install -y --no-install-recommends openvpn openconnect curl cifs-utils zip firefox-esr \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Firefox (Selenium)
RUN curl -OL https://github.com/mozilla/geckodriver/releases/download/$GECKO_DRIVER_VERSION/geckodriver-$GECKO_DRIVER_VERSION-linux64.tar.gz  \
  && tar -xvzf geckodriver-$GECKO_DRIVER_VERSION-linux64.tar.gz \
  && rm geckodriver-$GECKO_DRIVER_VERSION-linux64.tar.gz \
  && chmod +x geckodriver \
  && cp geckodriver /usr/local/bin/

# Install the dependencies first, so that they are cached across code changes
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Install the project itself
COPY README.md LICENCE ./
COPY ocma ./ocma
RUN uv sync --locked --no-dev --no-editable

ENTRYPOINT ["ocma"]
