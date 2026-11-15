# Member 4 - Personalized Healthcare & Medicine Recommendation System
# Task 3B: Backend Authentication (MongoDB, sessions, admin rules)
# Fresh code, not copied from medicare/ reference.

from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo.errors import DuplicateKeyError, PyMongoError

from config import SECRET_KEY
from db import users, ping_db

app = Flask(__name__)
app.secret_key = SECRET_KEY


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        if session["user"].get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not all([name, email, password, confirm_password]):
            flash("All fields are required.", "danger")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")

        try:
            # Registration always creates a normal user. Only seed/admin promotion can grant admin.
            users.insert_one({
                "name": name,
                "email": email,
                "password_hash": generate_password_hash(password),
                "role": "user",
            })
            flash("Account created successfully. Please log in.", "success")
            return redirect(url_for("login"))
        except DuplicateKeyError:
            flash("Email is already registered.", "danger")
        except PyMongoError as e:
            flash(f"Database error: {e}", "danger")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        selected_role = request.form.get("role", "")

        if not all([name, email, password, selected_role]):
            flash("All fields are required.", "danger")
            return render_template("login.html")

        try:
            user = users.find_one({"email": email})
        except PyMongoError as e:
            flash(f"Database error: {e}", "danger")
            return render_template("login.html")

        # Verify Name + Email + Password
        if not user or not check_password_hash(user.get("password_hash", ""), password):
            flash("Invalid name, email, or password.", "danger")
            return render_template("login.html")

        if user.get("name", "").strip() != name:
            flash("Name does not match this account.", "danger")
            return render_template("login.html")

        # Role rules (approved):
        # - Selecting Admin requires the account to be an approved admin.
        # - Selecting User allows login as user when credentials match (even if account is admin).
        if selected_role == "admin":
            if user.get("role") != "admin":
                flash("Not authorized as admin.", "danger")
                return render_template("login.html")
            effective_role = "admin"
        elif selected_role == "user":
            effective_role = "user"
        else:
            flash("Invalid role selected.", "danger")
            return render_template("login.html")

        session["user"] = {
            "name": user["name"],
            "email": user["email"],
            "role": effective_role,
        }
        flash(f"Logged in as {effective_role}.", "success")
        return redirect(url_for("admin_panel" if effective_role == "admin" else "dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/admin")
@admin_required
def admin_panel():
    return render_template("admin.html")


@app.route("/admin/promote", methods=["GET", "POST"])
@admin_required
def promote_user():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Email is required.", "danger")
            return render_template("promote.html")
        try:
            result = users.update_one({"email": email}, {"$set": {"role": "admin"}})
            if result.matched_count == 0:
                flash("No user found with that email.", "warning")
            elif result.modified_count == 0:
                flash("User is already an admin.", "info")
            else:
                flash(f"User {email} promoted to admin.", "success")
        except PyMongoError as e:
            flash(f"Database error: {e}", "danger")
    return render_template("promote.html")


if __name__ == "__main__":
    # debug=True for learning only, not for deployment.
    app.run(debug=True)