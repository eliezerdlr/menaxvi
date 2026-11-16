from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "docs" / "architecture" / "CUSTOMER-DASHBOARD.md"


class CustomerDashboardArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = DOCUMENT.read_text(encoding="utf-8")

    def test_defines_required_product_boundaries(self) -> None:
        for heading in (
            "## 1. Product boundary",
            "## 2. Component ownership",
            "## 3. Domain model",
            "## 4. API contract and ownership",
            "## 5. Authentication and authorization",
            "## 6. Persistence and consistency",
            "## 7. Approval, evidence, and artifact invariants",
            "## 8. Retry and rollback behavior",
            "## 9. Operational and packaging boundary",
            "## 10. Failure and recovery boundaries",
            "## 11. Observable release acceptance",
            "## 12. Explicit deferrals",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, self.text)

    def test_preserves_core_and_cli_ownership(self) -> None:
        self.assertIn("Python core remains the only owner", self.text)
        self.assertIn("The CLI remains the administration and recovery surface", self.text)
        self.assertIn("calls core functions in-process", self.text)
        self.assertIn("cannot reimplement digest, approval, retry, rollback, or evidence rules", self.text)

    def test_records_security_and_recovery_invariants(self) -> None:
        required_contracts = (
            "deny-by-default",
            "Cross-workspace resource IDs return `404`",
            "evidence outbox",
            "single-writer requirement",
            "Retries are available only for `failed` or `incomplete` attempts",
            "`automaticActionsPerformed: false`",
            "performs no external side effect",
        )
        for contract in required_contracts:
            with self.subTest(contract=contract):
                self.assertIn(contract, self.text)


if __name__ == "__main__":
    unittest.main()
