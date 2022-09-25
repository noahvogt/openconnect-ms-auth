FROM python:3.9.9-slim as Runner

# Env
ENV IS_DOCKER=true
ENV PYTHONPATH=/

# install VPN utils
RUN apt-get update
RUN apt-get install -y openvpn openconnect curl cifs-utils zip

# Firefox (Selenium)
RUN apt-get install -y firefox-esr
ENV GECKO_DRIVER_VERSION='v0.30.0'
RUN curl -OL https://github.com/mozilla/geckodriver/releases/download/$GECKO_DRIVER_VERSION/geckodriver-$GECKO_DRIVER_VERSION-linux64.tar.gz
RUN tar -xvzf geckodriver-$GECKO_DRIVER_VERSION-linux64.tar.gz
RUN rm geckodriver-$GECKO_DRIVER_VERSION-linux64.tar.gz
RUN chmod +x geckodriver
RUN cp geckodriver /usr/local/bin/

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Install the env
COPY poetry.lock .
COPY pyproject.toml .
RUN poetry install --no-interaction --no-ansi --without dev

# Copy the files
COPY ocma /ocma
WORKDIR /ocma
