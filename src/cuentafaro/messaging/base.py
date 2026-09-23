"""Contrato neutral para proveedores de mensajería (Fase 4, CF4-01).

El dominio y los routers hablan con esta interfaz. Cada canal (simulado hoy,
WhatsApp Cloud API oficial mañana) implementa el mismo contrato detrás de un
adaptador y se registra por configuración. El dominio nunca importa SDKs
externos de mensajería (ADR 0001).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class OutboundMessage:
    """Mensaje/plantilla que el dominio quiere entregar a una persona."""

    to: str
    template_kind: str
    title: str
    body: str
    metadata: dict = field(default_factory=dict)


@dataclass
class SendReceipt:
    provider: str
    message_id: str = ""


@runtime_checkable
class MessagingProvider(Protocol):
    name: str

    def send(self, message: OutboundMessage) -> SendReceipt: ...
