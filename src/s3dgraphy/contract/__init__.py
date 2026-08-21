"""The adapter contract — one shape, two consumers.

:mod:`~s3dgraphy.contract.core` is the contract: a descriptor, a registry, an
invocation with four refusals, and a DTC-attributed delta as the result.
:mod:`~s3dgraphy.contract.connector` specialises it for connectors (Blender,
viewers, imports, database syncs); the field assistant's `ToolRegistry`
specialises it for tools. Neither owns it.
"""

from .core import (CONTRACT_NAMESPACE, Delta, Descriptor, Handler, REFUSALS,
                   Refusals, Registry, Result, Slot, invoke, stable_id)
from .connector import (CAPABILITIES, CAPABILITY_LAYER, CAPABILITY_LAYERS,
                        CONNECTOR_API_VERSION, ConnectorDescriptor,
                        ConnectorRegistry, HOSTS, TRANSPORTS, Versions,
                        VOLATILE_KEY, WRITING_CAPABILITIES, apply_delta, bake,
                        current_versions, document_view, guard_write, handshake,
                        validate_delta)

__all__ = [
    "CONTRACT_NAMESPACE", "Delta", "Descriptor", "Handler", "REFUSALS",
    "Refusals", "Registry", "Result", "Slot", "invoke", "stable_id",
    "CAPABILITIES", "CAPABILITY_LAYER", "CAPABILITY_LAYERS",
    "CONNECTOR_API_VERSION", "ConnectorDescriptor", "ConnectorRegistry",
    "HOSTS", "TRANSPORTS", "Versions", "WRITING_CAPABILITIES",
    "VOLATILE_KEY", "apply_delta", "bake", "current_versions",
    "document_view", "guard_write", "handshake", "validate_delta",
]
