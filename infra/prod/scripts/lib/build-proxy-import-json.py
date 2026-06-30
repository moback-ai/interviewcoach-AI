#!/usr/bin/env python3
"""Build resources-to-import JSON for proxy stack after retain-delete."""
import json
import subprocess
import sys


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True)


def sg_id(region: str, name: str) -> str:
    return json.loads(
        run(
            "aws", "ec2", "describe-security-groups",
            "--region", region,
            "--filters", f"Name=group-name,Values={name}",
            "--query", "SecurityGroups[0].GroupId",
            "--output", "json",
        )
    )


def main() -> None:
    region = sys.argv[1]
    rds_sg = sys.argv[2]
    proxy_name = sys.argv[3]

    proxy_sg = sg_id(region, "interviewcoach-prod-rds-proxy-sg")
    rds_rules = json.loads(
        run(
            "aws", "ec2", "describe-security-group-rules",
            "--region", region,
            "--filters", f"Name=group-id,Values={rds_sg}",
            "--output", "json",
        )
    )["SecurityGroupRules"]
    proxy_rule_id = next(
        r["SecurityGroupRuleId"]
        for r in rds_rules
        if r.get("FromPort") == 5432
        and (r.get("ReferencedGroupInfo") or {}).get("GroupId") == proxy_sg
    )

    tg = json.loads(
        run(
            "aws", "rds", "describe-db-proxy-target-groups",
            "--region", region,
            "--db-proxy-name", proxy_name,
            "--query", "TargetGroups[0]",
            "--output", "json",
        )
    )

    imports = [
        ("RdsProxyRole", "AWS::IAM::Role", {"RoleName": "interviewcoach-prod-rds-proxy-role"}),
        ("RdsProxySecurityGroup", "AWS::EC2::SecurityGroup", {"Id": proxy_sg}),
        ("RdsIngressFromProxy", "AWS::EC2::SecurityGroupIngress", {"Id": proxy_rule_id}),
        ("DbProxy", "AWS::RDS::DBProxy", {"DBProxyName": proxy_name}),
        ("DbProxyTargetGroup", "AWS::RDS::DBProxyTargetGroup", {
            "DBProxyName": tg["DBProxyName"],
            "TargetGroupName": tg["TargetGroupName"],
        }),
    ]

    payload = [
        {
            "ResourceType": rtype,
            "LogicalResourceId": lid,
            "ResourceIdentifier": ident,
        }
        for lid, rtype, ident in imports
    ]
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
