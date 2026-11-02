"""Small reproducible practical example: validate one AI-proposed next step."""
import argparse
import json
from pathlib import Path

ALLOWED = {"execute", "verify", "defer"}


def validate(value):
    if not isinstance(value, dict):
        return {"accepted": False, "reason": "expected object"}
    if set(value) != {"action", "reason"}:
        return {"accepted": False, "reason": "missing or unexpected field"}
    if not isinstance(value["action"], str) or value["action"] not in ALLOWED:
        return {"accepted": False, "reason": "action outside allowlist"}
    if not isinstance(value["reason"], str) or not value["reason"].strip():
        return {"accepted": False, "reason": "empty/non-string reason"}
    return {"accepted": True, "action": value["action"], "reason": value["reason"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(json.loads(args.input.read_text(encoding="utf-8"))), ensure_ascii=False))
    except (ValueError, OSError) as exc:
        print(json.dumps({"accepted": False, "reason": type(exc).__name__}))
        raise SystemExit(2)
