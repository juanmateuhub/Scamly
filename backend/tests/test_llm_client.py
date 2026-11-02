import json

import httpx
import pytest

from app.llm.client import LLMError, OpenAICompatibleClient


def make_client(handler: httpx.MockTransport) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url="https://llm.test/v1",
        model="test-model",
        api_key="secret-key",
        timeout_s=8,
        http=httpx.Client(transport=handler),
    )


def ok_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_sends_deterministic_json_request() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return ok_response('{"ok": true}')

    content = make_client(httpx.MockTransport(handler)).complete_json("system", "user")

    assert content == '{"ok": true}'
    assert seen["url"] == "https://llm.test/v1/chat/completions"
    assert seen["auth"] == "Bearer secret-key"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == "test-model"
    assert body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user"},
    ]


def test_fallback_models_are_sent_after_the_primary() -> None:
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return ok_response("{}")

    client = OpenAICompatibleClient(
        "https://llm.test/v1",
        "primary",
        "key",
        timeout_s=8,
        fallback_models=["backup-1", "backup-2"],
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    client.complete_json("system", "user")

    assert seen[0]["model"] == "primary"
    assert seen[0]["models"] == ["primary", "backup-1", "backup-2"]


def test_reasoning_can_be_disabled() -> None:
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return ok_response("{}")

    client = OpenAICompatibleClient(
        "https://llm.test/v1",
        "m",
        "key",
        timeout_s=8,
        disable_reasoning=True,
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    client.complete_json("system", "user")

    assert seen[0]["reasoning"] == {"enabled": False}


def test_no_fallback_list_by_default() -> None:
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return ok_response("{}")

    make_client(httpx.MockTransport(handler)).complete_json("system", "user")

    assert "models" not in seen[0]
    assert "reasoning" not in seen[0]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429, json={"error": "rate limited"}),
        httpx.Response(500, text="boom"),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": {"content": None}}]}),
    ],
)
def test_bad_responses_raise_llm_error(response: httpx.Response) -> None:
    client = make_client(httpx.MockTransport(lambda _: response))

    with pytest.raises(LLMError):
        client.complete_json("system", "user")


def test_timeout_raises_llm_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(LLMError):
        make_client(httpx.MockTransport(handler)).complete_json("system", "user")
