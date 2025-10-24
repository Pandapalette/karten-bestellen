from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
import os
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Speicherorte
UPLOAD_FOLDER = "static/uploads"
ORDER_FILE = "orders.json"
USER_FILE = "users.json"
CHAT_FOLDER = "chats"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHAT_FOLDER, exist_ok=True)

# ---------------- Hilfsfunktionen ----------------

def load_orders():
    if not os.path.exists(ORDER_FILE):
        return {}
    with open(ORDER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_orders(data):
    with open(ORDER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(data):
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def norm_name_from_form(form):
    uname = form.get("username") or form.get("ingame_name") or form.get("ingame")
    if uname:
        return uname.strip()
    return None

# ---------------- Startseite ----------------

@app.route("/")
def home():
    return render_template("index.html")

# ---------------- Registrierung ----------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email") or ""
        username = norm_name_from_form(request.form)
        password = request.form.get("password") or ""

        if not username or not password or not email:
            flash("Bitte E-Mail, Benutzernamen und Passwort ausfüllen.")
            return redirect(url_for("register"))

        users = load_users()
        if username in users:
            flash("Benutzername existiert bereits!")
            return redirect(url_for("register"))

        users[username] = {"email": email, "password": password}
        save_users(users)
        flash("Registrierung erfolgreich! Du kannst dich jetzt anmelden.")
        return redirect(url_for("login"))

    return render_template("register.html")

# ---------------- Login ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = norm_name_from_form(request.form)
        password = request.form.get("password") or ""

        if not username or not password:
            flash("Bitte Benutzernamen und Passwort eingeben.")
            return redirect(url_for("login"))

        users = load_users()
        user = users.get(username)
        if user and user.get("password") == password:
            session["user"] = username
            flash("Erfolgreich eingeloggt!")
            return redirect(url_for("home"))
        else:
            flash("Nutzername oder Passwort ist falsch.")
            return redirect(url_for("login"))

    return render_template("login.html")

# ---------------- Logout ----------------

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Du wurdest ausgeloggt.")
    return redirect(url_for("home"))

# ---------------- Karte bestellen ----------------

@app.route("/bestellen", methods=["GET", "POST"])
def bestellen():
    if "user" not in session:
        flash("Bitte melde dich an, um eine Karte zu bestellen.")
        return redirect(url_for("login"))

    if request.method == "POST":
        breite = request.form.get("breite")
        hoehe = request.form.get("hoehe")
        bild = request.files.get("bild")
        user = session["user"]

        if not (breite and hoehe and bild):
            flash("Bitte fülle alle Felder aus!")
            return redirect(url_for("bestellen"))

        try:
            breite_i = int(breite)
            hoehe_i = int(hoehe)
        except ValueError:
            flash("Breite und Höhe müssen ganze Zahlen sein.")
            return redirect(url_for("bestellen"))

        safe_filename = f"{user}_{int(datetime.now().timestamp())}_{os.path.basename(bild.filename)}"
        bildpfad = os.path.join(UPLOAD_FOLDER, safe_filename)
        bild.save(bildpfad)

        orders = load_orders()
        if user not in orders:
            orders[user] = []

        nummer = len(orders[user]) + 1
        preis = breite_i * hoehe_i * 400_000

        new_order = {
            "nummer": nummer,
            "breite": breite_i,
            "hoehe": hoehe_i,
            "preis": preis,
            "bild": safe_filename,
            "timestamp": datetime.now().isoformat()
        }

        orders[user].append(new_order)
        save_orders(orders)

        chat_path = os.path.join(CHAT_FOLDER, f"{user}_Karte_{nummer}.json")
        with open(chat_path, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

        flash("Karte erfolgreich bestellt! 📦")
        return redirect(url_for("meine_auftraege"))

    return render_template("bestellen.html")

# ---------------- Meine Aufträge ----------------

@app.route("/meine_auftraege")
def meine_auftraege():
    if "user" not in session:
        flash("Bitte anmelden, um Deine Aufträge zu sehen!")
        return redirect(url_for("login"))

    user = session["user"]
    orders = load_orders().get(user, [])
    return render_template("meine_auftraege.html", orders=orders, ingame_name=user)

@app.route("/meine_auftraege/delete/<int:nummer>", methods=["POST"])
def user_delete_order(nummer):
    if "user" not in session:
        flash("Bitte anmelden, um Aufträge zu löschen!")
        return redirect(url_for("login"))

    user = session["user"]
    orders = load_orders()

    if user in orders:
        orders[user] = [o for o in orders[user] if o["nummer"] != nummer]
        if not orders[user]:
            orders.pop(user, None)
        save_orders(orders)

    chat_path = os.path.join(CHAT_FOLDER, f"{user}_Karte_{nummer}.json")
    if os.path.exists(chat_path):
        os.remove(chat_path)

    flash(f"Auftrag Karte_{nummer} gelöscht!")
    return redirect(url_for("meine_auftraege"))

# ---------------- Admin-Bereich ----------------

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        pw = request.form.get("admin_pass")
        if pw == "015569026859":
            orders = load_orders()
            return render_template("admin.html", orders=orders)
        else:
            flash("Falsches Admin-Passwort!")
            return redirect(url_for("admin"))
    return render_template("admin_login.html")

@app.route("/admin/delete/<ingame_name>/<int:nummer>", methods=["POST"])
def admin_delete(ingame_name, nummer):
    pw = request.form.get("admin_pass")
    if pw != "015569026859":
        flash("Falsches Passwort!")
        return redirect(url_for("admin"))

    orders = load_orders()
    if ingame_name in orders:
        orders[ingame_name] = [o for o in orders[ingame_name] if o["nummer"] != nummer]
        if not orders[ingame_name]:
            orders.pop(ingame_name, None)
        save_orders(orders)

    chat_path = os.path.join(CHAT_FOLDER, f"{ingame_name}_Karte_{nummer}.json")
    if os.path.exists(chat_path):
        os.remove(chat_path)

    flash(f"Auftrag von {ingame_name} (Karte {nummer}) gelöscht!")
    return redirect(url_for("admin"))

# ---------------- Chat & Kartenanzeige ----------------

def load_chat(ingame_name, nummer):
    path = os.path.join(CHAT_FOLDER, f"{ingame_name}_Karte_{nummer}.json")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_chat(ingame_name, nummer, messages):
    path = os.path.join(CHAT_FOLDER, f"{ingame_name}_Karte_{nummer}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

@app.route("/<ingame_name>/Karte_<int:nummer>", methods=["GET", "POST"])
def karte_detail(ingame_name, nummer):
    user = session.get("user")

    # Zugriff: Besitzer oder Admin "Pandapalette"
    if not user or (user != ingame_name and user != "Pandapalette"):
        return "Zugriff verweigert. Nur der Ersteller oder Admin kann diese Seite sehen.", 403

    orders = load_orders()
    user_orders = orders.get(ingame_name, [])
    order = next((o for o in user_orders if o["nummer"] == nummer), None)
    if not order:
        return "Bestellung nicht gefunden", 404

    if request.method == "POST":
        text = request.form.get("text")
        if text:
            messages = load_chat(ingame_name, nummer)
            messages.append({
                "user": user,
                "text": text,
                "time": datetime.now().isoformat()
            })
            save_chat(ingame_name, nummer, messages)
        return redirect(url_for("karte_detail", ingame_name=ingame_name, nummer=nummer))

    messages = load_chat(ingame_name, nummer)
    return render_template("karte_detail.html", ingame_name=ingame_name, order=order, messages=messages)

# ---------------- Uploads ausliefern ----------------

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ---------------- App starten ----------------

if __name__ == "__main__":
    app.run(debug=True)
