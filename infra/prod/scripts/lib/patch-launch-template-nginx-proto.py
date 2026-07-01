#!/usr/bin/env python3
"""Set nginx X-Forwarded-Proto=https for CloudFront→ALB (viewer HTTPS, origin HTTP)."""
from __future__ import annotations

import base64
import sys

import boto3

OLD = "proxy_set_header X-Forwarded-Proto $scheme;"
NEW = "proxy_set_header X-Forwarded-Proto https;"


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch-launch-template-nginx-proto.py REGION LAUNCH_TEMPLATE_ID")
    region, lt_id = sys.argv[1:3]
    ec2 = boto3.client("ec2", region_name=region)
    latest = ec2.describe_launch_template_versions(
        LaunchTemplateId=lt_id,
        Versions=["$Latest"],
    )["LaunchTemplateVersions"][0]
    user_data = base64.b64decode(latest["LaunchTemplateData"]["UserData"]).decode()
    if NEW in user_data:
        print(latest["VersionNumber"])
        return
    if OLD not in user_data:
        raise SystemExit("nginx X-Forwarded-Proto line not found in launch template UserData")
    data = dict(latest["LaunchTemplateData"])
    data["UserData"] = base64.b64encode(user_data.replace(OLD, NEW, 1).encode()).decode()
    new_version = ec2.create_launch_template_version(
        LaunchTemplateId=lt_id,
        SourceVersion=str(latest["VersionNumber"]),
        LaunchTemplateData=data,
    )["LaunchTemplateVersion"]["VersionNumber"]
    print(new_version)
