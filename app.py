import os
from dotenv import load_dotenv
import sqlite3

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (
    LoginManager, UserMixin, login_user,
    login_required, logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

DATABASE = "clients.db"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = None


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


class User(UserMixin):
    def __init__(self, user_id, email, password_hash):
        self.id = user_id
        self.email = email
        self.password_hash = password_hash


@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()

    if user is None:
        return None

    return User(user["id"], user["email"], user["password_hash"])


def init_db():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL
        )
    """)

    columns = [
        column["name"]
        for column in conn.execute("PRAGMA table_info(clients)").fetchall()
    ]

    if "owner_id" not in columns:
        conn.execute(
            "ALTER TABLE clients ADD COLUMN owner_id INTEGER REFERENCES users(id)"
        )

    conn.commit()
    conn.close()


@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)

        conn = get_db_connection()

        existing_user = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()

        if existing_user:
            conn.close()
            flash("An account with this email already exists.", "error")
            return redirect(url_for("register"))

        cursor = conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash)
        )

        new_user_id = cursor.lastrowid

        # Preserve existing records by assigning unowned records
        # to the first registered account.
        conn.execute(
            "UPDATE clients SET owner_id = ? WHERE owner_id IS NULL",
            (new_user_id,)
        )

        conn.commit()
        conn.close()

        user = User(new_user_id, email, password_hash)
        login_user(user)

        flash("Your account was created successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user_data = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()

        if user_data and check_password_hash(
            user_data["password_hash"], password
        ):
            user = User(
                user_data["id"],
                user_data["email"],
                user_data["password_hash"]
            )
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have logged out successfully.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db_connection()

    clients = conn.execute(
        "SELECT * FROM clients WHERE owner_id = ? ORDER BY id DESC",
        (current_user.id,)
    ).fetchall()

    total_clients = len(clients)
    conn.close()

    return render_template(
        "dashboard.html",
        clients=clients,
        total_clients=total_clients
    )


@app.route("/add-client", methods=["GET", "POST"])
@login_required
def add_client():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()

        if not name or not email or not phone:
            return "All fields are required.", 400

        conn = get_db_connection()
        conn.execute(
            """INSERT INTO clients (name, email, phone, owner_id)
               VALUES (?, ?, ?, ?)""",
            (name, email, phone, current_user.id)
        )
        conn.commit()
        conn.close()

        flash("Client added successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("add_client.html")


@app.route("/edit-client/<int:client_id>", methods=["GET", "POST"])
@login_required
def edit_client(client_id):
    conn = get_db_connection()

    client = conn.execute(
        "SELECT * FROM clients WHERE id = ? AND owner_id = ?",
        (client_id, current_user.id)
    ).fetchone()

    if client is None:
        conn.close()
        return "Client not found.", 404

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()

        if not name or not email or not phone:
            conn.close()
            return "All fields are required.", 400

        conn.execute(
            """UPDATE clients
               SET name = ?, email = ?, phone = ?
               WHERE id = ? AND owner_id = ?""",
            (name, email, phone, client_id, current_user.id)
        )
        conn.commit()
        conn.close()

        flash("Client updated successfully!", "success")
        return redirect(url_for("dashboard"))

    conn.close()
    return render_template("edit_client.html", client=client)


@app.route("/delete-client/<int:client_id>", methods=["POST"])
@login_required
def delete_client(client_id):
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM clients WHERE id = ? AND owner_id = ?",
        (client_id, current_user.id)
    )
    conn.commit()
    conn.close()

    flash("Client deleted successfully!", "success")
    return redirect(url_for("dashboard"))


@app.route("/client/<int:client_id>")
@login_required
def view_client(client_id):
    conn = get_db_connection()

    client = conn.execute(
        "SELECT * FROM clients WHERE id = ? AND owner_id = ?",
        (client_id, current_user.id)
    ).fetchone()

    conn.close()

    if client is None:
        return "Client not found.", 404

    return render_template("client_profile.html", client=client)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)




