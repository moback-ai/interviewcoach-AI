#!/usr/bin/env python3
"""Remove awslogs-stream-prefix from launch template UserData (unsupported on prod docker.io)."""
from __future__ import annotations

import base64
import re
import sys

import boto3


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch-launch-template-docker-logs.py REGION LAUNCH_TEMPLATE_ID")
    region, lt_id = sys.argv[1:3]
    ec2 = boto3.client("ec2", region_name=region)
    latest = ec2.describe_launch_template_versions(
        LaunchTemplateId=lt_id,
        Versions=["$Latest"],
    )["LaunchTemplateVersions"][0]
    user_data = base64.b64decode(latest["LaunchTemplateData"]["UserData"]).decode()
    if "awslogs-stream-prefix" not in user_data:
        print(latest["VersionNumber"])
        return
    data = dict(latest["LaunchTemplateData"])
    patched, count = re.subn(r"\n\s*awslogs-stream-prefix: api\n", "\n", user_data, count=1)
    if count != 1:
        raise SystemExit("awslogs-stream-prefix line not found in launch template UserData")
    data["UserData"] = base64.b64encode(patched.encode()).decode()
    new_version = ec2.create_launch_template_version(
        LaunchTemplateId=lt_id,
        SourceVersion=str(latest["VersionNumber"]),
        LaunchTemplateData=data,
    )["LaunchTemplateVersion"]["VersionNumber"]
    print(new_version)


if __name__ == "__main__":
    main()
