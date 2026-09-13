"""Shared helpers for HTTP AI backends."""

from __future__ import annotations

import os
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from lecturefoundry.ai.base import AIBackendError, BackendStatus


def retrying_session() -> requests.Session:
    """Create a session that retries short-lived connection and server failures."""

    retries = Retry(
        total=3,
        connect=3,
        read=0,
        status=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class APIKeyBackend:
    """Common environment-only credential handling for online APIs."""

    name: str

    def __init__(
        self,
        *,
        model: str | None,
        base_url: str,
        api_key_env: str,
        timeout_seconds: float,
        session: requests.Session | None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env.strip()
        self.timeout_seconds = timeout_seconds
        self._session = session or retrying_session()

    def _api_key(self) -> str:
        if not self.api_key_env:
            return ""
        value = os.environ.get(self.api_key_env, "").strip()
        if not value:
            raise AIBackendError(
                f"Environment variable {self.api_key_env} is required for {self.name}"
            )
        return value

    def _require_model(self) -> str:
        if not self.model:
            raise AIBackendError(f"A model must be configured for {self.name}")
        return self.model

    def _unavailable(self, error: Exception) -> BackendStatus:
        return BackendStatus(self.name, False, api_error_detail(error))


def api_error_detail(error: Exception) -> str:
    """Return a useful API error without including request headers or secrets."""

    response = getattr(error, "response", None)
    if response is not None:
        try:
            body: Any = response.json()
            detail = body.get("error", body) if isinstance(body, dict) else body
            if isinstance(detail, dict):
                message = detail.get("message") or detail.get("status")
                if message:
                    return f"HTTP {response.status_code}: {message}"
            if isinstance(detail, str) and detail:
                return f"HTTP {response.status_code}: {detail}"
        except (TypeError, ValueError):
            pass
        return f"HTTP {response.status_code}"
    return str(error)


def response_json(response: requests.Response, provider: str) -> dict[str, Any]:
    try:
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as error:
        raise AIBackendError(f"{provider} request failed: {api_error_detail(error)}") from error
    if not isinstance(body, dict):
        raise AIBackendError(f"{provider} returned a non-object JSON response")
    return body
