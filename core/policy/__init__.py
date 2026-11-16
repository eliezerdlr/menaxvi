"""Fail-closed authorization and human-gate policy evaluation."""

from .engine import (
    ApprovalVerifier,
    AuthorizationArtifact,
    AuthorizationVerifier,
    DigestApprovalVerifier,
    DigestAuthorizationVerifier,
    ExecutionRequest,
    HumanApproval,
    PolicyDecision,
    PolicyEngine,
)

__all__ = [
    "ApprovalVerifier",
    "AuthorizationArtifact",
    "AuthorizationVerifier",
    "DigestApprovalVerifier",
    "DigestAuthorizationVerifier",
    "ExecutionRequest",
    "HumanApproval",
    "PolicyDecision",
    "PolicyEngine",
]
