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
        sslmode="require",
        connect_timeout=5
    )


def init_db():
    with get_connection() as conn:
        with conn.cursor() as c:

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

            c.execute("""
                CREATE TABLE IF NOT EXISTS members (
                    id SERIAL PRIMARY KEY,
                    sabil_number TEXT UNIQUE,
                    name TEXT,
                    created_at TIMESTAMP
                );
            """)

            c.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id SERIAL PRIMARY KEY,
                    year TEXT
                );
            """)

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

            c.execute("SELECT * FROM settings;")
            if not c.fetchone():
                c.execute("INSERT INTO settings (year) VALUES (%s);", ("1447",))

            c.execute("SELECT * FROM users WHERE username=%s;", ("superadmin",))
            if not c.fetchone():
                c.execute("""
                    INSERT INTO users
                    (username, password, can_manage_members, can_mark_attendance, can_change_settings)
                    VALUES (%s,%s,%s,%s,%s);
                """, ("superadmin",
                      generate_password_hash("1234"),
                      1, 1, 1))

init_db()


# ---------------- HELPERS ---------------- #

def get_year():
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT year FROM settings LIMIT 1;")
            return c.fetchone()[0]


def get_current_user():
    if "user_id" not in session:
        return None
    with get_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT * FROM users WHERE id=%s;", (session["user_id"],))
            return c.fetchone()


# ---------------- LOGIN ---------------- #

@app.route("/", methods=["GET", "POST"])
def login():
    year = get_year()

    if request.method == "POST":
        username = request.form["username"]
        password_input = request.form["password"]

        with get_connection() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM users WHERE username=%s;", (username,))
                user = c.fetchone()

                if user and check_password_hash(user[2], password_input):
                    session["user_id"] = user[0]
                    return redirect(url_for("dashboard"))

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

    year = get_year()

    with get_connection() as conn:
        with conn.cursor() as c:

            # Total Members
            c.execute("SELECT COUNT(*) FROM members;")
            total_members = c.fetchone()[0]

            # Total Attendance for current year
            c.execute("SELECT COUNT(*) FROM attendance WHERE year=%s;", (year,))
            total_attendance = c.fetchone()[0]

    return render_template(
        "dashboard.html",
        year=year,
        total_members=total_members,
        total_attendance=total_attendance
    )


# ---------------- USERS ---------------- #

@app.route("/users", methods=["GET", "POST"])
def users():
    user = get_current_user()
    if not user or user[5] != 1:
        return "Access Denied"

    with get_connection() as conn:
        with conn.cursor() as c:

            if request.method == "POST":
                c.execute("""
                    INSERT INTO users
                    (username, password, can_manage_members, can_mark_attendance, can_change_settings)
                    VALUES (%s,%s,%s,%s,%s);
                """, (
                    request.form["username"],
                    generate_password_hash(request.form["password"]),
                    1 if request.form.get("manage") else 0,
                    1 if request.form.get("attendance") else 0,
                    1 if request.form.get("settings") else 0
                ))
                conn.commit()
                flash("User Created")

            c.execute("SELECT * FROM users;")
            users = c.fetchall()

    return render_template("users.html", users=users, year=get_year())


@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        current = request.form["current"]
        new = request.form["new"]

        if not check_password_hash(user[2], current):
            flash("Current password incorrect")
            return redirect(url_for("change_password"))

        with get_connection() as conn:
            with conn.cursor() as c:
                c.execute("UPDATE users SET password=%s WHERE id=%s;",
                          (generate_password_hash(new), user[0]))
                conn.commit()

        flash("Password updated")
        return redirect(url_for("dashboard"))

    return render_template("change_password.html", year=get_year())


# ---------------- SETTINGS ---------------- #

@app.route("/settings", methods=["GET", "POST"])
def settings():
    user = get_current_user()
    if not user or user[5] != 1:
        return "Access Denied"

    if request.method == "POST":
        with get_connection() as conn:
            with conn.cursor() as c:
                c.execute("UPDATE settings SET year=%s;", (request.form["year"],))
                conn.commit()
        flash("Year updated")

    return render_template("settings.html", year=get_year())


# ---------------- MEMBERS ---------------- #

@app.route("/members", methods=["GET", "POST"])
def members():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    year = get_year()

    with get_connection() as conn:
        with conn.cursor() as c:

            if request.method == "POST":
                sabil = request.form["sabil"]
                name = request.form["name"]

                c.execute("""
                    INSERT INTO members (sabil_number, name)
                    VALUES (%s, %s);
                """, (sabil, name))

                conn.commit()
                return redirect(url_for("members"))

            c.execute("""
                SELECT id, sabil_number, name
                FROM members
                ORDER BY id;
            """)
            members_list = c.fetchall()

    return render_template(
        "members.html",
        members=members_list,
        year=year
    )


# ---------------- ATTENDANCE ---------------- #

@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    user = get_current_user()
    if not user or user[4] != 1:
        return "Access Denied"

    year = get_year()

    with get_connection() as conn:
        with conn.cursor() as c:

            c.execute("SELECT id, name FROM members ORDER BY name;")
            members = c.fetchall()

            selected_member = request.args.get("member")
            attendance_days = []

            if selected_member:
                c.execute("""
                    SELECT day FROM attendance
                    WHERE member_id=%s AND year=%s;
                """, (selected_member, year))
                attendance_days = [r[0] for r in c.fetchall()]

            if request.method == "POST":
                try:
                    c.execute("""
                        INSERT INTO attendance (member_id, year, day, marked_at)
                        VALUES (%s,%s,%s,%s);
                    """, (
                        request.form["member_id"],
                        year,
                        request.form["day"],
                        datetime.now()
                    ))
                    conn.commit()
                except:
                    pass

                return redirect(url_for("attendance",
                                        member=request.form["member_id"]))

    return render_template("attendance.html",
                           members=members,
                           selected_member=selected_member,
                           attendance_days=attendance_days,
                           year=year)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)