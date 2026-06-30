#!/usr/bin/env python3
"""Format CloudFormation stack parameters for CLI (deploy / import)."""
import json
import sys


def format_value(value) -> str:
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    return str(value)


def main() -> None:
    mode = sys.argv[1]
    params = json.load(open(sys.argv[2], encoding="utf-8"))
    for p in params:
        value = format_value(p["ParameterValue"])
        if mode == "deploy":
            print(f"{p['ParameterKey']}={value}")
        elif mode == "import":
            print(f"ParameterKey={p['ParameterKey']},ParameterValue={value}")
        else:
            raise SystemExit(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
