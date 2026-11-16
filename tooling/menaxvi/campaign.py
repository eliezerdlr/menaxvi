"""Deterministic, dependency-free multichannel campaign package generation."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

SUPPORTED_LANGUAGES = {"pt-PT", "en-US"}
SUPPORTED_CHANNELS = ("meta-ads", "google-search", "email", "organic-social")


class CampaignError(ValueError):
    """Customer-safe campaign input or contract error."""


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _channels(value: str) -> list[str]:
    aliases = {
        "meta": "meta-ads", "meta ads": "meta-ads", "facebook": "meta-ads",
        "google": "google-search", "google ads": "google-search", "search": "google-search",
        "email": "email", "e-mail": "email",
        "social": "organic-social", "organic social": "organic-social",
    }
    selected: list[str] = []
    for raw in value.replace(";", ",").split(","):
        item = raw.strip().casefold()
        channel = aliases.get(item, item)
        if channel in SUPPORTED_CHANNELS and channel not in selected:
            selected.append(channel)
        elif item and channel not in SUPPORTED_CHANNELS:
            raise CampaignError(f"Unsupported campaign channel: {raw.strip()}.")
    if len(selected) < 2:
        raise CampaignError("Choose at least two campaign channels.")
    return selected


def _budget(value: str) -> Decimal:
    try:
        amount = Decimal(value.strip())
    except (InvalidOperation, AttributeError) as error:
        raise CampaignError("Enter a valid positive campaign budget.") from error
    if not amount.is_finite() or amount <= 0:
        raise CampaignError("Enter a valid positive campaign budget.")
    return amount


def _duration(value: str) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError) as error:
        raise CampaignError("Enter a campaign duration between 1 and 365 days.") from error
    if not 1 <= days <= 365:
        raise CampaignError("Enter a campaign duration between 1 and 365 days.")
    return days


def _copy(context: Mapping[str, str]) -> dict[str, str]:
    company, audience, offer = context["company"], context["audience"], context["offer"]
    if context["language"] == "pt-PT":
        return {
            "benefit": f"A {company} ajuda {audience} a obter {offer} com um processo claro e verificável.",
            "angle": f"Menos esforço para {audience}; um caminho claro para {offer}.",
            "cta": "Pedir uma proposta personalizada",
            "primary": f"Procura {offer}? A {company} ajuda {audience} com um processo claro, adequado às necessidades de cada cliente. Peça uma proposta personalizada.",
            "headline": f"{offer} para {audience}",
            "description": f"Conheça a abordagem da {company} e confirme a disponibilidade na sua região.",
            "search1": f"{offer} para {audience}",
            "search2": f"Peça uma proposta à {company}",
            "search3": "Serviço adaptado às suas necessidades",
            "email1": f"Uma forma mais simples de obter {offer}",
            "email2": f"Como a {company} trabalha com {audience}",
            "email3": "Próximo passo: peça uma proposta personalizada",
            "post": f"A {company} ajuda {audience} a avançar para {offer}. Peça uma proposta personalizada e confirme os próximos passos.",
            "approval": "Rever afirmações, orçamento, segmentação, páginas de destino e autorização antes da ativação.",
        }
    return {
        "benefit": f"{company} helps {audience} obtain {offer} through a clear, reviewable process.",
        "angle": f"Less effort for {audience}; a clear path to {offer}.",
        "cta": "Request a personalized quote",
        "primary": f"Looking for {offer}? {company} helps {audience} through a clear process tailored to each customer. Request a personalized quote.",
        "headline": f"{offer} for {audience}",
        "description": f"See how {company} works and confirm availability in your area.",
        "search1": f"{offer} for {audience}",
        "search2": f"Request a quote from {company}",
        "search3": "Service tailored to your needs",
        "email1": f"A simpler way to obtain {offer}",
        "email2": f"How {company} works with {audience}",
        "email3": "Next step: request a personalized quote",
        "post": f"{company} helps {audience} move toward {offer}. Request a personalized quote and confirm the next steps.",
        "approval": "Review claims, budget, targeting, landing pages, and authorization before activation.",
    }


def _allocate(total: Decimal, selected: list[str]) -> dict[str, str]:
    weights = {"meta-ads": Decimal("0.40"), "google-search": Decimal("0.35"), "email": Decimal("0.10"), "organic-social": Decimal("0.15")}
    denominator = sum(weights[channel] for channel in selected)
    allocations: dict[str, str] = {}
    remaining = total
    for index, channel in enumerate(selected):
        amount = remaining if index == len(selected) - 1 else (total * weights[channel] / denominator).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        allocations[channel] = _money(amount)
        remaining -= amount
    return allocations


def generate_campaign(context: Mapping[str, str], claim: str, evidence: str) -> dict[str, Any]:
    language = context.get("language", "")
    if language not in SUPPORTED_LANGUAGES:
        raise CampaignError("Choose a supported output language: pt-PT or en-US.")
    selected = _channels(context.get("channels", ""))
    total = _budget(context.get("budget", ""))
    days = _duration(context.get("durationDays", ""))
    currency = context.get("currency", "").strip().upper()
    if currency not in {"EUR", "USD", "GBP", "BRL", "CAD"}:
        raise CampaignError("Choose a supported currency: EUR, USD, GBP, BRL, or CAD.")
    if not context.get("objective", "").strip() or not context.get("geography", "").strip():
        raise CampaignError("Campaign objective and geography are required.")
    if not claim or not evidence:
        raise CampaignError("A separated claim and supporting evidence are required.")

    text = _copy(context)
    allocations = _allocate(total, selected)
    plans: dict[str, Any] = {}
    common = {"geography": context["geography"], "audience": context["audience"], "objective": context["objective"]}

    if "meta-ads" in selected:
        plans["metaAds"] = {
            **common, "campaignName": f"{context['company']} | {context['objective']} | Meta",
            "budget": {"currency": currency, "total": allocations["meta-ads"], "durationDays": days},
            "performanceGoal": "maximize-reach" if "reach" in context["objective"].casefold() or "alcance" in context["objective"].casefold() else "maximize-results",
            "adSets": [{"name": f"{context['geography']} | broad local audience", "location": context["geography"], "audienceGuidance": context["audience"], "placements": "Advantage+ placements; reviewer must confirm current platform availability"}],
            "ads": [
                {"format": "single-image", "primaryText": text["primary"], "headline": text["headline"], "description": text["description"], "cta": text["cta"], "creativeDirection": "Use authorized, representative customer or service imagery; do not simulate results."},
                {"format": "short-video", "primaryText": text["primary"], "headline": text["headline"], "description": text["description"], "cta": text["cta"], "creativeDirection": "15-second sequence: customer problem, real process, supported benefit, explicit CTA."},
            ],
            "tracking": {"utmSource": "meta", "utmMedium": "paid-social", "utmCampaign": "menaxvi_multichannel_campaign"},
        }
    if "google-search" in selected:
        plans["googleSearch"] = {
            **common, "campaignName": f"{context['company']} | {context['objective']} | Search",
            "budget": {"currency": currency, "total": allocations["google-search"], "durationDays": days},
            "keywordThemes": [context["offer"], f"{context['offer']} {context['geography']}", f"{context['company']} {context['geography']}"],
            "negativeKeywordGuidance": ["jobs", "free download", "training"],
            "responsiveSearchAd": {"headlines": [text["search1"], text["search2"], text["search3"]], "descriptions": [text["description"], text["primary"]], "finalUrl": "REQUIRED_BEFORE_ACTIVATION", "cta": text["cta"]},
            "tracking": {"utmSource": "google", "utmMedium": "paid-search", "utmCampaign": "menaxvi_multichannel_campaign"},
        }
    if "email" in selected:
        plans["email"] = {
            **common, "budget": {"currency": currency, "total": allocations["email"], "durationDays": days},
            "audienceRequirement": "Send only to recipients with a documented lawful contact basis and unsubscribe mechanism.",
            "sequence": [
                {"day": 1, "subject": text["email1"], "body": text["primary"], "cta": text["cta"]},
                {"day": min(4, days), "subject": text["email2"], "body": f"{text['benefit']} {claim}", "cta": text["cta"]},
                {"day": min(8, days), "subject": text["email3"], "body": text["description"], "cta": text["cta"]},
            ],
        }
    if "organic-social" in selected:
        plans["organicSocial"] = {
            **common, "budget": {"currency": currency, "total": allocations["organic-social"], "durationDays": days},
            "calendar": [
                {"day": 1, "format": "image", "purpose": "introduce-benefit", "copy": text["post"], "cta": text["cta"]},
                {"day": min(5, days), "format": "short-video", "purpose": "show-process", "copy": text["primary"], "cta": text["cta"]},
                {"day": min(10, days), "format": "carousel", "purpose": "explain-evidence", "copy": f"{claim} Supporting evidence: {evidence}" if language == "en-US" else f"{claim} Evidência de suporte: {evidence}", "cta": text["cta"]},
            ],
        }

    package = {
        "schemaVersion": "menaxvi.campaign/v1",
        "language": language,
        "summary": {"company": context["company"], "objective": context["objective"], "geography": context["geography"], "durationDays": days, "budget": {"currency": currency, "total": _money(total)}, "selectedChannels": selected},
        "positioning": {"audience": context["audience"], "offer": context["offer"], "coreBenefit": text["benefit"], "campaignAngle": text["angle"], "brandDirection": context["brand"]},
        "channelPlans": plans,
        "landingPage": {
            "hero": {"headline": text["headline"], "supportingCopy": text["description"], "cta": text["cta"]},
            "sections": [
                {"purpose": "audience-and-problem", "copy": text["angle"]},
                {"purpose": "supported-benefit", "copy": text["benefit"]},
                {"purpose": "evidence", "copy": evidence},
                {"purpose": "next-step", "copy": text["cta"]},
            ],
            "requiredBeforeUse": ["Approved final URL", "Privacy notice", "Consent language where applicable", "Verified contact and service-area details"],
        },
        "measurement": {"primaryKpis": ["reach", "frequency", "qualified responses"], "secondaryKpis": ["landing-page visits", "form starts", "approved conversions"], "reviewCadence": "weekly", "warning": "Targets and forecasts require verified historical account data; none are invented by MENAXVI."},
        "launchChecklist": ["Confirm service area and availability", "Verify every claim against the evidence ledger", "Add approved landing-page URLs", "Confirm consent, privacy, and unsubscribe requirements", "Review current platform policy and UI options", "Record final human approval before activation"],
        "assumptions": ["No external market, competitor, keyword-volume, or platform-account data was queried.", "Budget allocations are planning defaults and require human review.", "MENAXVI does not publish, spend funds, or modify ad accounts."],
        "constraints": context["constraints"],
        "approvalInstruction": text["approval"],
    }
    return package


def review_campaign(package: Mapping[str, Any], claim: str, evidence: str) -> dict[str, str]:
    summary = package.get("summary", {})
    channels = summary.get("selectedChannels", [])
    plans = package.get("channelPlans", {})
    plan_keys = {"meta-ads": "metaAds", "google-search": "googleSearch", "email": "email", "organic-social": "organicSocial"}
    checks = {
        "audience": bool(package.get("positioning", {}).get("audience")),
        "objective": bool(summary.get("objective")),
        "language": package.get("language") in SUPPORTED_LANGUAGES,
        "evidence": bool(claim and evidence),
        "budget": bool(summary.get("budget", {}).get("total")),
        "channels": len(channels) >= 2 and all(plan_keys[channel] in plans for channel in channels),
        "safety": len(package.get("assumptions", [])) >= 3 and len(package.get("launchChecklist", [])) >= 6 and bool(package.get("landingPage", {}).get("requiredBeforeUse")),
    }
    review = {key: "pass" if passed else "fail" for key, passed in checks.items()}
    review["overall"] = "pass" if all(checks.values()) else "fail"
    return review
