from flask import Flask, render_template, redirect, url_for, request, session, flash
import os
import psycopg2
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"

DATABASE_URL = os.environ.get("DATABASE_URL")


# ---------------- DATABASE ---------------- #

def get_connection():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require"
    )


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # USERS
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            can_manage_members INTEGER,
            can_mark_attendance INTEGER,
            can_change_settings INTEGER
        );
    """)

    # MEMBERS
    c.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id SERIAL PRIMARY KEY,
            sabil_number TEXT UNIQUE,
            name TEXT,
            created_at TIMESTAMP
        );
    """)

    # SETTINGS
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id SERIAL PRIMARY KEY,
            year TEXT
        );
    """)

    # ATTENDANCE
    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id SERIAL PRIMARY KEY,
            member_id INTEGER,
            year TEXT,
            day INTEGER,
            marked_at TIMESTAMP,
            UNIQUE(member_id, year, day)
        );
    """)

    # Default year
    c.execute("SELECT * FROM settings;")
    if not c.fetchone():
        c.execute("INSERT INTO settings (year) VALUES (%s);", ("1447",))

    # Default superadmin
    c.execute("SELECT * FROM users WHERE username=%s;", ("superadmin",))
    if not c.fetchone():
        hashed = generate_password_hash("1234")
        c.execute("""
            INSERT INTO users
            (username, password, can_manage_members, can_mark_attendance, can_change_settings)
            VALUES (%s,%s,%s,%s,%s);
        """, ("superadmin", hashed, 1, 1, 1))

    conn.commit()
    c.close()
    conn.close()


init_db()


# ---------------- HELPERS ---------------- #

def get_year():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT year FROM settings LIMIT 1;")
    year = c.fetchone()[0]
    c.close()
    conn.close()
    return year


def get_current_user():
    if "user_id" not in session:
        return None

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=%s;", (session["user_id"],))
    user = c.fetchone()
    c.close()
    conn.close()
    return user


# ---------------- LOGIN ---------------- #

@app.route("/", methods=["GET", "POST"])
def login():
    year = get_year()

    if request.method == "POST":
        username = request.form["username"]
        password_input = request.form["password"]

        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=%s;", (username,))
        user = c.fetchone()

        if user:
            stored_password = user[2]

            if stored_password.startswith("pbkdf2:"):
                if check_password_hash(stored_password, password_input):
                    session["user_id"] = user[0]
                    c.close()
                    conn.close()
                    return redirect(url_for("dashboard"))
            else:
                if stored_password == password_input:
                    new_hash = generate_password_hash(password_input)
                    c.execute("UPDATE users SET password=%s WHERE id=%s;",
                              (new_hash, user[0]))
                    conn.commit()
                    session["user_id"] = user[0]
                    c.close()
                    conn.close()
                    return redirect(url_for("dashboard"))

        c.close()
        conn.close()
        flash("Invalid Credentials")

    return render_template("login.html", year=year)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------- DASHBOARD ---------------- #

@app.route("/dashboard")
def dashboard():
    if not get_current_user():
        return redirect(url_for("login"))

    return render_template("dashboard.html", year=get_year())


# ---------------- ATTENDANCE ---------------- #

@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    user = get_current_user()
    if not user or user[4] != 1:
        return "Access Denied"

    conn = get_connection()
    c = conn.cursor()

    year = get_year()

    # Fetch members
    c.execute("SELECT id, name FROM members ORDER BY name;")
    members = c.fetchall()

    selected_member = request.args.get("member")
    attendance_days = []

    if selected_member:
        # Get already marked days
        c.execute("""
            SELECT day FROM attendance
            WHERE member_id=%s AND year=%s;
        """, (selected_member, year))
        rows = c.fetchall()
        attendance_days = [r[0] for r in rows]

    # Mark attendance
    if request.method == "POST":
        member_id = request.form["member_id"]
        day = request.form["day"]

        try:
            c.execute("""
                INSERT INTO attendance (member_id, year, day, marked_at)
                VALUES (%s,%s,%s,%s);
            """, (member_id, year, day, datetime.now()))
            conn.commit()
        except:
            pass  # Ignore duplicate (tick-lock)

        return redirect(url_for("attendance", member=member_id))

    c.close()
    conn.close()

    return render_template("attendance.html",
                           members=members,
                           selected_member=selected_member,
                           attendance_days=attendance_days,
                           year=year)