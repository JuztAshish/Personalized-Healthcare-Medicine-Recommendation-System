# Member 4 - Personalized Healthcare & Medicine Recommendation System
# Task 1: Initial Application Structure (Flask hello-world)
# This file is FRESH code, not copied from medicare/ reference.
# It proves the Flask setup works before we add auth, DB, dashboards.

from flask import Flask, render_template

# Create the Flask app. __name__ tells Flask where to find templates/static.
app = Flask(__name__)

@app.route("/")
def home():
    """Landing page - browser asks for '/' and Flask returns index.html."""
    return render_template("index.html")

@app.route("/about")
def about():
    """About page - Member 4 web application overview."""
    return render_template("about.html")

@app.route("/login")
def login():
    """Login placeholder - real auth will be added in Task 3."""
    return render_template("login.html")

@app.route("/register")
def register():
    """Register placeholder - real auth will be added in Task 3."""
    return render_template("register.html")

if __name__ == "__main__":
    # debug=True shows helpful errors while learning. Port 5000 is default.
    # NOTE: debug mode is for learning only, NOT for final deployment.
    app.run(debug=True)
