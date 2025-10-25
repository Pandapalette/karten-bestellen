from flask import Flask, render_template, request, redirect, url_for, session
import os, json, threading, time
from PIL import Image

app = Flask(__name__)
app.secret_key = "supersecretkey"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# JSON-Dateien
USERS_FILE = "data/users.json"
AUFTRAEGE_FILE = "data/auftraege.json"
BUGS_FILE = "data/bugs.json"
CHATS_FILE = "data/chats.json"
os.makedirs("data", exist_ok=True)

# Daten laden
def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

users = load_json(USERS_FILE, {})
auftraege = load_json(AUFTRAEGE_FILE, [])
bugs = load_json(BUGS_FILE, [])
chats = load_json(CHATS_FILE, {})

MAX_AUFTRAEGE = 40

# ======================= Auto-Save alle 5 Minuten =======================
def auto_save():
    while True:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=4)
        with open(AUFTRAEGE_FILE, "w", encoding="utf-8") as f:
            json.dump(auftraege, f, ensure_ascii=False, indent=4)
        with open(BUGS_FILE, "w", encoding="utf-8") as f:
            json.dump(bugs, f, ensure_ascii=False, indent=4)
        with open(CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump(chats, f, ensure_ascii=False, indent=4)
        time.sleep(300)

threading.Thread(target=auto_save, daemon=True).start()

# ======================= Hauptseiten =======================
@app.route("/")
def index():
    username = session.get("username")
    admin = session.get("admin")
    return render_template("index.html", username=username, admin=admin)

@app.route("/preise")
def preise():
    username = session.get("username")
    return render_template("preise.html", username=username)

# ======================= Benutzer Login/Register =======================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username or not password:
            return "Bitte Ingame-Namen und Passwort eingeben!"
        if username in users and users[username]["password"] == password:
            session["username"] = username
            return redirect(url_for("index"))
        else:
            return "Falscher Ingame-Name oder Passwort!"
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        username = request.form.get("username")
        password = request.form.get("password")
        confirm = request.form.get("confirm")
        if not email or not username or not password or not confirm:
            return "Bitte alle Felder ausfüllen!"
        if password != confirm:
            return "Passwörter stimmen nicht überein!"
        if username in users:
            return "Benutzername existiert bereits!"
        users[username] = {"email": email, "password": password}
        session["username"] = username
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=4)
        return redirect(url_for("index"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    session.pop("admin", None)
    return redirect(url_for("index"))

# ======================= Bestellen =======================
@app.route("/bestellen", methods=["GET", "POST"])
def bestellen():
    username = session.get("username")
    if not username:
        return redirect(url_for("login"))

    message = None
    preview_image = None

    if request.method == "POST":
        try:
            breite = int(request.form.get("breite"))
            hoehe = int(request.form.get("hoehe"))
        except (ValueError, TypeError):
            message = "Bitte gültige Breite und Höhe angeben!"
            return render_template("bestellen.html", username=username, message=message)

        user_auftraege = [a for a in auftraege if a["username"] == username]
        if len(user_auftraege) >= MAX_AUFTRAEGE:
            message = "Zu viele Kartenaufträge!"
            return render_template("bestellen.html", username=username, message=message)

        file = request.files.get("image")
        if file:
            filename = f"{username}_{len(auftraege)+1}.png"
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)

            try:
                with Image.open(path) as img:
                    if img.width > 1500 or img.height > 1500:
                        img.thumbnail((1500, 1500))
                        img.save(path)
            except:
                message = "Fehler beim Verarbeiten des Bildes!"
                return render_template("bestellen.html", username=username, message=message)

            preview_image = f"/{path.replace(os.sep, '/')}"

            # Auftrag speichern nach Absenden
            if request.form.get("submit"):
                auftrag_id = len(auftraege) + 1
                auftrag = {
                    "id": auftrag_id,
                    "username": username,
                    "breite": breite,
                    "hoehe": hoehe,
                    "image": preview_image
                }
                auftraege.append(auftrag)
                chats[str(auftrag_id)] = []
                return redirect(url_for("index"))

    return render_template("bestellen.html", username=username, message=message, preview_image=preview_image)

# ======================= Meine Aufträge =======================
@app.route("/meine_auftraege")
def meine_auftraege():
    username = session.get("username")
    if not username:
        return redirect(url_for("login"))
    user_auftraege = [a for a in auftraege if a["username"] == username]
    seite = int(request.args.get("seite", 1))
    max_seite = (len(user_auftraege)-1)//10 + 1 if user_auftraege else 1
    start = (seite-1)*10
    end = start + 10
    auftraege_seite = user_auftraege[start:end]
    return render_template("meine_auftraege.html",
                           username=username,
                           auftraege=auftraege_seite,
                           seite=seite,
                           max_seite=max_seite)

# ======================= Chat =======================
@app.route("/chat/<int:auftrag_id>", methods=["GET", "POST"])
def chat(auftrag_id):
    username = session.get("username")
    admin = session.get("admin", False)
    if not username:
        return redirect(url_for("login"))

    auftrag = next((a for a in auftraege if a["id"]==auftrag_id), None)
    if not auftrag:
        return "Auftrag nicht gefunden!"
    if auftrag["username"] != username and not admin:
        return "Zugriff verweigert!"

    if str(auftrag_id) not in chats:
        chats[str(auftrag_id)] = []

    if request.method == "POST":
        text = request.form.get("text")
        if text:
            chats[str(auftrag_id)].append({
                "user": username,
                "text": text,
                "timestamp": time.time()
            })

    return render_template("chat.html", chat=chats[str(auftrag_id)],
                           username=username, admin=admin, auftrag_id=auftrag_id)

@app.route("/chat/delete/<int:auftrag_id>", methods=["POST"])
def chat_delete(auftrag_id):
    if not session.get("admin"):
        return "Nur Admins können löschen!"
    chats.pop(str(auftrag_id), None)
    return redirect(url_for("admin"))

# ======================= Admin Login =======================
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == "015569026859":
            session["admin"] = True
            return redirect(url_for("admin"))
        else:
            error = "Falsches Passwort!"
            return render_template("admin_login.html", error=error)
    return render_template("admin_login.html")

# ======================= Admin Dashboard =======================
@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    return render_template("admin.html", auftraege=auftraege, bugs=bugs)

# ======================= Fehler melden =======================
@app.route("/bug_report", methods=["GET", "POST"])
def bug_report():
    username = session.get("username")
    if request.method == "POST":
        text = request.form.get("text")
        if text:
            bugs.append({"user": username, "text": text})
    return render_template("bug_report.html", username=username, bugs=bugs)

# =======================
if __name__ == "__main__":
    app.run(debug=True)
