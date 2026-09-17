"""Conversation entity: Jev route → light service or SpaceXAI Grok handoff."""

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

from .const import DOMAIN, GROK_HANDOFF_UNAVAILABLE_SPEECH, ROUTE_FAILURE_SPEECH
from .exposure import should_expose_compat, sort_lights_first
from .grok_handoff import (
    async_try_handoff_to_conversation_agent,
    resolve_grok_handoff_agent_id,
)
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
    """Assist agent that fast-paths lights via Jev and hands Grok off to SpaceXAI."""

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
        return await self._async_route_and_act(user_input, chat_log=chat_log)

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Older HA path without ChatLog wrapping."""
        return await self._async_route_and_act(user_input, chat_log=None)

    async def _async_route_and_act(
        self,
        user_input: conversation.ConversationInput,
        *,
        chat_log: conversation.ChatLog | None,
    ) -> conversation.ConversationResult:
        try:
            return await self._async_route_and_act_inner(
                user_input, chat_log=chat_log
            )
        except Exception:  # noqa: BLE001 — never raise into Assist
            _LOGGER.error(
                "Jev route-and-act failed text=%r",
                getattr(user_input, "text", None),
                exc_info=True,
            )
            speech = ROUTE_FAILURE_SPEECH
            result = _speech_result(user_input, speech)
            _attach_assistant(chat_log, user_input, speech)
            return result

    async def _async_route_and_act_inner(
        self,
        user_input: conversation.ConversationInput,
        *,
        chat_log: conversation.ChatLog | None,
    ) -> conversation.ConversationResult:
        runtime = self.hass.data[DOMAIN][self.entry.entry_id]
        try:
            exposed = _exposed_entities(self.hass)
        except Exception:  # noqa: BLE001 — registry/expose must not crash Assist
            _LOGGER.error("Jev exposed-entity collection failed", exc_info=True)
            exposed = []
        routed: RouteResult = await route(
            user_input.text,
            exposed,
            language=user_input.language or self.hass.config.language,
            client=runtime.jev,
        )
        if routed.kind == "fast_service":
            _LOGGER.debug("Jev route kind=%s reason=%s", routed.kind, routed.reason)
        else:
            _LOGGER.info("Jev route kind=%s reason=%s", routed.kind, routed.reason)

        if routed.kind == "grok":
            # Target agent owns ChatLog content on success; attach only on local fallback.
            try:
                handed, speech = await self._async_handoff_to_grok(
                    user_input,
                    route_kind=routed.kind,
                    route_reason=routed.reason,
                )
            except Exception as err:  # noqa: BLE001 — never raise into Assist
                _LOGGER.info(
                    "Grok handoff failed kind=%s reason=%s: %s",
                    routed.kind,
                    routed.reason,
                    err,
                )
                handed, speech = None, GROK_HANDOFF_UNAVAILABLE_SPEECH
            if handed is not None:
                return handed
            speech = speech or GROK_HANDOFF_UNAVAILABLE_SPEECH
            result = _speech_result(user_input, speech)
            _attach_assistant(chat_log, user_input, speech)
            return result

        if routed.kind == "fast_service" and routed.domain and routed.service:
            try:
                await self.hass.services.async_call(
                    routed.domain,
                    routed.service,
                    routed.service_data or {},
                    blocking=True,
                    context=user_input.context,
                )
            except Exception:  # noqa: BLE001 — service failure → speech, not crash
                _LOGGER.error(
                    "Jev fast_service %s.%s failed",
                    routed.domain,
                    routed.service,
                    exc_info=True,
                )
                speech = ROUTE_FAILURE_SPEECH
            else:
                speech = "OK"
        else:
            speech = ROUTE_FAILURE_SPEECH

        result = _speech_result(user_input, speech)
        _attach_assistant(chat_log, user_input, speech)
        return result

    async def _async_handoff_to_grok(
        self,
        user_input: conversation.ConversationInput,
        *,
        route_kind: str,
        route_reason: str,
    ) -> tuple[conversation.ConversationResult | None, str | None]:
        agent_id = resolve_grok_handoff_agent_id(self.entry)
        return await async_try_handoff_to_conversation_agent(
            self.hass,
            user_input,
            agent_id=agent_id,
            converse=conversation.async_converse,
            route_kind=route_kind,
            route_reason=route_reason,
        )


def _speech_result(
    user_input: conversation.ConversationInput, speech: str
) -> conversation.ConversationResult:
    intent_response = intent.IntentResponse(language=user_input.language)
    intent_response.async_set_speech(speech)
    return conversation.ConversationResult(
        response=intent_response,
        conversation_id=user_input.conversation_id,
    )


def _attach_assistant(
    chat_log: conversation.ChatLog | None,
    user_input: conversation.ConversationInput,
    speech: str,
) -> None:
    if chat_log is None or not speech:
        return
    try:
        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=user_input.agent_id,
                content=speech,
            )
        )
    except Exception:  # noqa: BLE001 — older ChatLog shapes
        _LOGGER.debug("Chat log attach skipped", exc_info=True)


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
    return sort_lights_first(items)


def _should_expose(hass: HomeAssistant, entity_id: str) -> bool:
    try:
        from homeassistant.components.homeassistant.exposed_entities import (
            async_should_expose,
        )
    except ImportError:
        return False

    return should_expose_compat(
        lambda: async_should_expose(hass, conversation.DOMAIN, entity_id)
    )
