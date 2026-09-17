"""Config-flow strings for Copilot review follow-ups (no Home Assistant import)."""

from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path("custom_components/jev_assist")
STRINGS = json.loads((_ROOT / "strings.json").read_text(encoding="utf-8"))
EN = json.loads((_ROOT / "translations" / "en.json").read_text(encoding="utf-8"))
DE = json.loads((_ROOT / "translations" / "de.json").read_text(encoding="utf-8"))


def test_oauth_failed_exposes_retry_api_key_and_abort() -> None:
    options = STRINGS["selector"]["oauth_recovery"]["options"]
    assert "retry_oauth" in options
    assert "api_key" in options
    assert "abort" in options
    assert "oauth_recovery" in STRINGS["config"]["step"]["oauth_failed"]["data"]


def test_reauth_confirm_has_auth_method_selector() -> None:
    assert "grok_auth_method" in STRINGS["config"]["step"]["reauth_confirm"]["data"]


def test_reauth_abort_reason_is_translated() -> None:
    assert "reauth_successful" in STRINGS["config"]["abort"]
    assert "oauth_failed" in STRINGS["config"]["abort"]


def test_typesafe_jev_api_key_labels_name_typesafe_ai() -> None:
    user = STRINGS["config"]["step"]["user"]
    label = user["data"]["typesafe_api_key"]
    field_help = user["data_description"]["typesafe_api_key"]
    step_help = user["description"]
    assert "TypeSafe" in label and "Jev" in label
    assert "typesafe.ai" in label
    assert "typesafe.ai" in field_help
    assert "source of truth" in field_help
    assert "Vercel" in field_help
    assert "typesafe.ai" in step_help
    assert "Vercel" in step_help
    assert "Grok API key" in step_help
    assert EN == STRINGS
    de_user = DE["config"]["step"]["user"]
    assert "typesafe.ai" in de_user["data"]["typesafe_api_key"]
    assert "typesafe.ai" in de_user["data_description"]["typesafe_api_key"]
    assert "Vercel" in de_user["data_description"]["typesafe_api_key"]
    assert "Grok-API-Schlüssel" in de_user["description"]
