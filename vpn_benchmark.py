#!/usr/bin/env python3
import csv
import datetime as dt
import re
import subprocess
import sys
import urllib.request

def run(cmd: list[str]) -> str:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        return out
    except subprocess.CalledProcessError as e:
        return e.output

def get_external_ip(timeout=3) -> str:
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=timeout) as r:
            return r.read().decode("utf-8").strip()
    except Exception:
        return "N/A"

def parse_network_quality(text: str) -> dict:
    # Flexible regexes to handle slight format changes across macOS versions
    # Examples we’ve seen:
    #   Downlink capacity: 369.737 Mbps
    #   Uplink capacity: 45.350 Mbps
    #   Responsiveness: Medium (208.467 milliseconds | 287 RPM)
    #   Responsiveness: Low (48 RPM)
    #   Idle Latency: 35.624 ms
    #   Idle Latency: 35.624 milliseconds | 1684 RPM

    def grab_float(pattern: str):
        m = re.search(pattern, text, re.IGNORECASE)
        return float(m.group(1)) if m else None

    def grab_int(pattern: str):
        m = re.search(pattern, text, re.IGNORECASE)
        return int(m.group(1)) if m else None

    def grab_label(pattern: str):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).title() if m else None

    down = grab_float(r"Downlink\s+capacity:\s*([\d.]+)")
    up   = grab_float(r"Uplink\s+capacity:\s*([\d.]+)")

    # Idle latency number (ms or milliseconds)
    latency = grab_float(r"Idle\s+Latency:\s*([\d.]+)\s*(?:ms|milliseconds)")
    # Optional Idle RPM if present
    idle_rpm = grab_int(r"Idle\s+Latency:.*?\|\s*(\d+)\s*RPM")

    # Responsiveness label (High/Medium/Low)
    resp_label = grab_label(r"Responsiveness:\s*(High|Medium|Low)")
    # Responsiveness RPM (if present)
    resp_rpm = grab_int(r"Responsiveness:.*?(\d+)\s*RPM")

    return {
        "down": down,
        "up": up,
        "latency_ms": latency,
        "resp_label": resp_label or "Unknown",
        "resp_rpm": resp_rpm,
        "idle_rpm": idle_rpm,
    }

def emoji_for_down(x: float) -> str:
    if x is None: return "🔴"
    if x > 300: return "🟢"
    if x >= 100: return "🟡"
    return "🔴"

def emoji_for_up(x: float) -> str:
    if x is None: return "🔴"
    if x > 20: return "🟢"
    if x >= 5: return "🟡"
    return "🔴"

def emoji_for_latency(ms: float) -> str:
    if ms is None: return "🔴"
    if ms < 50: return "🟢"
    if ms <= 150: return "🟡"
    return "🔴"

def emoji_for_resp(label: str) -> str:
    if label.lower() == "high": return "🟢"
    if label.lower() == "medium": return "🟡"
    return "🔴"  # Low or Unknown

def main():
    profile = sys.argv[1] if len(sys.argv) > 1 else "Unknown"

    print(f"Running VPN performance test for profile: {profile}")
    print("-------------------------------------------")

    raw = run(["networkQuality", "-v"])
    # Uncomment to debug the raw output:
    # print(raw)

    metrics = parse_network_quality(raw)
    down = metrics["down"]
    up = metrics["up"]
    lat = metrics["latency_ms"]
    resp_label = metrics["resp_label"]
    resp_rpm = metrics["resp_rpm"]
    idle_rpm = metrics["idle_rpm"]

    ip = get_external_ip()

    # Prepare display strings (avoid 'None' showing up)
    def fmt(x, nd=3):
        return f"{x:.{nd}f}" if isinstance(x, float) else "0.000"

    down_s = fmt(down)
    up_s   = fmt(up)
    lat_s  = fmt(lat, nd=3)

    # Emojis
    d_emo = emoji_for_down(down)
    u_emo = emoji_for_up(up)
    l_emo = emoji_for_latency(lat)
    r_emo = emoji_for_resp(resp_label)

    # Terminal line
    print("✅ Logged results to ./vpn_performance.csv")
    print(f"📊 Down: {down_s} Mbps {d_emo} | Up: {up_s} Mbps {u_emo} | Latency: {lat_s} ms {l_emo} | Resp: {resp_label} {r_emo}")

    # CSV logging
    path = "vpn_performance.csv"
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = [
        "Timestamp","Profile","IP",
        "Downlink (Mbps)","Uplink (Mbps)","Latency (ms)",
        "Responsiveness","Responsiveness RPM","Idle RPM"
    ]
    row = [
        timestamp, profile, ip,
        f"{down_s}", f"{up_s}", f"{lat_s}",
        resp_label, resp_rpm if resp_rpm is not None else "",
        idle_rpm if idle_rpm is not None else "",
    ]

    write_header = False
    try:
        with open(path, "r", newline="") as _:
            pass
    except FileNotFoundError:
        write_header = True

    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(header)
        w.writerow(row)

if __name__ == "__main__":
    main()