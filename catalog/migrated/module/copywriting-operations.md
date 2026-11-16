# Copywriting Operations Capability Bundle

This clean-room bundle is the canonical many-to-one target for the legacy copy domains.

```json
{
  "capabilityDomains": [
    {
      "id": "headline",
      "ownerRoleId": "audience-awareness-strategist",
      "supportRoleIds": [
        "long-form-direct-response-copywriter"
      ]
    },
    {
      "id": "sales-letter",
      "ownerRoleId": "long-form-direct-response-copywriter",
      "supportRoleIds": [
        "sales-angle-copywriter"
      ]
    },
    {
      "id": "email-sequence",
      "ownerRoleId": "lifecycle-email-storyteller",
      "supportRoleIds": [
        "daily-email-engagement-strategist"
      ]
    },
    {
      "id": "vsl",
      "ownerRoleId": "systematic-vsl-copywriter",
      "supportRoleIds": [
        "conversational-vsl-copywriter"
      ]
    },
    {
      "id": "webinar-script",
      "ownerRoleId": "funnel-webinar-copy-strategist",
      "supportRoleIds": [
        "cold-traffic-funnel-strategist"
      ]
    },
    {
      "id": "offer-creation",
      "ownerRoleId": "direct-response-marketing-strategist",
      "supportRoleIds": [
        "conversion-flow-copywriter"
      ]
    },
    {
      "id": "funnel-copy",
      "ownerRoleId": "funnel-webinar-copy-strategist",
      "supportRoleIds": [
        "launch-copy-strategist"
      ]
    },
    {
      "id": "big-idea",
      "ownerRoleId": "campaign-mechanism-strategist",
      "supportRoleIds": [
        "audience-awareness-strategist"
      ]
    },
    {
      "id": "bullet-points",
      "ownerRoleId": "proof-fascination-copy-specialist",
      "supportRoleIds": [
        "financial-health-copy-specialist"
      ]
    },
    {
      "id": "daily-emails",
      "ownerRoleId": "daily-email-engagement-strategist",
      "supportRoleIds": [
        "personal-brand-content-strategist"
      ]
    },
    {
      "id": "classic-mail",
      "ownerRoleId": "empathy-first-direct-mail-copywriter",
      "supportRoleIds": [
        "direct-mail-format-innovator"
      ]
    },
    {
      "id": "financial-health-copy",
      "ownerRoleId": "financial-health-copy-specialist",
      "supportRoleIds": [
        "control-beating-copy-specialist"
      ]
    },
    {
      "id": "brand-copy",
      "ownerRoleId": "brand-copy-research-strategist",
      "supportRoleIds": [
        "campaign-idea-development-strategist"
      ]
    },
    {
      "id": "ad-copy",
      "ownerRoleId": "direct-response-marketing-strategist",
      "supportRoleIds": [
        "launch-copy-strategist"
      ]
    },
    {
      "id": "launch-copy",
      "ownerRoleId": "launch-copy-strategist",
      "supportRoleIds": [
        "funnel-webinar-copy-strategist"
      ]
    },
    {
      "id": "personal-brand-copy",
      "ownerRoleId": "personal-brand-content-strategist",
      "supportRoleIds": [
        "belief-transformation-email-strategist"
      ]
    },
    {
      "id": "copy-review",
      "ownerRoleId": "copy-orchestration-lead",
      "supportRoleIds": [
        "audience-awareness-strategist"
      ]
    },
    {
      "id": "usp-development",
      "ownerRoleId": "usp-positioning-strategist",
      "supportRoleIds": [
        "headline-testing-specialist"
      ]
    },
    {
      "id": "offer-architecture",
      "ownerRoleId": "offer-architecture-strategist",
      "supportRoleIds": [
        "direct-response-marketing-strategist"
      ]
    },
    {
      "id": "saas-conversion-copy",
      "ownerRoleId": "conversion-research-copywriter",
      "supportRoleIds": [
        "advertising-testing-strategist"
      ]
    },
    {
      "id": "cold-traffic-funnels",
      "ownerRoleId": "cold-traffic-funnel-strategist",
      "supportRoleIds": [
        "launch-copy-strategist"
      ]
    },
    {
      "id": "belief-based-sales-letter",
      "ownerRoleId": "belief-based-sales-letter-strategist",
      "supportRoleIds": [
        "campaign-mechanism-strategist"
      ]
    },
    {
      "id": "persuasion-psychology",
      "ownerRoleId": "ethical-influence-reviewer",
      "supportRoleIds": [
        "emotional-persuasion-reviewer"
      ]
    },
    {
      "id": "objection-handling",
      "ownerRoleId": "objection-negotiation-strategist",
      "supportRoleIds": [
        "emotional-persuasion-reviewer"
      ]
    },
    {
      "id": "pitch-presentation",
      "ownerRoleId": "pitch-framing-strategist",
      "supportRoleIds": [
        "funnel-webinar-copy-strategist"
      ]
    },
    {
      "id": "scientific-testing",
      "ownerRoleId": "headline-testing-specialist",
      "supportRoleIds": [
        "advertising-testing-strategist"
      ]
    },
    {
      "id": "webinar-extended",
      "ownerRoleId": "funnel-webinar-copy-strategist",
      "supportRoleIds": [
        "cold-traffic-funnel-strategist"
      ]
    }
  ],
  "executionContract": {
    "failureMode": "Stop and request missing evidence or authorized review; do not invent facts.",
    "qualityGates": [
      "brief-completeness",
      "claim-evidence",
      "identity-and-endorsement",
      "channel-compliance",
      "human-publication-approval"
    ],
    "requiredInputs": [
      "brief",
      "audience",
      "offer",
      "channel",
      "evidence"
    ],
    "requiredOutputs": [
      "draft",
      "claim-ledger",
      "review-findings",
      "approval-decision"
    ]
  },
  "id": "copywriting-operations",
  "operations": {
    "checklists": [
      "output-quality.md"
    ],
    "knowledge": [
      "books-resources.yaml",
      "champion-swipe-files.yaml",
      "copy-frameworks.yaml",
      "persuasion-psychology.yaml",
      "routing-catalog.yaml"
    ],
    "tasks": [
      "analyze-copy.md",
      "create-funnel-copy.md",
      "create-offer.md",
      "critique-copy.md",
      "diagnose.md",
      "review.md",
      "write-ad-copy.md",
      "write-bullets.md",
      "write-email-sequence.md",
      "write-headline.md",
      "write-landing-page.md",
      "write-pitch-deck.md",
      "write-sales-letter.md",
      "write-vsl-script.md",
      "write-webinar-script.md"
    ],
    "workflows": [
      "wf-copy-review-cycle.yaml",
      "wf-full-copy-project.yaml",
      "wf-launch-sequence.yaml",
      "wf-vsl-production.yaml"
    ]
  },
  "roles": [
    {
      "capabilities": [
        "request triage",
        "specialist routing",
        "multi-role coordination",
        "quality review"
      ],
      "id": "copy-orchestration-lead",
      "responsibility": "Triage requests, assign specialists, coordinate reviews, and enforce delivery quality.",
      "title": "Copy Orchestration Lead"
    },
    {
      "capabilities": [
        "offer design",
        "value modeling",
        "pricing framing",
        "risk reversal"
      ],
      "id": "offer-architecture-strategist",
      "responsibility": "Design value propositions, offer stacks, guarantees, pricing logic, and risk reversal.",
      "title": "Offer Architecture Strategist"
    },
    {
      "capabilities": [
        "nurture sequences",
        "story-based email",
        "open-loop sequencing",
        "relationship building"
      ],
      "id": "lifecycle-email-storyteller",
      "responsibility": "Design narrative email sequences that build trust and move readers through a lifecycle.",
      "title": "Lifecycle Email Storyteller"
    },
    {
      "capabilities": [
        "daily email",
        "newsletter engagement",
        "voice consistency",
        "audience retention"
      ],
      "id": "daily-email-engagement-strategist",
      "responsibility": "Create frequent personality-led email content that sustains attention and engagement.",
      "title": "Daily Email Engagement Strategist"
    },
    {
      "capabilities": [
        "emotional resonance",
        "identity alignment",
        "motivation analysis",
        "persuasion review"
      ],
      "id": "emotional-persuasion-reviewer",
      "responsibility": "Review copy for ethical emotional resonance, identity alignment, fears, and motivations.",
      "title": "Emotional Persuasion Reviewer"
    },
    {
      "capabilities": [
        "objection handling",
        "conversational framing",
        "empathetic language",
        "sales dialogue"
      ],
      "id": "objection-negotiation-strategist",
      "responsibility": "Address resistance with empathetic language, objection handling, and conversational negotiation.",
      "title": "Objection and Negotiation Strategist"
    },
    {
      "capabilities": [
        "advertising experiments",
        "claim testing",
        "control design",
        "measurement planning"
      ],
      "id": "advertising-testing-strategist",
      "responsibility": "Plan measurable advertising hypotheses, reason-based claims, controls, and experiments.",
      "title": "Advertising Testing Strategist"
    },
    {
      "capabilities": [
        "regulated-market copy",
        "evidence framing",
        "long-form promotion",
        "risk-aware claims"
      ],
      "id": "financial-health-copy-specialist",
      "responsibility": "Develop evidence-aware long-form copy for high-scrutiny financial and health markets.",
      "title": "Financial and Health Copy Specialist"
    },
    {
      "capabilities": [
        "direct response",
        "campaign economics",
        "lead generation",
        "response mechanisms"
      ],
      "id": "direct-response-marketing-strategist",
      "responsibility": "Connect offers, response mechanisms, campaigns, and measurable commercial outcomes.",
      "title": "Direct Response Marketing Strategist"
    },
    {
      "capabilities": [
        "authority content",
        "short-form copy",
        "newsletter systems",
        "creator positioning"
      ],
      "id": "personal-brand-content-strategist",
      "responsibility": "Build concise authority content and repeatable publishing systems for expert-led brands.",
      "title": "Personal Brand Content Strategist"
    },
    {
      "capabilities": [
        "campaign ideation",
        "angle generation",
        "fascination development",
        "concept evaluation"
      ],
      "id": "campaign-idea-development-strategist",
      "responsibility": "Generate and evaluate campaign concepts, central ideas, angles, and supporting fascinations.",
      "title": "Campaign Idea Development Strategist"
    },
    {
      "capabilities": [
        "brand research",
        "premium positioning",
        "brand voice",
        "research-led copy"
      ],
      "id": "brand-copy-research-strategist",
      "responsibility": "Translate research and positioning into credible premium and institutional brand copy.",
      "title": "Brand Copy Research Strategist"
    },
    {
      "capabilities": [
        "awareness analysis",
        "market sophistication",
        "headline strategy",
        "message alignment"
      ],
      "id": "audience-awareness-strategist",
      "responsibility": "Align messages and headlines to audience awareness and market sophistication.",
      "title": "Audience Awareness Strategist"
    },
    {
      "capabilities": [
        "belief change",
        "sales argument",
        "origin narrative",
        "mechanism explanation"
      ],
      "id": "belief-based-sales-letter-strategist",
      "responsibility": "Structure sales arguments around a central belief, mechanism, and narrative progression.",
      "title": "Belief-Based Sales Letter Strategist"
    },
    {
      "capabilities": [
        "launch sequencing",
        "pre-launch content",
        "campaign timing",
        "close messaging"
      ],
      "id": "launch-copy-strategist",
      "responsibility": "Coordinate pre-launch, launch, and close messaging across campaign stages.",
      "title": "Launch Copy Strategist"
    },
    {
      "capabilities": [
        "proof architecture",
        "fascination bullets",
        "credibility",
        "competitive advantage"
      ],
      "id": "proof-fascination-copy-specialist",
      "responsibility": "Strengthen credibility and curiosity through proof elements, bullets, and competitive advantages.",
      "title": "Proof and Fascination Copy Specialist"
    },
    {
      "capabilities": [
        "sales letters",
        "direct mail",
        "story-led selling",
        "long-form structure"
      ],
      "id": "long-form-direct-response-copywriter",
      "responsibility": "Write emotionally engaging long-form sales letters and direct-response narratives.",
      "title": "Long-Form Direct Response Copywriter"
    },
    {
      "capabilities": [
        "direct-mail formats",
        "format experimentation",
        "reader attention",
        "long-form pacing"
      ],
      "id": "direct-mail-format-innovator",
      "responsibility": "Adapt long-form direct mail into distinctive formats that sustain reader attention.",
      "title": "Direct-Mail Format Innovator"
    },
    {
      "capabilities": [
        "voice-of-customer research",
        "SaaS copy",
        "conversion hypotheses",
        "product messaging"
      ],
      "id": "conversion-research-copywriter",
      "responsibility": "Use customer language and behavioral evidence to improve SaaS and product conversion copy.",
      "title": "Conversion Research Copywriter"
    },
    {
      "capabilities": [
        "conversion flow",
        "landing pages",
        "print advertising",
        "curiosity transitions"
      ],
      "id": "conversion-flow-copywriter",
      "responsibility": "Create sequential copy that moves readers through ads, pages, offers, and checkout flows.",
      "title": "Conversion Flow Copywriter"
    },
    {
      "capabilities": [
        "headline variants",
        "split testing",
        "benefit framing",
        "response analysis"
      ],
      "id": "headline-testing-specialist",
      "responsibility": "Develop headline variants and test plans based on clear reader benefits and measurable response.",
      "title": "Headline Testing Specialist"
    },
    {
      "capabilities": [
        "sales angles",
        "closing copy",
        "entertaining persuasion",
        "argument simplification"
      ],
      "id": "sales-angle-copywriter",
      "responsibility": "Find persuasive selling angles and turn them into direct, entertaining sales arguments.",
      "title": "Sales Angle Copywriter"
    },
    {
      "capabilities": [
        "video sales letters",
        "conversational scripts",
        "mechanism framing",
        "call-to-action pacing"
      ],
      "id": "conversational-vsl-copywriter",
      "responsibility": "Write conversational video sales letters with clear mechanisms and paced calls to action.",
      "title": "Conversational VSL Copywriter"
    },
    {
      "capabilities": [
        "pitch decks",
        "presentation framing",
        "status dynamics",
        "decision narratives"
      ],
      "id": "pitch-framing-strategist",
      "responsibility": "Structure high-stakes presentations and pitch narratives around status, novelty, and decision flow.",
      "title": "Pitch Framing Strategist"
    },
    {
      "capabilities": [
        "control analysis",
        "lead development",
        "curiosity bullets",
        "competitive iteration"
      ],
      "id": "control-beating-copy-specialist",
      "responsibility": "Challenge existing controls through deeper research, stronger leads, and high-curiosity bullets.",
      "title": "Control-Beating Copy Specialist"
    },
    {
      "capabilities": [
        "influence review",
        "social proof",
        "scarcity review",
        "ethical persuasion"
      ],
      "id": "ethical-influence-reviewer",
      "responsibility": "Audit copy for transparent, proportional, and ethically applied influence mechanisms.",
      "title": "Ethical Influence Reviewer"
    },
    {
      "capabilities": [
        "empathetic openings",
        "reader conversation",
        "vivid imagery",
        "follow-up letters"
      ],
      "id": "empathy-first-direct-mail-copywriter",
      "responsibility": "Enter the audience conversation with empathetic openings, vivid imagery, and personal letter flow.",
      "title": "Empathy-First Direct-Mail Copywriter"
    },
    {
      "capabilities": [
        "unique selling proposition",
        "positioning",
        "message simplification",
        "differentiation"
      ],
      "id": "usp-positioning-strategist",
      "responsibility": "Reduce complex offers to a differentiated, repeatable, and defensible positioning claim.",
      "title": "USP and Positioning Strategist"
    },
    {
      "capabilities": [
        "funnel copy",
        "webinar scripts",
        "customer journey",
        "offer presentation"
      ],
      "id": "funnel-webinar-copy-strategist",
      "responsibility": "Design funnel journeys and webinar narratives from initial hook through offer and close.",
      "title": "Funnel and Webinar Copy Strategist"
    },
    {
      "capabilities": [
        "launch email",
        "belief sequencing",
        "decision coaching",
        "ethical closing"
      ],
      "id": "belief-transformation-email-strategist",
      "responsibility": "Use email sequences to coach readers from current assumptions toward informed decisions.",
      "title": "Belief Transformation Email Strategist"
    },
    {
      "capabilities": [
        "cold traffic",
        "lead magnets",
        "audience warming",
        "full-funnel messaging"
      ],
      "id": "cold-traffic-funnel-strategist",
      "responsibility": "Warm unfamiliar audiences through lead magnets, staged education, and full-funnel copy.",
      "title": "Cold-Traffic Funnel Strategist"
    },
    {
      "capabilities": [
        "VSL production",
        "research synthesis",
        "mechanism development",
        "repeatable workflow"
      ],
      "id": "systematic-vsl-copywriter",
      "responsibility": "Produce research-led video sales letters through a repeatable mechanism-first process.",
      "title": "Systematic VSL Copywriter"
    },
    {
      "capabilities": [
        "big campaign idea",
        "unique mechanism",
        "campaign architecture",
        "cross-channel coherence"
      ],
      "id": "campaign-mechanism-strategist",
      "responsibility": "Develop campaign-level ideas and unique mechanisms that unify assets across channels.",
      "title": "Campaign Mechanism Strategist"
    }
  ],
  "safety": {
    "approval": "Require human approval before publication or paid distribution.",
    "claims": "Use supplied evidence for factual claims and identify unsupported claims.",
    "identity": "Do not imitate, impersonate, or claim endorsement by a named person.",
    "regulatedContent": "Escalate financial, health, legal, and other regulated claims for specialist review."
  },
  "schema": "menaxvi.copywriting-operations/v1",
  "status": "active",
  "summary": "A consolidated, professional copywriting capability package covering request routing, research, drafting, review, campaign production, and evidence-aware approval.",
  "title": "Copywriting Operations",
  "version": "1.0.0"
}
```
