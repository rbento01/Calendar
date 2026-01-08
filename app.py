from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///calendar.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- User model ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")

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
    event_type = db.Column(db.String(20), nullable=False)  # vacation / meeting
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="approved")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))



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
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Logged in successfully!", "success")
            return redirect(url_for("calendar"))
        else:
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
    events = Event.query.filter_by(status="approved").all()

    event_list = []
    for e in events:
        event_list.append({
            "title": f"{e.title} ({e.event_type})",
            "start": e.start_date.strftime("%Y-%m-%d"),
            "end": (e.end_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "color": "green" if e.event_type == "vacation" else "blue"
        })

    return render_template("calendar.html", events=event_list, user=current_user)


# Add event page
@app.route("/add_event", methods=["GET", "POST"])
@login_required
def add_event():
    if request.method == "POST":
        title = request.form["title"]
        event_type = request.form["event_type"]
        start_date = datetime.strptime(request.form["start_date"], "%Y-%m-%d").date()
        end_date = datetime.strptime(request.form["end_date"], "%Y-%m-%d").date()

        # Status logic
        if event_type == "vacation" and current_user.role != "admin":
            status = "pending"
            flash("Vacation request submitted for approval.", "info")
        else:
            status = "approved"
            flash("Event added successfully!", "success")

        new_event = Event(
            title=title,
            event_type=event_type,
            start_date=start_date,
            end_date=end_date,
            status=status,
            created_by=current_user.id
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

@app.route("/approve_event/<int:event_id>")
@login_required
def approve_event(event_id):
    if current_user.role != "admin":
        flash("Access denied", "danger")
        return redirect(url_for("calendar"))

    event = Event.query.get_or_404(event_id)
    event.status = "approved"
    db.session.commit()

    flash("Vacation approved", "success")
    return redirect(url_for("pending_vacations"))


@app.route("/reject_event/<int:event_id>")
@login_required
def reject_event(event_id):
    if current_user.role != "admin":
        flash("Access denied", "danger")
        return redirect(url_for("calendar"))

    event = Event.query.get_or_404(event_id)
    event.status = "rejected"
    db.session.commit()

    flash("Vacation rejected", "info")
    return redirect(url_for("pending_vacations"))


# Run app
if __name__ == "__main__":
    # Create tables and default users inside app context
    with app.app_context():
        db.create_all()  # Creates database tables if they don't exist

        # Create default admin and user (for first run)
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", password_hash=generate_password_hash("adminpass"), role="admin")
            user = User(username="alice", password_hash=generate_password_hash("alicepass"), role="user")
            db.session.add(admin)
            db.session.add(user)
            db.session.commit()

    # Run app
    app.run(debug=True)

