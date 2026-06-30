#!/usr/bin/env python3
"""Build resources-to-import JSON for compute stack after retain-delete."""
import json
import subprocess
import sys


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True)


def ingress_identifier(region: str, rule_id: str) -> dict:
    rule = json.loads(
        run(
            "aws", "ec2", "describe-security-group-rules",
            "--region", region,
            "--security-group-rule-ids", rule_id,
            "--query", "SecurityGroupRules[0]",
            "--output", "json",
        )
    )
    ident = {
        "GroupId": rule["GroupId"],
        "IpProtocol": rule["IpProtocol"],
        "FromPort": str(rule["FromPort"]),
        "ToPort": str(rule["ToPort"]),
    }
    ref = rule.get("ReferencedGroupInfo") or {}
    if ref.get("GroupId"):
        ident["SourceSecurityGroupId"] = ref["GroupId"]
    elif rule.get("CidrIpv4"):
        ident["CidrIp"] = rule["CidrIpv4"]
    return ident


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
    api_sg = sg_id(region, "interviewcoach-prod-api-asg-sg")
    alb_sg = sg_id(region, "interviewcoach-prod-alb-sg")
    redis_sg = sg_id(region, "interviewcoach-prod-redis-sg")

    alb_arn = json.loads(
        run(
            "aws", "elbv2", "describe-load-balancers",
            "--region", region,
            "--names", "interviewcoach-prod-alb",
            "--query", "LoadBalancers[0].LoadBalancerArn",
            "--output", "json",
        )
    )
    tg_arn = json.loads(
        run(
            "aws", "elbv2", "describe-target-groups",
            "--region", region,
            "--names", "interviewcoach-prod-api-tg",
            "--query", "TargetGroups[0].TargetGroupArn",
            "--output", "json",
        )
    )
    listener_arn = json.loads(
        run(
            "aws", "elbv2", "describe-listeners",
            "--region", region,
            "--load-balancer-arn", alb_arn,
            "--query", "Listeners[?Port==`80`].ListenerArn | [0]",
            "--output", "json",
        )
    )
    lt_id = json.loads(
        run(
            "aws", "ec2", "describe-launch-templates",
            "--region", region,
            "--launch-template-names", "interviewcoach-prod-api-lt",
            "--query", "LaunchTemplates[0].LaunchTemplateId",
            "--output", "json",
        )
    )

    policies = json.loads(
        run(
            "aws", "autoscaling", "describe-policies",
            "--region", region,
            "--auto-scaling-group-name", "interviewcoach-prod-api-asg",
            "--output", "json",
        )
    )["ScalingPolicies"]
    scale_up = next(p for p in policies if "CpuScaleUpPolicy" in p["PolicyName"])
    scale_down = next(p for p in policies if "CpuScaleDownPolicy" in p["PolicyName"])

    alarms = json.loads(
        run(
            "aws", "cloudwatch", "describe-alarms",
            "--region", region,
            "--alarm-name-prefix", "interviewcoach-prod-hybrid-Cpu",
            "--output", "json",
        )
    )["MetricAlarms"]
    cpu_high = next(a for a in alarms if "CpuHighAlarm" in a["AlarmName"])
    cpu_low = next(a for a in alarms if "CpuLowAlarm" in a["AlarmName"])

    rds_rules = json.loads(
        run(
            "aws", "ec2", "describe-security-group-rules",
            "--region", region,
            "--filters", f"Name=group-id,Values={rds_sg}",
            "--output", "json",
        )
    )["SecurityGroupRules"]
    rds_rule_id = next(
        r["SecurityGroupRuleId"]
        for r in rds_rules
        if r.get("FromPort") == 5432
        and (r.get("ReferencedGroupInfo") or {}).get("GroupId") == api_sg
    )

    imports = [
        ("AlbSecurityGroup", "AWS::EC2::SecurityGroup", {"Id": alb_sg}),
        ("ApiSecurityGroup", "AWS::EC2::SecurityGroup", {"Id": api_sg}),
        ("RedisSecurityGroup", "AWS::EC2::SecurityGroup", {"Id": redis_sg}),
        ("RdsIngressFromApi", "AWS::EC2::SecurityGroupIngress", {"Id": rds_rule_id}),
        ("CacheSubnetGroup", "AWS::ElastiCache::SubnetGroup", {"CacheSubnetGroupName": "interviewcoach-prod-redis-subnets"}),
        ("RedisReplicationGroup", "AWS::ElastiCache::ReplicationGroup", {"ReplicationGroupId": "interviewcoach-prod-redis"}),
        ("ApplicationLoadBalancer", "AWS::ElasticLoadBalancingV2::LoadBalancer", {"LoadBalancerArn": alb_arn}),
        ("ApiTargetGroup", "AWS::ElasticLoadBalancingV2::TargetGroup", {"TargetGroupArn": tg_arn}),
        ("AlbHttpListener", "AWS::ElasticLoadBalancingV2::Listener", {"ListenerArn": listener_arn}),
        ("ApiLaunchTemplate", "AWS::EC2::LaunchTemplate", {"LaunchTemplateId": lt_id}),
        ("ApiAutoScalingGroup", "AWS::AutoScaling::AutoScalingGroup", {"AutoScalingGroupName": "interviewcoach-prod-api-asg"}),
        ("CpuScaleUpPolicy", "AWS::AutoScaling::ScalingPolicy", {"Arn": scale_up["PolicyARN"]}),
        ("CpuScaleDownPolicy", "AWS::AutoScaling::ScalingPolicy", {"Arn": scale_down["PolicyARN"]}),
        ("CpuHighAlarm", "AWS::CloudWatch::Alarm", {"AlarmName": cpu_high["AlarmName"]}),
        ("CpuLowAlarm", "AWS::CloudWatch::Alarm", {"AlarmName": cpu_low["AlarmName"]}),
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
