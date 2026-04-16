FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY profgraph/ profgraph/

RUN pip install --no-cache-dir ".[deploy]"

RUN mkdir -p /app/data

ENV PROFGRAPH_TRANSPORT=streamable-http
ENV PROFGRAPH_HOST=0.0.0.0
ENV PROFGRAPH_PORT=8000

EXPOSE 8000

CMD ["python", "-m", "profgraph"]
