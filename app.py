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

    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    """)

    # Members table
    c.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sabil_number TEXT UNIQUE,
            name TEXT,
            created_at TEXT
        )
    """)

    # Attendance table
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

    # Settings table
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year TEXT
        )
    """)

    # Insert default year if not exists
    c.execute("SELECT * FROM settings")
    if not c.fetchone():
        c.execute("INSERT INTO settings (year) VALUES (?)", ("1447",))

    # Insert default users
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


def get_year():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT year FROM settings LIMIT 1")
    year = c.fetchone()[0]
    conn.close()
    return year


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


# ---------------- RUN ---------------- #

if __name__ == "__main__":
    init_db()
    app.run(debug=True)