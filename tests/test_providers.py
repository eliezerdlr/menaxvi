from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tooling"))

from menaxvi.providers import (
    ProviderError,
    ProviderRegistry,
    ProviderRequest,
    ProviderResult,
)


class StubProvider:
    provider_id = "stub"
    capabilities = frozenset({"structured-output"})

    def execute(self, request: ProviderRequest) -> ProviderResult:
        return ProviderResult(
            provider_id=self.provider_id,
            output={"operation": request.operation, "inputs": dict(request.inputs)},
            evidence={"adapter": "stub", "networkUsed": False},
        )


class WrongIdentityProvider(StubProvider):
    provider_id = "wrong-identity"

    def execute(self, request: ProviderRequest) -> ProviderResult:
        return ProviderResult(provider_id="other", output={}, evidence={})


class ProviderContractTests(unittest.TestCase):
    def test_executes_explicit_provider_with_normalized_result(self) -> None:
        registry = ProviderRegistry()
        registry.register(StubProvider())
        request = ProviderRequest(
            operation="render-plan",
            inputs={"workflow": "workflow.example@1.0.0"},
            required_capabilities=frozenset({"structured-output"}),
        )

        result = registry.execute("stub", request)

        self.assertEqual(result.provider_id, "stub")
        self.assertEqual(result.output["operation"], "render-plan")
        self.assertFalse(result.evidence["networkUsed"])

    def test_rejects_unknown_provider_and_missing_capability(self) -> None:
        registry = ProviderRegistry()
        registry.register(StubProvider())

        with self.assertRaisesRegex(ProviderError, "provider is not registered"):
            registry.execute("claude", ProviderRequest("run", {}))
        with self.assertRaisesRegex(ProviderError, "lacks required capabilities: tool-use"):
            registry.execute(
                "stub",
                ProviderRequest("run", {}, frozenset({"tool-use"})),
            )

    def test_rejects_duplicate_registration_and_identity_mismatch(self) -> None:
        registry = ProviderRegistry()
        registry.register(StubProvider())
        with self.assertRaisesRegex(ProviderError, "already registered"):
            registry.register(StubProvider())

        registry.register(WrongIdentityProvider())
        with self.assertRaisesRegex(ProviderError, "identity mismatch"):
            registry.execute("wrong-identity", ProviderRequest("run", {}))

    def test_rejects_empty_operation(self) -> None:
        with self.assertRaisesRegex(ValueError, "operation must be a non-empty string"):
            ProviderRequest(" ", {})


if __name__ == "__main__":
    unittest.main()
