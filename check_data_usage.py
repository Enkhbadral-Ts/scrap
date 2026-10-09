#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_data_usage.py
===================
CM5 дээрх G-Mobile 150GB Дата симийн зарцуулалт, үлдэгдлийг шалгах скрипт.
G-Mobile операторын албан ёсны 236 дугаар луу "D" илгээж үлдэгдэл шалгах боломжтой.
"""

import os
import sys
import re
import time
import json
import argparse
import subprocess
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_USAGE_FILE = os.path.join(SCRIPT_DIR, "sim_data_usage.json")
TOTAL_PLAN_GB = 150.0

def get_latest_carrier_sms():
    """ModemManager-оос 236 дугаараас ирсэн сүүлийн SMS хариуг унших"""
    try:
        out = subprocess.getoutput("sudo mmcli -m 0 --messaging-list-sms 2>/dev/null")
        sms_ids = re.findall(r'/SMS/(\d+)\s+\(received\)', out)
        for sid in reversed(sms_ids):
            detail = subprocess.getoutput(f"sudo mmcli -s {sid} 2>/dev/null")
            if re.search(r'number:\s*(\+?976)?236\b', detail):
                m = re.search(r'text:\s*(.*)', detail)
                if m:
                    return m.group(1).strip()
    except Exception:
        pass
    return None

def send_carrier_check_sms():
    """G-Mobile 236 дугаар луу 'D' мессеж илгээж үлдэгдэл лавлах"""
    print("⏳ G-Mobile (236) рүү дата үлдэгдэл шалгах 'D' мессеж илгээж байна...")
    try:
        res = subprocess.getoutput("sudo mmcli -m 0 --messaging-create-sms=\"text='D',number='236'\"")
        sms_id_match = re.search(r'/SMS/(\d+)', res)
        if not sms_id_match:
            print(f"❌ Мессеж үүсгэхэд алдаа гарлаа: {res}")
            return None
        sid = sms_id_match.group(1)
        send_res = subprocess.getoutput(f"sudo mmcli -s {sid} --send")
        if "successfully sent" not in send_res:
            print(f"❌ Мессеж илгээхэд алдаа: {send_res}")
            return None
        print("📨 Мессеж амжилттай илгээгдлээ. Хариу хүлээж байна (4 секунд)...")
        time.sleep(4)
        return get_latest_carrier_sms()
    except Exception as e:
        print(f"❌ Алдаа: {e}")
        return None

def get_stats(check_sms=False):
    carrier_msg = None
    if check_sms:
        carrier_msg = send_carrier_check_sms()
    if not carrier_msg:
        carrier_msg = get_latest_carrier_sms()

    accumulated_bytes = 0
    if os.path.exists(DATA_USAGE_FILE):
        try:
            with open(DATA_USAGE_FILE, "r") as f:
                accumulated_bytes = json.load(f).get("accumulated_bytes", 0)
        except Exception:
            pass

    rx_path = "/sys/class/net/wwan0/statistics/rx_bytes"
    tx_path = "/sys/class/net/wwan0/statistics/tx_bytes"
    raw_rx = 0
    raw_tx = 0
    if os.path.exists(rx_path) and os.path.exists(tx_path):
        try:
            with open(rx_path) as f:
                raw_rx = int(f.read().strip())
            with open(tx_path) as f:
                raw_tx = int(f.read().strip())
            if accumulated_bytes == 0:
                accumulated_bytes = raw_rx + raw_tx
        except Exception:
            pass

    total_bytes = max(accumulated_bytes, raw_rx + raw_tx)
    used_mb = total_bytes / (1024 * 1024)
    used_gb = used_mb / 1024
    remaining_gb = max(0.0, TOTAL_PLAN_GB - used_gb)
    pct = (used_gb / TOTAL_PLAN_GB) * 100

    public_ip = subprocess.getoutput("curl -s -4 --max-time 2 https://icanhazip.com || echo 'Холбогдож байна...'").strip()

    # Save to status file for dashboard
    status_data = {
        "accumulated_bytes": total_bytes,
        "used_mb": round(used_mb, 2),
        "used_gb": round(used_gb, 4),
        "remaining_gb": round(remaining_gb, 2),
        "carrier_sms": carrier_msg,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(DATA_USAGE_FILE, "w") as f:
            json.dump(status_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    print("=" * 65)
    print("📡  G-MOBILE 150GB ДАТА ЗАРЦУУЛАЛТ БОЛОН ҮЛДЭГДЭЛ (CM5)")
    print("=" * 65)
    print(f"📦 Нийт багцын эрх:       {TOTAL_PLAN_GB:.2f} GB")
    if used_mb < 1024:
        print(f"📉 Ашигласан дата:         {used_mb:.2f} MB ({pct:.3f}%)")
    else:
        print(f"📉 Ашигласан дата:         {used_gb:.2f} GB ({pct:.2f}%)")
    print(f"🟢 Үлдсэн дата (Тооцоолсон): {remaining_gb:.2f} GB")
    if carrier_msg:
        print(f"📩 G-Mobile SMS (236):     {carrier_msg}")
    print(f"📶 Модем Public IP:        {public_ip}")
    print(f"🌐 4G LTE Модем гарц:      wwan0 (G-Mobile)")
    print(f"🔄 Системийн update:       Зөвхөн Wi-Fi (wlan0 Univision)")
    print(f"🕒 Шалгасан огноо:         {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="G-Mobile SIM Data Usage & Carrier Balance Checker")
    parser.add_argument("--check-sms", action="store_true", help="G-Mobile 236 луу SMS илгээж албан ёсны үлдэгдэл лавлах")
    args = parser.parse_args()
    get_stats(check_sms=args.check_sms)
