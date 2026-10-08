FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
ENV PANCHANGA_MCP_TRANSPORT=streamable-http
EXPOSE 8000
CMD ["panchanga-mcp"]
