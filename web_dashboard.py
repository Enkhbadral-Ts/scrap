#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web_dashboard.py
================
Raspberry Pi CM5 дээр ажиллаж буй тендер таталтыг гар утас (iPhone/Android),
компьютерээс шууд хөтчөөр (Safari/Chrome) бодит хугацаанд хянах хөнгөн вэб сервер.
Порт: 8088
"""

import os
import re
import json
import time
import sqlite3
import subprocess
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse

PORT = 8088
HARVEST_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_PATH = os.path.join(HARVEST_DIR, "harvest_status.json")
DB_PATH = os.path.join(HARVEST_DIR, "tender_bidders.db")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="mn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Тендер 24/7 Таталт | CM5 Хяналт</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #090d16;
            --card-bg: rgba(22, 28, 45, 0.7);
            --card-border: rgba(255, 255, 255, 0.08);
            --primary: #3b82f6;
            --accent: #10b981;
            --accent-glow: rgba(16, 185, 129, 0.25);
            --warning: #f59e0b;
            --danger: #ef4444;
            --text-main: #f8fafc;
            --text-sub: #94a3b8;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            background-color: var(--bg);
            background-image: 
                radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.12) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(16, 185, 129, 0.08) 0px, transparent 50%);
            color: var(--text-main);
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            min-height: 100vh;
            padding: 16px;
            display: flex;
            justify-content: center;
        }

        .container {
            width: 100%;
            max-width: 580px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        /* Header Card */
        .card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 20px;
            padding: 20px;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
        }

        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .device-info {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .device-icon {
            width: 44px;
            height: 44px;
            background: rgba(59, 130, 246, 0.15);
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
        }

        .device-title {
            font-size: 17px;
            font-weight: 700;
            color: #fff;
            letter-spacing: -0.3px;
        }

        .device-sub {
            font-size: 12px;
            color: var(--text-sub);
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .live-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
            padding: 6px 12px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
        }

        .pulse-dot {
            width: 8px;
            height: 8px;
            background: #10b981;
            border-radius: 50%;
            box-shadow: 0 0 10px #10b981;
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.9); opacity: 0.7; }
            50% { transform: scale(1.3); opacity: 1; box-shadow: 0 0 14px #10b981; }
            100% { transform: scale(0.9); opacity: 0.7; }
        }

        /* Progress Section */
        .progress-box {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .progress-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
        }

        .progress-percent {
            font-size: 40px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            background: linear-gradient(135deg, #60a5fa, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            line-height: 1;
        }

        .progress-numbers {
            text-align: right;
            font-size: 13px;
            color: var(--text-sub);
            font-family: 'JetBrains Mono', monospace;
        }

        .progress-numbers strong {
            color: #fff;
            font-size: 15px;
        }

        .bar-container {
            width: 100%;
            height: 14px;
            background: rgba(255, 255, 255, 0.06);
            border-radius: 999px;
            overflow: hidden;
            position: relative;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }

        .bar-fill {
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, #3b82f6, #10b981);
            border-radius: 999px;
            transition: width 0.5s ease-out;
            box-shadow: 0 0 12px rgba(52, 211, 153, 0.4);
        }

        /* Grid Cards */
        .grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }

        .stat-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 14px 16px;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .stat-label {
            font-size: 12px;
            font-weight: 500;
            color: var(--text-sub);
        }

        .stat-val {
            font-size: 22px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            color: #fff;
        }

        .val-win { color: #34d399; }
        .val-lost { color: #f87171; }
        .val-speed { color: #60a5fa; }
        .val-eta { color: #fbbf24; }

        /* Meta bar */
        .meta-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
            font-size: 13px;
        }

        .meta-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .meta-row:last-child {
            border-bottom: none;
            padding-bottom: 0;
        }

        .meta-key {
            color: var(--text-sub);
        }

        .meta-val {
            color: #e2e8f0;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 500;
        }

        .badge-net {
            background: rgba(59, 130, 246, 0.15);
            color: #93c5fd;
            padding: 2px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
        }

        .footer {
            text-align: center;
            font-size: 11px;
            color: #64748b;
            padding: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="card header">
            <div class="device-info">
                <div class="device-icon">🍓</div>
                <div>
                    <div class="device-title">CM5 Harvester</div>
                    <div class="device-sub">
                        <span>G-Mobile 4G LTE (150GB)</span>
                        <span>•</span>
                        <span id="uptime-text">NVMe SSD</span>
                    </div>
                </div>
            </div>
            <div class="live-badge" id="live-badge">
                <div class="pulse-dot"></div>
                <span id="status-title">ONLINE</span>
            </div>
        </div>

        <!-- Progress Card -->
        <div class="card progress-box">
            <div class="progress-header">
                <div class="progress-percent" id="pct-val">0.0%</div>
                <div class="progress-numbers">
                    <div id="tenders-ratio"><strong>0</strong> / 0</div>
                    <div style="font-size: 11px; margin-top: 2px;">Тендер боловсруулсан</div>
                </div>
            </div>
            <div class="bar-container">
                <div class="bar-fill" id="bar-fill"></div>
            </div>
        </div>

        <!-- Key Stats Grid -->
        <div class="grid">
            <div class="stat-card">
                <div class="stat-label">👥 Нийт Оролцогчид</div>
                <div class="stat-val" id="total-bidders">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">⚡ Татах хурд</div>
                <div class="stat-val val-speed" id="speed-val">0.0 /с</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">🏆 Шалгарсан (Winners)</div>
                <div class="stat-val val-win" id="winners-val">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">❌ Хасагдсан / Татгалзсан</div>
                <div class="stat-val val-lost" id="losers-val">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">⏱️ Дуусах хугацаа (ETA)</div>
                <div class="stat-val val-eta" id="eta-val">--:--:--</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">⚠️ Алдаа (Errors)</div>
                <div class="stat-val" id="err-val" style="color: #34d399;">0</div>
            </div>
        </div>

        <!-- 150GB Cellular Data Meter Card -->
        <div class="card data-box" style="border: 1px solid rgba(59, 130, 246, 0.3); background: rgba(15, 23, 42, 0.75);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 16px;">📊</span>
                    <span style="font-weight: 700; font-size: 14px; color: #f1f5f9;">G-Mobile 150GB Дата Хяналт</span>
                </div>
                <div style="font-size: 12px; color: #34d399; font-weight: 700;" id="data-remaining">150.00 GB үлдсэн</div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px;">
                <span id="data-used" style="font-weight: 600; color: #60a5fa;">0.00 MB ашигласан</span>
                <span id="data-pct" style="color: #94a3b8; font-size: 12px;">0.00%</span>
            </div>
            <div class="bar-container" style="height: 8px; margin-bottom: 8px;">
                <div class="bar-fill" id="data-bar-fill" style="width: 0.1%; background: linear-gradient(90deg, #3b82f6, #10b981);"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 11px; color: #64748b; margin-bottom: 6px;">
                <span>📶 4G Гарц: <strong>wwan0 (G-Mobile)</strong></span>
                <span>🔄 Систем update: <strong style="color: #34d399;">Зөвхөн Wi-Fi (wlan0)</strong></span>
            </div>
            <!-- Carrier Official SMS Verification Card -->
            <div id="carrier-sms-box" style="margin-top: 10px; font-size: 11.5px; color: #cbd5e1; background: rgba(15, 23, 42, 0.85); padding: 10px 12px; border-radius: 8px; border: 1px solid rgba(59, 130, 246, 0.35); border-left: 4px solid #10b981;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <span style="font-size: 13px;">📩</span>
                        <span style="font-weight: 700; color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">G-Mobile SMS Лавлагаа (236)</span>
                    </div>
                    <button id="btn-check-sms" onclick="sendSmsCheck()" style="background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #ffffff; border: 1px solid rgba(255,255,255,0.15); padding: 5px 12px; border-radius: 6px; font-size: 11px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); transition: all 0.2s ease;">
                        <span id="sms-btn-icon">💬</span>
                        <span id="sms-btn-text">Үлдэгдэл шалгах</span>
                    </button>
                </div>
                <div id="carrier-sms-val" style="color: #f1f5f9; font-weight: 500; line-height: 1.45; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', monospace; background: rgba(0,0,0,0.3); padding: 8px 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05); min-height: 20px;">
                    Шалгаж байна...
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px; font-size: 10px; color: #64748b;">
                    <span>Заавар: <code>D ➔ 236</code> руу мессеж илгээнэ</span>
                    <span id="carrier-sms-time"></span>
                </div>
            </div>
        </div>

        <!-- System & Network Meta -->
        <div class="card meta-list">
            <div class="meta-row">
                <span class="meta-key">📶 Гарч буй Public IP</span>
                <span class="meta-val"><span class="badge-net" id="public-ip">Шалгаж байна...</span></span>
            </div>
            <div class="meta-row">
                <span class="meta-key">💾 SQLite бааз (Нийт тендер)</span>
                <span class="meta-val" id="db-total-tenders">--</span>
            </div>
            <div class="meta-row">
                <span class="meta-key">🏢 SQLite бааз (Нийт оролцогчид)</span>
                <span class="meta-val" id="db-total-bidders">--</span>
            </div>
            <div class="meta-row">
                <span class="meta-key">🕒 Сүүлийн шинэчлэл</span>
                <span class="meta-val" id="updated-at">--:--:--</span>
            </div>
        </div>

        <div class="footer">
            24/7 Background Systemd Service • Auto-rotates 4G IP on Cloudflare Rate Limits
        </div>
    </div>

    <script>
        let cachedIp = "";

        async function updateStatus() {
            try {
                const res = await fetch('/api/status');
                if (!res.ok) throw new Error('Network response error');
                const data = await res.json();

                // Live badge
                const isRunning = data.is_running;
                const badge = document.getElementById('live-badge');
                const statusTitle = document.getElementById('status-title');
                if (isRunning) {
                    badge.style.background = 'rgba(16, 185, 129, 0.15)';
                    badge.style.color = '#34d399';
                    badge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
                    statusTitle.innerText = 'ONLINE';
                } else {
                    badge.style.background = 'rgba(239, 68, 68, 0.15)';
                    badge.style.color = '#f87171';
                    badge.style.borderColor = 'rgba(239, 68, 68, 0.3)';
                    statusTitle.innerText = 'PAUSED';
                }

                // Progress
                const pct = (data.progress_percent || 0).toFixed(1);
                document.getElementById('pct-val').innerText = pct + '%';
                document.getElementById('bar-fill').style.width = Math.min(100, Math.max(0, pct)) + '%';
                
                const done = (data.processed_tenders || 0).toLocaleString();
                const total = (data.total_tenders || 0).toLocaleString();
                document.getElementById('tenders-ratio').innerHTML = `<strong>${done}</strong> / ${total}`;

                // Stats
                document.getElementById('total-bidders').innerText = (data.total_bidders || 0).toLocaleString();
                document.getElementById('speed-val').innerText = (data.speed_per_second || 0).toFixed(1) + ' /с';
                document.getElementById('winners-val').innerText = (data.total_winners || 0).toLocaleString();
                document.getElementById('losers-val').innerText = (data.total_losers || 0).toLocaleString();
                document.getElementById('eta-val').innerText = data.eta || '--:--:--';
                
                const errCount = data.total_errors || 0;
                const errEl = document.getElementById('err-val');
                errEl.innerText = errCount;
                if (errCount > 0) {
                    errEl.style.color = '#f87171';
                } else {
                    errEl.style.color = '#34d399';
                }

                // Meta
                if (data.public_ip) {
                    document.getElementById('public-ip').innerText = data.public_ip;
                }
                if (data.db_total_tenders) {
                    document.getElementById('db-total-tenders').innerText = Number(data.db_total_tenders).toLocaleString();
                }
                if (data.db_total_bidders) {
                    document.getElementById('db-total-bidders').innerText = Number(data.db_total_bidders).toLocaleString();
                }
                // Data Usage
                if (data.data_usage) {
                    const du = data.data_usage;
                    const usedText = du.used_mb >= 1024 
                        ? (du.used_gb.toFixed(2) + ' GB') 
                        : (du.used_mb.toFixed(2) + ' MB');
                    document.getElementById('data-used').innerText = usedText + ' ашигласан';
                    document.getElementById('data-pct').innerText = du.used_pct.toFixed(3) + '%';
                    document.getElementById('data-remaining').innerText = du.remaining_gb.toFixed(2) + ' GB үлдсэн';
                    document.getElementById('data-bar-fill').style.width = Math.max(0.2, Math.min(100, du.used_pct)) + '%';
                    if (du.carrier_sms && !isSmsChecking) {
                        const smsVal = document.getElementById('carrier-sms-val');
                        smsVal.innerText = du.carrier_sms;
                    }
                }

                if (data.updated_at) {
                    document.getElementById('updated-at').innerText = data.updated_at;
                }
            } catch (e) {
                console.error('Fetch error:', e);
                document.getElementById('status-title').innerText = 'CONNECTING...';
            }
        }

        let isSmsChecking = false;

        async function sendSmsCheck() {
            if (isSmsChecking) return;
            isSmsChecking = true;
            
            const btn = document.getElementById('btn-check-sms');
            const btnText = document.getElementById('sms-btn-text');
            const btnIcon = document.getElementById('sms-btn-icon');
            const smsVal = document.getElementById('carrier-sms-val');
            const smsTime = document.getElementById('carrier-sms-time');

            btn.disabled = true;
            btn.style.opacity = '0.7';
            btn.style.cursor = 'not-allowed';
            btnIcon.innerText = '⏳';
            btnText.innerText = 'Илгээж байна...';
            smsVal.innerHTML = '<span style="color: #60a5fa;">📡 4G модемоос G-Mobile (236) руу "D" мессеж илгээлээ. Хариу хүлээж байна (4-6с)...</span>';

            try {
                const res = await fetch('/api/sms/check', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    btnIcon.innerText = '✅';
                    btnText.innerText = 'Ирсэн!';
                    smsVal.innerHTML = `<span style="color: #34d399; font-weight: 600;">${data.sms_text}</span>`;
                    smsTime.innerText = 'Шалгасан: ' + (data.timestamp || new Date().toLocaleTimeString());
                    setTimeout(updateStatus, 1000);
                } else {
                    btnIcon.innerText = '⚠️';
                    btnText.innerText = 'Алдаа';
                    smsVal.innerHTML = `<span style="color: #f87171;">${data.error || 'Хариу ирсэнгүй'}</span>`;
                }
            } catch (err) {
                btnIcon.innerText = '❌';
                btnText.innerText = 'Алдаа';
                smsVal.innerHTML = `<span style="color: #f87171;">Холболтын алдаа: ${err.message}</span>`;
            } finally {
                setTimeout(() => {
                    btn.disabled = false;
                    btn.style.opacity = '1';
                    btn.style.cursor = 'pointer';
                    btnIcon.innerText = '💬';
                    btnText.innerText = 'Дахин шалгах';
                    isSmsChecking = false;
                }, 3000);
            }
        }

        // Initial fetch and loop every 2.5 seconds
        updateStatus();
        setInterval(updateStatus, 2500);
    </script>
</body>
</html>
"""

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_USAGE_FILE = os.path.join(SCRIPT_DIR, "sim_data_usage.json")
TOTAL_PLAN_GB = 150.0
last_raw_rx = 0
last_raw_tx = 0
accumulated_bytes = 0
last_save_time = 0
cached_carrier_sms = None

def get_data_usage():
    global last_raw_rx, last_raw_tx, accumulated_bytes, last_save_time, cached_carrier_sms
    now = time.time()
    
    if os.path.exists(DATA_USAGE_FILE):
        try:
            with open(DATA_USAGE_FILE, "r") as f:
                d_file = json.load(f)
                if accumulated_bytes == 0:
                    accumulated_bytes = d_file.get("accumulated_bytes", 0)
                if d_file.get("carrier_sms"):
                    cached_carrier_sms = d_file.get("carrier_sms")
        except Exception:
            pass

    rx_path = "/sys/class/net/wwan0/statistics/rx_bytes"
    tx_path = "/sys/class/net/wwan0/statistics/tx_bytes"

    if os.path.exists(rx_path) and os.path.exists(tx_path):
        try:
            with open(rx_path) as f:
                curr_rx = int(f.read().strip())
            with open(tx_path) as f:
                curr_tx = int(f.read().strip())

            if last_raw_rx > 0:
                d_rx = curr_rx - last_raw_rx if curr_rx >= last_raw_rx else curr_rx
                d_tx = curr_tx - last_raw_tx if curr_tx >= last_raw_tx else curr_tx
                accumulated_bytes += (d_rx + d_tx)
            else:
                accumulated_bytes += (curr_rx + curr_tx)

            last_raw_rx = curr_rx
            last_raw_tx = curr_tx

            if now - last_save_time > 15:
                last_save_time = now
                try:
                    with open(DATA_USAGE_FILE, "w") as f:
                        json.dump({
                            "plan_gb": TOTAL_PLAN_GB,
                            "accumulated_bytes": accumulated_bytes,
                            "carrier_sms": cached_carrier_sms,
                            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
        except Exception:
            pass

    used_mb = accumulated_bytes / (1024 * 1024)
    used_gb = used_mb / 1024
    remaining_gb = max(0.0, TOTAL_PLAN_GB - used_gb)
    used_pct = (used_gb / TOTAL_PLAN_GB) * 100

    return {
        "plan_gb": TOTAL_PLAN_GB,
        "used_bytes": accumulated_bytes,
        "used_mb": round(used_mb, 2),
        "used_gb": round(used_gb, 3),
        "remaining_gb": round(remaining_gb, 2),
        "used_pct": round(used_pct, 3),
        "carrier_sms": cached_carrier_sms
    }

sms_check_lock = threading.Lock()
last_sms_check_time = 0

def get_latest_carrier_sms():
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

def trigger_carrier_sms_check():
    global cached_carrier_sms, last_sms_check_time
    now = time.time()
    if now - last_sms_check_time < 10.0 and cached_carrier_sms:
        return {
            "success": True,
            "sms_text": cached_carrier_sms,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cached": True
        }

    with sms_check_lock:
        try:
            res = subprocess.getoutput("sudo mmcli -m 0 --messaging-create-sms=\"text='D',number='236'\" 2>/dev/null")
            sms_id_match = re.search(r'/SMS/(\d+)', res)
            if not sms_id_match:
                latest = get_latest_carrier_sms()
                if latest:
                    return {"success": True, "sms_text": latest, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                return {"success": False, "error": f"Мессеж үүсгэхэд алдаа: {res}"}

            sid = sms_id_match.group(1)
            send_res = subprocess.getoutput(f"sudo mmcli -s {sid} --send 2>/dev/null")
            if "successfully sent" not in send_res:
                return {"success": False, "error": f"Илгээхэд алдаа: {send_res}"}

            time.sleep(4)
            reply = get_latest_carrier_sms()
            if not reply:
                time.sleep(2)
                reply = get_latest_carrier_sms()

            if reply:
                cached_carrier_sms = reply
                last_sms_check_time = time.time()
                try:
                    current_data = {}
                    if os.path.exists(DATA_USAGE_FILE):
                        with open(DATA_USAGE_FILE, "r") as f:
                            current_data = json.load(f)
                    current_data["carrier_sms"] = reply
                    current_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with open(DATA_USAGE_FILE, "w") as f:
                        json.dump(current_data, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
                return {
                    "success": True,
                    "sms_text": reply,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            else:
                return {"success": False, "error": "236 дугаараас хариу мессеж ирсэнгүй, дахин шалгана уу."}
        except Exception as e:
            return {"success": False, "error": str(e)}

class DashboardHandler(BaseHTTPRequestHandler):
    cached_ip = ""
    last_ip_check = 0

    def log_message(self, format, *args):
        # Suppress noisy HTTP request logs
        return

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Connection", "close")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))

        elif parsed.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Connection", "close")
            self.end_headers()
            
            payload = {}
            if os.path.exists(STATUS_PATH):
                try:
                    with open(STATUS_PATH, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                except Exception:
                    pass

            # Cache public IP for 30s to avoid unnecessary network roundtrips
            now = time.time()
            if now - DashboardHandler.last_ip_check > 30.0 or not DashboardHandler.cached_ip:
                try:
                    ip = subprocess.getoutput("curl -s -4 --max-time 2 https://icanhazip.com || echo ''").strip()
                    if ip and len(ip) < 45:
                        DashboardHandler.cached_ip = ip
                        DashboardHandler.last_ip_check = now
                except Exception:
                    pass

            payload["public_ip"] = DashboardHandler.cached_ip

            # Quick read SQLite counts
            if os.path.exists(DB_PATH):
                try:
                    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=2.0)
                    cur = conn.cursor()
                    cur.execute("SELECT count(*) FROM tender_sync_log;")
                    payload["db_total_tenders"] = cur.fetchone()[0]
                    cur.execute("SELECT count(*) FROM tender_bidders;")
                    payload["db_total_bidders"] = cur.fetchone()[0]
                    conn.close()
                except Exception:
                    pass

            payload["data_usage"] = get_data_usage()

            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

        elif parsed.path == "/api/sms/check":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Connection", "close")
            self.end_headers()
            
            res = trigger_carrier_sms_check()
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))

        else:
            self.send_response(404)
            self.send_header("Connection", "close")
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/sms/check":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Connection", "close")
            self.end_headers()
            
            res = trigger_carrier_sms_check()
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.send_header("Connection", "close")
            self.end_headers()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def main():
    def run_server(port):
        try:
            server = ThreadedHTTPServer(("0.0.0.0", port), DashboardHandler)
            print(f"🚀 CM5 Tender Web Dashboard running on http://0.0.0.0:{port}")
            server.serve_forever()
        except Exception as e:
            print(f"⚠️ Failed to bind port {port}: {e}")

    # Launch Port 80 in background thread
    t = threading.Thread(target=run_server, args=(80,), daemon=True)
    t.start()

    # Launch Port 8088 in main thread
    run_server(PORT)

if __name__ == "__main__":
    main()
