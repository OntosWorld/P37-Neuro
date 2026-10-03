FROM python:3.12-slim

LABEL org.opencontainers.image.title="P37 Neuro CLI"
LABEL org.opencontainers.image.source="https://github.com/OntosWorld/P37-Neuro"
LABEL org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /opt/p37
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

ENTRYPOINT ["p37"]
CMD ["info"]
