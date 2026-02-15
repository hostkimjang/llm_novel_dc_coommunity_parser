FROM python:3.11-slim

WORKDIR /app
# mcp-bridge는 SearchXNG 프록시만 하므로, llama-cpp-python(빌드 필요) 같은 무거운 의존성은 설치하지 않는다.
RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic

COPY src /app/src
ENV PYTHONPATH=/app/src

EXPOSE 3333
CMD ["python", "-m", "llm_batch.mcp_bridge.server"]

