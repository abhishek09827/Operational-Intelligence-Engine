import re
import math
from typing import Any, Dict, List, Union

SECRET_PATTERNS = [
    # Connection string passwords e.g. postgres://user:pass@host:5432/db
    (re.compile(r'([a-zA-Z0-9+.\-]+:\/\/[^:\s]+:)([^@\s]+)(@[^/\s]+)'), r'\g<1>[REDACTED_PASSWORD]\g<3>'),
    # JWT tokens: eyJ...
    (re.compile(r'\beyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}(?:\.[a-zA-Z0-9_\-]{10,})?\b'), '[REDACTED_JWT_TOKEN]'),
    # Generic bearer tokens in headers / logs
    (re.compile(r'(?i)(bearer\s+|token\s+)[a-zA-Z0-9_\-\.]{16,}', re.IGNORECASE), r'\g<1>[REDACTED_TOKEN]'),
    # OpenAI & OpenRouter keys: sk-... or sk-or-v1-...
    (re.compile(r'sk-(?:or-v1-)?[a-zA-Z0-9_\-]{20,}', re.IGNORECASE), '[REDACTED_API_KEY]'),
    # AWS access key ID
    (re.compile(r'\b(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b'), '[REDACTED_AWS_KEY]'),
    # AWS Secret Access Key
    (re.compile(r'(?i)(aws_secret_access_key|aws_secret|aws_key)[\s:=]+([a-zA-Z0-9\/+=]{40})'), r'\g<1>=[REDACTED_AWS_SECRET]'),
    # GitHub Tokens: ghp_, gho_, ghu_, ghs_, ghr_
    (re.compile(r'\bgh[pousr]_[a-zA-Z0-9]{36,255}\b'), '[REDACTED_GITHUB_TOKEN]'),
    # Slack tokens: xox[baprs]-...
    (re.compile(r'\bxox[baprs]-[0-9a-zA-Z\-]{10,}\b'), '[REDACTED_SLACK_TOKEN]'),
    # Generic Private Key blocks
    (re.compile(r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(?:RSA\s+)?PRIVATE\s+KEY-----'), '[REDACTED_PRIVATE_KEY]'),
    # Key-value secret assignments in config/json (skips values already redacted)
    (re.compile(r'(?i)(password|passwd|secret|api_key|apikey|auth_token|access_token|private_key)\s*[:=]\s*["\x27]?([^"\x27\s,;\[]{4,})["\x27]?'), r'\g<1>=[REDACTED_SECRET]'),
    # Basic PII: IPv4 addresses
    (re.compile(r'\b(?!(?:127\.0\.0\.1|0\.0\.0\.0)\b)(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'), '[IP_REDACTED]'),
    # Email addresses
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL_REDACTED]'),
]

def shannon_entropy(data: str) -> float:
    """Calculate the Shannon entropy of a string."""
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    for x in set(data):
        p_x = float(data.count(x)) / length
        entropy += - p_x * math.log2(p_x)
    return entropy

class SecretSanitizer:
    """
    Deterministic Secret and PII Sanitizer for alerts, telemetry, and payloads.
    Redacts known patterns, API keys, credentials, IP addresses, emails,
    and high-entropy potential password/secret hex strings.
    """

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        if not text:
            return text

        sanitized = text
        for pattern, replacement in SECRET_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)

        # High entropy string check for isolated tokens >= 32 chars without scheme/url
        words = sanitized.split()
        for w in words:
            clean_w = w.strip('"\',;:()[]{}')
            if len(clean_w) >= 32 and not clean_w.startswith('[REDACTED') and not clean_w.startswith('[IP_'):
                if '://' not in clean_w and shannon_entropy(clean_w) >= 4.2:
                    sanitized = sanitized.replace(clean_w, '[HIGH_ENTROPY_SECRET_REDACTED]')

        return sanitized

    @classmethod
    def sanitize_data(cls, data: Any) -> Any:
        """Recursively scrub dictionary, list, string, or primitive datatypes."""
        if isinstance(data, str):
            return cls.sanitize_text(data)
        elif isinstance(data, dict):
            scrubbed_dict = {}
            for k, v in data.items():
                if any(sec in k.lower() for sec in ('password', 'secret', 'token', 'key', 'auth', 'cred')):
                    scrubbed_dict[k] = '[REDACTED_SECRET]'
                else:
                    scrubbed_dict[k] = cls.sanitize_data(v)
            return scrubbed_dict
        elif isinstance(data, list):
            return [cls.sanitize_data(item) for item in data]
        return data

sanitize_text = SecretSanitizer.sanitize_text
sanitize_data = SecretSanitizer.sanitize_data
