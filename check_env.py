"""
Quick sanity-check script for VEGA .env API key loading.
Run: python check_env.py
"""
from dotenv import load_dotenv
from pathlib import Path
import os

# Load from the .env in the same folder
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

KEYS = {
    "GOOGLE_AI_API_KEY":    ("CRITICAL", "Gemini AI conversation"),
    "PICOVOICE_ACCESS_KEY": ("CRITICAL", "Hey-Vega wake word"),
    "OPENWEATHER_API_KEY":  ("OPTIONAL", "Weather command"),
    "GNEWS_API_KEY":        ("OPTIONAL", "News headlines command"),
    "GMAIL_USER":           ("OPTIONAL", "Email sender address"),
    "GMAIL_APP_PASSWORD":   ("OPTIONAL", "Email sending authentication"),
}

print("\n" + "=" * 60)
print("   VEGA — Environment Key Validation Report")
print("=" * 60)

all_critical_ok = True

for name, (priority, purpose) in KEYS.items():
    val = os.getenv(name, "")
    if val:
        # Show first 8 chars and mask the rest for safety
        preview = val[:8] + ("*" * min(6, max(0, len(val) - 8)))
        status = "✅ OK     "
    else:
        preview = "(empty / missing)"
        status = "❌ MISSING"
        if priority == "CRITICAL":
            all_critical_ok = False

    print(f"  {status} [{priority}] {name}")
    print(f"             Purpose : {purpose}")
    if val:
        print(f"             Preview : {preview}")
    print()

print("=" * 60)
if all_critical_ok:
    print("  🟢 All critical keys are loaded. VEGA can start!")
else:
    print("  🔴 Some CRITICAL keys are missing. VEGA will not start.")
    print("     Please check your .env file.")
print("=" * 60 + "\n")
