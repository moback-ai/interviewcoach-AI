"""
Start/stop InterviewCoach EC2 + RDS on a weekday schedule (Mon–Fri 10:00–19:30 IST).

Weekend: Sat/Sun 00:05 IST force-stop schedules keep instances off.
Start runs Mon–Fri only (no weekend starts).

Invoked by EventBridge Scheduler with {"action": "start"} or {"action": "stop"}.
"""
import json
import os
import time

import boto3

REGION = os.environ.get("SCHEDULE_REGION", os.environ.get("AWS_DEFAULT_REGION", "ap-south-1"))
EC2_IDS = [x.strip() for x in os.environ.get("EC2_INSTANCE_IDS", "").split(",") if x.strip()]
RDS_ID = os.environ.get("RDS_INSTANCE_ID", "").strip()


def _log(msg: str) -> None:
    print(msg)


def stop_all() -> dict:
    ec2 = boto3.client("ec2", region_name=REGION)
    rds = boto3.client("rds", region_name=REGION)
    results = {"ec2": [], "rds": None}

    if EC2_IDS:
        _log(f"Stopping EC2: {EC2_IDS}")
        ec2.stop_instances(InstanceIds=EC2_IDS)
        results["ec2"] = EC2_IDS

    if RDS_ID:
        try:
            status = rds.describe_db_instances(DBInstanceIdentifier=RDS_ID)["DBInstances"][0]["DBInstanceStatus"]
            if status == "available":
                _log(f"Stopping RDS: {RDS_ID}")
                rds.stop_db_instance(DBInstanceIdentifier=RDS_ID)
                results["rds"] = "stopping"
            else:
                _log(f"RDS {RDS_ID} already {status}")
                results["rds"] = status
        except Exception as exc:
            _log(f"RDS stop skipped: {exc}")
            results["rds"] = str(exc)

    return results


def start_all() -> dict:
    ec2 = boto3.client("ec2", region_name=REGION)
    rds = boto3.client("rds", region_name=REGION)
    results = {"rds": None, "ec2": []}

    if RDS_ID:
        try:
            status = rds.describe_db_instances(DBInstanceIdentifier=RDS_ID)["DBInstances"][0]["DBInstanceStatus"]
            if status == "stopped":
                _log(f"Starting RDS: {RDS_ID}")
                rds.start_db_instance(DBInstanceIdentifier=RDS_ID)
                waiter = rds.get_waiter("db_instance_available")
                waiter.wait(
                    DBInstanceIdentifier=RDS_ID,
                    WaiterConfig={"Delay": 30, "MaxAttempts": 40},
                )
                results["rds"] = "available"
            else:
                _log(f"RDS {RDS_ID} already {status}")
                results["rds"] = status
        except Exception as exc:
            _log(f"RDS start error: {exc}")
            results["rds"] = str(exc)

    if EC2_IDS:
        _log(f"Starting EC2: {EC2_IDS}")
        ec2.start_instances(InstanceIds=EC2_IDS)
        waiter = ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=EC2_IDS, WaiterConfig={"Delay": 15, "MaxAttempts": 40})
        results["ec2"] = EC2_IDS
        # Brief pause for cloud-init / systemd
        time.sleep(30)

    return results


def handler(event, context):
    action = (event.get("action") or event.get("detail", {}).get("action") or "").strip().lower()
    _log(f"action={action} event={json.dumps(event)}")
    if action == "stop":
        out = stop_all()
    elif action == "start":
        out = start_all()
    else:
        raise ValueError(f"Unknown action: {action}")
    _log(f"done: {json.dumps(out)}")
    return {"ok": True, "action": action, "result": out}
