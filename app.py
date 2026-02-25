from flask import Flask, render_template, redirect, url_for, request, session, send_file
import sqlite3
import os
from datetime import datetime
import pandas as pd

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
            role TEXT
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
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER,
            year TEXT,
            day INTEGER,
            marked_by TEXT,
            marked_at TEXT,
            UNIQUE(member_id, year, day)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year TEXT
        )
    """)

    # Default Year
    c.execute("SELECT * FROM settings")
    if not c.fetchone():
        c.execute("INSERT INTO settings (year) VALUES (?)", ("1447",))

    # Default Users
    c.execute("SELECT * FROM users WHERE username='superadmin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)",
                  ("superadmin", "1234", "superadmin"))

    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)",
                  ("admin", "1234", "admin"))

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


# ---------------- AUTH ---------------- #

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
            session["user"] = user[1]
            session["role"] = user[3]
            return redirect(url_for("dashboard"))
        else:
            return "Invalid Credentials"

    return render_template("login.html", year=year)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------- DASHBOARD ---------------- #

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM members")
    total_members = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM attendance WHERE year=?", (get_year(),))
    total_attendance = c.fetchone()[0]

    conn.close()

    return render_template("dashboard.html",
                           total_members=total_members,
                           total_attendance=total_attendance,
                           role=session["role"],
                           year=get_year())


# ---------------- MEMBERS ---------------- #

@app.route("/members", methods=["GET", "POST"])
def members():
    if "user" not in session:
        return redirect(url_for("login"))

    if session["role"] != "superadmin":
        return "Access Denied"

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    if request.method == "POST":
        sabil = request.form["sabil"]
        name = request.form["name"]
        c.execute("INSERT INTO members (sabil_number, name, created_at) VALUES (?,?,?)",
                  (sabil, name, datetime.now()))
        conn.commit()

    c.execute("SELECT * FROM members ORDER BY id DESC")
    all_members = c.fetchall()
    conn.close()

    return render_template("members.html",
                           members=all_members,
                           year=get_year())


@app.route("/delete_member/<int:id>")
def delete_member(id):
    if session.get("role") != "superadmin":
        return "Access Denied"

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("DELETE FROM members WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("members"))


@app.route("/export_members")
def export_members():
    conn = sqlite3.connect(DATABASE)
    df = pd.read_sql_query("SELECT sabil_number, name, created_at FROM members", conn)
    conn.close()

    filename = "members_export.csv"
    df.to_csv(filename, index=False)

    return send_file(filename, as_attachment=True)


# ---------------- RUN LOCAL ---------------- #

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)