"""Adaptador simulado de mensajería (Fase 4, CF4-01).

No envía nada a ninguna red real: registra el mensaje en el log del proceso.
Es el canal por defecto mientras no haya credenciales de WhatsApp Cloud API.
"""

from __future__ import annotations

import logging
import uuid

from cuentafaro.messaging.base import OutboundMessage, SendReceipt

logger = logging.getLogger(__name__)


class SimulatedProvider:
    name = "simulated"

    def send(self, message: OutboundMessage) -> SendReceipt:
        logger.info(
            "[messaging:simulated] %s para %s: %s — %s",
            message.template_kind,
            message.to,
            message.title,
            message.body,
        )
        return SendReceipt(provider=self.name, message_id=str(uuid.uuid4()))
