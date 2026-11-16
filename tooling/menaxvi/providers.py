"""Provider-neutral contracts for optional MENAXVI runtime integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable


class ProviderError(RuntimeError):
    """Raised when a provider cannot satisfy a governed execution request."""


@dataclass(frozen=True)
class ProviderRequest:
    """A portable request passed to an explicitly selected provider adapter."""

    operation: str
    inputs: Mapping[str, Any]
    required_capabilities: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.operation.strip():
            raise ValueError("provider operation must be a non-empty string")
        if any(not capability.strip() for capability in self.required_capabilities):
            raise ValueError("required provider capabilities must be non-empty strings")


@dataclass(frozen=True)
class ProviderResult:
    """The normalized result returned by every provider adapter."""

    provider_id: str
    output: Mapping[str, Any]
    evidence: Mapping[str, Any]


@runtime_checkable
class ProviderAdapter(Protocol):
    """Minimal contract implemented by optional model or orchestration providers."""

    @property
    def provider_id(self) -> str: ...

    @property
    def capabilities(self) -> frozenset[str]: ...

    def execute(self, request: ProviderRequest) -> ProviderResult: ...


class ProviderRegistry:
    """Explicit provider registry with fail-closed capability negotiation."""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderAdapter] = {}

    def register(self, provider: ProviderAdapter) -> None:
        provider_id = provider.provider_id.strip()
        if not provider_id:
            raise ProviderError("provider id must be a non-empty string")
        if provider_id in self._providers:
            raise ProviderError(f"provider is already registered: {provider_id}")
        self._providers[provider_id] = provider

    def execute(self, provider_id: str, request: ProviderRequest) -> ProviderResult:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise ProviderError(f"provider is not registered: {provider_id}")
        missing = request.required_capabilities - provider.capabilities
        if missing:
            raise ProviderError(
                f"provider {provider_id} lacks required capabilities: {', '.join(sorted(missing))}"
            )
        result = provider.execute(request)
        if result.provider_id != provider_id:
            raise ProviderError(
                f"provider result identity mismatch: expected {provider_id}, got {result.provider_id}"
            )
        return result
