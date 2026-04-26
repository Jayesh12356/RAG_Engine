
import re

import structlog
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

# ── Keyword sets for fast routing ──────────────────────────────────────
# IMPORTANT: matching is **word-boundary** based (see ``_match_count``) so
# that short keywords like "lan", "wan", "ca", "port" do not false-match
# inside common English words ("languages", "wanted", "scan", "report").
_CATEGORY_KEYWORDS = {
    "VPN":     ["vpn", "virtual private network", "tunneling", "tunnel", "ipsec",
                "openvpn", "wireguard", "pptp", "l2tp", "ikev2", "sstp",
                "remote access", "site-to-site", "encapsulation"],
    "SSL":     ["ssl", "tls", "certificate", "https", "handshake",
                "public key", "private key", "ca", "certificate authority"],
    "NETWORK": ["network", "tcp", "udp", "ip address", "subnet", "dns",
                "dhcp", "firewall", "router", "switch", "osi", "lan", "wan",
                "mac address", "gateway", "nat", "port"],
    "CLOUD":   ["cloud", "aws", "azure", "gcp", "iaas", "paas", "saas",
                "virtualization", "container", "docker", "kubernetes"],
    "LINUX":   ["linux", "ubuntu", "bash", "shell", "terminal", "chmod",
                "grep", "sudo", "kernel", "daemon"],
    "EMAIL":   ["email", "smtp", "imap", "pop3", "outlook", "mailbox",
                "spam", "phishing"],
}

_INTENT_KEYWORDS = {
    "troubleshoot": ["fix", "error", "issue", "problem", "not working",
                     "fail", "broken", "troubleshoot", "debug", "resolve"],
    "howto":        ["how to", "how do", "steps", "guide", "setup",
                     "configure", "install", "create", "design", "implement"],
    "info":         ["what is", "explain", "describe", "compare", "difference",
                     "types", "benefits", "limitations", "why", "when",
                     "which", "does", "is ", "can "],
}


def _match_keyword(keyword: str, text: str) -> bool:
    """Return True if ``keyword`` appears in ``text`` as a whole word/phrase.

    Multi-word phrases (containing whitespace or hyphen) match as substrings;
    single-word keywords use ``\\b`` word boundaries so "lan" does NOT match
    inside "languages" or "plan".
    """
    if " " in keyword or "-" in keyword:
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


class RouterResult(BaseModel):
    service_category: str
    intent: str
    key_terms: list[str]


class QueryRouter:
    def __init__(self, demo_mode: bool = False):
        self.demo_mode = demo_mode

    async def detect(self, question: str) -> RouterResult:
        lower_q = question.lower()

        category = "GENERAL"
        best_hits = 0
        matched_terms: list[str] = []
        for cat, keywords in _CATEGORY_KEYWORDS.items():
            hits = [kw for kw in keywords if _match_keyword(kw, lower_q)]
            if len(hits) > best_hits:
                best_hits = len(hits)
                category = cat
                matched_terms = hits

        intent = "info"
        for intent_name, keywords in _INTENT_KEYWORDS.items():
            if any(_match_keyword(kw, lower_q) for kw in keywords):
                intent = intent_name
                break

        result = RouterResult(
            service_category=category,
            intent=intent,
            key_terms=matched_terms[:5],
        )
        logger.info("router_detect_fast", result=result.model_dump())
        return result
