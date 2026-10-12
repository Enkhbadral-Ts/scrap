#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_data_usage.py
===================
CM5 дээрх 4G Дата симийн зарцуулалт, үлдэгдлийг шалгах скрипт.
MobiCom болон G-Mobile операторыг автоматаар таньж, хоёуланд нь зохицон ажиллана.
- MobiCom: 592 дугаар луу "B" илгээж үлдэгдэл лавлах
- G-Mobile: 236 дугаар луу "D" илгээж үлдэгдэл лавлах
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

def detect_carrier():
    """
    Модем дээр идэвхтэй байгаа үүрэн телефоны операторыг (MobiCom, G-Mobile) автоматаар таних.
    """
    try:
        out = subprocess.getoutput("sudo mmcli -m 0 2>/dev/null")
        sim_out = subprocess.getoutput("sudo mmcli -i 0 2>/dev/null || sudo mmcli -m 0 --sim=0 2>/dev/null")
        combined = out + " " + sim_out
        
        op_id = ""
        op_name = ""
        m = re.search(r"operator name:\s*([^\n\r]+)", combined, re.I)
        if m:
            op_name = m.group(1).strip()
        m2 = re.search(r"operator id:\s*(\d+)", combined, re.I)
        if m2:
            op_id = m2.group(1).strip()
            
        if "mobi" in op_name.lower() or op_id.startswith("42801"):
            return {
                "code": "mobicom",
                "name": "MobiCom",
                "full_label": "MobiCom 4G LTE",
                "sms_num": "592",
                "sms_text": "B",
                "sender_match": r"592\b",
                "default_plan_gb": 5.0
            }
        elif "gmobile" in op_name.lower() or "g-mobile" in op_name.lower() or op_id.startswith("42806"):
            return {
                "code": "gmobile",
                "name": "G-Mobile",
                "full_label": "G-Mobile 4G LTE",
                "sms_num": "236",
                "sms_text": "D",
                "sender_match": r"236\b",
                "default_plan_gb": 150.0
            }
        elif "unitel" in op_name.lower() or op_id.startswith("42888"):
            return {
                "code": "unitel",
                "name": "Unitel",
                "full_label": "Unitel 4G LTE",
                "sms_num": "1414",
                "sms_text": "DATA",
                "sender_match": r"1414\b",
                "default_plan_gb": 10.0
            }
        elif "skytel" in op_name.lower() or op_id.startswith("42899"):
            return {
                "code": "skytel",
                "name": "Skytel",
                "full_label": "Skytel 4G LTE",
                "sms_num": "123",
                "sms_text": "DATA",
                "sender_match": r"123\b",
                "default_plan_gb": 10.0
            }
            
        # Fallback check from SMS inbox
        sms_out = subprocess.getoutput("sudo mmcli -m 0 --messaging-list-sms 2>/dev/null")
        if "236" in sms_out:
            return {
                "code": "gmobile",
                "name": "G-Mobile",
                "full_label": "G-Mobile 4G LTE",
                "sms_num": "236",
                "sms_text": "D",
                "sender_match": r"236\b",
                "default_plan_gb": 150.0
            }
        elif "592" in sms_out:
            return {
                "code": "mobicom",
                "name": "MobiCom",
                "full_label": "MobiCom 4G LTE",
                "sms_num": "592",
                "sms_text": "B",
                "sender_match": r"592\b",
                "default_plan_gb": 5.0
            }
    except Exception:
        pass
        
    return {
        "code": "mobicom",
        "name": "MobiCom",
        "full_label": "MobiCom 4G LTE",
        "sms_num": "592",
        "sms_text": "B",
        "sender_match": r"592\b",
        "default_plan_gb": 5.0
    }

def parse_carrier_sms(data_text):
    """MobiCom болон G-Mobile аль алиных нь SMS хариуг задалж унших"""
    res = {
        'packages': [],
        'total_plan_mb': 0.0,
        'total_used_mb': 0.0,
        'total_remaining_mb': 0.0,
        'expiry': None,
        'summary': ''
    }
    if not data_text:
        return res

    # Дуусах огноог хайх
    exp_m = re.findall(r'(?:duusah hugatsaa|xugacaa|hugatsaa)[:\s]*([\d\.\-]+(?:\s+[\d:]+)?)', data_text, re.I)
    if exp_m:
        res['expiry'] = exp_m[-1].strip()

    # 1. G-Mobile: 'Tany dansand 153564.75MB undsen data baina'
    gm_undsen = re.search(r'([\d,]+(?:\.\d+)?)\s*(MB|GB)\s+undsen\s+data', data_text, re.I)
    if not gm_undsen:
        gm_undsen = re.search(r'dansand\s*([\d,]+(?:\.\d+)?)\s*(MB|GB)', data_text, re.I)
    if gm_undsen:
        rem_str = gm_undsen.group(1).replace(',', '')
        rem_val = float(rem_str) * (1024 if gm_undsen.group(2).upper() == 'GB' else 1)
        plan_val = 153600.0 if rem_val > 50000 else (float(int(rem_val / 1024) + 1) * 1024)
        used_val = max(0.0, plan_val - rem_val)
        res['packages'].append({'name': 'Үндсэн дата', 'plan_mb': plan_val, 'remaining_mb': rem_val, 'used_mb': used_val})

    # 2. G-Mobile хоногийн багц: 'X honogiin data bagts... uldegdel Y (MB|GB)'
    honog_m = re.search(r'(\d+)\s*honogiin\s*data\s*bagts.*?uldegdel\s*([\d,]+(?:\.\d+)?)\s*(MB|GB)', data_text, re.I)
    if honog_m:
        h_name = f"{honog_m.group(1)} хоногийн багц"
        rem_str = honog_m.group(2).replace(',', '')
        rem_val = float(rem_str) * (1024 if honog_m.group(3).upper() == 'GB' else 1)
        res['packages'].append({'name': h_name, 'plan_mb': rem_val, 'remaining_mb': rem_val, 'used_mb': 0.0})

    # 3. MobiCom / G-Mobile урамшуулал: 'uramshuulliin X (GB|MB)... uldegdel Y (MB|GB)'
    uram_m = re.search(r'uramshuull?iin\s*([\d\.]+)\s*(GB|MB).*?uldegdel\s*([\d,]+(?:\.\d+)?)\s*(MB|GB)', data_text, re.I)
    if uram_m:
        plan_val = float(uram_m.group(1)) * (1024 if uram_m.group(2).upper() == 'GB' else 1)
        rem_str = uram_m.group(3).replace(',', '')
        rem_val = float(rem_str) * (1024 if uram_m.group(4).upper() == 'GB' else 1)
        used_val = max(0.0, plan_val - rem_val)
        res['packages'].append({'name': 'Урамшуулал', 'plan_mb': plan_val, 'remaining_mb': rem_val, 'used_mb': used_val})

    # 4. MobiCom Дагалдах багц: 'Dagaldah X (GB|MB)... ashiglasan Y (MB|GB)'
    dag_m = re.search(r'Dagaldah\s*([\d\.]+)\s*(GB|MB).*?ashiglasan\s*([\d,]+(?:\.\d+)?)\s*(MB|GB)', data_text, re.I)
    if dag_m:
        plan_val = float(dag_m.group(1)) * (1024 if dag_m.group(2).upper() == 'GB' else 1)
        used_str = dag_m.group(3).replace(',', '')
        used_val = float(used_str) * (1024 if dag_m.group(4).upper() == 'GB' else 1)
        rem_val = max(0.0, plan_val - used_val)
        res['packages'].append({'name': 'Дагалдах багц', 'plan_mb': plan_val, 'remaining_mb': rem_val, 'used_mb': used_val})

    # 5. MobiCom ерөнхий / Single fallback
    if not res['packages']:
        single_rem = re.search(r'uldegdel\s*([\d,]+(?:\.\d+)?)\s*(MB|GB)', data_text, re.I)
        single_used = re.search(r'ashiglasan\s*([\d,]+(?:\.\d+)?)\s*(MB|GB)', data_text, re.I)
        single_plan = re.search(r'(\d+(?:\.\d+)?)\s*GB\s*data', data_text, re.I)
        plan_val = float(single_plan.group(1)) * 1024 if single_plan else 5120.0
        rem_val = 0.0
        used_val = 0.0
        if single_rem:
            rem_val = float(single_rem.group(1).replace(',', '')) * (1024 if single_rem.group(2).upper() == 'GB' else 1)
            used_val = max(0.0, plan_val - rem_val)
        elif single_used:
            used_val = float(single_used.group(1).replace(',', '')) * (1024 if single_used.group(2).upper() == 'GB' else 1)
            rem_val = max(0.0, plan_val - used_val)
        if single_rem or single_used:
            res['packages'].append({'name': 'Үндсэн багц', 'plan_mb': plan_val, 'remaining_mb': rem_val, 'used_mb': used_val})

    for p in res['packages']:
        res['total_plan_mb'] += p['plan_mb']
        res['total_remaining_mb'] += p['remaining_mb']
        res['total_used_mb'] += p['used_mb']

    if res['total_remaining_mb'] > 0:
        rem_gb = res['total_remaining_mb'] / 1024
        pkg_summaries = []
        for p in res['packages']:
            p_rem = f"{p['remaining_mb']/1024:.2f} GB" if p['remaining_mb'] >= 1024 else f"{p['remaining_mb']:.1f} MB"
            pkg_summaries.append(f"{p['name']}: {p_rem}")
        res['summary'] = f"🟢 Нийт үлдсэн: {rem_gb:.2f} GB ({' + '.join(pkg_summaries)}) | Хүчинтэй: {res['expiry'] or 'Тодорхойгүй'}"
    else:
        res['summary'] = data_text

    return res

def get_latest_carrier_sms(carrier_info):
    """ModemManager-оос тухайн оператороос ирсэн сүүлийн SMS хариуг унших"""
    try:
        out = subprocess.getoutput("sudo mmcli -m 0 --messaging-list-sms 2>/dev/null")
        sms_ids = [int(x) for x in re.findall(r'/SMS/(\d+)\s+\(received\)', out)]
        sms_ids.sort(reverse=True)
        for sid in sms_ids:
            detail = subprocess.getoutput(f"sudo mmcli -s {sid} 2>/dev/null")
            if re.search(r'number:\s*(\+?976)?' + carrier_info['sender_match'], detail, re.I):
                m = re.search(r'text:\s*([^\n\r]+)', detail)
                if m:
                    return m.group(1).strip()
    except Exception:
        pass
    return None

def send_carrier_check_sms(carrier_info):
    """Оператор луу үлдэгдэл лавлах SMS илгээх (MobiCom: 592/'B', G-Mobile: 236/'D')"""
    dest = carrier_info['sms_num']
    text = carrier_info['sms_text']
    c_name = carrier_info['name']
    print(f"⏳ {c_name} ({dest}) рүү дата үлдэгдэл шалгах '{text}' мессеж илгээж байна...")
    try:
        res = subprocess.getoutput(f"sudo mmcli -m 0 --messaging-create-sms=\"text='{text}',number='{dest}'\" 2>/dev/null")
        sms_id_match = re.search(r'/SMS/(\d+)', res)
        if not sms_id_match:
            print(f"❌ Мессеж үүсгэхэд алдаа гарлаа: {res}")
            return get_latest_carrier_sms(carrier_info)
        sid = sms_id_match.group(1)
        send_res = subprocess.getoutput(f"sudo mmcli -s {sid} --send 2>/dev/null")
        subprocess.getoutput(f"sudo mmcli -m 0 --messaging-delete-sms={sid} 2>/dev/null")
        
        print("📨 Мессеж амжилттай илгээгдлээ. Хариу хүлээж байна (5 секунд)...")
        time.sleep(5)
        return get_latest_carrier_sms(carrier_info)
    except Exception as e:
        print(f"❌ Алдаа: {e}")
        return None

def get_stats(carrier_override=None, check_sms=False):
    carrier = detect_carrier()
    if carrier_override:
        if carrier_override.lower() == "mobicom":
            carrier = {
                "code": "mobicom", "name": "MobiCom", "full_label": "MobiCom 4G LTE",
                "sms_num": "592", "sms_text": "B", "sender_match": r"592\b", "default_plan_gb": 5.0
            }
        elif carrier_override.lower() == "gmobile":
            carrier = {
                "code": "gmobile", "name": "G-Mobile", "full_label": "G-Mobile 4G LTE",
                "sms_num": "236", "sms_text": "D", "sender_match": r"236\b", "default_plan_gb": 150.0
            }

    carrier_msg = None
    if check_sms:
        carrier_msg = send_carrier_check_sms(carrier)
    if not carrier_msg:
        carrier_msg = get_latest_carrier_sms(carrier)

    parsed = parse_carrier_sms(carrier_msg) if carrier_msg else None

    total_plan_gb = carrier["default_plan_gb"]
    if parsed and parsed.get("total_plan_mb", 0) > 0:
        total_plan_gb = parsed["total_plan_mb"] / 1024

    accumulated_bytes = 0
    if os.path.exists(DATA_USAGE_FILE):
        try:
            with open(DATA_USAGE_FILE, "r") as f:
                d = json.load(f)
                accumulated_bytes = d.get("accumulated_bytes", 0)
        except Exception:
            pass

    rx_path = "/sys/class/net/wwan0/statistics/rx_bytes"
    tx_path = "/sys/class/net/wwan0/statistics/tx_bytes"
    raw_rx = 0
    raw_tx = 0
    if os.path.exists(rx_path) and os.path.exists(tx_path):
        try:
            with open(rx_path) as f: raw_rx = int(f.read().strip())
            with open(tx_path) as f: raw_tx = int(f.read().strip())
            if accumulated_bytes == 0:
                accumulated_bytes = raw_rx + raw_tx
        except Exception:
            pass

    total_bytes = max(accumulated_bytes, raw_rx + raw_tx)
    used_mb = total_bytes / (1024 * 1024)
    used_gb = used_mb / 1024
    
    # Remaining GB from SMS if available, otherwise calculated
    if parsed and parsed.get("total_remaining_mb", 0) > 0:
        remaining_gb = parsed["total_remaining_mb"] / 1024
    else:
        remaining_gb = max(0.0, total_plan_gb - used_gb)
    pct = (used_gb / total_plan_gb * 100) if total_plan_gb > 0 else 0

    public_ip = subprocess.getoutput("curl -s -4 --max-time 2 https://icanhazip.com || echo 'Холбогдож байна...'").strip()

    status_data = {
        "carrier_code": carrier["code"],
        "carrier_name": carrier["name"],
        "carrier_label": carrier["full_label"],
        "plan_gb": round(total_plan_gb, 2),
        "accumulated_bytes": total_bytes,
        "used_mb": round(used_mb, 2),
        "used_gb": round(used_gb, 4),
        "remaining_gb": round(remaining_gb, 2),
        "carrier_sms": carrier_msg,
        "carrier_parsed": parsed,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(DATA_USAGE_FILE, "w") as f:
            json.dump(status_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    print("=" * 68)
    print(f"📡  {carrier['full_label'].upper()} ДАТА ЗАРЦУУЛАЛТ БОЛОН ҮЛДЭГДЭЛ (CM5)")
    print("=" * 68)
    print(f"🏢 Оператор:              {carrier['name']} (Автомат танигдсан)")
    print(f"📦 Нийт багцын эрх:       {total_plan_gb:.2f} GB")
    if used_mb < 1024:
        print(f"📉 Модемийн ашигласан:    {used_mb:.2f} MB ({pct:.3f}%)")
    else:
        print(f"📉 Модемийн ашигласан:    {used_gb:.2f} GB ({pct:.2f}%)")
    print(f"🟢 Үлдсэн дата (Нийт):    {remaining_gb:.2f} GB")
    if parsed and parsed.get("summary"):
        print(f"📋 Багцын задаргаа:       {parsed['summary']}")
    if carrier_msg:
        print(f"📩 {carrier['name']} SMS ({carrier['sms_num']}): {carrier_msg}")
    print(f"📶 Модем Public IP:        {public_ip}")
    print(f"🌐 4G LTE Модем гарц:      wwan0 ({carrier['name']})")
    print(f"🕒 Шалгасан огноо:         {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 68)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CM5 Dual-Carrier (MobiCom / G-Mobile) Data Usage Checker")
    parser.add_argument("--carrier", choices=["auto", "mobicom", "gmobile"], default="auto", help="Операторыг гараар сонгох (default: auto)")
    parser.add_argument("--check-sms", action="store_true", help="Оператор луу SMS илгээж албан ёсны үлдэгдэл лавлах")
    args = parser.parse_args()
    carrier_arg = None if args.carrier == "auto" else args.carrier
    get_stats(carrier_override=carrier_arg, check_sms=args.check_sms)
