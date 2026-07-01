#!/usr/bin/env python3
"""Write CloudFormation import parameters JSON for --parameters file://."""
import json
import sys


def format_value(value) -> str:
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    return str(value)


def main() -> None:
    params = json.load(open(sys.argv[1], encoding="utf-8"))
    payload = [
        {"ParameterKey": p["ParameterKey"], "ParameterValue": format_value(p["ParameterValue"])}
        for p in params
    ]
    json.dump(payload, open(sys.argv[2], "w", encoding="utf-8"), indent=2)


if __name__ == "__main__":
    main()
