#!/usr/bin/env python3
"""Create a new launch template version with an updated API image tag in UserData."""
from __future__ import annotations

import base64
import re
import sys

import boto3


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit(
            "usage: bump-launch-template-image.py REGION LAUNCH_TEMPLATE_ID ECR_REGISTRY IMAGE_TAG"
        )
    region, lt_id, ecr_registry, image_tag = sys.argv[1:5]
    ec2 = boto3.client("ec2", region_name=region)
    latest = ec2.describe_launch_template_versions(
        LaunchTemplateId=lt_id,
        Versions=["$Latest"],
    )["LaunchTemplateVersions"][0]
    data = dict(latest["LaunchTemplateData"])
    user_data = base64.b64decode(data["UserData"]).decode()
    image_line = f"image: {ecr_registry}/interviewcoach-api:{image_tag}"
    user_data, count = re.subn(
        r"image: .+/interviewcoach-api:[^\s]+",
        image_line,
        user_data,
        count=1,
    )
    if count != 1:
        raise SystemExit("Could not find interviewcoach-api image line in launch template UserData")
    data["UserData"] = base64.b64encode(user_data.encode()).decode()
    new_version = ec2.create_launch_template_version(
        LaunchTemplateId=lt_id,
        SourceVersion=str(latest["VersionNumber"]),
        LaunchTemplateData=data,
    )["LaunchTemplateVersion"]["VersionNumber"]
    print(new_version)


if __name__ == "__main__":
    main()
