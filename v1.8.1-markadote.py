import sqlite3
import time
import threading
import websocket
from websocket import WebSocketApp
import json
import requests
import os
import logging
from datetime import datetime, timedelta, timezone
import uuid
import re
from statistics import mean

# === CẤU HÌNH CHÍNH ===
USER_STATES = {}  # Lưu trữ trạng thái từng người dùng
PREDICTION_HISTORY = []
ADMIN_ACTIVE = True
BOT_VERSION = "8.0 Pro Ultra"
BROADCAST_IN_PROGRESS = False
FORMULA_WEIGHTS = {i: 1.0 for i in range(153)}  # Trọng số 153 công thức
CURRENT_MODE = "vip"  # Chế độ mặc định

# === CẤU HÌNH TELEGRAM ===
BOT_TOKEN = "" #add bot token here

# === BIỂU TƯỢNG EMOJI ===
EMOJI = {
    "dice": "🎲", "money": "💰", "chart": "📊", "clock": "⏱️", "bell": "🔔", "rocket": "🚀",
    "warning": "⚠️", "trophy": "🏆", "fire": "🔥", "up": "📈", "down": "📉", "right": "↪️",
    "left": "↩️", "check": "✅", "cross": "❌", "star": "⭐", "medal": "🏅", "id": "🆔",
    "sum": "🧮", "prediction": "🔮", "trend": "📶", "history": "🔄", "pattern": "🧩",
    "settings": "⚙️", "vip": "💎", "team": "👥", "ae": "🔷", "key": "🔑", "admin": "🛡️",
    "play": "▶️", "pause": "⏸️", "add": "➕", "list": "📜", "delete": "🗑️",
    "infinity": "♾️", "calendar": "📅", "streak": "🔥", "analysis": "🔍",
    "heart": "❤️", "diamond": "♦️", "spade": "♠️", "club": "♣️", "luck": "🍀",
    "money_bag": "💰", "crown": "👑", "shield": "🛡", "zap": "⚡", "target": "🎯",
    "info": "ℹ️", "user": "👤", "broadcast": "📢", "stats": "📈", "percent": "%"
}

# === HÀM LẤY GIỜ VIỆT NAM ===
def get_vn_time():
    """Lấy thời gian hiện tại theo múi giờ Việt Nam (UTC+7)"""
    vn_tz = timezone(timedelta(hours=7))
    return datetime.now(timezone.utc).astimezone(vn_tz)

def format_vn_time(dt=None):
    """Định dạng thời gian VN"""
    if dt is None:
        dt = get_vn_time()
    return dt.strftime("%H:%M:%S %d/%m/%Y")

def handle_telegram_updates():
    global ADMIN_ACTIVE, CURRENT_MODE
    offset = 0
    while True:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        params = {"offset": offset, "timeout": 30}
        try:
            response = requests.get(url, params=params, timeout=40)
            response.raise_for_status()
            updates = response.json()["result"]
            for update in updates:
                offset = update["update_id"] + 1
                
                # Xử lý callback query (ấn button)
                if "callback_query" in update:
                    callback_query = update["callback_query"]
                    data = callback_query["data"]
                    chat_id = callback_query["message"]["chat"]["id"]
                    message_id = callback_query["message"]["message_id"]
                    
                    # Trả lời callback query trước
                    answer_callback_query(callback_query["id"])
                    
                    if data == "help_activate":
                        help_message = (
                            f"{EMOJI['key']} *HƯỚNG DẪN KÍCH HOẠT BOT*\n"
                            f"══════════════════════════\n"
                            f"1. Liên hệ admin để mua key VIP\n"
                            f"2. Nhập lệnh `/key <key_của_bạn>` để kích hoạt\n"
                            f"3. Nhập `/chaybot` để bắt đầu nhận dự đoán\n"
                            f"══════════════════════════\n"
                            f"{EMOJI['warning']} *Lưu ý:*\n"
                            f"- Mỗi key có giới hạn sử dụng nhất định\n"
                            f"- Key có thể có thời hạn sử dụng\n"
                            f"══════════════════════════\n"
                            f"{EMOJI['team']} Liên hệ admin: @qqaassdd1231"
                        )
                        edit_message_text(chat_id, message_id, help_message)
                    continue
                
                # Xử lý tin nhắn thông thường
                if "message" in update:
                    message = update["message"]
                    chat_id = message["chat"]["id"]
                    text = message.get("text")

                    if text:
                        if text.startswith("/start"):
                            welcome_message = (
                                f"{EMOJI['diamond']} *SUNWIN VIP - CHÀO MỪNG BẠN* {EMOJI['diamond']}\n"
                                f"══════════════════════════\n"
                                f"{EMOJI['rocket']} *BOT PHÂN TÍCH TÀI XỈU CHUẨN XÁC*\n"
                                f"{EMOJI['vip']} Phiên bản: {BOT_VERSION}\n"
                                f"══════════════════════════\n"
                                f"{EMOJI['bell']} *Hướng dẫn sử dụng:*\n"
                                f"- Nhập `/key <key_của_bạn>` để kích hoạt bot\n"
                                f"- `/chaybot` để bật nhận thông báo\n"
                                f"- `/tatbot` để tắt nhận thông báo\n"
                                f"- `/thongtin` để xem thông tin tài khoản\n"
                                f"- `/lichsu` để xem lịch sử 10 phiên gần nhất\n"
                                f"- `/thongke` để xem thống kê chi tiết\n"
                                f"══════════════════════════\n"
                                f"{EMOJI['team']} *Liên hệ admin để mua key VIP* {EMOJI['team']}"
                            )
                            
                            buttons = [
                                [{"text": f"{EMOJI['key']} Hướng dẫn kích hoạt", "callback_data": "help_activate"}],
                                [{"text": f"{EMOJI['money_bag']} Liên hệ mua key", "url": "https://t.me/qqaassdd1231"}]
                            ]
                            
                            send_telegram_with_buttons(chat_id, welcome_message, buttons)
                            
                            user_state = get_user_state(chat_id)
                            if not user_state or not user_state.get("key_value"):
                                pass
                            else:
                                key_to_check = user_state["key_value"]
                                if is_key_valid(key_to_check):
                                    update_user_state(chat_id, True)
                                    increment_key_usage(key_to_check)
                                    send_telegram(chat_id, f"{EMOJI['check']} Bot đã được kích hoạt cho bạn. Nhận thông báo dự đoán tự động.")
                                else:
                                    send_telegram(chat_id, f"{EMOJI['warning']} Key của bạn đã hết lượt sử dụng hoặc đã hết hạn.")
                                    update_user_state(chat_id, False)

                        elif text.startswith("/key"):
                            parts = text.split()
                            if len(parts) == 2:
                                key = parts[1]
                                if is_key_valid(key):
                                    update_user_state(chat_id, True, key)
                                    increment_key_usage(key)
                                    
                                    # Lấy thông tin key
                                    conn = get_db_connection()
                                    c = conn.cursor()
                                    c.execute("SELECT prefix, max_uses, expiry_date FROM keys WHERE key_value = ?", (key,))
                                    key_info = c.fetchone()
                                    conn.close()
                                    
                                    if key_info:
                                        prefix, max_uses, expiry_date = key_info
                                        uses_left = f"{max_uses} lần" if max_uses != -1 else "không giới hạn"
                                        expiry_info = f"hết hạn {expiry_date}" if expiry_date else "vĩnh viễn"
                                        
                                        success_message = (
                                            f"{EMOJI['check']} *KÍCH HOẠT THÀNH CÔNG*\n"
                                            f"══════════════════════════\n"
                                            f"{EMOJI['key']} *Loại key:* `{prefix}`\n"
                                            f"{EMOJI['chart']} *Số lần còn lại:* `{uses_left}`\n"
                                            f"{EMOJI['calendar']} *Thời hạn:* `{expiry_info}`\n"
                                            f"══════════════════════════\n"
                                            f"{EMOJI['bell']} Gõ `/chaybot` để bắt đầu nhận dự đoán!"
                                        )
                                        send_telegram(chat_id, success_message)
                                    else:
                                        send_telegram(chat_id, f"{EMOJI['key']} Key hợp lệ. Bot đã được kích hoạt cho bạn.")
                                else:
                                    send_telegram(chat_id, f"{EMOJI['warning']} Key không hợp lệ hoặc đã hết lượt sử dụng/hết hạn. Vui lòng kiểm tra lại.")
                            else:
                                send_telegram(chat_id, f"{EMOJI['warning']} Sử dụng: `/key <your_key>`")

                        elif text.startswith("/chaybot"):
                            user_state = get_user_state(chat_id)
                            if user_state and user_state.get("key_value") and is_key_valid(user_state["key_value"]):
                                update_user_state(chat_id, True)
                                
                                # Kiểm tra lịch sử 5 phiên gần nhất
                                last_sessions = get_last_sessions(5)
                                if last_sessions:
                                    last_result = last_sessions[0]["result"]
                                    streak = 1
                                    for i in range(1, len(last_sessions)):
                                        if last_sessions[i]["result"] == last_result:
                                            streak += 1
                                        else:
                                            break
                                    
                                    streak_info = f"\n{EMOJI['streak']} *Cầu hiện tại:* {last_result} {streak} nút" if streak >= 3 else ""
                                
                                message = (
                                    f"{EMOJI['check']} *BOT ĐÃ ĐƯỢC BẬT*\n"
                                    f"══════════════════════════\n"
                                    f"{EMOJI['bell']} Bạn sẽ nhận thông báo dự đoán tự động.{streak_info if 'streak_info' in locals() else ''}\n"
                                    f"══════════════════════════\n"
                                    f"{EMOJI['warning']} Lưu ý: Đây là công cụ hỗ trợ, không đảm bảo 100% chính xác."
                                )
                                send_telegram(chat_id, message)
                                
                                print(f"{EMOJI['play']} Bot đã được bật cho người dùng {chat_id}.")
                                log_message(f"Bot đã được bật cho người dùng {chat_id}.")
                            elif is_admin(chat_id):
                                ADMIN_ACTIVE = True
                                send_telegram(chat_id, f"{EMOJI['play']} Bot đã được bật cho tất cả người dùng (admin).")
                                print(f"{EMOJI['play']} Bot đã được bật bởi admin.")
                                log_message("Bot đã được bật bởi admin.")
                            else:
                                send_telegram(chat_id, f"{EMOJI['warning']} Bạn cần kích hoạt bot bằng key trước hoặc bạn không có quyền sử dụng lệnh này.")

                        elif text.startswith("/tatbot"):
                            user_state = get_user_state(chat_id)
                            if user_state and user_state.get("key_value"):
                                update_user_state(chat_id, False)
                                send_telegram(chat_id, f"{EMOJI['pause']} Bot đã được tắt cho bạn. Bạn sẽ không nhận thông báo nữa.")
                                print(f"{EMOJI['pause']} Bot đã được tắt cho người dùng {chat_id}.")
                                log_message(f"Bot đã được tắt cho người dùng {chat_id}.")
                            elif is_admin(chat_id):
                                ADMIN_ACTIVE = False
                                send_telegram(chat_id, f"{EMOJI['pause']} Bot đã được tắt cho tất cả người dùng (admin).")
                                print(f"{EMOJI['pause']} Bot đã được tắt bởi admin.")
                                log_message("Bot đã được tắt bởi admin.")
                            else:
                                send_telegram(chat_id, f"{EMOJI['warning']} Bạn cần kích hoạt bot bằng key trước hoặc bạn không có quyền sử dụng lệnh này.")

                        elif text.startswith("/thongtin"):
                            user_info = get_user_info(chat_id)
                            if user_info:
                                status = "ĐANG BẬT" if user_info["is_active"] else "ĐÃ TẮT"
                                key_status = "HỢP LỆ" if is_key_valid(user_info["key_value"]) else "HẾT HẠN/HẾT LƯỢT"
                                
                                message = (
                                    f"{EMOJI['user']} *THÔNG TIN TÀI KHOẢN*\n"
                                    f"══════════════════════════\n"
                                    f"{EMOJI['id']} *ID:* `{chat_id}`\n"
                                    f"{EMOJI['bell']} *Trạng thái:* `{status}`\n"
                                    f"{EMOJI['key']} *Key:* `{user_info['key_value'] or 'CHƯA KÍCH HOẠT'}`\n"
                                    f"{EMOJI['check']} *Tình trạng key:* `{key_status if user_info['key_value'] else 'N/A'}`\n"
                                    f"{EMOJI['info']} *Chế độ:* `{user_info['mode'].upper()}`\n"
                                    f"{EMOJI['calendar']} *Ngày tham gia:* `{user_info['join_date']}`\n"
                                    f"{EMOJI['clock']} *Lần hoạt động cuối:* `{user_info['last_active']}`\n"
                                    f"══════════════════════════\n"
                                    f"{EMOJI['chart']} *THỐNG KÊ DỰ ĐOÁN*\n"
                                    f"- Tổng dự đoán: `{user_info['total_predictions']}`\n"
                                    f"- Dự đoán đúng: `{user_info['correct_predictions']}`\n"
                                    f"- Tỷ lệ chính xác: `{user_info['accuracy']:.1f}%`\n"
                                    f"- Chuỗi đúng hiện tại: `{user_info['current_streak']}`\n"
                                    f"- Chuỗi đúng cao nhất: `{user_info['max_streak']}`\n"
                                    f"══════════════════════════\n"
                                    f"{EMOJI['info']} Sử dụng `/thongke` để xem thống kê chi tiết"
                                )
                                send_telegram(chat_id, message)
                            else:
                                send_telegram(chat_id, f"{EMOJI['warning']} Bạn chưa kích hoạt bot. Vui lòng sử dụng lệnh /key để kích hoạt.")

                        elif text.startswith("/lichsu"):
                            last_sessions = get_last_sessions(10)
                            if last_sessions:
                                sessions_info = []
                                for i, session in enumerate(last_sessions):
                                    dice_str = "-".join(map(str, session["dice"]))
                                    sessions_info.append(
                                        f"{EMOJI['id']} *Phiên {session['session_id']}*: "
                                        f"{dice_str} | Tổng: `{session['total']}` | "
                                        f"{'Tài' if session['result'] == 'Tài' else 'Xỉu'}"
                                    )
                                
                                # Phân tích xu hướng
                                tai_count = sum(1 for s in last_sessions if s["result"] == "Tài")
                                xiu_count = len(last_sessions) - tai_count
                                
                                message = (
                                    f"{EMOJI['history']} *LỊCH SỬ 10 PHIÊN GẦN NHẤT*\n"
                                    f"══════════════════════════\n"
                                    + "\n".join(sessions_info) +
                                    f"\n══════════════════════════\n"
                                    f"{EMOJI['chart']} *Thống kê:* Tài: {tai_count} | Xỉu: {xiu_count}\n"
                                    f"{EMOJI['trend']} *Xu hướng:* {'Tài' if tai_count > xiu_count else 'Xỉu' if xiu_count > tai_count else 'Cân bằng'}"
                                )
                                send_telegram(chat_id, message)
                            else:
                                send_telegram(chat_id, f"{EMOJI['warning']} Chưa có dữ liệu lịch sử.")

                        elif text.startswith("/thongke"):
                            stats = get_session_stats(100)
                            if stats:
                                message = (
                                    f"{EMOJI['stats']} *THỐNG KÊ 100 PHIÊN GẦN NHẤT*\n"
                                    f"══════════════════════════\n"
                                    f"{EMOJI['chart']} *Tổng số phiên:* `{stats['total_sessions']}`\n"
                                    f"{EMOJI['up']} *Tài:* `{stats['tai_count']}` ({stats['tai_percent']:.1f}%)\n"
                                    f"{EMOJI['down']} *Xỉu:* `{stats['xiu_count']}` ({stats['xiu_percent']:.1f}%)\n"
                                    f"{EMOJI['sum']} *Tổng điểm trung bình:* `{stats['avg_total']:.1f}`\n"
                                    f"{EMOJI['streak']} *Cầu lớn nhất:* `{stats['max_streak']}` nút\n"
                                    f"══════════════════════════\n"
                                    f"{EMOJI['info']} *Phiên gần nhất:*\n"
                                    f"- ID: `{stats['last_session']['session_id']}`\n"
                                    f"- Xúc xắc: `{'-'.join(map(str, stats['last_session']['dice']))}`\n"
                                    f"- Tổng: `{stats['last_session']['total']}`\n"
                                    f"- Kết quả: `{stats['last_session']['result']}`\n"
                                    f"══════════════════════════\n"
                                    f"{EMOJI['trend']} *Xu hướng hiện tại:* `{analyze_trend()}`"
                                )
                                send_telegram(chat_id, message)
                            else:
                                send_telegram(chat_id, f"{EMOJI['warning']} Chưa có đủ dữ liệu thống kê.")

                        elif text.startswith("/taokey"):
                            if is_admin(chat_id):
                                parts = text.split()
                                if len(parts) >= 2:
                                    prefix = parts[1]
                                    limit_str = "unlimited"
                                    time_str = "vĩnh viễn"

                                    if len(parts) >= 3:
                                        limit_str = parts[2].lower()
                                    if len(parts) >= 4:
                                        time_str = " ".join(parts[3:]).lower()

                                    max_uses = -1
                                    if limit_str.isdigit():
                                        max_uses = int(limit_str)
                                    elif limit_str != "unlimited" and limit_str != "voihan":
                                        send_telegram(chat_id, f"{EMOJI['warning']} Giới hạn dùng không hợp lệ. Nhập số hoặc 'unlimited'.")
                                        continue

                                    expiry_date = None
                                    if time_str and time_str != "vĩnh viễn" and time_str != "unlimited":
                                        time_parts = time_str.split()
                                        if len(time_parts) >= 2 and time_parts[0].isdigit():
                                            time_value = int(time_parts[0])
                                            time_unit = " ".join(time_parts[1:])

                                            now = datetime.now()
                                            if "ngày" in time_unit:
                                                expiry_date = now + timedelta(days=time_value)
                                            elif "tuần" in time_unit:
                                                expiry_date = now + timedelta(weeks=time_value)
                                            elif "tháng" in time_unit:
                                                expiry_date = now + timedelta(days=time_value * 30)
                                            elif "năm" in time_unit:
                                                expiry_date = now + timedelta(days=time_value * 365)
                                            elif "giờ" in time_unit:
                                                expiry_date = now + timedelta(hours=time_value)
                                            elif "phút" in time_unit:
                                                expiry_date = now + timedelta(minutes=time_value)
                                            elif "giây" in time_unit:
                                                expiry_date = now + timedelta(seconds=time_value)

                                            if expiry_date:
                                                expiry_date = expiry_date.strftime("%Y-%m-%d %H:%M:%S")
                                            else:
                                                send_telegram(chat_id, f"{EMOJI['warning']} Đơn vị thời gian không hợp lệ. Ví dụ: '30 ngày', '1 tuần', '6 tháng', '1 năm'.")
                                                continue
                                        else:
                                            send_telegram(chat_id, f"{EMOJI['warning']} Định dạng thời gian không hợp lệ. Ví dụ: '30 ngày', '1 tuần', 'vĩnh viễn'.")
                                            continue

                                    new_key_value = f"{prefix}-{str(uuid.uuid4())[:8]}"
                                    if add_key_to_db(new_key_value, chat_id, prefix, max_uses, expiry_date):
                                        uses_display = f"{max_uses} lần" if max_uses != -1 else f"{EMOJI['infinity']} không giới hạn"
                                        expiry_display = f"{EMOJI['calendar']} {expiry_date}" if expiry_date else f"{EMOJI['infinity']} vĩnh viễn"
                                        send_telegram(chat_id, f"{EMOJI['add']} Đã tạo key '{new_key_value}'. Giới hạn: {uses_display}, Thời hạn: {expiry_display}.")
                                        log_message(f"Admin {chat_id} đã tạo key '{new_key_value}' với giới hạn {max_uses}, thời hạn {expiry_date}.")
                                    else:
                                        send_telegram(chat_id, f"{EMOJI['warning']} Không thể tạo key (có thể đã tồn tại).")
                                else:
                                    send_telegram(chat_id, f"{EMOJI['warning']} Sử dụng: `/taokey <tên_key> [giới_hạn_dùng/unlimited] [thời_gian (ví dụ: 30 ngày, 1 tuần, vĩnh viễn)]`. Các tham số giới hạn và thời gian là tùy chọn (mặc định là không giới hạn).")
                            else:
                                send_telegram(chat_id, f"{EMOJI['warning']} Chỉ admin mới có quyền sử dụng lệnh này.")

                        elif text.startswith("/lietkekey"):
                            if is_admin(chat_id):
                                keys_data = get_all_keys_from_db()
                                if keys_data:
                                    keys_list = []
                                    for key in keys_data:
                                        key_value, created_at, created_by, prefix, max_uses, current_uses, expiry_date = key
                                        uses_left = f"{current_uses}/{max_uses}" if max_uses != -1 else f"{current_uses}/{EMOJI['infinity']}"
                                        expiry_display = expiry_date if expiry_date else f"{EMOJI['infinity']}"
                                        keys_list.append(f"- `{key_value}` (Prefix: {prefix}, Dùng: {uses_left}, Hết hạn: {expiry_display})")
                                    
                                    keys_str = "\n".join(keys_list)
                                    message = (
                                        f"{EMOJI['list']} *DANH SÁCH KEY*\n"
                                        f"══════════════════════════\n"
                                        f"{keys_str}\n"
                                        f"══════════════════════════\n"
                                        f"{EMOJI['info']} Tổng số key: {len(keys_data)}"
                                    )
                                    send_telegram(chat_id, message)
                                else:
                                    send_telegram(chat_id, f"{EMOJI['list']} Không có key nào trong hệ thống.")
                            else:
                                send_telegram(chat_id, f"{EMOJI['warning']} Chỉ admin mới có quyền sử dụng lệnh này.")

                        elif text.startswith("/xoakey"):
                            if is_admin(chat_id):
                                parts = text.split()
                                if len(parts) == 2:
                                    key_to_delete = parts[1]
                                    if delete_key_from_db(key_to_delete):
                                        send_telegram(chat_id, f"{EMOJI['delete']} Đã xóa key `{key_to_delete}`.")
                                        log_message(f"Admin {chat_id} đã xóa key {key_to_delete}.")
                                    else:
                                        send_telegram(chat_id, f"{EMOJI['warning']} Không tìm thấy key `{key_to_delete}`.")
                                else:
                                    send_telegram(chat_id, f"{EMOJI['warning']} Sử dụng: `/xoakey <key_cần_xóa>`")
                            else:
                                send_telegram(chat_id, f"{EMOJI['warning']} Chỉ admin mới có quyền sử dụng lệnh này.")

                        elif text.startswith("/themadmin"):
                            if is_admin(chat_id):
                                parts = text.split()
                                if len(parts) == 2 and parts[1].isdigit():
                                    new_admin_id = int(parts[1])
                                    if add_admin_to_db(new_admin_id):
                                        send_telegram(chat_id, f"{EMOJI['admin']} Đã thêm admin ID `{new_admin_id}`.")
                                        log_message(f"Admin {chat_id} đã thêm admin {new_admin_id}.")
                                    else:
                                        send_telegram(chat_id, f"{EMOJI['warning']} Admin ID `{new_admin_id}` đã tồn tại.")
                                else:
                                    send_telegram(chat_id, f"{EMOJI['warning']} Sử dụng: `/themadmin <telegram_id>` (telegram_id phải là số).")
                            else:
                                send_telegram(chat_id, f"{EMOJI['warning']} Chỉ admin mới có quyền sử dụng lệnh này.")

                        elif text.startswith("/xoaadmin"):
                            if is_admin(chat_id):
                                parts = text.split()
                                if len(parts) == 2 and parts[1].isdigit():
                                    admin_to_remove = int(parts[1])
                                    if remove_admin_from_db(admin_to_remove):
                                        send_telegram(chat_id, f"{EMOJI['admin']} Đã xóa admin ID `{admin_to_remove}`.")
                                        log_message(f"Admin {chat_id} đã xóa admin {admin_to_remove}.")
                                    else:
                                        send_telegram(chat_id, f"{EMOJI['warning']} Không tìm thấy admin ID `{admin_to_remove}`.")
                                else:
                                    send_telegram(chat_id, f"{EMOJI['warning']} Sử dụng: `/xoaadmin <telegram_id>` (telegram_id phải là số).")
                            else:
                                send_telegram(chat_id, f"{EMOJI['warning']} Chỉ admin mới có quyền sử dụng lệnh này.")

                        elif text.startswith("/danhsachadmin"):
                            if is_admin(chat_id):
                                admins = get_all_admins_from_db()
                                if admins:
                                    admin_list_str = "\n".join([f"- `{admin_id}`" for admin_id in admins])
                                    message = (
                                        f"{EMOJI['admin']} *DANH SÁCH ADMIN*\n"
                                        f"══════════════════════════\n"
                                        f"{admin_list_str}\n"
                                        f"══════════════════════════\n"
                                        f"{EMOJI['info']} Tổng số admin: {len(admins)}"
                                    )
                                    send_telegram(chat_id, message)
                                else:
                                    send_telegram(chat_id, f"{EMOJI['admin']} Hiện tại không có admin nào.")
                            else:
                                send_telegram(chat_id, f"{EMOJI['warning']} Chỉ admin mới có quyền sử dụng lệnh này.")

                        elif text.startswith("/broadcast"):
                            if is_admin(chat_id):
                                broadcast_text = text.replace("/broadcast", "").strip()
                                if broadcast_text:
                                    success, result_msg = broadcast_message(broadcast_text)
                                    if success:
                                        send_telegram(chat_id, f"{EMOJI['broadcast']} {result_msg}")
                                    else:
                                        send_telegram(chat_id, f"{EMOJI['warning']} {result_msg}")
                                else:
                                    send_telegram(chat_id, f"{EMOJI['warning']} Sử dụng: `/broadcast <nội_dung>`")
                            else:
                                send_telegram(chat_id, f"{EMOJI['warning']} Chỉ admin mới có quyền sử dụng lệnh này.")

                        elif text.startswith("/help") or text.startswith("/trogiup"):
                            help_message = (
                                f"{EMOJI['bell']} *HƯỚNG DẪN SỬ DỤNG BOT*\n"
                                f"══════════════════════════\n"
                                f"{EMOJI['key']} *Lệnh cơ bản:*\n"
                                f"- `/start`: Hiển thị thông tin chào mừng\n"
                                f"- `/key <key>`: Nhập key để kích hoạt bot\n"
                                f"- `/chaybot`: Bật nhận thông báo\n"
                                f"- `/tatbot`: Tắt nhận thông báo\n"
                                f"- `/thongtin`: Xem thông tin tài khoản\n"
                                f"- `/lichsu`: Xem lịch sử 10 phiên gần nhất\n"
                                f"- `/thongke`: Xem thống kê chi tiết\n"
                                f"\n{EMOJI['admin']} *Lệnh admin:*\n"
                                f"- `/taokey <tên_key> [giới_hạn] [thời_gian]`: Tạo key mới\n"
                                f"- `/lietkekey`: Liệt kê tất cả key\n"
                                f"- `/xoakey <key>`: Xóa key\n"
                                f"- `/themadmin <id>`: Thêm admin\n"
                                f"- `/xoaadmin <id>`: Xóa admin\n"
                                f"- `/danhsachadmin`: Xem danh sách admin\n"
                                f"- `/broadcast <nội_dung>`: Gửi thông báo đến tất cả người dùng\n"
                                f"══════════════════════════\n"
                                f"{EMOJI['team']} Liên hệ admin để được hỗ trợ thêm"
                            )
                            send_telegram(chat_id, help_message)

        except requests.exceptions.RequestException as e:
            print(f"{EMOJI['warning']} Lỗi khi lấy updates từ Telegram: {e}")
            time.sleep(5)
        except json.JSONDecodeError as e:
            print(f"{EMOJI['warning']} Lỗi giải mã JSON từ Telegram: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"{EMOJI['warning']} Lỗi không xác định trong handle_telegram_updates: {e}")
            time.sleep(5)

# === HÀM CHÍNH ===
def main():
    init_db()

    # Thêm admin mặc định nếu chưa có
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM admins")
    if c.fetchone()[0] == 0:
        print(f"{EMOJI['admin']} Thêm admin đầu tiên với ID: 7761915412")
        c.execute("INSERT INTO admins (chat_id) VALUES (?)", ("7761915412",))
        conn.commit()
    conn.close()

    print(f"\n{EMOJI['diamond']} {'*'*20} {EMOJI['diamond']}")
    print(f"{EMOJI['rocket']} *SUNWIN VIP - BOT TÀI XỈU CHUẨN XÁC* {EMOJI['rocket']}")
    print(f"{EMOJI['diamond']} {'*'*20} {EMOJI['diamond']}\n")
    print(f"{EMOJI['settings']} Phiên bản: {BOT_VERSION}")
    print(f"{EMOJI['chart']} Hệ thống phân tích nâng cao")
    print(f"{EMOJI['team']} Phát triển bởi ??????\n")
    print(f"{EMOJI['bell']} Bot đã sẵn sàng hoạt động!")

    # Khởi chạy các luồng xử lý
    threading.Thread(target=background_task, daemon=True).start()
    threading.Thread(target=handle_telegram_updates, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{EMOJI['warning']} Đang dừng bot...")
        conn = get_db_connection()
        conn.close()
        print(f"{EMOJI['check']} Bot đã dừng an toàn")

if __name__ == "__main__":
    main()
