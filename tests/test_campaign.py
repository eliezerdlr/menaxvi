from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tooling"))

from menaxvi.campaign import CampaignError, generate_campaign, review_campaign


class CampaignGeneratorTests(unittest.TestCase):
    def test_generation_is_deterministic_and_budget_is_conserved(self) -> None:
        context = {
            "company": "North Texas Clean Co.",
            "audience": "busy homeowners in North Texas",
            "offer": "dependable residential cleaning",
            "brand": "local and practical",
            "objective": "local reach",
            "geography": "North Texas, United States",
            "channels": "meta-ads,google-search,email,organic-social",
            "language": "en-US",
            "budget": "900",
            "currency": "USD",
            "durationDays": "30",
            "constraints": "No unsupported claims.",
        }
        first = generate_campaign(context, "Quotes are reviewed.", "Documented quote-review policy.")
        second = generate_campaign(context, "Quotes are reviewed.", "Documented quote-review policy.")
        self.assertEqual(first, second)
        amounts = [float(plan["budget"]["total"]) for plan in first["channelPlans"].values()]
        self.assertAlmostEqual(sum(amounts), 900.0)
        self.assertEqual(review_campaign(first, "Quotes are reviewed.", "Documented policy.")["overall"], "pass")
        self.assertEqual(first["schemaVersion"], "menaxvi.campaign/v1")

    def test_selected_channels_only_are_generated(self) -> None:
        context = {
            "company": "Empresa Norte",
            "audience": "gestores de pequenas empresas",
            "offer": "consultoria operacional",
            "brand": "clara e profissional",
            "objective": "pedidos de proposta",
            "geography": "Porto, Portugal",
            "channels": "meta-ads,email",
            "language": "pt-PT",
            "budget": "500",
            "currency": "EUR",
            "durationDays": "21",
            "constraints": "Sem garantias de resultado.",
        }
        campaign = generate_campaign(context, "A proposta é revista.", "Processo interno documentado.")
        self.assertEqual(set(campaign["channelPlans"]), {"metaAds", "email"})
        self.assertEqual(campaign["language"], "pt-PT")

    def test_invalid_inputs_fail_closed(self) -> None:
        base = {
            "company": "Company", "audience": "Audience", "offer": "Offer", "brand": "Brand",
            "objective": "Reach", "geography": "Market", "channels": "email,meta-ads",
            "language": "en-US", "budget": "100", "currency": "USD", "durationDays": "30",
            "constraints": "No unsupported claims.",
        }
        cases = [
            ({"language": "en"}, "pt-PT or en-US"),
            ({"channels": "email"}, "at least two"),
            ({"budget": "NaN"}, "positive campaign budget"),
            ({"durationDays": "0"}, "between 1 and 365"),
            ({"currency": "XYZ"}, "supported currency"),
        ]
        for changed, message in cases:
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(CampaignError, message):
                    generate_campaign({**base, **changed}, "Claim", "Evidence")


if __name__ == "__main__":
    unittest.main()
