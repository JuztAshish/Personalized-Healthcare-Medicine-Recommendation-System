# Member 4 - Personalized Healthcare & Medicine Recommendation System
# Task 3B: Backend Authentication (MongoDB, sessions, admin rules)
# Fresh code, not copied from medicare/ reference.

from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo.errors import DuplicateKeyError, PyMongoError

from config import SECRET_KEY
from db import users, activity_logs, ping_db
from services.flask_adapter import CLINICAL_DISCLAIMER, predict_and_recommend

PROFILE_FIELDS = [
    ("age", "Age"),
    ("gender", "Gender"),
    ("blood_group", "Blood Group"),
    ("phone", "Phone"),
    ("allergies", "Known Allergies"),
    ("medical_history", "Existing Conditions / Medical History"),
    ("current_medications", "Current Medications"),
    ("emergency_contact", "Emergency Contact"),
]

GENDER_CHOICES = ["", "Male", "Female", "Other", "Prefer not to say"]
BLOOD_GROUP_CHOICES = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]


def log_activity(action, details="", email=None, name=None, role=None):
    """Store a simple activity log entry in MongoDB. Logging must not break user flow."""
    try:
        current = session.get("user", {}) if session else {}
        doc = {
            "email": (email or current.get("email") or "").lower(),
            "name": name or current.get("name") or "",
            "role": role or current.get("role") or "",
            "action": action,
            "details": details,
            "timestamp": datetime.now(timezone.utc),
        }
        activity_logs.insert_one(doc)
    except Exception:
        pass


def format_log(log):
    ts = log.get("timestamp")
    return {
        "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S UTC") if ts else "",
        "name": log.get("name", ""),
        "email": log.get("email", ""),
        "role": log.get("role", ""),
        "action": log.get("action", ""),
        "details": log.get("details", ""),
    }

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
            log_activity("register", "New user registered", email=email, name=name, role="user")
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
                log_activity("login_denied_admin", "User attempted admin login without admin privileges", email=user.get("email", email), name=user.get("name", name), role=user.get("role", "user"))
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
        log_activity("login_success", f"Logged in as {effective_role}", email=user["email"], name=user["name"], role=effective_role)
        flash(f"Logged in as {effective_role}.", "success")
        return redirect(url_for("admin_panel" if effective_role == "admin" else "dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    current = session.get("user", {})
    log_activity("logout", "User logged out", email=current.get("email"), name=current.get("name"), role=current.get("role"))
    session.pop("user", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    profile = {}
    my_logs = []
    email = session["user"]["email"]
    try:
        user = users.find_one({"email": email}, {"profile": 1})
        if user:
            profile = user.get("profile") or {}
        my_logs = [format_log(l) for l in activity_logs.find({"email": email}).sort("timestamp", -1).limit(10)]
    except PyMongoError as e:
        flash(f"Database error: {e}", "danger")
    return render_template("dashboard.html", profile=profile, my_logs=my_logs)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    email = session["user"]["email"]
    profile_data = {}

    if request.method == "POST":
        age_raw = request.form.get("age", "").strip()
        age = ""
        if age_raw:
            try:
                age_val = int(age_raw)
                if age_val < 0 or age_val > 120:
                    flash("Age must be between 0 and 120.", "danger")
                    return redirect(url_for("profile"))
                age = str(age_val)
            except ValueError:
                flash("Age must be a valid number.", "danger")
                return redirect(url_for("profile"))

        gender = request.form.get("gender", "").strip()
        blood_group = request.form.get("blood_group", "").strip()
        if gender not in GENDER_CHOICES:
            gender = ""
        if blood_group not in BLOOD_GROUP_CHOICES:
            blood_group = ""

        profile_data = {
            "age": age,
            "gender": gender,
            "blood_group": blood_group,
            "phone": request.form.get("phone", "").strip(),
            "allergies": request.form.get("allergies", "").strip(),
            "medical_history": request.form.get("medical_history", "").strip(),
            "current_medications": request.form.get("current_medications", "").strip(),
            "emergency_contact": request.form.get("emergency_contact", "").strip(),
        }

        try:
            users.update_one({"email": email}, {"$set": {"profile": profile_data}})
            log_activity("profile_update", "User updated profile")
            flash("Profile saved successfully.", "success")
            return redirect(url_for("profile"))
        except PyMongoError as e:
            flash(f"Database error: {e}", "danger")

    try:
        user = users.find_one({"email": email}, {"profile": 1})
        if user:
            profile_data = user.get("profile") or {}
    except PyMongoError as e:
        flash(f"Database error: {e}", "danger")

    return render_template(
        "profile.html",
        profile=profile_data,
        gender_choices=GENDER_CHOICES,
        blood_group_choices=BLOOD_GROUP_CHOICES,
    )


@app.route("/predict", methods=["GET", "POST"])
@login_required
def predict():
    result = None
    form_data = {"symptoms": "", "allergies": "", "conditions": "", "top_k": "5"}
    if request.method == "POST":
        form_data = {
            "symptoms": request.form.get("symptoms", "").strip(),
            "allergies": request.form.get("allergies", "").strip(),
            "conditions": request.form.get("conditions", "").strip(),
            "top_k": request.form.get("top_k", "5").strip() or "5",
        }
        if not form_data["symptoms"]:
            flash("Please enter at least one symptom.", "danger")
            return render_template("predict.html", result=None, form_data=form_data, clinical_disclaimer=CLINICAL_DISCLAIMER)

        try:
            result = predict_and_recommend(
                symptoms=form_data["symptoms"],
                allergies=form_data["allergies"],
                conditions=form_data["conditions"],
                top_k=form_data["top_k"],
                filter_allergies=True,
            )
            pred = result.get("predicted_disease") or "unknown"
            log_activity("prediction_request", f"Predicted: {pred}; recommendations: {result.get('count', 0)}")
            if result.get("status") == "error":
                flash(result.get("message", "Unable to generate prediction."), "danger")
        except Exception as e:
            flash(f"Prediction service error: {e}", "danger")
            result = None

    return render_template("predict.html", result=result, form_data=form_data, clinical_disclaimer=CLINICAL_DISCLAIMER)


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
                log_activity("admin_promote", f"Promoted {email} to admin")
                flash(f"User {email} promoted to admin.", "success")
        except PyMongoError as e:
            flash(f"Database error: {e}", "danger")
    return render_template("promote.html")


@app.route("/admin/activity")
@admin_required
def admin_activity():
    logs = []
    try:
        logs = [format_log(l) for l in activity_logs.find().sort("timestamp", -1).limit(100)]
    except PyMongoError as e:
        flash(f"Database error: {e}", "danger")
    return render_template("activity.html", logs=logs)


@app.route("/admin/users")
@admin_required
def admin_users():
    """Admin-only view of users and their profile data. Password hashes are never shown."""
    user_rows = []
    try:
        for u in users.find({}, {"password_hash": 0}).sort("email", 1):
            profile = u.get("profile") or {}
            user_rows.append({
                "name": u.get("name", ""),
                "email": u.get("email", ""),
                "role": u.get("role", ""),
                "profile": profile,
            })
    except PyMongoError as e:
        flash(f"Database error: {e}", "danger")
    return render_template("admin_users.html", users=user_rows)


if __name__ == "__main__":
    # debug=True for learning only, not for deployment.
    app.run(debug=True)