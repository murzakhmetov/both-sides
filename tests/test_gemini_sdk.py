"""The real google-genai package on a mock transport: what goes over the wire.

Skipped when the package is not installed (the offline demo needs none).
"""

from __future__ import annotations

import json

import pytest

genai = pytest.importorskip("google.genai")
httpx = pytest.importorskip("httpx2")

from bothsides.matching.gemini import GeminiMatcher, make_client  # noqa: E402
from bothsides.matching.types import MatcherError  # noqa: E402

from .fakes import gemini_json  # noqa: E402

KEY = "test-key-not-real"


def build(handler: object) -> GeminiMatcher:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return GeminiMatcher(make_client(KEY, http_client=http), "gemini-3.8-flash", timeout_seconds=5)


def completed(text: str) -> "httpx.Response":
    return httpx.Response(
        200,
        json={
            "id": "x",
            "object": "interaction",
            "model": "gemini-3.8-flash",
            "status": "completed",
            "steps": [{"type": "model_output", "content": [{"type": "text", "text": text}]}],
        },
    )


def test_request_body_on_the_wire(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "wrong-key-from-another-variable")
    seen = []

    def handler(request: "httpx.Request") -> "httpx.Response":
        seen.append(request)
        return completed(gemini_json(probability=0.9))

    result = build(handler).compare("ағам пәтер", "Брату, аренда 90000 тенге")
    assert result.probability == pytest.approx(0.9)
    (request,) = seen
    body = json.loads(request.content)
    assert request.url.path.endswith("/interactions")
    assert request.headers["x-goog-api-key"] == KEY
    assert body["store"] is False
    assert body["response_format"]["mime_type"] == "application/json"
    assert body["response_format"]["schema"]["properties"]["same_reason"]["enum"] == ["true", "false", "unknown"]
    assert body["generation_config"]["thinking_level"] == "low"
    assert "90000" not in request.content.decode() and "тенге" not in request.content.decode()
    assert KEY not in request.content.decode() and KEY not in str(request.url)


@pytest.mark.parametrize(
    ("status", "code"), [(401, "auth"), (403, "auth"), (404, "model_not_found"), (429, "rate_limited"), (500, "error")]
)
def test_http_errors_are_not_retried(status: int, code: str) -> None:
    calls = []

    def handler(request: "httpx.Request") -> "httpx.Response":
        calls.append(request)
        return httpx.Response(status, json={"error": {"code": status, "message": "no", "status": "X"}})

    with pytest.raises(MatcherError) as caught:
        build(handler).compare("ағам пәтер", "Брату, аренда")
    assert caught.value.code == code
    assert len(calls) == 1


def test_transport_timeout() -> None:
    def handler(request: "httpx.Request") -> "httpx.Response":
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(MatcherError) as caught:
        build(handler).compare("ағам пәтер", "Брату, аренда")
    assert caught.value.code == "timeout"


def test_model_list_names() -> None:
    from bothsides.matching.gemini_models import list_flash_names

    def handler(request: "httpx.Request") -> "httpx.Response":
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "models/gemini-3.8-flash", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/gemini-embedding-2", "supportedGenerationMethods": ["embedContent"]},
                ]
            },
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    names = list_flash_names(make_client(KEY, http_client=http))
    assert "gemini-3.8-flash" in names
    assert "gemini-embedding-2" not in names
