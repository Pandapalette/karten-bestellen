from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import os
import json
import time

app = Flask(__name__)
app.secret_key = "supersecretkey"

# JSON-Dateien
USERS_FILE = "users.json"
ORDERS_FILE = "orders.json"
BUG_REPORTS_FILE = "bug_reports.json"
CHATS_DIR = "chats"

# Verzeichnisse anlegen, falls nicht vorhanden
os.makedirs(CHATS_DIR, exist_ok=True)
os.makedirs("static/uploads", exist_ok=True)


# Hilfsfunktionen ------------------------------------------------------

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# Startseite -----------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# Preise-Seite ---------------------------------------------------------
@app.route("/preise")
def preise():
    return render_template("preise.html")


# Registrierung --------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    users = load_json(USERS_FILE)
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username in users:
            return "Benutzername bereits vergeben."
        users[username] = {"password": password, "is_admin": False}
        save_json(USERS_FILE, users)
        return redirect(url_for("login"))

    return render_template("register.html")


# Login ---------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    users = load_json(USERS_FILE)
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username in users and users[username]["password"] == password:
            session["username"] = username
            session["is_admin"] = users[username].get("is_admin", False)
            if session["is_admin"]:
                return redirect(url_for("admin_menu"))
            return redirect(url_for("index"))
        return "Falscher Benutzername oder Passwort."

    return render_template("login.html")


# Logout ---------------------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# Bestellung -----------------------------------------------------------
@app.route("/bestellen", methods=["GET", "POST"])
def bestellen():
    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        orders = load_json(ORDERS_FILE)
        username = session["username"]
        titel = request.form["titel"]
        beschreibung = request.form["beschreibung"]
        bild = request.files["bild"]

        if bild:
            filename = f"{username}_{int(time.time())}_{bild.filename}"
            filepath = os.path.join("static/uploads", filename)
            bild.save(filepath)
        else:
            filename = None

        auftrag_id = f"{username}_Karte_{len(orders) + 1}"
        orders[auftrag_id] = {
            "user": username,
            "titel": titel,
            "beschreibung": beschreibung,
            "bild": filename,
            "status": "Offen"
        }

        save_json(ORDERS_FILE, orders)

        chat_file = os.path.join(CHATS_DIR, f"{auftrag_id}.json")
        save_json(chat_file, [])

        return redirect(url_for("meine_auftraege"))

    return render_template("bestellen.html")


# Eigene Aufträge ------------------------------------------------------
@app.route("/meine_auftraege")
def meine_auftraege():
    if "username" not in session:
        return redirect(url_for("login"))

    orders = load_json(ORDERS_FILE)
    eigene_auftraege = {
        k: v for k, v in orders.items() if v["user"] == session["username"]
    }

    return render_template("meine_auftraege.html", auftraege=eigene_auftraege)


# Karte-Detail + Chat --------------------------------------------------
@app.route("/karte/<auftrag_id>")
def karte_detail(auftrag_id):
    if "username" not in session:
        return redirect(url_for("login"))

    orders = load_json(ORDERS_FILE)
    if auftrag_id not in orders:
        return "Auftrag nicht gefunden."

    auftrag = orders[auftrag_id]
    username = session["username"]

    # Admin darf alles sehen
    if auftrag["user"] != username and username != "Pandapalette":
        return "Zugriff verweigert."

    chat_file = os.path.join(CHATS_DIR, f"{auftrag_id}.json")
    if not os.path.exists(chat_file):
        save_json(chat_file, [])

    with open(chat_file, "r", encoding="utf-8") as f:
        chat = json.load(f)

    return render_template("karte_detail.html", auftrag=auftrag, chat=chat, auftrag_id=auftrag_id)


# Nachricht im Chat senden ---------------------------------------------
@app.route("/chat/<auftrag_id>", methods=["POST"])
def chat_send(auftrag_id):
    if "username" not in session:
        return "Nicht eingeloggt", 403

    msg = request.form["message"]
    chat_file = os.path.join(CHATS_DIR, f"{auftrag_id}.json")

    chat = load_json(chat_file)
    chat.append({
        "user": session["username"],
        "message": msg,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    save_json(chat_file, chat)
    return redirect(url_for("karte_detail", auftrag_id=auftrag_id))


# Fehler melden --------------------------------------------------------
@app.route("/bug_report", methods=["GET", "POST"])
def bug_report():
    if request.method == "POST":
        bug_reports = load_json(BUG_REPORTS_FILE)
        bug_id = str(int(time.time()))
        bug_reports[bug_id] = {
            "user": session.get("username", "Unbekannt"),
            "beschreibung": request.form["beschreibung"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        save_json(BUG_REPORTS_FILE, bug_reports)
        return redirect(url_for("index"))
    return render_template("bug_report.html")


# Admin Menü -----------------------------------------------------------
@app.route("/admin")
def admin_menu():
    if "username" not in session or session["username"] != "Pandapalette":
        return redirect(url_for("login"))

    orders = load_json(ORDERS_FILE)
    return render_template("admin.html", auftraege=orders)


# Static Uploads -------------------------------------------------------
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory("static/uploads", filename)


# Startpunkt -----------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
