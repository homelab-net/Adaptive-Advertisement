"""
test_no_hardcoded_values.py — Golden-image hygiene gate

Verifies that no device-specific, credential, or secret values are hardcoded
in the source tree in ways that would prevent safe flashing the same image to
multiple devices.

DESIGN PRINCIPLES
-----------------
* Template files (*.template, *.example) are EXCLUDED — they are supposed to
  contain placeholder tokens by design.
* Test fixtures are excluded from the strictest rules (device paths, IPs) but
  are still checked for private key material and placeholder leaks.
* The accepted pattern for configurable values is os.environ.get("VAR", default).
  Defaults behind that call are ALLOWED even if they contain localhost addresses
  or port numbers — they are overridable at deploy time.
* Production config Python source (services/**/config.py) must use env-var
  lookup for all host/port/URL/path values.

FAILURE MODES CAUGHT
--------------------
1. <PLACEHOLDER> tokens accidentally copied from a template into a real config.
2. PEM / SSH private key headers committed to source.
3. WireGuard private key patterns (44-char base64) committed to source.
4. Non-loopback, non-container IP addresses hardcoded in production Python
   (not overridable via env vars).
5. PostgreSQL DSN with embedded username:password that bypasses os.environ.get().
6. Any .env file containing credential assignments committed to the repo.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterator

import pytest

# ---------------------------------------------------------------------------
# Repository root
# ---------------------------------------------------------------------------
_REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# File selection helpers
# ---------------------------------------------------------------------------

def _iter_files(*globs: str, exclude_dirs: tuple[str, ...] = ()) -> Iterator[Path]:
    """Yield all files matching any of the given glob patterns, skipping
    excluded directory name segments and __pycache__ trees."""
    seen: set[Path] = set()
    for pattern in globs:
        for p in _REPO.glob(pattern):
            if not p.is_file():
                continue
            # Skip __pycache__ and .git
            parts = p.parts
            if any(seg in ("__pycache__", ".git") for seg in parts):
                continue
            if exclude_dirs and any(seg in exclude_dirs for seg in parts):
                continue
            if p not in seen:
                seen.add(p)
                yield p


def _is_template(path: Path) -> bool:
    """Return True if the file is a placeholder template by convention."""
    return path.suffix in (".template", ".example") or path.name.endswith(".template")


def _uses_pydantic_settings(path: Path) -> bool:
    """Return True if the file imports from pydantic_settings (BaseSettings).
    Fields in a BaseSettings subclass are automatically overridable via
    environment variables — they do not need os.environ.get() wrappers."""
    try:
        text = path.read_text(errors="replace")
        return "pydantic_settings" in text and "BaseSettings" in text
    except OSError:
        return False


def _production_python() -> list[Path]:
    """Python source files under services/ that are NOT test files."""
    files = []
    for p in _iter_files("services/**/*.py"):
        # Exclude test directories
        if "tests" in p.parts or p.name.startswith("test_") or p.name == "conftest.py":
            continue
        files.append(p)
    return files


def _config_python() -> list[Path]:
    """Python config module files across all services."""
    return [p for p in _production_python() if "config" in p.name]


def _all_python() -> list[Path]:
    """All Python files in the repo (services + tests)."""
    return list(_iter_files("services/**/*.py", "tests/**/*.py"))


def _all_source() -> list[Path]:
    """Non-template, non-binary source files across the whole repo."""
    files = []
    for p in _iter_files(
        "services/**/*.py",
        "tests/**/*.py",
        "provisioning/**/*.sh",
        "provisioning/**/*.conf",
        "provisioning/**/*.yml",
        ".github/**/*.yml",
        "*.yml",
        "*.yaml",
        "*.toml",
        "contracts/**/*.json",
    ):
        if _is_template(p):
            continue
        files.append(p)
    return files


# ---------------------------------------------------------------------------
# 1. No <PLACEHOLDER> tokens outside template files
# ---------------------------------------------------------------------------

# The generic word PLACEHOLDER is used in documentation and error messages to
# describe the concept — it is NOT an unfilled template token itself.
_PLACEHOLDER_RE = re.compile(r"<(?!PLACEHOLDER>)[A-Z][A-Z0-9_]{2,}>")

class TestNoPlaceholderTokens:
    """<PLACEHOLDER> tokens must only appear in *.template / *.example files."""

    def test_no_placeholder_tokens_in_python_source(self):
        violations: list[str] = []
        # Exclude this test file itself — it documents the <PLACEHOLDER> pattern
        _self = Path(__file__).resolve()
        for path in _all_python():
            if path == _self:
                continue
            text = path.read_text(errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                # Skip comment-only lines describing placeholder syntax
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                matches = _PLACEHOLDER_RE.findall(line)
                if matches:
                    rel = path.relative_to(_REPO)
                    violations.append(f"{rel}:{lineno} — {matches}")
        assert not violations, (
            "Placeholder tokens found in Python source (should only exist in *.template files):\n"
            + "\n".join(violations)
        )

    def test_no_placeholder_tokens_in_shell_scripts(self):
        violations: list[str] = []
        for path in _iter_files("provisioning/**/*.sh"):
            text = path.read_text(errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                # Skip lines where <> is part of a grep/regex pattern string
                # (e.g. the validation check `grep -qE '<[A-Z_]+>'`)
                if re.search(r"""grep\s+.*['"<]""", line):
                    continue
                matches = _PLACEHOLDER_RE.findall(line)
                if matches:
                    rel = path.relative_to(_REPO)
                    violations.append(f"{rel}:{lineno} — {matches}")
        assert not violations, (
            "Placeholder tokens found in shell scripts:\n" + "\n".join(violations)
        )

    def test_no_placeholder_tokens_in_yaml_configs(self):
        violations: list[str] = []
        for path in _iter_files(".github/**/*.yml", "*.yml", "*.yaml"):
            if _is_template(path):
                continue
            text = path.read_text(errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                matches = _PLACEHOLDER_RE.findall(line)
                if matches:
                    rel = path.relative_to(_REPO)
                    violations.append(f"{rel}:{lineno} — {matches}")
        assert not violations, (
            "Placeholder tokens found in YAML files:\n" + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# 2. No private key material in source
# ---------------------------------------------------------------------------

# PEM headers for any private key type
_PEM_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN\s+(?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
)

# WireGuard private keys are 44-character base64 strings (256-bit key, base64url or standard)
# They appear standalone (not as part of a longer base64 blob).
# Pattern: word boundary, 43 base64 chars + optional padding, word boundary.
_WG_PRIVATE_KEY_RE = re.compile(
    r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{43}=(?![A-Za-z0-9+/=])"
)

# Known safe 44-char base64-ish strings that are NOT keys (schema version strings etc.)
_WG_KEY_ALLOWLIST: frozenset[str] = frozenset()


class TestNoPrivateKeyMaterial:
    """No PEM private keys or WireGuard private keys should be committed."""

    def test_no_pem_private_keys_in_python(self):
        violations: list[str] = []
        for path in _all_python():
            text = path.read_text(errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                if _PEM_PRIVATE_KEY_RE.search(line):
                    rel = path.relative_to(_REPO)
                    violations.append(f"{rel}:{lineno}")
        assert not violations, (
            "PEM private key headers found in Python source:\n" + "\n".join(violations)
        )

    def test_no_pem_private_keys_in_shell(self):
        violations: list[str] = []
        for path in _iter_files("provisioning/**/*.sh"):
            text = path.read_text(errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                if _PEM_PRIVATE_KEY_RE.search(line):
                    rel = path.relative_to(_REPO)
                    violations.append(f"{rel}:{lineno}")
        assert not violations, (
            "PEM private key headers found in shell scripts:\n" + "\n".join(violations)
        )

    def test_no_wireguard_keys_in_python_source(self):
        """Catch WireGuard private keys (44-char base64) in Python source.

        Only fires on non-test production source to avoid flagging test
        vectors that use dummy key-shaped strings.
        """
        violations: list[str] = []
        for path in _production_python():
            text = path.read_text(errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                # Skip comment and docstring lines
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                for match in _WG_PRIVATE_KEY_RE.finditer(line):
                    if match.group() not in _WG_KEY_ALLOWLIST:
                        rel = path.relative_to(_REPO)
                        violations.append(f"{rel}:{lineno} — key-shaped value found")
        assert not violations, (
            "WireGuard key-shaped base64 values in production Python source:\n"
            + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# 3. No non-loopback IPs hardcoded in production Python (outside env defaults)
# ---------------------------------------------------------------------------

# Regex to find IPv4 literals in Python string literals
_IPV4_RE = re.compile(r"\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b")

# Acceptable IP literals in production source (loopback, unspecified, broadcast)
_SAFE_IP_PREFIXES = ("127.", "0.0.0", "255.255.255", "169.254.")
_SAFE_IPS = frozenset(["127.0.0.1", "0.0.0.0", "::1", "localhost"])

# Patterns that indicate the IP is a comment or documentation example
_IP_COMMENT_RE = re.compile(r"^\s*#")


def _ip_is_safe(ip: str) -> bool:
    return ip in _SAFE_IPS or any(ip.startswith(p) for p in _SAFE_IP_PREFIXES)


class TestNoHardcodedNonLoopbackIPs:
    """Non-loopback IPs must not be hardcoded in production Python source.

    Container-internal hostnames (player, dashboard-api, etc.) are fine —
    only numeric IPv4 addresses are checked.  IPs that appear only inside
    os.environ.get() default strings are flagged because the default itself
    is device-specific.
    """

    def test_no_routable_ips_in_production_source(self):
        violations: list[str] = []
        for path in _production_python():
            text = path.read_text(errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                if _IP_COMMENT_RE.match(line):
                    continue
                for m in _IPV4_RE.finditer(line):
                    ip = m.group(0)
                    if not _ip_is_safe(ip):
                        rel = path.relative_to(_REPO)
                        violations.append(f"{rel}:{lineno} — {ip!r}")
        assert not violations, (
            "Non-loopback IP addresses hardcoded in production Python source.\n"
            "Use environment variables for all host addresses:\n"
            + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# 4. All host/port/URL values in config modules must be env-var overridable
# ---------------------------------------------------------------------------

_BARE_URL_ASSIGN_RE = re.compile(
    r"""(?x)
    ^\s*                             # optional indent
    [\w_]+                           # variable name
    \s*[=:]\s*                       # assignment or type annotation
    (?:str\s*=\s*)?                  # optional type hint
    ["\']                            # opening quote
    (?:https?://|ws://|wss://|       # URL scheme
       postgresql\+|mqtt://)         # DB / MQTT scheme
    [^"\']*?                         # URL body
    :\d+                             # :port
    [^"\']*                          # rest of URL
    ["\']                            # closing quote
    """,
    re.MULTILINE,
)

_ENV_GET_RE = re.compile(r"os\.environ\.get\s*\(")


class TestConfigValuesAreEnvOverridable:
    """Every URL with an embedded port in a config module must appear on the
    same logical expression as os.environ.get() so it can be overridden at
    deploy time without changing source."""

    def test_service_urls_in_config_are_behind_env_get(self):
        violations: list[str] = []
        for path in _config_python():
            # Pydantic BaseSettings: all field defaults are env-overridable
            # automatically (e.g. via DASHBOARD_* prefix).  No os.environ.get()
            # wrapper needed — the framework reads env vars itself.
            if _uses_pydantic_settings(path):
                continue
            text = path.read_text(errors="replace")
            lines = text.splitlines()
            for lineno, line in enumerate(lines, 1):
                # Only care about URL-shaped string literals in assignments
                if not _BARE_URL_ASSIGN_RE.match(line):
                    continue
                if "os.environ.get" in line:
                    continue
                if "Field(" in line or "field(" in line:
                    continue
                # Check 3 preceding lines for context (multi-line os.environ.get)
                context_start = max(0, lineno - 4)
                context = "\n".join(lines[context_start:lineno])
                if _ENV_GET_RE.search(context):
                    continue
                rel = path.relative_to(_REPO)
                violations.append(f"{rel}:{lineno} — {line.strip()!r}")
        assert not violations, (
            "URL/host values in config modules are not behind os.environ.get().\n"
            "Every address that contains a port must be overridable at deploy time:\n"
            + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# 5. No .env files with credential assignments committed to the repo
# ---------------------------------------------------------------------------

_CREDENTIAL_ASSIGN_RE = re.compile(
    r"(?i)^(?:export\s+)?(?:password|passwd|secret|api_key|private_key|"
    r"token|preshared_key|auth_token)\s*=\s*.+",
    re.MULTILINE,
)


class TestNoDotEnvCredentials:
    """No .env files containing credential assignments should be committed."""

    def test_no_dotenv_credential_files(self):
        violations: list[str] = []
        for path in _iter_files("**/.env", "**/*.env"):
            if _is_template(path):
                continue
            text = path.read_text(errors="replace")
            if _CREDENTIAL_ASSIGN_RE.search(text):
                rel = path.relative_to(_REPO)
                violations.append(str(rel))
        assert not violations, (
            ".env files with credential assignments found in repo "
            "(use .env.template and supply real values at provisioning time):\n"
            + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# 6. No hardcoded PostgreSQL DSNs with embedded passwords (not via env)
# ---------------------------------------------------------------------------

# Match postgresql://user:password@... or postgresql+asyncpg://user:pass@...
_PG_DSN_WITH_CREDS_RE = re.compile(
    r"""postgresql(?:\+\w+)?://[^@:/"'\s]+:[^@/"'\s@]+@"""
)


class TestNoDatabaseCredentials:
    """PostgreSQL DSN strings that embed a password must only appear as the
    default value inside an os.environ.get() call, making them overridable."""

    def test_pg_dsn_credentials_are_behind_env_get(self):
        violations: list[str] = []
        for path in _production_python():
            # Pydantic BaseSettings fields are env-overridable without
            # os.environ.get() — the DSN default is NOT hardcoded in the
            # golden-image sense because it can be overridden via DASHBOARD_DATABASE_URL.
            if _uses_pydantic_settings(path):
                continue
            text = path.read_text(errors="replace")
            lines = text.splitlines()
            for lineno, line in enumerate(lines, 1):
                if not _PG_DSN_WITH_CREDS_RE.search(line):
                    continue
                # Skip pure comments
                if line.strip().startswith("#"):
                    continue
                # Check whether the DSN is the default arg inside os.environ.get
                context_start = max(0, lineno - 3)
                context = "\n".join(lines[context_start : lineno + 1])
                if _ENV_GET_RE.search(context):
                    continue
                # Pydantic Settings / Field with env= sourcing is also OK
                if "Field(" in context or "settings_customise_sources" in context:
                    continue
                rel = path.relative_to(_REPO)
                violations.append(f"{rel}:{lineno} — DSN with embedded password")
        assert not violations, (
            "PostgreSQL DSN strings with embedded credentials found outside "
            "of os.environ.get() defaults.\n"
            "Supply credentials via environment variable at provisioning time:\n"
            + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# 7. No device-specific MQTT topics hardcoded without env override
#    (tenant / site / camera identifiers must be configurable)
# ---------------------------------------------------------------------------

# A topic is "device-specific" if it contains a segment that looks like a
# site ID or camera ID (pattern: word-digit suffix like site-01, cam-01)
_DEVICE_TOPIC_RE = re.compile(
    r"""["\'](?:[\w/]+/)?(?:site|cam|device)-\d+(?:/[\w/]*)?["\']"""
)


class TestMqttTopicsAreConfigurable:
    """MQTT topics that embed site/cam/device identifiers must be env-overridable."""

    def test_device_mqtt_topics_behind_env_get(self):
        violations: list[str] = []
        for path in _config_python():
            text = path.read_text(errors="replace")
            lines = text.splitlines()
            for lineno, line in enumerate(lines, 1):
                if line.strip().startswith("#"):
                    continue
                if not _DEVICE_TOPIC_RE.search(line):
                    continue
                # Must be inside an os.environ.get() default
                context_start = max(0, lineno - 3)
                context = "\n".join(lines[context_start : lineno + 1])
                if _ENV_GET_RE.search(context):
                    continue
                rel = path.relative_to(_REPO)
                violations.append(f"{rel}:{lineno} — {line.strip()!r}")
        assert not violations, (
            "Device-specific MQTT topics (site-NN, cam-NN) hardcoded in config "
            "without os.environ.get().\n"
            "Each deployed unit must be able to override its topic segments:\n"
            + "\n".join(violations)
        )
