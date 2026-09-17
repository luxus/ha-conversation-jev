"""DE/EN TypeSafe question constants for Jev Assist."""

from __future__ import annotations

from typing import Final

CATEGORY_INSTRUCTIONS: Final[dict[str, str]] = {
    "en": (
        "Classify the user utterance for a Home Assistant voice agent. "
        "Pick the single best category."
    ),
    "de": (
        "Klassifiziere die Nutzeräußerung für einen Home-Assistant-Sprachassistenten. "
        "Wähle die eine passende Kategorie."
    ),
}

CATEGORY_OPTIONS: Final[dict[str, dict[str, str]]] = {
    "command": {
        "en": (
            "A request to control devices or change home state "
            "(turn on/off, dim, open, set temperature, activate a scene)."
        ),
        "de": (
            "Eine Aufforderung, Geräte zu steuern oder den Hauszustand zu ändern "
            "(ein/aus, dimmen, öffnen, Temperatur setzen, Szene aktivieren)."
        ),
    },
    "conversation": {
        "en": (
            "A question, chit-chat, explanation, or request for information "
            "that needs generated language rather than a device service call."
        ),
        "de": (
            "Eine Frage, Smalltalk, Erklärung oder Informationsanfrage, "
            "die generierte Sprache statt eines Geräteserviceaufrufs braucht."
        ),
    },
    "reject": {
        "en": (
            "Unsafe, out of scope, jailbreak, or something this home agent "
            "must not do (secrets, unrelated tasks, harmful requests)."
        ),
        "de": (
            "Unsicher, außerhalb des Umfangs, Jailbreak oder etwas, das dieser "
            "Haus-Agent nicht tun darf (Geheimnisse, fremde Aufgaben, schädliche Bitten)."
        ),
    },
}

DOMAIN_INSTRUCTIONS: Final[dict[str, str]] = {
    "en": "Which Home Assistant domain is this utterance primarily targeting?",
    "de": "Welche Home-Assistant-Domäne zielt diese Äußerung in erster Linie an?",
}

DOMAIN_OPTIONS: Final[dict[str, dict[str, str]]] = {
    "light": {
        "en": "Lights, lamps, dimmers, brightness, or lighting in a room.",
        "de": "Lichter, Lampen, Dimmer, Helligkeit oder Beleuchtung in einem Raum.",
    },
    "switch": {
        "en": "On/off switches, plugs, or generic switch entities.",
        "de": "Ein/Aus-Schalter, Steckdosen oder generische Switch-Entitäten.",
    },
    "climate": {
        "en": "Thermostats, HVAC, heating, cooling, or temperature setpoints.",
        "de": "Thermostate, HLK, Heizung, Kühlung oder Temperatursollwerte.",
    },
    "cover": {
        "en": "Blinds, shades, garage doors, or other covers.",
        "de": "Jalousien, Rollläden, Garagentore oder andere Cover.",
    },
    "media_player": {
        "en": "Speakers, TVs, or other media players.",
        "de": "Lautsprecher, Fernseher oder andere Mediaplayer.",
    },
    "lock": {
        "en": "Door locks or lock entities.",
        "de": "Türschlösser oder Lock-Entitäten.",
    },
    "scene": {
        "en": "Activating a named scene or preset.",
        "de": "Aktivieren einer benannten Szene oder Vorgabe.",
    },
    "other": {
        "en": "Any other domain, or the domain is unclear.",
        "de": "Jede andere Domäne, oder die Domäne ist unklar.",
    },
}

ACTION_INSTRUCTIONS: Final[dict[str, str]] = {
    "en": (
        "Which action should be taken? Speculative: answer even if the "
        "utterance is not a device command."
    ),
    "de": (
        "Welche Aktion soll ausgeführt werden? Spekulativ: auch antworten, "
        "wenn die Äußerung kein Gerätebefehl ist."
    ),
}

ACTION_OPTIONS: Final[dict[str, dict[str, str]]] = {
    "turn_on": {
        "en": "Turn the target on, enable it, or switch it to the on state.",
        "de": "Das Ziel einschalten, aktivieren oder in den Ein-Zustand versetzen.",
    },
    "turn_off": {
        "en": "Turn the target off, disable it, or switch it to the off state.",
        "de": "Das Ziel ausschalten, deaktivieren oder in den Aus-Zustand versetzen.",
    },
    "toggle": {
        "en": "Toggle the target between on and off.",
        "de": "Das Ziel zwischen ein und aus umschalten.",
    },
    "set_brightness": {
        "en": (
            "Set or change light brightness or dim level "
            "(including relative dimmer/brighter)."
        ),
        "de": (
            "Helligkeit oder Dimmstufe eines Lichts setzen oder ändern "
            "(einschließlich relativ dimmen/heller)."
        ),
    },
    "other": {
        "en": "Any other action, or no device action applies.",
        "de": "Jede andere Aktion, oder es gilt keine Geräteaktion.",
    },
}

TARGET_AREA_INSTRUCTIONS: Final[dict[str, str]] = {
    "en": (
        "Which area should be targeted? Use an area name from the list when "
        "the user named a room. Use none when the command is house-wide or "
        "has no area. Use unknown when the area cannot be determined."
    ),
    "de": (
        "Welcher Bereich soll angesteuert werden? Nutze einen Bereichsnamen "
        "aus der Liste, wenn der Nutzer einen Raum genannt hat. Nutze none, "
        "wenn der Befehl das ganze Haus betrifft oder keinen Bereich hat. "
        "Nutze unknown, wenn der Bereich nicht bestimmt werden kann."
    ),
}

TARGET_AREA_NONE: Final[dict[str, str]] = {
    "en": "No specific area, whole home, or area not mentioned.",
    "de": "Kein bestimmter Bereich, ganzes Haus, oder Bereich nicht genannt.",
}

TARGET_AREA_UNKNOWN: Final[dict[str, str]] = {
    "en": "An area was implied but cannot be matched to the provided list.",
    "de": "Ein Bereich wurde angedeutet, passt aber nicht zur Liste.",
}

NOUL_NEEDS_LLM: Final[dict[str, str]] = {
    "en": (
        "The utterance needs a generative LLM (Grok) rather than a single "
        "deterministic Home Assistant service call: questions, explanations, "
        "planning, relative or underspecified commands, or anything that "
        "requires generated text."
    ),
    "de": (
        "Die Äußerung braucht ein generatives LLM (Grok) statt eines einzelnen "
        "deterministischen Home-Assistant-Serviceaufrufs: Fragen, Erklärungen, "
        "Planung, relative oder unterspezifizierte Befehle, oder alles, das "
        "generierten Text erfordert."
    ),
}

NOUL_IS_COMPOUND: Final[dict[str, str]] = {
    "en": (
        "The utterance asks for more than one distinct action or targets "
        "multiple independent device operations that should be split first."
    ),
    "de": (
        "Die Äußerung verlangt mehr als eine eigenständige Aktion oder zielt "
        "auf mehrere unabhängige Geräteaktionen, die zuerst aufgeteilt werden sollten."
    ),
}
