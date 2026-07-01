#!/usr/bin/env python3
"""Add DeletionPolicy/UpdateReplacePolicy Retain to every CFN resource in a template."""
import re
import sys


def main() -> None:
    src, dst = sys.argv[1:3]
    lines = open(src, encoding="utf-8").read().splitlines()
    out: list[str] = []
    in_resources = False
    for line in lines:
        if line.rstrip() == "Outputs:":
            in_resources = False
        if line.rstrip() == "Resources:":
            in_resources = True
        out.append(line)
        if in_resources and re.match(r"^    Type: AWS::", line):
            out.append("    DeletionPolicy: Retain")
            out.append("    UpdateReplacePolicy: Retain")
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
