FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
ENV PYTHONPATH=/app/src
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
COPY data/sample ./data/sample
COPY evaluation ./evaluation
RUN useradd --uid 10001 --create-home rag && chown -R rag:rag /app
USER rag
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health',timeout=2)" || exit 1
ENTRYPOINT ["python", "-m", "grounded_rag.cli"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8765"]
