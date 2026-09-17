"""Config-flow strings for Copilot review follow-ups (no Home Assistant import)."""

from __future__ import annotations

import json
from pathlib import Path

STRINGS = json.loads(
    Path("custom_components/jev_assist/strings.json").read_text(encoding="utf-8")
)


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
