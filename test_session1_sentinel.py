import sys
import os

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

# Set required environment variable for testing
os.environ.setdefault("openai_api_key", "test-key-for-testing")

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("=" * 50)
print("TESTING ALL SESSION 1 COMPONENTS (SENTINEL)")
print("=" * 50)

# === MODELS ===
from sentinel.domain.models import (
    Role, FinishReason, Message, ModelParameters,
    ChatRequest, TokenUsage, ChatResponse
)

r1 = ChatRequest(model="gpt-4", messages=[])
r2 = ChatRequest(model="gpt-4", messages=[])
assert r1.id != r2.id
print("✅ Models: Auto-generated IDs work")

msg = Message(role=Role.USER, content="test")
try:
    msg.content = "changed"
    print("❌ Models: Message should be frozen")
except:
    print("✅ Models: Message is frozen")

assert TokenUsage(prompt_tokens=10, completion_tokens=5).total_tokens == 15
print("✅ Models: TokenUsage.total_tokens works")

# === EXCEPTIONS ===
from sentinel.domain.exceptions import (
    SentinelError, ProviderError, ProviderRateLimitError
)

e = ProviderRateLimitError("test", provider="openai", status_code=429)
assert isinstance(e, SentinelError)
print("✅ Exceptions: Hierarchy works")

# === CONFIG ===
from sentinel.core.config import get_settings

s1 = get_settings()
s2 = get_settings()
assert s1 is s2
print("✅ Config: Caching works")

# === HTTP ===
from sentinel.core.http import get_http_client

c1 = get_http_client()
c2 = get_http_client()
assert c1 is c2
print("✅ HTTP: Caching works")

# === TELEMETRY ===
from sentinel.core.telemetry import log_request_started
print("✅ Telemetry: Imports work")

# === NEW SENTINEL MODELS ===
from sentinel.domain.models import GuardrailAction, PIIType, PIIEntity, GuardrailResult

result = GuardrailResult(action=GuardrailAction.BLOCK)
assert result.action == GuardrailAction.BLOCK
print("✅ Sentinel: GuardrailResult works")

pii = PIIEntity(type=PIIType.EMAIL, text="test@example.com", start=0, end=16, confidence=0.95)
assert pii.type == PIIType.EMAIL
print("✅ Sentinel: PIIEntity works")

# === NEW SENTINEL EXCEPTIONS ===
from sentinel.domain.exceptions import GuardrailError, PIIDetectedError

error = PIIDetectedError("PII found", pii_types=["email"])
assert isinstance(error, GuardrailError)
assert isinstance(error, SentinelError)
print("✅ Sentinel: Exception hierarchy works")

print("\n" + "=" * 50)
print("✅ SESSION 1 + SENTINEL BRIDGE COMPLETE")
print("=" * 50)
