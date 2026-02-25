from flask import Flask, render_template, redirect, url_for, request, session, flash
import os
import psycopg2
from datetime import datetime

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

    c.execute("SELECT * FROM settings;")
    if not c.fetchone():
        c.execute("INSERT INTO settings (year) VALUES (%s);", ("1447",))

    c.execute("SELECT * FROM users WHERE username=%s;", ("superadmin",))
    if not c.fetchone():
        c.execute("""
            INSERT INTO users
            (username, password, can_manage_members, can_mark_attendance, can_change_settings)
            VALUES (%s,%s,%s,%s,%s);
        """, ("superadmin", "1234", 1, 1, 1))

    conn.commit()
    c.close()
    conn.close()


# Initialize DB safely
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
        password = request.form["password"]

        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=%s AND password=%s;",
                  (username, password))
        user = c.fetchone()
        c.close()
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
    if not get_current_user():
        return redirect(url_for("login"))

    return render_template("dashboard.html", year=get_year())


# ---------------- USERS ---------------- #

@app.route("/users", methods=["GET", "POST"])
def users():
    user = get_current_user()
    if not user or user[5] != 1:
        return "Access Denied"

    conn = get_connection()
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
            VALUES (%s,%s,%s,%s,%s);
        """, (username, password, manage, attendance, settings))
        conn.commit()
        flash("User Created Successfully")

    c.execute("SELECT * FROM users;")
    users = c.fetchall()

    c.close()
    conn.close()

    return render_template("users.html", users=users, year=get_year())


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

        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE users SET password=%s WHERE id=%s;", (new, user[0]))
        conn.commit()
        c.close()
        conn.close()

        flash("Password Updated Successfully")
        return redirect(url_for("dashboard"))

    return render_template("change_password.html", year=get_year())


# ---------------- SETTINGS ---------------- #

@app.route("/settings", methods=["GET", "POST"])
def settings():
    user = get_current_user()
    if not user or user[5] != 1:
        return "Access Denied"

    if request.method == "POST":
        new_year = request.form["year"]

        conn = get_connection()
        c = conn.cursor()
        c.execute("UPDATE settings SET year=%s;", (new_year,))
        conn.commit()
        c.close()
        conn.close()

        flash("Year Updated Successfully")

    return render_template("settings.html", year=get_year())


# ---------------- MEMBERS ---------------- #

@app.route("/members", methods=["GET", "POST"])
def members():
    user = get_current_user()
    if not user or user[3] != 1:
        return "Access Denied"

    conn = get_connection()
    c = conn.cursor()

    if request.method == "POST":
        sabil = request.form["sabil"]
        name = request.form["name"]
        c.execute("""
            INSERT INTO members (sabil_number, name, created_at)
            VALUES (%s,%s,%s);
        """, (sabil, name, datetime.now()))
        conn.commit()

    c.execute("SELECT * FROM members ORDER BY id DESC;")
    members = c.fetchall()

    c.close()
    conn.close()

    return render_template("members.html",
                           members=members,
                           year=get_year())


@app.route("/edit_member/<int:id>", methods=["GET", "POST"])
def edit_member(id):
    user = get_current_user()
    if not user or user[3] != 1:
        return "Access Denied"

    conn = get_connection()
    c = conn.cursor()

    if request.method == "POST":
        sabil = request.form["sabil"]
        name = request.form["name"]
        c.execute("""
            UPDATE members SET sabil_number=%s, name=%s WHERE id=%s;
        """, (sabil, name, id))
        conn.commit()
        c.close()
        conn.close()
        return redirect(url_for("members"))

    c.execute("SELECT * FROM members WHERE id=%s;", (id,))
    member = c.fetchone()

    c.close()
    conn.close()

    return render_template("edit_member.html",
                           member=member,
                           year=get_year())


@app.route("/delete_member/<int:id>")
def delete_member(id):
    user = get_current_user()
    if not user or user[3] != 1:
        return "Access Denied"

    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM members WHERE id=%s;", (id,))
    conn.commit()
    c.close()
    conn.close()

    return redirect(url_for("members"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)