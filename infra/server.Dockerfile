FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.5
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,id=offerpilot-uv,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project --link-mode=copy
COPY apps/server apps/server
RUN --mount=type=cache,id=offerpilot-uv,target=/root/.cache/uv uv sync --frozen --no-dev --link-mode=copy
ENV PATH="/app/.venv/bin:$PATH"
USER 10001
CMD ["uvicorn", "offerpilot.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
