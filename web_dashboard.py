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
                        <span>MobiCom 4G LTE (99603525)</span>
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

        <!-- MobiCom Cellular Data Meter Card -->
        <div class="card data-box" style="border: 1px solid rgba(59, 130, 246, 0.3); background: rgba(15, 23, 42, 0.75);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 16px;">📊</span>
                    <span style="font-weight: 700; font-size: 14px; color: #f1f5f9;">MobiCom 4G Дата Хяналт</span>
                    <span id="data-live-badge" style="display: none; background: rgba(16, 185, 129, 0.2); border: 1px solid #10b981; color: #34d399; font-size: 10px; font-weight: 600; padding: 2px 7px; border-radius: 10px;">● LIVE ХЯНАЛТ</span>
                </div>
                <div style="font-size: 13px; color: #34d399; font-weight: 700;" id="data-remaining">-- GB үлдсэн</div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px;">
                <span id="data-used" style="font-weight: 600; color: #60a5fa;">-- MB ашигласан</span>
                <span id="data-pct" style="color: #94a3b8; font-size: 12px;">--%</span>
            </div>
            <div class="bar-container" style="height: 8px; margin-bottom: 8px;">
                <div class="bar-fill" id="data-bar-fill" style="width: 0.1%; background: linear-gradient(90deg, #3b82f6, #10b981);"></div>
            </div>

            <!-- Dynamic Package Breakdown Badges -->
            <div id="data-packages" style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; font-size: 11px;"></div>

            <!-- Contract & Payment Status -->
            <div id="carrier-bill-row" style="display: flex; justify-content: space-between; font-size: 11px; color: #93c5fd; background: rgba(30, 58, 138, 0.25); padding: 6px 10px; border-radius: 6px; margin-bottom: 8px; border: 1px solid rgba(59, 130, 246, 0.2);">
                <span>💳 Гэрээний төлбөрийн үлдэгдэл: <strong id="carrier-bill-val" style="color: #34d399;">0₮</strong></span>
                <span id="carrier-expiry-val" style="color: #cbd5e1;">Хүчинтэй: 2026-10-31 23:59</span>
            </div>

            <div style="display: flex; justify-content: space-between; font-size: 11px; color: #64748b; margin-bottom: 6px;">
                <span>📶 Идэвхтэй гарц: <strong id="gateway-val" style="color: #34d399;">Шалгаж байна...</strong></span>
                <span>🛡️ Автомат шилжилт: <strong style="color: #60a5fa;">MobiCom 4G Failover бэлэн</strong></span>
            </div>
            <!-- Carrier Official SMS Verification Card -->
            <div id="carrier-sms-box" style="margin-top: 10px; font-size: 11.5px; color: #cbd5e1; background: rgba(15, 23, 42, 0.85); padding: 10px 12px; border-radius: 8px; border: 1px solid rgba(59, 130, 246, 0.35); border-left: 4px solid #10b981;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <span style="font-size: 13px;">📩</span>
                        <span style="font-weight: 700; color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">MobiCom Албан ёсны SMS (592)</span>
                    </div>
                    <button id="btn-check-sms" onclick="sendSmsCheck()" style="background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #ffffff; border: 1px solid rgba(255,255,255,0.15); padding: 5px 12px; border-radius: 6px; font-size: 11px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); transition: all 0.2s ease;">
                        <span id="sms-btn-icon">💬</span>
                        <span id="sms-btn-text">Үлдэгдэл шалгах (592)</span>
                    </button>
                </div>
                <div id="carrier-sms-val" style="color: #f1f5f9; font-weight: 500; line-height: 1.45; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', monospace; background: rgba(0,0,0,0.3); padding: 8px 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05); min-height: 20px;">
                    Шалгаж байна...
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px; font-size: 10px; color: #64748b;">
                    <span>Заавар: <code>B ➔ 592</code> руу мессеж илгээж бодит үлдэгдлийг татна</span>
                    <span id="carrier-sms-time"></span>
                </div>
            </div>
        </div>

        <!-- Live Feed Card: Recent Harvested Bidders -->
        <div class="card" style="margin-top: 14px; border: 1px solid rgba(255, 255, 255, 0.08); background: rgba(15, 23, 42, 0.75);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 16px;">⚡</span>
                    <span style="font-weight: 700; font-size: 13.5px; color: #f1f5f9;">Бодит хугацааны таталт (Сүүлийн оролцогчид)</span>
                </div>
                <div class="live-badge" style="padding: 2px 8px; font-size: 10.5px;">
                    <span class="pulse-dot" style="width: 6px; height: 6px;"></span> Шууд бааз
                </div>
            </div>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 11.5px; text-align: left;">
                    <thead>
                        <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.1); color: var(--text-sub);">
                            <th style="padding: 5px 6px;">Компани</th>
                            <th style="padding: 5px 6px;">Тендер</th>
                            <th style="padding: 5px 6px; text-align: right;">Үнийн санал</th>
                            <th style="padding: 5px 6px; text-align: center;">Төлөв</th>
                            <th style="padding: 5px 6px; text-align: right;">Огноо</th>
                        </tr>
                    </thead>
                    <tbody id="live-bidders-tbody">
                        <tr><td colspan="5" style="text-align: center; color: var(--text-sub); padding: 12px;">Уншиж байна...</td></tr>
                    </tbody>
                </table>
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

                // Progress: use cumulative total
                const totalTendersCount = data.total_tenders || 131871;
                const doneTendersCount = data.processed_tenders || data.db_total_tenders || 0;
                const pct = data.progress_percent !== undefined 
                    ? data.progress_percent.toFixed(1) 
                    : ((doneTendersCount / totalTendersCount) * 100).toFixed(1);
                    
                document.getElementById('pct-val').innerText = pct + '%';
                document.getElementById('bar-fill').style.width = Math.min(100, Math.max(0, pct)) + '%';
                
                document.getElementById('tenders-ratio').innerHTML = `<strong>${doneTendersCount.toLocaleString()}</strong> / ${totalTendersCount.toLocaleString()}`;

                // Stats: prioritize cumulative database totals so user sees real numbers
                const totalBidders = data.total_bidders || data.db_total_bidders || 0;
                const totalWinners = data.total_winners || data.db_total_winners || 0;
                const totalLosers = data.total_losers || data.db_total_losers || 0;

                document.getElementById('total-bidders').innerText = totalBidders.toLocaleString();
                document.getElementById('speed-val').innerText = (data.speed_per_second || 0).toFixed(1) + ' /с';
                document.getElementById('winners-val').innerText = totalWinners.toLocaleString();
                document.getElementById('losers-val').innerText = totalLosers.toLocaleString();
                document.getElementById('eta-val').innerText = data.eta || '--:--:--';

                // Render Live Bidders Feed
                if (data.recent_bidders && data.recent_bidders.length > 0) {
                    const tbody = document.getElementById('live-bidders-tbody');
                    tbody.innerHTML = data.recent_bidders.map(b => {
                        const isWin = (b.status || '').includes('Шалгарсан');
                        const statusBadge = isWin
                            ? `<span style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); padding: 2px 6px; border-radius: 4px; font-weight: 600; font-size: 10px;">🏆 Шалгарсан</span>`
                            : `<span style="background: rgba(148, 163, 184, 0.15); color: #94a3b8; padding: 2px 6px; border-radius: 4px; font-size: 10px;">${b.status || 'Хасагдсан'}</span>`;
                        
                        const priceText = b.price !== null && b.price !== undefined 
                            ? Number(b.price).toLocaleString() + ' ₮' 
                            : '--';
                            
                        const timeStr = b.created_at ? b.created_at.split(' ')[1] || b.created_at : '--';
                        const tenderShort = b.tender_name && b.tender_name.length > 25 ? b.tender_name.slice(0, 25) + '...' : (b.tender_name || '--');
                        const compShort = b.company_name && b.company_name.length > 18 ? b.company_name.slice(0, 18) + '...' : b.company_name;

                        return `<tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
                            <td style="padding: 6px; font-weight: 600; color: #f8fafc;" title="${b.company_name}">${compShort}</td>
                            <td style="padding: 6px; color: #cbd5e1;" title="${b.tender_name}">${tenderShort}</td>
                            <td style="padding: 6px; text-align: right; font-weight: 500; color: #38bdf8; font-family: monospace;">${priceText}</td>
                            <td style="padding: 6px; text-align: center;">${statusBadge}</td>
                            <td style="padding: 6px; text-align: right; color: #64748b; font-size: 10px;">${timeStr}</td>
                        </tr>`;
                    }).join('');
                }
                
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
                if (data.gateway_label) {
                    const gwEl = document.getElementById('gateway-val');
                    if (gwEl) gwEl.innerText = data.gateway_label;
                }
                if (data.db_total_bidders) {
                    document.getElementById('db-total-bidders').innerText = Number(data.db_total_bidders).toLocaleString();
                }
                // Data Usage
                if (data.data_usage) {
                    const du = data.data_usage;
                    const usedText = du.used_mb >= 1024 
                        ? (du.used_gb.toFixed(2) + ' GB') 
                        : (du.used_mb.toFixed(1) + ' MB');
                    
                    const deltaHtml = (du.live_delta_mb !== undefined && du.live_delta_mb > 0)
                        ? `<span style="font-size: 11px; color: #38bdf8; font-weight: 500; margin-left: 5px;">(+${du.live_delta_mb.toFixed(1)} MB live)</span>`
                        : '';
                    
                    const speedHtml = (du.speed_kbps !== undefined && du.speed_kbps > 0)
                        ? `<span style="background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.4); color: #38bdf8; padding: 2px 7px; border-radius: 5px; font-size: 11px; font-weight: 600; margin-left: 6px;">⚡️ ${du.speed_kbps} KB/s</span>`
                        : '';

                    document.getElementById('data-used').innerHTML = `${usedText} ашигласан ${deltaHtml} ${speedHtml}`;
                    document.getElementById('data-pct').innerText = du.used_pct.toFixed(1) + '%';
                    
                    const remMbText = du.remaining_mb !== undefined ? ` (${Number(du.remaining_mb).toFixed(0)} MB)` : '';
                    document.getElementById('data-remaining').innerHTML = `${du.remaining_gb !== undefined ? du.remaining_gb.toFixed(2) : '--'} GB үлдсэн <span style="font-size: 11px; color: #94a3b8; font-weight: normal;">${remMbText}</span>`;
                    document.getElementById('data-bar-fill').style.width = Math.max(0.2, Math.min(100, du.used_pct)) + '%';
                    
                    const liveBadge = document.getElementById('data-live-badge');
                    if (liveBadge) {
                        liveBadge.style.display = (data.active_gateway === 'mobicom' || (du.speed_kbps !== undefined && du.speed_kbps > 0)) ? 'inline-block' : 'none';
                    }
                    
                    // Render packages chips
                    const pkgContainer = document.getElementById('data-packages');
                    if (pkgContainer && du.packages && du.packages.length > 0) {
                        pkgContainer.innerHTML = du.packages.map(p => {
                            const remStr = p.remaining_mb >= 1024 ? (p.remaining_mb / 1024).toFixed(2) + ' GB' : p.remaining_mb.toFixed(1) + ' MB';
                            const planStr = p.plan_mb >= 1024 ? (p.plan_mb / 1024).toFixed(0) + ' GB' : p.plan_mb.toFixed(0) + ' MB';
                            return `<span style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.35); color: #6ee7b7; padding: 3px 8px; border-radius: 5px; font-weight: 500;">
                                🎁 ${p.name} (${planStr}): <strong style="color: #ffffff;">${remStr} үлдсэн</strong>
                            </span>`;
                        }).join('');
                    }

                    // Render billing / contract info
                    if (du.bill_info) {
                        const billVal = document.getElementById('carrier-bill-val');
                        if (billVal) billVal.innerText = du.bill_info.balance_text || '0₮';
                    }
                    if (du.expiry) {
                        const expVal = document.getElementById('carrier-expiry-val');
                        if (expVal) expVal.innerText = 'Хүчинтэй: ' + du.expiry;
                    }

                    if (du.carrier_sms && !isSmsChecking) {
                        const smsVal = document.getElementById('carrier-sms-val');
                        if (smsVal) {
                            if (du.summary) {
                                smsVal.innerHTML = `<div style="color: #34d399; font-weight: 600; margin-bottom: 4px;">${du.summary}</div><div style="font-size: 10.5px; color: #94a3b8; font-style: italic;">Эх мессеж: ${du.carrier_sms}</div>`;
                            } else {
                                smsVal.innerText = du.carrier_sms;
                            }
                        }
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
            smsVal.innerHTML = '<span style="color: #60a5fa;">📡 4G модемоос MobiCom (592) руу "B" мессеж илгээлээ. Хариу хүлээж байна (4-6с)...</span>';

            try {
                const res = await fetch('/api/sms/check', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    btnIcon.innerText = '✅';
                    btnText.innerText = 'Ирсэн!';
                    if (data.summary) {
                        smsVal.innerHTML = `<div style="color: #34d399; font-weight: 600; margin-bottom: 4px;">${data.summary}</div><div style="font-size: 10.5px; color: #94a3b8; font-style: italic;">Эх мессеж: ${data.sms_text}</div>`;
                    } else {
                        smsVal.innerHTML = `<span style="color: #34d399; font-weight: 600;">${data.sms_text}</span>`;
                    }
                    smsTime.innerText = 'Шалгасан: ' + (data.timestamp || new Date().toLocaleTimeString());
                    updateStatus();
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
TOTAL_PLAN_GB = 8.0
last_raw_rx = 0
last_raw_tx = 0
accumulated_bytes = 0
sms_baseline_wwan_bytes = 0
last_speed_bytes = 0
last_speed_time = 0
current_speed_kbps = 0.0
last_save_time = 0
cached_carrier_sms = None
cached_bill_sms = None
sms_check_lock = threading.Lock()
last_sms_check_time = 0

def parse_carrier_sms(data_text, bill_text=None):
    if not data_text and not bill_text:
        return None
    res = {
        'packages': [],
        'total_plan_mb': 0.0,
        'total_used_mb': 0.0,
        'total_remaining_mb': 0.0,
        'expiry': None,
        'summary': '',
        'bill_info': None
    }
    
    if data_text:
        # Expiry
        exp_m = re.findall(r'duusah hugatsaa\s*([\d\-]+(?:\s+[\d:]+)?)', data_text, re.I)
        if exp_m:
            res['expiry'] = exp_m[-1].strip()

        # 1. Check for bonus / uramshuulal
        uram_m = re.search(r'uramshuull?iin\s*([\d\.]+)\s*(GB|MB).*?uldegdel\s*([\d,]+(?:\.\d+)?)\s*(MB|GB)', data_text, re.I)
        if uram_m:
            plan_val = float(uram_m.group(1)) * (1024 if uram_m.group(2).upper() == 'GB' else 1)
            rem_str = uram_m.group(3).replace(',', '')
            rem_val = float(rem_str) * (1024 if uram_m.group(4).upper() == 'GB' else 1)
            used_val = max(0.0, plan_val - rem_val)
            res['packages'].append({'name': 'Урамшуулал', 'plan_mb': plan_val, 'remaining_mb': rem_val, 'used_mb': used_val})
        
        # 2. Check for Dagaldah / regular package
        dag_m = re.search(r'Dagaldah\s*([\d\.]+)\s*(GB|MB).*?ashiglasan\s*([\d,]+(?:\.\d+)?)\s*(MB|GB)', data_text, re.I)
        if dag_m:
            plan_val = float(dag_m.group(1)) * (1024 if dag_m.group(2).upper() == 'GB' else 1)
            used_str = dag_m.group(3).replace(',', '')
            used_val = float(used_str) * (1024 if dag_m.group(4).upper() == 'GB' else 1)
            rem_val = max(0.0, plan_val - used_val)
            res['packages'].append({'name': 'Дагалдах багц', 'plan_mb': plan_val, 'remaining_mb': rem_val, 'used_mb': used_val})

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
            res['summary'] = f"🟢 Нийт үлдсэн: {rem_gb:.2f} GB ({' + '.join(pkg_summaries)}) | Хүчинтэй: {res['expiry'] or '2026-10-31'}"
        else:
            res['summary'] = data_text

    if bill_text:
        bal_m = re.search(r'tulburiin uldegdel\s*([\d\.]+)\s*T', bill_text, re.I)
        geree_m = re.search(r'(\d+)\s+toot\s+gereend', bill_text, re.I)
        res['bill_info'] = {
            'balance_text': f"{bal_m.group(1)}₮" if bal_m else "0₮",
            'contract_no': geree_m.group(1) if geree_m else ""
        }

    return res

def get_carrier_sms_messages():
    """ModemManager-оос 592 болон TULBUR-аас ирсэн сүүлийн SMS-үүдийг унших"""
    data_sms = None
    bill_sms = None
    try:
        out = subprocess.getoutput("sudo mmcli -m 0 --messaging-list-sms 2>/dev/null")
        sms_ids = [int(x) for x in re.findall(r'/SMS/(\d+)\s+\(received\)', out)]
        sms_ids.sort(reverse=True) # Newest first!
        for sid in sms_ids:
            detail = subprocess.getoutput(f"sudo mmcli -s {sid} 2>/dev/null")
            m_num = re.search(r'number:\s*([^\n\r]+)', detail)
            m_txt = re.search(r'text:\s*([^\n\r]+)', detail)
            if not m_txt:
                continue
            sender = m_num.group(1).strip() if m_num else ""
            txt = m_txt.group(1).strip()
            
            # Check for 592 Data SMS
            if re.search(r'592\b', sender, re.I):
                if re.search(r'(uldegdel|ashiglasan|data bagts)', txt, re.I):
                    if not data_sms:
                        data_sms = txt
                elif not data_sms:
                    data_sms = txt # fallback
            
            # Check for TULBUR Billing SMS
            if re.search(r'tulbur\b', sender, re.I):
                if not bill_sms:
                    bill_sms = txt
    except Exception:
        pass
    return data_sms, bill_sms

def get_data_usage():
    global last_raw_rx, last_raw_tx, accumulated_bytes, last_save_time, cached_carrier_sms, cached_bill_sms
    global sms_baseline_wwan_bytes, last_speed_bytes, last_speed_time, current_speed_kbps
    now = time.time()
    
    if os.path.exists(DATA_USAGE_FILE):
        try:
            with open(DATA_USAGE_FILE, "r") as f:
                d_file = json.load(f)
                if accumulated_bytes == 0:
                    accumulated_bytes = d_file.get("accumulated_bytes", 0)
                if sms_baseline_wwan_bytes == 0:
                    sms_baseline_wwan_bytes = d_file.get("sms_baseline_wwan_bytes", 0)
                if d_file.get("carrier_sms") and not cached_carrier_sms:
                    cached_carrier_sms = d_file.get("carrier_sms")
        except Exception:
            pass

    # If no cached carrier sms, fetch from modem
    if not cached_carrier_sms or not cached_bill_sms:
        d_sms, b_sms = get_carrier_sms_messages()
        if d_sms:
            cached_carrier_sms = d_sms
        if b_sms:
            cached_bill_sms = b_sms

    rx_path = "/sys/class/net/wwan0/statistics/rx_bytes"
    tx_path = "/sys/class/net/wwan0/statistics/tx_bytes"

    curr_total = 0
    if os.path.exists(rx_path) and os.path.exists(tx_path):
        try:
            with open(rx_path) as f:
                curr_rx = int(f.read().strip())
            with open(tx_path) as f:
                curr_tx = int(f.read().strip())
            curr_total = curr_rx + curr_tx

            if last_raw_rx > 0:
                d_rx = curr_rx - last_raw_rx if curr_rx >= last_raw_rx else curr_rx
                d_tx = curr_tx - last_raw_tx if curr_tx >= last_raw_tx else curr_tx
                accumulated_bytes += (d_rx + d_tx)
            else:
                accumulated_bytes += (curr_rx + curr_tx)

            # Live speed in KB/s
            if last_speed_time == 0:
                last_speed_time = now
                last_speed_bytes = curr_total
            else:
                dt = now - last_speed_time
                if dt >= 1.5:
                    diff_b = curr_total - last_speed_bytes if curr_total >= last_speed_bytes else curr_total
                    current_speed_kbps = round(diff_b / dt / 1024, 1)
                    last_speed_bytes = curr_total
                    last_speed_time = now

            if sms_baseline_wwan_bytes == 0:
                sms_baseline_wwan_bytes = curr_total

            last_raw_rx = curr_rx
            last_raw_tx = curr_tx
        except Exception:
            pass

    # Calculate live delta since SMS was received
    live_delta_bytes = 0
    if curr_total > 0 and sms_baseline_wwan_bytes > 0:
        if curr_total >= sms_baseline_wwan_bytes:
            live_delta_bytes = curr_total - sms_baseline_wwan_bytes
        else:
            live_delta_bytes = curr_total
    live_delta_mb = round(live_delta_bytes / (1024 * 1024), 2)

    parsed = parse_carrier_sms(cached_carrier_sms, cached_bill_sms)
    
    if parsed and parsed.get('total_remaining_mb', 0) > 0:
        plan_gb = round(parsed['total_plan_mb'] / 1024, 2)
        base_used_mb = parsed['total_used_mb']
        base_rem_mb = parsed['total_remaining_mb']
        
        live_used_mb = base_used_mb + live_delta_mb
        live_rem_mb = max(0.0, base_rem_mb - live_delta_mb)
        
        used_mb = round(live_used_mb, 1)
        used_gb = round(live_used_mb / 1024, 3)
        remaining_gb = round(live_rem_mb / 1024, 2)
        remaining_mb = round(live_rem_mb, 1)
        used_pct = round((live_used_mb / parsed['total_plan_mb']) * 100, 2) if parsed['total_plan_mb'] > 0 else 0.0
        
        # Package level live tracking (Deduct from 'Урамшуулал' first, then 'Дагалдах багц')
        live_packages = []
        rem_delta = live_delta_mb
        for p in parsed.get('packages', []):
            p_copy = dict(p)
            if rem_delta > 0:
                p_rem = p_copy['remaining_mb']
                deduct = min(p_rem, rem_delta)
                p_copy['remaining_mb'] = max(0.0, round(p_rem - deduct, 1))
                p_copy['used_mb'] = round(p_copy['used_mb'] + deduct, 1)
                rem_delta -= deduct
            live_packages.append(p_copy)
            
        packages = live_packages
        expiry = parsed.get('expiry')
        summary = parsed.get('summary')
        bill_info = parsed.get('bill_info')
    else:
        plan_gb = TOTAL_PLAN_GB
        used_mb = round(accumulated_bytes / (1024 * 1024), 2)
        used_gb = round(used_mb / 1024, 3)
        remaining_gb = round(max(0.0, plan_gb - used_gb), 2)
        remaining_mb = round(remaining_gb * 1024, 1)
        used_pct = round((used_gb / plan_gb) * 100, 2) if plan_gb > 0 else 0.0
        packages = []
        expiry = None
        summary = cached_carrier_sms or ""
        bill_info = None

    if now - last_save_time > 15:
        last_save_time = now
        try:
            with open(DATA_USAGE_FILE, "w") as f:
                json.dump({
                    "plan_gb": plan_gb,
                    "accumulated_bytes": accumulated_bytes,
                    "sms_baseline_wwan_bytes": sms_baseline_wwan_bytes,
                    "carrier_sms": cached_carrier_sms,
                    "carrier_parsed": parsed,
                    "live_delta_mb": live_delta_mb,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return {
        "plan_gb": plan_gb,
        "used_bytes": accumulated_bytes,
        "used_mb": used_mb,
        "used_gb": used_gb,
        "remaining_gb": remaining_gb,
        "remaining_mb": remaining_mb,
        "live_delta_mb": live_delta_mb,
        "speed_kbps": current_speed_kbps,
        "used_pct": used_pct,
        "packages": packages,
        "expiry": expiry,
        "summary": summary,
        "bill_info": bill_info,
        "carrier_sms": cached_carrier_sms
    }

def trigger_carrier_sms_check():
    global cached_carrier_sms, cached_bill_sms, last_sms_check_time
    now = time.time()
    
    with sms_check_lock:
        try:
            # Get max existing SMS ID before sending
            out_before = subprocess.getoutput("sudo mmcli -m 0 --messaging-list-sms 2>/dev/null")
            ids_before = [int(x) for x in re.findall(r'/SMS/(\d+)', out_before)]
            max_id = max(ids_before) if ids_before else -1

            # Create SMS: B to 592
            res = subprocess.getoutput("sudo mmcli -m 0 --messaging-create-sms=\"text='B',number='592'\" 2>/dev/null")
            sms_id_match = re.search(r'/SMS/(\d+)', res)
            if not sms_id_match:
                d_sms, b_sms = get_carrier_sms_messages()
                parsed = parse_carrier_sms(d_sms, b_sms)
                return {
                    "success": True,
                    "sms_text": d_sms or "Хариу олдсонгүй",
                    "summary": parsed['summary'] if parsed else "",
                    "parsed": parsed,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

            sid = sms_id_match.group(1)
            send_res = subprocess.getoutput(f"sudo mmcli -s {sid} --send 2>/dev/null")
            
            # Delete the sent SMS from modem to avoid filling SIM memory
            subprocess.getoutput(f"sudo mmcli -m 0 --messaging-delete-sms={sid} 2>/dev/null")

            # Poll for new incoming SMS from 592 (up to 8 seconds)
            new_data_sms = None
            for _ in range(8):
                time.sleep(1)
                out_after = subprocess.getoutput("sudo mmcli -m 0 --messaging-list-sms 2>/dev/null")
                new_ids = [int(x) for x in re.findall(r'/SMS/(\d+)\s+\(received\)', out_after) if int(x) > max_id]
                new_ids.sort(reverse=True)
                for nid in new_ids:
                    detail = subprocess.getoutput(f"sudo mmcli -s {nid} 2>/dev/null")
                    if re.search(r'number:\s*(\+?976)?592\b', detail, re.I):
                        m = re.search(r'text:\s*([^\n\r]+)', detail)
                        if m:
                            new_data_sms = m.group(1).strip()
                            break
                if new_data_sms:
                    break

            if not new_data_sms:
                # Fallback to newest existing 592 message
                new_data_sms, _ = get_carrier_sms_messages()

            if new_data_sms:
                cached_carrier_sms = new_data_sms
                _, bill_sms = get_carrier_sms_messages()
                if bill_sms:
                    cached_bill_sms = bill_sms
                last_sms_check_time = time.time()
                
                parsed = parse_carrier_sms(new_data_sms, cached_bill_sms)
                
                rx_path = "/sys/class/net/wwan0/statistics/rx_bytes"
                tx_path = "/sys/class/net/wwan0/statistics/tx_bytes"
                if os.path.exists(rx_path) and os.path.exists(tx_path):
                    try:
                        with open(rx_path) as f: c_rx = int(f.read().strip())
                        with open(tx_path) as f: c_tx = int(f.read().strip())
                        sms_baseline_wwan_bytes = c_rx + c_tx
                    except Exception:
                        pass

                try:
                    current_data = {}
                    if os.path.exists(DATA_USAGE_FILE):
                        with open(DATA_USAGE_FILE, "r") as f:
                            current_data = json.load(f)
                    current_data["carrier_sms"] = new_data_sms
                    current_data["carrier_parsed"] = parsed
                    current_data["sms_baseline_wwan_bytes"] = sms_baseline_wwan_bytes
                    current_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with open(DATA_USAGE_FILE, "w") as f:
                        json.dump(current_data, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass

                return {
                    "success": True,
                    "sms_text": new_data_sms,
                    "summary": parsed['summary'] if parsed else new_data_sms,
                    "parsed": parsed,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            else:
                return {"success": False, "error": "592 дугаараас хариу мессеж ирсэнгүй, түр хүлээгээд дахин шалгана уу."}
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

            lines = subprocess.getoutput("ip -4 route show default").strip().splitlines()
            first = lines[0] if lines else ""
            if "wwan0" in first:
                payload["active_gateway"] = "mobicom"
                payload["gateway_label"] = "📶 MobiCom 4G (Нөөц гарц)"
            elif "wlan0" in first:
                payload["active_gateway"] = "wifi"
                payload["gateway_label"] = "🟢 Univision Wi-Fi (Шилэн кабель)"
            else:
                payload["active_gateway"] = "unknown"
                payload["gateway_label"] = "Автомат холболт"

            # Detailed read from SQLite DB
            if os.path.exists(DB_PATH):
                try:
                    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=2.0)
                    cur = conn.cursor()
                    cur.execute("SELECT count(*) FROM tender_sync_log;")
                    payload["db_total_tenders"] = cur.fetchone()[0] or 0
                    
                    cur.execute("""
                        SELECT 
                            count(*),
                            sum(case when status like '%Шалгарсан%' then 1 else 0 end),
                            sum(case when status not like '%Шалгарсан%' then 1 else 0 end)
                        FROM tender_bidders;
                    """)
                    row = cur.fetchone()
                    payload["db_total_bidders"] = row[0] or 0
                    payload["db_total_winners"] = row[1] or 0
                    payload["db_total_losers"] = row[2] or 0
                    
                    # Fetch latest 8 bidders for live feed
                    cur.execute("""
                        SELECT company_name, tender_name, offered_price, status, created_at, tender_code
                        FROM tender_bidders
                        ORDER BY id DESC
                        LIMIT 8;
                    """)
                    payload["recent_bidders"] = [
                        {
                            "company_name": r[0] or "Тодорхойгүй",
                            "tender_name": r[1] or "",
                            "price": r[2],
                            "status": r[3] or "",
                            "created_at": r[4] or "",
                            "tender_code": r[5] or ""
                        }
                        for r in cur.fetchall()
                    ]
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
