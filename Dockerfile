FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

COPY ./ /opt/latency-monitor/

WORKDIR /opt/latency-monitor/

RUN uv sync --locked --all-extras

ENTRYPOINT ["uv", "run", "latency-monitor"]
