import os
from dotenv import load_dotenv

# --- Load environment variables from a .env file into os.environ ---
load_dotenv()  # allows accessing variables like FLASK_SECRET_KEY, LDAP_SERVER, etc.

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, login_user, logout_user, login_required, current_user)
from flask_login import UserMixin
from sqlalchemy import and_, or_
from werkzeug.security import generate_password_hash, check_password_hash
from flask_ldap3_login import LDAP3LoginManager  # LDAP authentication integration

# --- Initialize Flask application ---
app = Flask(
    __name__,
    template_folder=os.environ.get("TEMPLATE_FOLDER", "templates"),  # template folder path
    static_folder=os.environ.get("STATIC_FOLDER", "static")          # static files folder
)

# --- Flask configuration ---
app.secret_key = os.environ.get("FLASK_SECRET_KEY")  # secret key for sessions, flash messages, etc.
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("SQLALCHEMY_DATABASE_URI")  # database connection
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = os.environ.get("SQLALCHEMY_TRACK_MODIFICATIONS") == "True"

# --- Initialize SQLAlchemy database ---
db = SQLAlchemy(app)

# --- Setup Flask-Login for user session management ---
login_manager = LoginManager()
login_manager.login_view = "login"  # redirect unauthenticated users to /login
login_manager.init_app(app)

# --- LDAP setup ---
app.config["LDAP_HOST"] = os.environ.get("LDAP_SERVER")            # LDAP server address
app.config["LDAP_BASE_DN"] = os.environ.get("LDAP_BASEDN")         # base DN for LDAP searches
app.config["LDAP_USER_DN"] = "cn=NCS,cn=Users"                     # DN under which users exist
app.config["LDAP_BIND_USER_DN"] = os.environ.get("LDAP_BIND_USER")  # user to bind for searches
app.config["LDAP_BIND_USER_PASSWORD"] = os.environ.get("LDAP_BIND_PASS")  # bind user's password
app.config["LDAP_USER_RDN_ATTR"] = "cn"                             # attribute used in user DN
app.config["LDAP_USER_LOGIN_ATTR"] = "cn"                           # login attribute
ldap_manager = LDAP3LoginManager(app)  # initialize LDAP manager

# --- Database models ---

# User model for local users and LDAP-synced users
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # primary key
    username = db.Column(db.String(80), unique=True, nullable=False)  # username
    password_hash = db.Column(db.String(128), nullable=True)  # password hash, nullable for LDAP-only users
    role = db.Column(db.String(20), nullable=False, default="user")  # user role (user/admin)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)  # optional team assignment
    is_ldap = db.Column(db.Boolean, default=False)  # flag for LDAP users

    def check_password(self, password):
        """Verify password against stored hash. Returns False if no local password."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    # Flask-Login required properties
    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

# Event model to track calendar events
from datetime import datetime

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)  # event title
    event_type = db.Column(db.String(20), nullable=False)  # type-> meeting, vacation, etc.
    status = db.Column(db.String(20), nullable=False, default="approved")  # status
    start_datetime = db.Column(db.DateTime, nullable=False)  # start time
    end_datetime = db.Column(db.DateTime, nullable=False)    # end time
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # user who created it
    creator = db.relationship("User", backref="events")  # relationship to User model
    scope = db.Column(db.String(20), nullable=False, default="personal")  # personal/team/global
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)  # optional team association

# Team model
class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    users = db.relationship("User", backref="team", lazy=True)  # back reference to users

# --- Flask-Login user loader ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))  # load user by ID for session management

# --- Routes ---
@app.route("/")
def home():
    # If user is logged in → go to calendar, else → login page
    if current_user.is_authenticated:
        return redirect(url_for("calendar"))
    return redirect(url_for("login"))

import time  # used later if needed (currently unused)

# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # --- Try to authenticate local user first ---
        local_user = User.query.filter_by(username=username).first()
        if local_user:
            if local_user.check_password(password):
                login_user(local_user)  # log in user
                flash("Logged in locally", "success")
                return redirect(url_for("calendar"))
            else:
                flash("Invalid password", "danger")
                return render_template("login.html")

        # --- If no local user, try LDAP authentication ---
        try:
            ldap_user = ldap_manager.authenticate(username, password)
        except Exception:
            ldap_user = None

        if ldap_user:
            # First successful LDAP login → create local user record
            new_user = User(
                username=username,
                password_hash=generate_password_hash(password),  # optional local password
                role="user",
                is_ldap=True
            )
            db.session.add(new_user)
            db.session.commit()

            login_user(new_user)
            flash("Logged in via LDAP (local account created)", "success")
            return redirect(url_for("calendar"))

        # --- Neither local nor LDAP authentication succeeded ---
        flash("Account does not exist locally or in LDAP", "danger")
        return render_template("login.html")

    # GET request → render login page
    return render_template("login.html")

# --- Logout route ---
@app.route("/logout")
@login_required  # ensure only logged-in users can access
def logout():
    logout_user()  # remove user from session
    flash("Logged out successfully", "info")  # show message
    return redirect(url_for("login"))  # redirect to login page

# --- Calendar page ---
from datetime import timedelta

@app.route("/calendar")
@login_required
def calendar():
    pending = []  # store pending vacation requests for admin

    if current_user.role == "admin":
        # Admin sees all events
        events = Event.query.all()
        # Admin also sees pending vacation requests separately
        pending = Event.query.filter_by(
            event_type="vacation",
            status="pending"
        ).all()
    else:
        # Non-admin users see:
        # - their own events
        # - team events that are approved
        events = Event.query.filter(
            or_(
                Event.created_by == current_user.id,
                and_(
                    Event.scope == "team",
                    Event.team_id == current_user.team_id,
                    Event.status == "approved"
                )
            )
        ).all()

    # Prepare events for FullCalendar JS
    event_list = []
    for e in events:
        all_day = (e.event_type == "vacation")  # vacations are all-day events
        status_colors = {
            "pending": "#facc15",  # yellow
            "approved": "#10b981",  # green
            "rejected": "#ef4444"   # red
        }

        event_list.append({
            "id": e.id,
            "title": e.title,
            "start": e.start_datetime.isoformat() if not all_day else e.start_datetime.date().isoformat(),
            "end": e.end_datetime.isoformat() if not all_day else (e.end_datetime.date() + timedelta(days=1)).isoformat(),
            "allDay": all_day,
            "color": status_colors[e.status],
            "status": e.status,
            # include user info for display in calendar tooltip or popup
            "username": e.creator.username,
            "team": e.creator.team.name if e.creator.team else "No team"
        })

    return render_template("calendar.html", events=event_list, user=current_user, pending=pending)

# --- Add Event page ---
from datetime import datetime

@app.route("/add_event", methods=["GET", "POST"])
@login_required
def add_event():
    if request.method == "POST":
        # Retrieve form data
        title = request.form["title"]
        event_type = request.form["event_type"]
        scope = request.form["scope"]

        # Convert datetime strings to Python datetime objects
        start_dt = datetime.strptime(
            request.form["start_datetime"], "%Y-%m-%dT%H:%M"
        )
        end_dt = datetime.strptime(
            request.form["end_datetime"], "%Y-%m-%dT%H:%M"
        )

        # Vacation requests by non-admin users must be approved
        if event_type == "vacation" and current_user.role != "admin":
            status = "pending"
            flash("Vacation request submitted for approval.", "info")
        else:
            status = "approved"
            flash("Event added successfully!", "success")

        # Create event object
        new_event = Event(
            title=title,
            event_type=event_type,
            start_datetime=start_dt,
            end_datetime=end_dt,
            status=status,
            created_by=current_user.id,
            scope=scope,
            team_id=current_user.team_id if scope == "team" else None
        )

        # Save event to database
        db.session.add(new_event)
        db.session.commit()
        return redirect(url_for("calendar"))

    # GET request → show add event form
    return render_template("add_event.html", user=current_user)

# --- Pending vacations page (admin only) ---
@app.route("/pending_vacations")
@login_required
def pending_vacations():
    if current_user.role != "admin":
        flash("Access denied", "danger")
        return redirect(url_for("calendar"))

    # Get all pending vacation events
    pending = Event.query.filter_by(
        event_type="vacation",
        status="pending"
    ).all()

    return render_template("pending_vacations.html", pending=pending)

# --- Approve event (admin only) ---
from flask import jsonify

@app.route("/approve_event/<int:event_id>", methods=["POST"])
@login_required
def approve_event(event_id):
    if current_user.role != "admin":
        return {"error": "Access denied"}, 403

    event = Event.query.get_or_404(event_id)  # get event or 404
    event.status = "approved"
    db.session.commit()
    return {"success": True, "status": "approved"}

# --- Reject event (admin only) ---
@app.route("/reject_event/<int:event_id>", methods=["POST"])
@login_required
def reject_event(event_id):
    if current_user.role != "admin":
        return {"error": "Access denied"}, 403

    event = Event.query.get_or_404(event_id)
    event.status = "rejected"
    db.session.commit()
    return {"success": True, "status": "rejected"}

# --- Initialize database, teams, and sample users ---
with app.app_context():
    db.create_all()  # create tables if they don't exist

    # Create or fetch teams
    team1 = Team.query.filter_by(name="Engineering").first()
    if not team1:
        team1 = Team(name="Engineering")
        db.session.add(team1)

    team2 = Team.query.filter_by(name="HR").first()
    if not team2:
        team2 = Team(name="HR")
        db.session.add(team2)

    db.session.commit()  # commit teams to assign IDs

    # Initialize sample users (only if they don't exist)
    admin = alice = bob = john = None

    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            password_hash=generate_password_hash("adminpass"),
            role="admin"
        )

    if not User.query.filter_by(username="alice").first():
        alice = User(
            username="alice",
            password_hash=generate_password_hash("alicepass"),
            role="user",
            team_id=team1.id
        )

    if not User.query.filter_by(username="bob").first():
        bob = User(
            username="bob",
            password_hash=generate_password_hash("bobpass"),
            role="user",
            team_id=team2.id
        )

    if not User.query.filter_by(username="john").first():
        john = User(
            username="john",
            password_hash=generate_password_hash("johnpass"),
            role="user",
            team_id=team1.id
        )

    # Add any newly created users to database
    users_to_add = [u for u in [admin, alice, bob, john] if u is not None]
    if users_to_add:
        db.session.add_all(users_to_add)
        db.session.commit()

    # --- Run Flask app ---
    # app.run(debug=True)
    if __name__ == "__main__":
        app.run(host="0.0.0.0", port=5000)
