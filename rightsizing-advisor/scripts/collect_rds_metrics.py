#!/usr/bin/env python3
"""
Collect and aggregate CloudWatch metrics for RDS instances via MCP.
Returns compact JSON summary for AI agent analysis.

Usage:
  python3 collect_rds_metrics.py \
    --arns '["arn:aws-cn:rds:cn-northwest-1:123456789012:db:mydb"]' \
    --region cn-northwest-1 \
    --days 7 \
    --role-arn arn:aws-cn:iam::123456789012:role/ReadOnly \
    --mcp-url https://example.com/aws-api/mcp \
    --mcp-headers '{"Authorization":"Bearer xxx"}'

Accepts single ARN or JSON array of ARNs. Outputs one JSON summary per instance.
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import httpx


RDS_METRICS = [
    {"name": "CPUUtilization", "stats": ["Average", "Maximum"], "primary": "Average"},
    {"name": "DatabaseConnections", "stats": ["Average", "Maximum"], "primary": "Average"},
    {"name": "FreeableMemory", "stats": ["Average", "Minimum"], "primary": "Average"},
    {"name": "ReadIOPS", "stats": ["Average"], "primary": "Average"},
    {"name": "WriteIOPS", "stats": ["Average"], "primary": "Average"},
    {"name": "FreeStorageSpace", "stats": ["Average", "Minimum"], "primary": "Average"},
]

# 1-minute period, batch by day to stay under 1440 limit
PERIOD = 60
BATCH_DAYS = 1  # 1 day × 1440 points/day = 1440 (at limit)


async def call_aws(session, cli_command, role_arn=None):
    """Call the call_aws MCP tool."""
    args = {"cli_command": cli_command}
    if role_arn:
        args["role_arn"] = role_arn
    result = await session.call_tool("call_aws", arguments=args)
    for content in result.content:
        if hasattr(content, "text"):
            data = json.loads(content.text)
            if isinstance(data, list) and data:
                resp = data[0].get("response", {})
                if resp.get("error"):
                    return None, resp["error"]
                return json.loads(resp.get("as_json", "{}")), None
            return data, None
    return None, "No content"


async def fetch_metric_batched(session, instance_id, metric_name, stats, region, start, end, role_arn):
    """Fetch metric in day-sized batches to support 1-minute granularity over long periods."""
    all_datapoints = []
    current = start
    batch_num = 0

    while current < end:
        batch_end = min(current + timedelta(days=BATCH_DAYS), end)
        stats_str = " ".join(stats)
        cmd = (
            f"aws cloudwatch get-metric-statistics "
            f"--namespace AWS/RDS "
            f"--metric-name {metric_name} "
            f"--dimensions Name=DBInstanceIdentifier,Value={instance_id} "
            f"--start-time {current.strftime('%Y-%m-%dT%H:%M:%SZ')} "
            f"--end-time {batch_end.strftime('%Y-%m-%dT%H:%M:%SZ')} "
            f"--period {PERIOD} "
            f"--statistics {stats_str} "
            f"--region {region}"
        )
        data, err = await call_aws(session, cmd, role_arn)
        if err:
            print(f"  ⚠ {metric_name} batch {batch_num}: {err}", file=sys.stderr)
        elif data:
            batch_pts = data.get("Datapoints", [])
            all_datapoints.extend(batch_pts)

        batch_num += 1
        current = batch_end
        # Throttle protection
        await asyncio.sleep(0.2)

    return all_datapoints


def aggregate(datapoints, stat_key):
    values = [dp[stat_key] for dp in datapoints if stat_key in dp]
    if not values:
        return {"avg": None, "max": None, "min": None, "count": 0}
    return {"avg": round(sum(values)/len(values), 4), "max": round(max(values), 4),
            "min": round(min(values), 4), "count": len(values)}


def hourly_profile(datapoints, stat_key):
    buckets = defaultdict(list)
    for dp in datapoints:
        ts = datetime.fromisoformat(dp["Timestamp"].replace("+00:00", "+00:00"))
        buckets[ts.hour].append(dp.get(stat_key, 0))
    return {f"{h:02d}": round(sum(v)/len(v), 4) if (v := buckets.get(h)) else None for h in range(24)}


def weekday_weekend(datapoints, stat_key):
    wd, we = [], []
    for dp in datapoints:
        ts = datetime.fromisoformat(dp["Timestamp"].replace("+00:00", "+00:00"))
        (wd if ts.weekday() < 5 else we).append(dp.get(stat_key, 0))
    def s(vals):
        return {"avg": round(sum(vals)/len(vals), 4), "max": round(max(vals), 4), "min": round(min(vals), 4)} if vals else None
    return {"weekday": s(wd), "weekend": s(we)}


def detect_peak(hourly_cpu):
    values = [v for v in hourly_cpu.values() if v is not None]
    if not values:
        return {"pattern": "no_data"}
    mean = sum(values) / len(values)
    threshold = max(mean * 1.5, 20)
    peak = [int(h) for h, v in hourly_cpu.items() if v and v > threshold]
    offpeak = [int(h) for h, v in hourly_cpu.items() if not v or v <= threshold]
    if not peak:
        return {"pattern": "steady_state", "mean_cpu": round(mean, 2)}
    peak_avg = round(sum(hourly_cpu[f"{h:02d}"] for h in peak) / len(peak), 2)
    op_vals = [hourly_cpu[f"{h:02d}"] for h in offpeak if hourly_cpu[f"{h:02d}"] is not None]
    op_avg = round(sum(op_vals) / len(op_vals), 2) if op_vals else None
    return {"pattern": "variable", "peak_hours": peak, "offpeak_hours": offpeak,
            "peak_cpu_avg": peak_avg, "offpeak_cpu_avg": op_avg}


def b2g(val):
    return round(val / (1024**3), 2) if val is not None else None


async def analyze_instance(session, instance_id, region, days, role_arn, is_aurora, total_mem_gib, alloc_storage_gb):
    """Fetch all metrics for one instance and return aggregated summary."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    metrics_list = [m for m in RDS_METRICS if not (is_aurora and m["name"] == "FreeStorageSpace")]

    print(f"  📊 {instance_id}: fetching {len(metrics_list)} metrics, {days} days, {PERIOD}s period, batched by {BATCH_DAYS} day(s)", file=sys.stderr)

    results = {}
    errors = []

    for metric in metrics_list:
        print(f"    → {metric['name']}...", file=sys.stderr, end=" ", flush=True)
        dps = await fetch_metric_batched(session, instance_id, metric["name"], metric["stats"], region, start, end, role_arn)
        print(f"{len(dps)} pts", file=sys.stderr)

        if not dps:
            errors.append({"metric": metric["name"], "error": "no datapoints"})
            continue

        primary = metric["primary"]
        overall = aggregate(dps, primary)
        if len(metric["stats"]) > 1:
            sec = metric["stats"][1]
            sec_agg = aggregate(dps, sec)
            overall[sec.lower()] = sec_agg.get("max" if sec == "Maximum" else "min")

        results[metric["name"]] = {
            "overall": overall,
            "hourly_profile": hourly_profile(dps, primary),
            "weekday_weekend": weekday_weekend(dps, primary),
        }

    summary = {
        "instance_id": instance_id, "region": region,
        "window": {"days": days},
        "metrics": {},
    }

    # Compact metrics: only avg and max per metric
    for name, data in results.items():
        o = data["overall"]
        compact = {"avg": o.get("avg"), "max": o.get("max" if "max" in o else "maximum", o.get("maximum"))}
        if o.get("maximum") is not None:
            compact["max"] = o["maximum"]  # use absolute max for CPU etc
        if o.get("minimum") is not None:
            compact["min"] = o["minimum"]  # use absolute min for FreeableMemory
        # Weekday vs weekend: only avg
        ww = data.get("weekday_weekend", {})
        wd_avg = ww.get("weekday", {}).get("avg") if ww.get("weekday") else None
        we_avg = ww.get("weekend", {}).get("avg") if ww.get("weekend") else None
        if wd_avg is not None and we_avg is not None and wd_avg != we_avg:
            compact["weekday_avg"] = wd_avg
            compact["weekend_avg"] = we_avg
        summary["metrics"][name] = compact

    if "CPUUtilization" in results:
        pa = detect_peak(results["CPUUtilization"]["hourly_profile"])
        summary["peak_analysis"] = pa
        # Only include hourly CPU profile if pattern is variable (agent needs it for scheduling)
        if pa.get("pattern") == "variable":
            summary["cpu_hourly_profile"] = results["CPUUtilization"]["hourly_profile"]

    cpu_max = results.get("CPUUtilization", {}).get("overall", {}).get("max")
    conn_max = results.get("DatabaseConnections", {}).get("overall", {}).get("max")
    summary["idle_detection"] = {
        "max_cpu": cpu_max, "max_connections": conn_max,
        "is_idle": (cpu_max or 100) < 5 and (conn_max or 999) < 2,
    }

    if "FreeableMemory" in results and total_mem_gib:
        free_avg = results["FreeableMemory"]["overall"].get("avg")
        if free_avg:
            used = total_mem_gib - b2g(free_avg)
            summary["memory"] = {"total_gib": total_mem_gib, "used_gib": round(used, 2),
                                 "pct": round(used / total_mem_gib * 100, 1)}

    if "FreeStorageSpace" in results and alloc_storage_gb:
        free_avg = results["FreeStorageSpace"]["overall"].get("avg")
        if free_avg:
            free_gb = b2g(free_avg)
            summary["storage"] = {"allocated_gb": alloc_storage_gb,
                                  "used_gb": round(alloc_storage_gb - free_gb, 2),
                                  "pct": round((alloc_storage_gb - free_gb) / alloc_storage_gb * 100, 1)}

    pa = summary.get("peak_analysis", {})
    if pa.get("pattern") == "variable":
        ph = len(pa.get("peak_hours", []))
        oc = pa.get("offpeak_cpu_avg", 0) or 0
        summary["waste_ratio_pct"] = round((24 - ph) / 24 * (1 - oc / 100) * 100, 1)
    elif pa.get("pattern") == "steady_state":
        summary["waste_ratio_pct"] = round((1 - pa.get("mean_cpu", 0) / 100) * 100, 1)

    if errors:
        summary["errors"] = errors
    return summary


async def run(args):
    # Parse instance list
    instances = json.loads(args.instances) if args.instances.startswith("[") else [args.instances]

    headers = json.loads(args.mcp_headers) if args.mcp_headers else {}

    async with httpx.AsyncClient(headers=headers, timeout=120) as http_client:
        async with streamable_http_client(args.mcp_url, http_client=http_client) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                all_results = []
                for inst in instances:
                    # inst can be ARN or instance-id; extract id from ARN
                    instance_id = inst.split(":")[-1] if ":" in inst else inst
                    if instance_id.startswith("db:"):
                        instance_id = instance_id[3:]

                    result = await analyze_instance(
                        session, instance_id, args.region, args.days,
                        args.role_arn, args.is_aurora,
                        args.total_memory_gib, args.allocated_storage_gb,
                    )
                    all_results.append(result)

    if len(all_results) == 1:
        print(json.dumps(all_results[0], indent=2))
    else:
        print(json.dumps(all_results, indent=2))


def main():
    p = argparse.ArgumentParser(description="Collect RDS CloudWatch metrics via MCP")
    p.add_argument("--instances", required=True, help='Instance ID, ARN, or JSON array of them')
    p.add_argument("--region", required=True)
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--role-arn", default=None)
    p.add_argument("--total-memory-gib", type=float, default=None)
    p.add_argument("--allocated-storage-gb", type=float, default=None)
    p.add_argument("--is-aurora", action="store_true")
    p.add_argument("--mcp-url", required=True, help="MCP streamable HTTP endpoint URL")
    p.add_argument("--mcp-headers", default=None, help='JSON string of HTTP headers, e.g. \'{"Authorization":"Bearer xxx"}\'')
    args = p.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
