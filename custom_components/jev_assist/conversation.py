"""Conversation entity: Jev route → light service or Grok-path stub."""

from __future__ import annotations

import logging
from typing import Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    intent,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .jev_router import ExposedEntity, RouteResult, route

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the conversation entity."""
    async_add_entities([JevAssistConversationEntity(hass, entry)])


class JevAssistConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
):
    """Assist agent that fast-paths lights via Jev and stubs the Grok path."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}-conversation"
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Jev Assist",
            model="jev-latest",
        )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        result = await self._async_route_and_act(user_input)
        speech = _speech_from_result(result)
        try:
            chat_log.async_add_assistant_content_without_tools(
                conversation.AssistantContent(
                    agent_id=user_input.agent_id,
                    content=speech,
                )
            )
        except Exception:  # noqa: BLE001 — older ChatLog shapes
            _LOGGER.debug("Chat log attach skipped", exc_info=True)
        return result

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Older HA path without ChatLog wrapping."""
        return await self._async_route_and_act(user_input)

    async def _async_route_and_act(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        runtime = self.hass.data[DOMAIN][self.entry.entry_id]
        exposed = _exposed_entities(self.hass)
        routed: RouteResult = await route(
            user_input.text,
            exposed,
            language=user_input.language or self.hass.config.language,
            client=runtime.jev,
        )
        _LOGGER.debug("Jev route kind=%s reason=%s", routed.kind, routed.reason)

        intent_response = intent.IntentResponse(language=user_input.language)
        if routed.kind == "fast_service" and routed.domain and routed.service:
            await self.hass.services.async_call(
                routed.domain,
                routed.service,
                routed.service_data or {},
                blocking=True,
                context=user_input.context,
            )
            speech = "OK"
            intent_response.async_set_speech(speech)
        elif routed.kind == "grok":
            speech = f"Grok path ({routed.reason})."
            intent_response.async_set_speech(speech)
        else:
            speech = "I can't help with that."
            intent_response.async_set_speech(speech)

        return conversation.ConversationResult(
            response=intent_response,
            conversation_id=user_input.conversation_id,
        )


def _speech_from_result(result: conversation.ConversationResult) -> str:
    try:
        speech = result.response.speech.get("plain", {}).get("speech")
        if isinstance(speech, str):
            return speech
    except Exception:  # noqa: BLE001
        pass
    return ""


def _exposed_entities(hass: HomeAssistant) -> list[ExposedEntity]:
    """Collect Assist-exposed entities (lights first; cap applied in the client)."""
    ent_reg = er.async_get(hass)
    area_reg = ar.async_get(hass)
    should_expose = _should_expose
    items: list[ExposedEntity] = []
    for state in hass.states.async_all():
        entity_id = state.entity_id
        domain = entity_id.split(".", 1)[0]
        if not should_expose(hass, entity_id):
            continue
        entry = ent_reg.async_get(entity_id)
        area_name: str | None = None
        aliases: tuple[str, ...] = ()
        if entry is not None:
            aliases = tuple(entry.aliases or ())
            area_id = entry.area_id
            if not area_id and entry.device_id:
                device = dr.async_get(hass).async_get(entry.device_id)
                area_id = device.area_id if device else None
            if area_id:
                area = area_reg.async_get_area(area_id)
                area_name = area.name if area else None
        items.append(
            ExposedEntity(
                entity_id=entity_id,
                domain=domain,
                name=state.name,
                area=area_name,
                aliases=aliases,
            )
        )
    return items


def _should_expose(hass: HomeAssistant, entity_id: str) -> bool:
    try:
        from homeassistant.components.homeassistant.exposed_entities import (
            async_should_expose,
        )

        return bool(async_should_expose(hass, conversation.DOMAIN, entity_id))
    except Exception:  # noqa: BLE001
        return entity_id.startswith("light.")
