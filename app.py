from flask import Flask, render_template, redirect, url_for, request, session, flash
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"

DATABASE = "database.db"


# ---------------- DATABASE ---------------- #

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            can_manage_members INTEGER,
            can_mark_attendance INTEGER,
            can_change_settings INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sabil_number TEXT UNIQUE,
            name TEXT,
            created_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year TEXT
        )
    """)

    # Default year
    c.execute("SELECT * FROM settings")
    if not c.fetchone():
        c.execute("INSERT INTO settings (year) VALUES (?)", ("1447",))

    # Default superadmin
    c.execute("SELECT * FROM users WHERE username='superadmin'")
    if not c.fetchone():
        c.execute("""
            INSERT INTO users
            (username, password, can_manage_members, can_mark_attendance, can_change_settings)
            VALUES (?,?,?,?,?)
        """, ("superadmin", "1234", 1, 1, 1))

    conn.commit()
    conn.close()


@app.before_request
def ensure_database():
    if not os.path.exists(DATABASE):
        init_db()


def get_year():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT year FROM settings LIMIT 1")
    year = c.fetchone()[0]
    conn.close()
    return year


def get_current_user():
    if "user_id" not in session:
        return None

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (session["user_id"],))
    user = c.fetchone()
    conn.close()
    return user


# ---------------- LOGIN ---------------- #

@app.route("/", methods=["GET", "POST"])
def login():
    year = get_year()

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?",
                  (username, password))
        user = c.fetchone()
        conn.close()

        if user:
            session["user_id"] = user[0]
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid Credentials")

    return render_template("login.html", year=year)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------- DASHBOARD ---------------- #

@app.route("/dashboard")
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    return render_template("dashboard.html",
                           year=get_year())


# ---------------- USERS MANAGEMENT ---------------- #

@app.route("/users", methods=["GET", "POST"])
def users():
    user = get_current_user()
    if not user or user[5] != 1:
        return "Access Denied"

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        manage = 1 if request.form.get("manage") else 0
        attendance = 1 if request.form.get("attendance") else 0
        settings = 1 if request.form.get("settings") else 0

        c.execute("""
            INSERT INTO users
            (username, password, can_manage_members, can_mark_attendance, can_change_settings)
            VALUES (?,?,?,?,?)
        """, (username, password, manage, attendance, settings))
        conn.commit()
        flash("User Created Successfully")

    c.execute("SELECT * FROM users")
    all_users = c.fetchall()
    conn.close()

    return render_template("users.html",
                           users=all_users,
                           year=get_year())


@app.route("/reset_password/<int:user_id>", methods=["POST"])
def reset_password(user_id):
    user = get_current_user()
    if not user or user[5] != 1:
        return "Access Denied"

    new_password = request.form["new_password"]

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("UPDATE users SET password=? WHERE id=?", (new_password, user_id))
    conn.commit()
    conn.close()

    flash("Password Reset Successfully")
    return redirect(url_for("users"))


# ---------------- CHANGE OWN PASSWORD ---------------- #

@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        current = request.form["current"]
        new = request.form["new"]

        if current != user[2]:
            flash("Current password incorrect")
            return redirect(url_for("change_password"))

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("UPDATE users SET password=? WHERE id=?", (new, user[0]))
        conn.commit()
        conn.close()

        flash("Password Updated Successfully")
        return redirect(url_for("dashboard"))

    return render_template("change_password.html",
                           year=get_year())


# ---------------- RUN LOCAL ---------------- #

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)