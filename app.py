import os
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()  # loads .env into os.environ

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager,login_user,logout_user,login_required,current_user)
from sqlalchemy import and_, or_
from werkzeug.security import generate_password_hash, check_password_hash
from flask_ldap3_login import LDAP3LoginManager

# --- Initialize Flask app ---
app = Flask(
    __name__,
    template_folder=os.environ.get("TEMPLATE_FOLDER", "templates"),
    static_folder=os.environ.get("STATIC_FOLDER", "static")
)

app.secret_key = os.environ.get("FLASK_SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("SQLALCHEMY_DATABASE_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = os.environ.get("SQLALCHEMY_TRACK_MODIFICATIONS") == "True"

# --- Initialize database ---
db = SQLAlchemy(app)

# --- Flask-Login setup ---
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

# --- LDAP setup ---
app.config["LDAP_HOST"] = os.environ.get("LDAP_SERVER")
app.config["LDAP_BASE_DN"] = os.environ.get("LDAP_BASEDN")
app.config["LDAP_USER_DN"] = "cn=NCS,cn=Users"  # adjust if needed
app.config["LDAP_BIND_USER_DN"] = os.environ.get("LDAP_BIND_USER")
app.config["LDAP_BIND_USER_PASSWORD"] = os.environ.get("LDAP_BIND_PASS")
app.config["LDAP_USER_RDN_ATTR"] = "cn"
app.config["LDAP_USER_LOGIN_ATTR"] = "cn"

ldap_manager = LDAP3LoginManager(app)

# --- User model ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Flask-Login properties
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


# --- Event model ---
from datetime import datetime

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    event_type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="approved")

    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)

    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    creator = db.relationship("User", backref="events")

    scope = db.Column(db.String(20), nullable=False, default="personal")
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)



class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    users = db.relationship("User", backref="team", lazy=True)


# --- Setup Flask-Login ---
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---
@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("calendar"))
    return redirect(url_for("login"))

# Login/logout
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Try LDAP authentication
        try:
            ldap_user = ldap_manager.authenticate(username, password)
        except Exception:
            ldap_user = None

        if ldap_user:
            local_user = User.query.filter_by(username=username).first()
            if not local_user:
                local_user = User(
                    username=username,
                    password_hash=generate_password_hash(""),  # LDAP handles password
                    role="user"
                )
                db.session.add(local_user)
                db.session.commit()
            login_user(local_user)
            flash("Logged in via LDAP!", "success")
            return redirect(url_for("calendar"))

        # Fallback to local DB
        local_user = User.query.filter_by(username=username).first()
        if local_user and local_user.check_password(password):
            login_user(local_user)
            flash("Logged in successfully!", "success")
            return redirect(url_for("calendar"))

        flash("Invalid username or password", "danger")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully", "info")
    return redirect(url_for("login"))

# Calendar page
from datetime import timedelta

@app.route("/calendar")
@login_required
def calendar():
    pending = []

    if current_user.role == "admin":
        events = Event.query.all()
        pending = Event.query.filter_by(
            event_type="vacation",
            status="pending"
        ).all()
    else:
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

    event_list = []
    for e in events:
        all_day = (e.event_type == "vacation")
        status_colors = {
            "pending": "#facc15",
            "approved": "#10b981",
            "rejected": "#ef4444"
        }

        event_list.append({
            "id": e.id,
            "title": e.title,
            "start": e.start_datetime.isoformat() if not all_day else e.start_datetime.date().isoformat(),
            "end": e.end_datetime.isoformat() if not all_day else (e.end_datetime.date() + timedelta(days=1)).isoformat(),
            "allDay": all_day,
            "color": status_colors[e.status],
            "status": e.status,
            
        # user info for better readability
        "username": e.creator.username,
        "team": e.creator.team.name if e.creator.team else "No team"
        })

    return render_template("calendar.html", events=event_list, user=current_user, pending=pending)

# Add event page
from datetime import datetime

@app.route("/add_event", methods=["GET", "POST"])
@login_required
def add_event():
    if request.method == "POST":
        title = request.form["title"]
        event_type = request.form["event_type"]
        scope = request.form["scope"]

        start_dt = datetime.strptime(
            request.form["start_datetime"], "%Y-%m-%dT%H:%M"
        )
        end_dt = datetime.strptime(
            request.form["end_datetime"], "%Y-%m-%dT%H:%M"
        )

        if event_type == "vacation" and current_user.role != "admin":
            status = "pending"
            flash("Vacation request submitted for approval.", "info")
        else:
            status = "approved"
            flash("Event added successfully!", "success")

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

        db.session.add(new_event)
        db.session.commit()
        return redirect(url_for("calendar"))

    return render_template("add_event.html", user=current_user)


@app.route("/pending_vacations")
@login_required
def pending_vacations():
    if current_user.role != "admin":
        flash("Access denied", "danger")
        return redirect(url_for("calendar"))

    pending = Event.query.filter_by(
        event_type="vacation",
        status="pending"
    ).all()

    return render_template("pending_vacations.html", pending=pending)

from flask import jsonify

@app.route("/approve_event/<int:event_id>", methods=["POST"])
@login_required
def approve_event(event_id):
    if current_user.role != "admin":
        return {"error": "Access denied"}, 403

    event = Event.query.get_or_404(event_id)
    event.status = "approved"
    db.session.commit()
    return {"success": True, "status": "approved"}


@app.route("/reject_event/<int:event_id>", methods=["POST"])
@login_required
def reject_event(event_id):
    if current_user.role != "admin":
        return {"error": "Access denied"}, 403

    event = Event.query.get_or_404(event_id)
    event.status = "rejected"
    db.session.commit()
    return {"success": True, "status": "rejected"}




# Run app
with app.app_context():
    db.create_all()

    # Create or get teams
    team1 = Team.query.filter_by(name="Engineering").first()
    if not team1:
        team1 = Team(name="Engineering")
        db.session.add(team1)

    team2 = Team.query.filter_by(name="HR").first()
    if not team2:
        team2 = Team(name="HR")
        db.session.add(team2)

    db.session.commit()  # commit teams to get IDs

    # Initialize user variables
    admin = alice = bob = john = None

    # Create users only if not exist
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

    # Add only users that were created
    users_to_add = [u for u in [admin, alice, bob, john] if u is not None]
    if users_to_add:
        db.session.add_all(users_to_add)
        db.session.commit()

            
    app.run(debug=True)