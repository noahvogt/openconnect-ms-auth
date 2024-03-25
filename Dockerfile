FROM python:3.12-slim as Runner

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Env
ENV IS_DOCKER=true
ENV PYTHONPATH=/
ENV GECKO_DRIVER_VERSION='v0.30.0'
ENV PATH="/root/.local/bin:$PATH"

# install VPN utils
# hadolint ignore=DL3008
RUN apt-get update \
  && apt-get install -y --no-install-recommends openvpn openconnect curl cifs-utils zip firefox-esr \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Firefox (Selenium)
RUN curl -OL https://github.com/mozilla/geckodriver/releases/download/$GECKO_DRIVER_VERSION/geckodriver-$GECKO_DRIVER_VERSION-linux64.tar.gz  \
  && tar -xvzf geckodriver-$GECKO_DRIVER_VERSION-linux64.tar.gz \
  && rm geckodriver-$GECKO_DRIVER_VERSION-linux64.tar.gz \
  && chmod +x geckodriver \
  && cp geckodriver /usr/local/bin/ \
  curl -sSL https://install.python-poetry.org | python3 -

# Install the env
WORKDIR /
COPY poetry.lock .
COPY pyproject.toml .
RUN poetry install --no-interaction --no-ansi --without dev --no-root

# Copy the files
COPY ocma /ocma
WORKDIR /ocma
