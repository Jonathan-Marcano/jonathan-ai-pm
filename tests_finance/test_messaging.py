"""Contrato de mensajería neutral y adaptador simulado (Fase 4, CF4-01)."""

import pytest

from cuentafaro.config import get_settings
from cuentafaro.messaging import (
    OutboundMessage,
    SimulatedProvider,
    get_messaging_provider,
)
from cuentafaro.messaging.base import MessagingProvider
from cuentafaro.services import DomainRuleError


@pytest.fixture(autouse=True)
def fresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default_provider_is_simulated(monkeypatch) -> None:
    monkeypatch.setenv("MESSAGING_PROVIDER", "")
    provider = get_messaging_provider()
    assert isinstance(provider, MessagingProvider)
    assert provider.name == "simulated"


def test_aliases_select_simulated(monkeypatch) -> None:
    for alias in ("local", "mock", "simulated"):
        monkeypatch.setenv("MESSAGING_PROVIDER", alias)
        assert get_messaging_provider().name == "simulated"


def test_unknown_provider_raises_domain_error(monkeypatch) -> None:
    monkeypatch.setenv("MESSAGING_PROVIDER", "whatsapp-cloud")
    with pytest.raises(DomainRuleError):
        get_messaging_provider()


def test_simulated_send_returns_receipt() -> None:
    receipt = SimulatedProvider().send(
        OutboundMessage(to="+56900000000", template_kind="reminder", title="Pago", body="Hola")
    )
    assert receipt.provider == "simulated"
    assert receipt.message_id


def test_explicit_provider_name_wins(monkeypatch) -> None:
    monkeypatch.setenv("MESSAGING_PROVIDER", "whatsapp-cloud")
    assert get_messaging_provider("simulated").name == "simulated"
