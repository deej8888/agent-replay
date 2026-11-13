FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY packages/python-sdk packages/python-sdk
COPY examples examples
COPY apps/api apps/api
# Editable API install keeps the versioned migration files beside the package.
RUN pip install ./packages/python-sdk ./examples -e ./apps/api \
    && useradd --create-home agentreplay \
    && mkdir /data && chown agentreplay:agentreplay /data
USER agentreplay
ENV AGENTREPLAY_DATABASE_URL=sqlite:////data/agentreplay.db
EXPOSE 8000
CMD ["uvicorn", "agentreplay_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
