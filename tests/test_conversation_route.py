"""Classify/route/service failures must speak, never raise into Assist."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from jev_assist.const import (
    DOMAIN,
    GROK_HANDOFF_UNAVAILABLE_SPEECH,
    ROUTE_FAILURE_SPEECH,
)
from jev_assist.jev_router import RouteResult


def _ensure_module(name: str) -> types.ModuleType:
    existing = sys.modules.get(name)
    if isinstance(existing, types.ModuleType):
        return existing
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


def _install_homeassistant_stubs() -> None:
    """conversation.py imports Home Assistant; tests stub the surface it needs."""
    if getattr(sys.modules.get("homeassistant"), "_jev_assist_test_stub", False):
        return

    ha = _ensure_module("homeassistant")
    ha._jev_assist_test_stub = True  # type: ignore[attr-defined]

    components = _ensure_module("homeassistant.components")
    ha.components = components  # type: ignore[attr-defined]

    conv = _ensure_module("homeassistant.components.conversation")
    components.conversation = conv  # type: ignore[attr-defined]

    class ConversationEntity:
        async def async_added_to_hass(self) -> None:
            return None

        async def async_will_remove_from_hass(self) -> None:
            return None

    class AbstractConversationAgent:
        pass

    class ConversationEntityFeature:
        CONTROL = 1

    class ConversationResult:
        def __init__(self, response: Any, conversation_id: str | None = None) -> None:
            self.response = response
            self.conversation_id = conversation_id

    class AssistantContent:
        def __init__(self, agent_id: Any = None, content: str | None = None) -> None:
            self.agent_id = agent_id
            self.content = content

    conv.ConversationEntity = ConversationEntity
    conv.AbstractConversationAgent = AbstractConversationAgent
    conv.ConversationEntityFeature = ConversationEntityFeature
    conv.ConversationResult = ConversationResult
    conv.AssistantContent = AssistantContent
    conv.ChatLog = object
    conv.ConversationInput = object
    conv.DOMAIN = "conversation"
    conv.async_set_agent = lambda *args, **kwargs: None
    conv.async_unset_agent = lambda *args, **kwargs: None
    conv.async_converse = AsyncMock(side_effect=RuntimeError("converse unused"))

    const = _ensure_module("homeassistant.const")
    ha.const = const  # type: ignore[attr-defined]
    const.MATCH_ALL = "*"

    core = _ensure_module("homeassistant.core")
    ha.core = core  # type: ignore[attr-defined]
    core.HomeAssistant = object

    config_entries = _ensure_module("homeassistant.config_entries")
    ha.config_entries = config_entries  # type: ignore[attr-defined]
    config_entries.ConfigEntry = object

    helpers = _ensure_module("homeassistant.helpers")
    ha.helpers = helpers  # type: ignore[attr-defined]

    area_registry = _ensure_module("homeassistant.helpers.area_registry")
    device_registry = _ensure_module("homeassistant.helpers.device_registry")
    entity_registry = _ensure_module("homeassistant.helpers.entity_registry")
    intent = _ensure_module("homeassistant.helpers.intent")
    entity_platform = _ensure_module("homeassistant.helpers.entity_platform")
    helpers.area_registry = area_registry  # type: ignore[attr-defined]
    helpers.device_registry = device_registry  # type: ignore[attr-defined]
    helpers.entity_registry = entity_registry  # type: ignore[attr-defined]
    helpers.intent = intent  # type: ignore[attr-defined]
    helpers.entity_platform = entity_platform  # type: ignore[attr-defined]

    class DeviceInfo:
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    class IntentResponse:
        def __init__(self, language: str | None = None) -> None:
            self.language = language
            self.speech: str | None = None

        def async_set_speech(self, speech: str, **kwargs: Any) -> None:
            self.speech = speech

    device_registry.DeviceInfo = DeviceInfo
    intent.IntentResponse = IntentResponse
    entity_platform.AddEntitiesCallback = object


_install_homeassistant_stubs()

from jev_assist.conversation import (  # noqa: E402
    JevAssistConversationEntity,
)


class RaisingJevClient:
    def __init__(self, error: BaseException) -> None:
        self.error = error
        self.classify_calls = 0

    async def classify(self, utterance: str, exposed: Any, *, language: str) -> Any:
        self.classify_calls += 1
        raise self.error


def _entity(*, jev: Any, async_call: Any | None = None) -> JevAssistConversationEntity:
    hass = SimpleNamespace(
        data={DOMAIN: {"entry-1": SimpleNamespace(jev=jev)}},
        config=SimpleNamespace(language="de"),
        services=SimpleNamespace(async_call=async_call or AsyncMock()),
    )
    entry = SimpleNamespace(entry_id="entry-1", title="Jev Assist")
    return JevAssistConversationEntity(hass, entry)


def _input(text: str = "Licht aus") -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        language="de",
        conversation_id="conv-licht",
        context="ctx",
        agent_id="conversation.jev_assist",
    )


def _speech(result: Any) -> str | None:
    return getattr(getattr(result, "response", None), "speech", None)


@pytest.mark.asyncio
async def test_classify_runtime_error_returns_speech_not_raise(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = RaisingJevClient(RuntimeError("typesafe exploded"))
    entity = _entity(jev=client)
    monkeypatch.setattr(
        "jev_assist.conversation._exposed_entities",
        lambda hass: [],
    )
    user_input = _input()

    with caplog.at_level("ERROR"):
        result = await entity._async_route_and_act(user_input, chat_log=None)

    assert client.classify_calls == 1
    assert _speech(result) == ROUTE_FAILURE_SPEECH
    assert result.conversation_id == "conv-licht"
    assert "Jev route-and-act failed" in caplog.text
    assert "typesafe exploded" in caplog.text


@pytest.mark.asyncio
async def test_async_process_classify_runtime_error_does_not_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entity = _entity(jev=RaisingJevClient(RuntimeError("typesafe exploded")))
    monkeypatch.setattr(
        "jev_assist.conversation._exposed_entities",
        lambda hass: [],
    )
    result = await entity.async_process(_input())
    assert _speech(result) == ROUTE_FAILURE_SPEECH


@pytest.mark.asyncio
async def test_fast_service_async_call_failure_returns_speech(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def fake_route(*args: Any, **kwargs: Any) -> RouteResult:
        return RouteResult(
            kind="fast_service",
            reason="light_v0",
            domain="light",
            service="turn_off",
            service_data={"entity_id": "light.wohnzimmer"},
        )

    async_call = AsyncMock(side_effect=RuntimeError("service exploded"))
    entity = _entity(jev=SimpleNamespace(), async_call=async_call)
    monkeypatch.setattr("jev_assist.conversation.route", fake_route)
    monkeypatch.setattr(
        "jev_assist.conversation._exposed_entities",
        lambda hass: [],
    )

    with caplog.at_level("ERROR"):
        result = await entity._async_route_and_act(_input(), chat_log=None)

    assert _speech(result) == ROUTE_FAILURE_SPEECH
    assert "Jev fast_service light.turn_off failed" in caplog.text
    assert "service exploded" in caplog.text
    async_call.assert_awaited_once()


@pytest.mark.asyncio
async def test_grok_handoff_failure_still_uses_unavailable_speech(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_route(*args: Any, **kwargs: Any) -> RouteResult:
        return RouteResult(kind="grok", reason="no_named_or_area_target")

    entity = _entity(jev=SimpleNamespace())
    monkeypatch.setattr("jev_assist.conversation.route", fake_route)
    monkeypatch.setattr(
        "jev_assist.conversation._exposed_entities",
        lambda hass: [],
    )
    monkeypatch.setattr(
        "jev_assist.conversation.async_try_handoff_to_conversation_agent",
        AsyncMock(side_effect=RuntimeError("agent lookup exploded")),
    )

    result = await entity._async_route_and_act(_input(), chat_log=None)
    assert _speech(result) == GROK_HANDOFF_UNAVAILABLE_SPEECH
    assert _speech(result) != ROUTE_FAILURE_SPEECH
