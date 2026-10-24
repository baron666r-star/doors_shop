from flask import Flask, render_template, request, session, redirect, url_for, flash
import json
import requests
import datetime
import socket
import re

# ==========================================
# ПАТЧ ДЛЯ ОБХОДА БЛОКИРОВКИ DNS TELEGRAM
# ==========================================
_original_getaddrinfo = socket.getaddrinfo

def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host == 'api.telegram.org':
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('149.154.167.220', port))]
    return _original_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = _patched_getaddrinfo
# ==========================================

app = Flask(__name__)
app.secret_key = "door-dvor-secret-2026"

# ==========================================
# ⚠️ ВАЖНО: ВСТАВЬТЕ СВОИ ДАННЫЕ СЮДА
# ==========================================
TELEGRAM_TOKEN = "8951150406:AAEHuvUzqVQwFl815PMUfd9DB933hHmWE6A"
TELEGRAM_CHAT_ID = "1178599530"
# ==========================================

# Загружаем входные двери
try:
    with open("doors.json", "r", encoding="utf-8") as f:
        DOORS = json.load(f)
except FileNotFoundError:
    DOORS = []

# Загружаем межкомнатные двери и делаем их ID уникальными
try:
    with open("interior.json", "r", encoding="utf-8") as f:
        INTERIOR = json.load(f)
        for door in INTERIOR:
            door["id"] = int(door["id"]) + 1000
except FileNotFoundError:
    INTERIOR = []

def get_door(door_id):
    for door in DOORS:
        if door["id"] == door_id:
            return door
    for door in INTERIOR:
        if door["id"] == door_id:
            return door
    return None

@app.template_filter("rub")
def rub_filter(value):
    return "{:,}".format(int(value)).replace(",", " ") + " ₽"

@app.context_processor
def inject_cart():
    cart = session.get("cart", {})
    return {"cart_count": sum(cart.values())}

# --- ФУНКЦИЯ ДЛЯ ТЕЛЕГРАМА ---
def send_telegram_message(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        requests.post(url, json=payload, timeout=10)
        print("Уведомление в Telegram успешно отправлено!")
    except Exception as e:
        print("Ошибка отправки в Telegram:", e)

# --- МАРШРУТЫ ---

@app.route("/")
def index():
    return render_template("index.html", doors=DOORS)

@app.route("/interior")
def interior_page():
    return render_template("interior.html", doors=INTERIOR)

@app.route("/door/<int:door_id>")
def door_detail(door_id):
    door = get_door(door_id)
    if not door:
        flash("Дверь не найдена", "error")
        return redirect(url_for("index"))
    return render_template("door.html", door=door)

@app.route("/add_to_cart/<int:door_id>", methods=["POST"])
def add_to_cart(door_id):
    door = get_door(door_id)
    if not door:
        flash("Дверь не найдена", "error")
        return redirect(request.referrer or url_for("index"))
    cart = session.get("cart", {})
    key = str(door_id)
    cart[key] = cart.get(key, 0) + 1
    session["cart"] = cart
    flash(f"«{door['name']}» добавлена в корзину", "success")
    return redirect(request.referrer or url_for("index"))

@app.route("/cart")
def cart():
    cart = session.get("cart", {})
    items = []
    total = 0
    for door_id, qty in cart.items():
        door = get_door(int(door_id))
        if door:
            item_total = door["price"] * qty
            total += item_total
            items.append({"id": door["id"], "name": door["name"],
                          "price": door["price"], "qty": qty, "total": item_total})
    return render_template("cart.html", items=items, total=total)

@app.route("/remove_from_cart/<int:door_id>", methods=["POST"])
def remove_from_cart(door_id):
    cart = session.get("cart", {})
    if str(door_id) in cart:
        del cart[str(door_id)]
        session["cart"] = cart
        flash("Товар удалён из корзины", "success")
    return redirect(url_for("cart"))

@app.route("/clear_cart", methods=["POST"])
def clear_cart():
    session["cart"] = {}
    flash("Корзина очищена", "success")
    return redirect(url_for("cart"))

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = session.get("cart", {})
    items = []
    total = 0
    for door_id, qty in cart.items():
        door = get_door(int(door_id))
        if door:
            item_total = door["price"] * qty
            total += item_total
            items.append({"id": door["id"], "name": door["name"],
                          "price": door["price"], "qty": qty, "total": item_total})

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        
        # --- СЕРВЕРНАЯ ВАЛИДАЦИЯ ---
        if not re.match(r"^[А-Яа-яЁёA-Za-z\s\-]{2,50}$", name):
            flash("Пожалуйста, введите корректное имя (только буквы).", "error")
            return redirect(url_for("checkout"))
            
        phone_digits = re.sub(r"\D", "", phone)
        if len(phone_digits) < 10:
            flash("Пожалуйста, введите корректный номер телефона (минимум 10 цифр).", "error")
            return redirect(url_for("checkout"))
        # ---------------------------

        order = {
            "id": int(datetime.datetime.now().timestamp()),
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "name": name,
            "phone": phone,
            "address": request.form.get("address"),
            "comment": request.form.get("comment"),
            "items": items,
            "total": total
        }
        
        try:
            with open("orders.json", "r", encoding="utf-8") as f:
                orders = json.load(f)
        except FileNotFoundError:
            orders = []
            
        orders.append(order)
        
        with open("orders.json", "w", encoding="utf-8") as f:
            json.dump(orders, f, ensure_ascii=False, indent=4)
            
        session["cart"] = {}
        
        # Отправка в Telegram
        msg = f"🚪 <b>Новый заказ №{order['id']}</b>\n\n"
        msg += f"👤 <b>Имя:</b> {order['name']}\n"
        msg += f"📞 <b>Телефон:</b> {order['phone']}\n"
        msg += f"📍 <b>Адрес:</b> {order['address']}\n"
        msg += f"💰 <b>Сумма:</b> {order['total']} ₽\n\n"
        msg += "<b>Состав заказа:</b>\n"
        for item in order['items']:
            msg += f"• {item['name']} — {item['qty']} шт.\n"
        
        send_telegram_message(msg)
        
        return render_template("success.html", order_id=order["id"])
        
    return render_template("checkout.html", items=items, total=total)

@app.route("/request_call", methods=["POST"])
def request_call():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    
    # --- СЕРВЕРНАЯ ВАЛИДАЦИЯ ДЛЯ ЗВОНКА ---
    if not re.match(r"^[А-Яа-яЁёA-Za-z\s\-]{2,50}$", name):
        return "Ошибка: неверное имя", 400
        
    phone_digits = re.sub(r"\D", "", phone)
    if len(phone_digits) < 10:
        return "Ошибка: неверный телефон", 400
    # --------------------------------------

    msg = f"📞 <b>Заявка на звонок!</b>\n\n"
    msg += f"👤 <b>Имя:</b> {name}\n"
    msg += f"📱 <b>Телефон:</b> {phone}\n"
    send_telegram_message(msg)
    
    return "OK", 200

# --- АДМИН-ПАНЕЛЬ ---
ADMIN_PASSWORD = "admin123"

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_orders"))
        else:
            flash("Неверный пароль!", "error")
    return render_template("admin_login.html")

@app.route("/admin")
def admin_orders():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    
    try:
        with open("orders.json", "r", encoding="utf-8") as f:
            orders = json.load(f)
    except FileNotFoundError:
        orders = []
        
    return render_template("admin_orders.html", orders=orders)

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)