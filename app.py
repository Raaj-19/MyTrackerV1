
import os, sqlite3, csv, datetime, json, random
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "mytracker.db")

app = Flask(__name__)
app.secret_key = os.environ.get("MYTRACKER_SECRET", "change_this_secret_for_production")

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    cursor = db.cursor()
    # Users
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        display_name TEXT,
        avatar TEXT,
        last_login TEXT
    )
    """)
    # Records (user-specific)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        r_type TEXT NOT NULL, -- Income/Expense/Investment
        category TEXT,
        amount REAL NOT NULL,
        notes TEXT,
        date TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    db.commit()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# Helpers
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    db = get_db()
    user = db.execute("SELECT id,email,display_name,avatar,last_login FROM users WHERE id=?", (uid,)).fetchone()
    return user

def login_user(user_id):
    session["user_id"] = user_id
    db = get_db()
    last_login = datetime.datetime.utcnow().isoformat()
    db.execute("UPDATE users SET last_login=? WHERE id=?", (last_login, user_id))
    db.commit()

# Sample data loader (for initial demo)
def seed_sample(user_id):
    db = get_db()
    cur = db.cursor()
    sample = [
        ("Income","Salary",50000,"Monthly salary","2025-07-01"),
        ("Expense","Rent",15000,"July rent","2025-07-02"),
        ("Expense","Grocery",5000,"Groceries","2025-07-05"),
        ("Investment","Mutual Fund",10000,"SIP monthly","2025-07-03"),
        ("Income","Freelance",12000,"Project","2025-06-15"),
        ("Expense","Internet",1000,"Net","2025-06-20")
    ]
    for r in sample:
        cur.execute("INSERT INTO records (user_id,r_type,category,amount,notes,date) VALUES (?,?,?,?,?,?)", (user_id,)+r)
    db.commit()

# Routes
@app.route("/")
def index():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    # randomize background from images list
    images = os.listdir(os.path.join(BASE_DIR, "static", "images"))
    banner = None
    if images:
        banner = "/static/images/" + random.choice(images)
    return render_template("dashboard.html", user=user, banner=banner)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        email = request.form.get("email")
        password = request.form.get("password")
        display = request.form.get("display") or email.split("@")[0]
        db = get_db()
        try:
            db.execute("INSERT INTO users (email,password,display_name) VALUES (?,?,?)", (email, generate_password_hash(password), display))
            db.commit()
            user = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            # seed sample data for first account (optional)
            seed_sample(user["id"])
            login_user(user["id"])
            return redirect(url_for("index"))
        except sqlite3.IntegrityError:
            flash("Email already registered")
            return redirect(url_for("register"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email = request.form.get("email")
        password = request.form.get("password")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], password):
            login_user(user["id"])
            return redirect(url_for("index"))
        flash("Invalid credentials")
        return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# CRUD: add record
@app.route("/add", methods=["GET","POST"])
def add_record():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    if request.method=="POST":
        r_type = request.form.get("type")
        category = request.form.get("category") or ""
        amount = float(request.form.get("amount") or 0)
        notes = request.form.get("notes") or ""
        date = request.form.get("date") or datetime.date.today().isoformat()
        db = get_db()
        db.execute("INSERT INTO records (user_id,r_type,category,amount,notes,date) VALUES (?,?,?,?,?)", (user["id"],r_type,category,amount,notes,date))
        db.commit()
        return redirect(url_for("records"))
    return render_template("add_entry.html")

@app.route("/records")
def records():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    db = get_db()
    rows = db.execute("SELECT * FROM records WHERE user_id=? ORDER BY date DESC", (user["id"],)).fetchall()
    return render_template("records.html", rows=rows, user=user)

@app.route("/record/<int:rid>/edit", methods=["GET","POST"])
def edit_record(rid):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    db = get_db()
    rec = db.execute("SELECT * FROM records WHERE id=? AND user_id=?", (rid, user["id"])).fetchone()
    if not rec:
        flash("Record not found"); return redirect(url_for("records"))
    if request.method=="POST":
        db.execute("UPDATE records SET r_type=?, category=?, amount=?, notes=?, date=? WHERE id=? AND user_id=?", 
                   (request.form.get("type"), request.form.get("category"), float(request.form.get("amount")), request.form.get("notes"), request.form.get("date"), rid, user["id"]))
        db.commit()
        return redirect(url_for("records"))
    return render_template("edit_record.html", rec=rec)

@app.route("/record/<int:rid>/delete", methods=["POST"])
def delete_record(rid):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    db = get_db()
    db.execute("DELETE FROM records WHERE id=? AND user_id=?", (rid, user["id"]))
    db.commit()
    return redirect(url_for("records"))

# API endpoints for charts and summaries (JSON)
@app.route("/api/summary")
def api_summary():
    user = current_user()
    if not user:
        return jsonify({}), 401
    db = get_db()
    # current month totals
    now = datetime.date.today()
    month_start = now.replace(day=1).isoformat()
    rows = db.execute("SELECT r_type, SUM(amount) as total FROM records WHERE user_id=? AND date>=? GROUP BY r_type", (user["id"], month_start)).fetchall()
    summary = {"Income":0,"Expense":0,"Investment":0}
    for r in rows:
        summary[r["r_type"]] = r["total"] or 0
    return jsonify(summary)

@app.route("/api/chart_data")
def api_chart_data():
    user = current_user()
    if not user:
        return jsonify({}), 401
    db = get_db()
    # expenses by category
    rows = db.execute("SELECT category, SUM(amount) as total FROM records WHERE user_id=? AND r_type='Expense' GROUP BY category", (user["id"],)).fetchall()
    exp = [{"category":r["category"] or "Other", "total": r["total"]} for r in rows]
    # monthly totals (income/expense)
    rows2 = db.execute("SELECT date, r_type, SUM(amount) as total FROM records WHERE user_id=? GROUP BY date, r_type ORDER BY date", (user["id"],)).fetchall()
    monthly = {}
    for r in rows2:
        d = r["date"][:7]  # YYYY-MM
        if d not in monthly: monthly[d] = {"Income":0,"Expense":0}
        monthly[d][r["r_type"]] = monthly[d].get(r["r_type"],0) + r["total"]
    monthly_sorted = sorted(monthly.items())
    labels = [m for m,_ in monthly_sorted]
    income_vals = [v.get("Income",0) for _,v in monthly_sorted]
    expense_vals = [v.get("Expense",0) for _,v in monthly_sorted]
    return jsonify({"expense_by_category":exp, "monthly": {"labels": labels, "income": income_vals, "expense": expense_vals}})

# Export CSV
@app.route("/export")
def export_csv():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    db = get_db()
    rows = db.execute("SELECT r_type, category, amount, notes, date, created_at FROM records WHERE user_id=? ORDER BY date DESC", (user["id"],)).fetchall()
    fname = f"mytracker_export_{user['email'].replace('@','_')}.csv"
    path = os.path.join(BASE_DIR, fname)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Type","Category","Amount","Notes","Date","CreatedAt"])
        for r in rows:
            writer.writerow([r["r_type"], r["category"], r["amount"], r["notes"], r["date"], r["created_at"]])
    return send_file(path, as_attachment=True)

# Reset user data
@app.route("/reset", methods=["POST"])
def reset_data():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    db = get_db()
    db.execute("DELETE FROM records WHERE user_id=?", (user["id"],))
    db.commit()
    return redirect(url_for("index"))

if __name__ == "__main__":
    # initialize DB if missing
    if not os.path.exists(DB_PATH):
        with app.app_context():
            init_db()
    app.run(host="0.0.0.0", port=10000, debug=True)
