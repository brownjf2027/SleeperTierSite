# Sleeper Tiers
# BSD-3-Clause License
# Copyright (c) [2024] [Jasen Brown]
from _datetime import datetime
from collections import OrderedDict
from csv import DictWriter
from io import StringIO
from os import environ

import sqlalchemy.exc
from flask import Flask, render_template, redirect, url_for, make_response, jsonify, flash, request, session
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from pandas import read_csv
from requests import get
from sqlalchemy import Integer, String, Date, LargeBinary
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from wtforms import StringField, SubmitField, FileField, TextAreaField, EmailField
from wtforms.validators import DataRequired, ValidationError

from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

import data
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import time

SALT_ROUNDS = 16

app = Flask(__name__)
app.config['SECRET_KEY'] = environ.get('FLASK_KEY')  # Replace with your secret key
bootstrap = Bootstrap5(app)
scheduler = BackgroundScheduler()


class Base(DeclarativeBase):
    pass


# Replace {your_password_here} with your actual password
connection_string = (
    f"mssql+pymssql://sleeperadmin:{environ.get('FEEDBACK_DB_PASS')}@sleepertiers.database.windows.net:1433/feedback"
    "?timeout=30"
)
print(connection_string)
app.config['SQLALCHEMY_DATABASE_URI'] = connection_string
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# db = SQLAlchemy(model_class=Base)
# db.init_app(app)


class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(500))
    name: Mapped[str] = mapped_column(String(1000))
    admin: Mapped[bool]


class Feedback(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str]
    feedback: Mapped[str]


db_up = True
try:
    with app.app_context():
        db.create_all()
except sqlalchemy.exc.OperationalError:
    print("not available")
    db_up = False


# Configure Flask-Login's Login Manager
login_manager = LoginManager()
login_manager.init_app(app)


# Create a user_loader callback
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.')
            return redirect(url_for('login', logged_in=current_user.is_authenticated))
        elif not current_user.is_authenticated:
            flash('You do not have permission to view this page.')
            return redirect(url_for('index', logged_in=current_user.is_authenticated))  # or any other appropriate page
        return f(*args, **kwargs)
    return decorated_function


#  TODO Would need to update authentication to handle both regular and admin users if we wanted to enable ability to save tier sheets, currently only setup for admin
# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     if request.method == 'POST':
#         name = request.form.get('name')
#         email = request.form.get('email')
#         password = request.form.get('password')
#         admin = request.form.get('admin') == 'True'
#
#         if User.query.filter_by(email=email).first():
#             flash('Email address already exists')
#             return redirect(url_for('register'))
#
#         hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
#         new_user = User(name=name, email=email, password=hashed_password, admin=admin)
#         db.session.add(new_user)
#         db.session.commit()
#
#         login_user(new_user)
#         return redirect(url_for('/'))
#
#     return render_template('register.html')


@app.route("/post/<int:post_id>")
@admin_required
def show_post(post_id):
    requested_post = Feedback.query.filter_by(id=post_id).first()

    return render_template("post.html", post=requested_post, logged_in=current_user.is_authenticated)


@app.route("/posts")
@admin_required
def all_posts():
    all_posts = Feedback.query.all()

    return render_template("posts.html", posts=all_posts, logged_in=current_user.is_authenticated)


@app.route("/delete/<int:post_id>")
@admin_required
def delete_post(post_id):
    requested_post = Feedback.query.filter_by(id=post_id).first()
    db.session.delete(requested_post)
    db.session.commit()
    flash("Deleted!")
    all_posts = Feedback.query.all()
    return redirect(url_for('all_posts', posts=all_posts, logged_in=current_user.is_authenticated))


class CSVFileValidator:
    def __init__(self, message=None):
        if not message:
            message = 'File must be a CSV'
        self.message = message

    def __call__(self, form, field):
        if field.data:
            filename = field.data.filename
            if not (filename.endswith('.csv') or filename.endswith('.CSV')):
                raise ValidationError(self.message)


class LoginForm(FlaskForm):
    draft_id = StringField('Draft ID: (You can paste the full draft URL)', validators=[DataRequired()])
    draft_position = StringField('Your Drafting Position:', validators=[DataRequired()])
    csv_doc = FileField('CSV File for Players with Tier Assignments:', validators=[DataRequired(), CSVFileValidator()])
    submit = SubmitField('Launch Draft Tracker')


class SleeperIdForm(FlaskForm):
    sleeper_id = StringField('Sleeper Username:', validators=[DataRequired()])
    csv_doc = FileField('CSV File for Players with Tier Assignments:', validators=[DataRequired(), CSVFileValidator()])
    submit = SubmitField('Find Drafts')


class ManualLoginForm(FlaskForm):
    csv_doc = FileField('CSV File for Players with Tier Assignments:', validators=[DataRequired(), CSVFileValidator()])
    submit = SubmitField('Launch Draft Tracker')


class ContactForm(FlaskForm):
    name = StringField('Name')
    email = EmailField('Email')
    suggestion = TextAreaField('Suggestion *', validators=[DataRequired()])
    submit = SubmitField('Submit')


draft_status = ""
picks = []
draft_info = []
rbs_drafted = []
top_rbs = {}
top_wrs = {}
top_qbs = {}
top_tes = {}
top_ks = {}
top_defs = {}
my_rbs = {}
my_wrs = {}
my_qbs = {}
my_tes = {}
my_ks = {}
my_defs = {}
qb1s = 0
qb2s = 0
qb3s = 0
rb1s = 0
rb2s = 0
rb3s = 0
wr1s = 0
wr2s = 0
wr3s = 0
te1s = 0
te2s = 0
te3s = 0
def1s = 0
def2s = 0
def3s = 0
k1s = 0
k2s = 0
k3s = 0
my_picks = []


def start_scheduler():
    # Schedule the function to run at midnight every day
    scheduler.add_job(data.update_player_data_for_site, 'cron', hour=0, minute=0)
    scheduler.start()
    print("scheduler started.")


def send_contact(name, email, suggestion):
    pass


def get_current_date():
    return {'current_year': datetime.today().strftime('%Y')}


app.context_processor(get_current_date)
current_state = None


@app.route("/")
def home():
    return render_template('index.html', logged_in=current_user.is_authenticated)


@app.route('/signin', methods=['GET', 'POST'])
def login():
    # check_password_hash(pwhash, password)
    if request.method == "POST":
        user_email = request.form.get("email")
        user_password = request.form.get("password")

        # Querying the user based on the provided email
        user_check = User.query.filter_by(email=user_email).first()

        if user_check:
            if check_password_hash(user_check.password, user_password):
                login_user(user_check)
                return redirect(url_for("home", logged_in=current_user.is_authenticated))
            else:
                flash("Incorrect password, please try again.")
                return render_template("login.html", logged_in=current_user.is_authenticated)
        else:
            flash("That email does not exist, please try again.")
            return render_template("login.html", logged_in=current_user.is_authenticated)
    return render_template("login.html", logged_in=current_user.is_authenticated)


@app.route('/logout', methods=["GET"])
def logout():
    logout_user()
    return redirect(url_for('home', logged_in=current_user.is_authenticated))


@app.route("/contact", methods=["GET", "POST"])
def contact():
    contact_form = ContactForm()
    if contact_form.validate_on_submit():
        name = contact_form.name.data
        email = contact_form.email.data
        suggestion = contact_form.suggestion.data

        try:
            # CREATE RECORD
            new_feedback = Feedback(
                name=name,
                email=email,
                feedback=suggestion
            )
            db.session.add(new_feedback)
            db.session.commit()
        except Exception as ex:
            print(ex)

        return redirect(url_for("thanks", logged_in=current_user.is_authenticated))
    return render_template('contact.html', form=contact_form, logged_in=current_user.is_authenticated)


@app.route("/thanks", methods=["GET"])
def thanks():
    return render_template('thanks.html', logged_in=current_user.is_authenticated)


@app.route("/about", methods=["GET"])
def about():
    return render_template('about.html', logged_in=current_user.is_authenticated)


@app.route("/draft_login_choice", methods=["GET"])
def draft_login_choice():
    return render_template('draft_login_choice.html', logged_in=current_user.is_authenticated)


@app.route("/choose_draft", methods=["GET"])
def choose_draft():
    drafts = session.get('drafts')
    user = session.get('user_id')
    # Preprocess drafts to add 'position' field
    for draft in drafts:
        if draft['draft_order']:
            if user in draft['draft_order']:
                draft['draft_position'] = draft['draft_order'][user]
            else:
                draft['draft_position'] = 0
        else:
            draft['draft_position'] = 0

    session['drafts'] = drafts
    return render_template('choose_draft.html', drafts=drafts, logged_in=current_user.is_authenticated)


@app.route("/draft/manual", methods=['GET'])
def manual():
    global draft_status
    global picks
    global rbs_drafted
    global top_rbs
    global top_wrs
    global top_qbs
    global top_tes
    global top_ks
    global top_defs
    global my_rbs
    global my_wrs
    global my_qbs
    global my_tes
    global my_ks
    global my_defs
    global qb1s
    global qb2s
    global qb3s
    global rb1s
    global rb2s
    global rb3s
    global wr1s
    global wr2s
    global wr3s
    global te1s
    global te2s
    global te3s
    global def1s
    global def2s
    global def3s
    global k1s
    global k2s
    global k3s
    global my_picks

    # Retrieve the CSV content from the session
    csv_contents = data.get_csv()

    draft_status = ""
    if draft_status == "Complete":
        redirect_url = url_for('draft_complete', draft_id="manual", draft_position="", logged_in=current_user.is_authenticated)
        print("Redirect URL:", redirect_url)

        return redirect(url_for('draft_complete', draft_id="manual", draft_position="", logged_in=current_user.is_authenticated))

    picks = []
    picks = list(reversed(picks))
    top_players = data.top_players()
    for player, values in top_players.items():  # Assuming top_players is a dictionary
        if player in csv_contents and 'tier' in csv_contents[player] and csv_contents[player]['tier'] is not None:
            tier = csv_contents[player]['tier']
            # Convert tier to integer
            values['tier'] = int(tier)
        else:
            values['tier'] = 99

    rbs_drafted = [player for player in picks if player['metadata']['position'] == "RB"]
    drafted_rb_ids = [player_info.get('player_id') for player_info in rbs_drafted]
    # my_rbs = [player for player in rbs_drafted if player['picked_by'] == my_team]
    my_rbs = list(reversed(my_rbs))

    for player in my_rbs:
        id = player['player_id']
        player['tier'] = top_players[id].get('tier')

    print(list(my_rbs))
    top_rbs = {k: v for k, v in top_players.items() if v['position'] == "RB" and k not in drafted_rb_ids}
    sorted_rbs = sorted(top_rbs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
    top_rbs = OrderedDict(sorted_rbs)

    rb1s = len([player for player in top_rbs.values() if player.get('tier') == 1])
    rb2s = len([player for player in top_rbs.values() if player.get('tier') == 2])
    rb3s = len([player for player in top_rbs.values() if player.get('tier') == 3])

    wrs_drafted = [player for player in picks if player['metadata']['position'] == "WR"]
    # my_wrs = [player for player in wrs_drafted if player['picked_by'] == my_team]
    my_wrs = list(reversed(my_wrs))

    for player in my_wrs:
        id = player['player_id']
        player['tier'] = top_players[id].get('tier')

    drafted_wr_ids = [player_info.get('player_id') for player_info in wrs_drafted]
    top_wrs = {k: v for k, v in top_players.items() if v['position'] == "WR" and k not in drafted_wr_ids}
    sorted_wrs = sorted(top_wrs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
    top_wrs = OrderedDict(sorted_wrs)

    wr1s = len([player for player in top_wrs.values() if player.get('tier') == 1])
    wr2s = len([player for player in top_wrs.values() if player.get('tier') == 2])
    wr3s = len([player for player in top_wrs.values() if player.get('tier') == 3])

    qbs_drafted = [player for player in picks if player['metadata']['position'] == "QB"]
    # my_qbs = [player for player in qbs_drafted if player['picked_by'] == my_team]
    my_qbs = list(reversed(my_qbs))
    for player in my_qbs:
        id = player['player_id']
        player['tier'] = top_players[id].get('tier')

    drafted_qb_ids = [player_info.get('player_id') for player_info in qbs_drafted]
    top_qbs = {k: v for k, v in top_players.items() if v['position'] == "QB" and k not in drafted_qb_ids}
    sorted_qbs = sorted(top_qbs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
    top_qbs = OrderedDict(sorted_qbs)

    qb1s = len([player for player in top_qbs.values() if player.get('tier') == 1])
    qb2s = len([player for player in top_qbs.values() if player.get('tier') == 2])
    qb3s = len([player for player in top_qbs.values() if player.get('tier') == 3])

    tes_drafted = [player for player in picks if player['metadata']['position'] == "TE"]
    # my_tes = [player for player in tes_drafted if player['picked_by'] == my_team]
    my_tes = list(reversed(my_tes))
    for player in my_tes:
        id = player['player_id']
        player['tier'] = top_players[id].get('tier')

    drafted_te_ids = [player_info.get('player_id') for player_info in tes_drafted]
    top_tes = {k: v for k, v in top_players.items() if v['position'] == "TE" and k not in drafted_te_ids}
    sorted_tes = sorted(top_tes.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
    top_tes = OrderedDict(sorted_tes)

    te1s = len([player for player in top_tes.values() if player.get('tier') == 1])
    te2s = len([player for player in top_tes.values() if player.get('tier') == 2])
    te3s = len([player for player in top_tes.values() if player.get('tier') == 3])

    ks_drafted = [player for player in picks if player['metadata']['position'] == "K"]
    # my_ks = [player for player in ks_drafted if player['picked_by'] == my_team]
    my_ks = list(reversed(my_ks))
    for player in my_ks:
        id = player['player_id']
        player['tier'] = top_players[id].get('tier')

    drafted_k_ids = [player_info.get('player_id') for player_info in ks_drafted]
    top_ks = {k: v for k, v in top_players.items() if v['position'] == "K" and k not in drafted_k_ids}
    sorted_ks = sorted(top_ks.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
    top_ks = OrderedDict(sorted_ks)

    k1s = len([player for player in top_ks.values() if player.get('tier') == 1])
    k2s = len([player for player in top_ks.values() if player.get('tier') == 2])
    k3s = len([player for player in top_ks.values() if player.get('tier') == 3])

    defs_drafted = [player for player in picks if player['metadata']['position'] == "DEF"]
    # my_defs = [player for player in defs_drafted if player['picked_by'] == my_team]
    my_defs = list(reversed(my_defs))
    for player in my_defs:
        id = player['player_id']
        player['tier'] = top_players[id].get('tier')

    drafted_def_ids = [player_info.get('player_id') for player_info in defs_drafted]
    top_defs = {k: v for k, v in top_players.items() if v['position'] == "DEF" and k not in drafted_def_ids}
    sorted_defs = sorted(top_defs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
    top_defs = OrderedDict(sorted_defs)

    def1s = len([player for player in top_defs.values() if player.get('tier') == 1])
    def2s = len([player for player in top_defs.values() if player.get('tier') == 2])
    def3s = len([player for player in top_defs.values() if player.get('tier') == 3])

    return render_template('manual_draft.html',
                           draft_status=draft_status,
                           draft_picks=picks,
                           rbs_drafted_count=len(rbs_drafted),
                           top_rbs=top_rbs,
                           top_wrs=top_wrs,
                           top_tes=top_tes,
                           top_qbs=top_qbs,
                           top_ks=top_ks,
                           top_defs=top_defs,
                           my_qbs=my_qbs,
                           my_rbs=my_rbs,
                           my_wrs=my_wrs,
                           my_tes=my_tes,
                           my_ks=my_ks,
                           my_defs=my_defs,
                           rb1s=rb1s,
                           rb2s=rb2s,
                           rb3s=rb3s,
                           wr1s=wr1s,
                           wr2s=wr2s,
                           wr3s=wr3s,
                           te1s=te1s,
                           te2s=te2s,
                           te3s=te3s,
                           qb1s=qb1s,
                           qb2s=qb2s,
                           qb3s=qb3s,
                           def1s=def1s,
                           def2s=def2s,
                           def3s=def3s,
                           k1s=k1s,
                           k2s=k2s,
                           k3s=k3s, logged_in=current_user.is_authenticated,
                           )


@app.route("/draft/manual/<function>/<player>", methods=['GET'])
def manual_picked(function, player):
    global draft_status
    global picks
    global rbs_drafted
    global top_rbs
    global top_wrs
    global top_qbs
    global top_tes
    global top_ks
    global top_defs
    global my_rbs
    global my_wrs
    global my_qbs
    global my_tes
    global my_ks
    global my_defs
    global qb1s
    global qb2s
    global qb3s
    global rb1s
    global rb2s
    global rb3s
    global wr1s
    global wr2s
    global wr3s
    global te1s
    global te2s
    global te3s
    global def1s
    global def2s
    global def3s
    global k1s
    global k2s
    global k3s
    global my_picks

    # Retrieve the CSV content from the session
    csv_contents = data.get_csv()
    print(player)

    draft_status = ""
    if draft_status == "Complete":
        redirect_url = url_for('draft_complete', draft_id="manual", draft_position="", logged_in=current_user.is_authenticated)
        print("Redirect URL:", redirect_url)

        return redirect(url_for('draft_complete', draft_id="manual", draft_position="", logged_in=current_user.is_authenticated))

    top_players = data.top_players()

    if function == "undo":
        print(f"Initial picks: {picks}")
        print(f"Initial my_picks: {my_picks}")
        print(f"Player ID to remove: {player}")
        # Remove picks from picks list
        picks = [pick for pick in picks if pick['player_id'] != player]

        # Remove picks from my_picks list
        if my_picks:
            my_picks = [pick for pick in my_picks if pick['player_id'] != player]

    else:
        picks.append(top_players[player])
        # picks = list(reversed(picks))
        if function == "chosen":
            my_picks.append(top_players[player])

    for player, values in top_players.items():  # Assuming top_players is a dictionary
        if player in csv_contents and 'tier' in csv_contents[player] and csv_contents[player]['tier'] is not None:
            tier = csv_contents[player]['tier']
            # Convert tier to integer
            values['tier'] = int(tier)
        else:
            values['tier'] = 99

    rbs_drafted = [player for player in picks if player['position'] == "RB"]
    drafted_rb_ids = [player_info.get('player_id') for player_info in rbs_drafted]
    my_rbs = [player for player in my_picks if player['position'] == "RB"]
    # my_rbs = list(reversed(my_rbs))

    for player in my_rbs:
        id = player['player_id']
        player['tier'] = top_players[id].get('tier')

    print(list(my_rbs))
    top_rbs = {k: v for k, v in top_players.items() if v['position'] == "RB" and k not in drafted_rb_ids}
    sorted_rbs = sorted(top_rbs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
    top_rbs = OrderedDict(sorted_rbs)

    rb1s = len([player for player in top_rbs.values() if player.get('tier') == 1])
    rb2s = len([player for player in top_rbs.values() if player.get('tier') == 2])
    rb3s = len([player for player in top_rbs.values() if player.get('tier') == 3])

    wrs_drafted = [player for player in picks if player['position'] == "WR"]
    my_wrs = [player for player in my_picks if player['position'] == "WR"]
    # my_wrs = list(reversed(my_wrs))

    for player in my_wrs:
        id = player['player_id']
        player['tier'] = top_players[id].get('tier')

    drafted_wr_ids = [player_info.get('player_id') for player_info in wrs_drafted]
    top_wrs = {k: v for k, v in top_players.items() if v['position'] == "WR" and k not in drafted_wr_ids}
    sorted_wrs = sorted(top_wrs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
    top_wrs = OrderedDict(sorted_wrs)

    wr1s = len([player for player in top_wrs.values() if player.get('tier') == 1])
    wr2s = len([player for player in top_wrs.values() if player.get('tier') == 2])
    wr3s = len([player for player in top_wrs.values() if player.get('tier') == 3])

    qbs_drafted = [player for player in picks if player['position'] == "QB"]
    my_qbs = [player for player in my_picks if player['position'] == "QB"]
    # my_qbs = list(reversed(my_qbs))
    for player in my_qbs:
        id = player['player_id']
        player['tier'] = top_players[id].get('tier')

    drafted_qb_ids = [player_info.get('player_id') for player_info in qbs_drafted]
    top_qbs = {k: v for k, v in top_players.items() if v['position'] == "QB" and k not in drafted_qb_ids}
    sorted_qbs = sorted(top_qbs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
    top_qbs = OrderedDict(sorted_qbs)

    qb1s = len([player for player in top_qbs.values() if player.get('tier') == 1])
    qb2s = len([player for player in top_qbs.values() if player.get('tier') == 2])
    qb3s = len([player for player in top_qbs.values() if player.get('tier') == 3])

    tes_drafted = [player for player in picks if player['position'] == "TE"]
    my_tes = [player for player in my_picks if player['position'] == "TE"]
    # my_tes = list(reversed(my_tes))
    for player in my_tes:
        id = player['player_id']
        player['tier'] = top_players[id].get('tier')

    drafted_te_ids = [player_info.get('player_id') for player_info in tes_drafted]
    top_tes = {k: v for k, v in top_players.items() if v['position'] == "TE" and k not in drafted_te_ids}
    sorted_tes = sorted(top_tes.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
    top_tes = OrderedDict(sorted_tes)

    te1s = len([player for player in top_tes.values() if player.get('tier') == 1])
    te2s = len([player for player in top_tes.values() if player.get('tier') == 2])
    te3s = len([player for player in top_tes.values() if player.get('tier') == 3])

    ks_drafted = [player for player in picks if player['position'] == "K"]
    my_ks = [player for player in my_picks if player['position'] == "K"]
    # my_ks = list(reversed(my_ks))
    for player in my_ks:
        id = player['player_id']
        player['tier'] = top_players[id].get('tier')

    drafted_k_ids = [player_info.get('player_id') for player_info in ks_drafted]
    top_ks = {k: v for k, v in top_players.items() if v['position'] == "K" and k not in drafted_k_ids}
    sorted_ks = sorted(top_ks.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
    top_ks = OrderedDict(sorted_ks)

    k1s = len([player for player in top_ks.values() if player.get('tier') == 1])
    k2s = len([player for player in top_ks.values() if player.get('tier') == 2])
    k3s = len([player for player in top_ks.values() if player.get('tier') == 3])

    defs_drafted = [player for player in picks if player['position'] == "DEF"]
    my_defs = [player for player in my_picks if player['position'] == "DEF"]
    # my_defs = list(reversed(my_defs))
    for player in my_defs:
        id = player['player_id']
        player['tier'] = top_players[id].get('tier')

    drafted_def_ids = [player_info.get('player_id') for player_info in defs_drafted]
    top_defs = {k: v for k, v in top_players.items() if v['position'] == "DEF" and k not in drafted_def_ids}
    sorted_defs = sorted(top_defs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
    top_defs = OrderedDict(sorted_defs)

    def1s = len([player for player in top_defs.values() if player.get('tier') == 1])
    def2s = len([player for player in top_defs.values() if player.get('tier') == 2])
    def3s = len([player for player in top_defs.values() if player.get('tier') == 3])

    return render_template('manual_draft.html',
                           draft_status=draft_status,
                           draft_picks=list(reversed(picks)),
                           rbs_drafted_count=len(rbs_drafted),
                           top_rbs=top_rbs,
                           top_wrs=top_wrs,
                           top_tes=top_tes,
                           top_qbs=top_qbs,
                           top_ks=top_ks,
                           top_defs=top_defs,
                           my_qbs=list(reversed(my_qbs)),
                           my_rbs=list(reversed(my_rbs)),
                           my_wrs=list(reversed(my_wrs)),
                           my_tes=list(reversed(my_tes)),
                           my_ks=list(reversed(my_ks)),
                           my_defs=list(reversed(my_defs)),
                           rb1s=rb1s,
                           rb2s=rb2s,
                           rb3s=rb3s,
                           wr1s=wr1s,
                           wr2s=wr2s,
                           wr3s=wr3s,
                           te1s=te1s,
                           te2s=te2s,
                           te3s=te3s,
                           qb1s=qb1s,
                           qb2s=qb2s,
                           qb3s=qb3s,
                           def1s=def1s,
                           def2s=def2s,
                           def3s=def3s,
                           k1s=k1s,
                           k2s=k2s,
                           k3s=k3s,
                           my_picks=list(reversed(my_picks)), logged_in=current_user.is_authenticated
                           )


@app.route("/download_csv", methods=["POST"])
def download_csv():
    # Generate CSV content
    top_players = data.top_players()

    # Define the fieldnames for the CSV
    fieldnames = [
        "player_id",
        "full_name",
        "position",
        "team",
        "depth_chart_order",
        "pts_std",
        "pts_half_ppr",
        "pts_ppr",
        "adp_std",
        "adp_half_ppr",
        "adp_ppr",
        "tier"
    ]

    # Create a StringIO object to hold CSV content
    csv_buffer = StringIO()

    # Create a DictWriter object to write the CSV
    csv_writer = DictWriter(csv_buffer, fieldnames=fieldnames)

    # Write the header row
    csv_writer.writeheader()

    # Write the rows of player data
    for player_id, player_data in top_players.items():
        # Extract the relevant fields
        row_data = {
            'player_id': player_data['player_id'],
            'full_name': player_data.get('full_name', ''),
            'position': player_data['position'],
            'team': player_data['team'],
            'depth_chart_order': player_data.get('depth_chart_order', ''),
            'pts_std': player_data['stats'].get('pts_std', ''),
            'pts_half_ppr': player_data['stats'].get('pts_half_ppr', ''),
            'pts_ppr': player_data['stats'].get('pts_ppr', ''),
            'adp_std': player_data['stats'].get('adp_std', ''),
            'adp_half_ppr': player_data['stats'].get('adp_half_ppr', ''),
            'adp_ppr': player_data['stats'].get('adp_ppr', ''),
            'tier': ""
        }

        # Write the row to the CSV
        csv_writer.writerow(row_data)

    # Set up response headers
    headers = {
        "Content-Disposition": "attachment; filename=tiers.csv",
        "Content-Type": "text/csv"
    }

    # Create a Flask response with the CSV data
    response = make_response(csv_buffer.getvalue())

    # Set the headers
    for key, value in headers.items():
        response.headers[key] = value

    # Return the response
    return response


@app.route("/login", methods=["GET", "POST"])
def draft_login():
    form = LoginForm()
    if form.validate_on_submit():
        draft_id = form.draft_id.data
        if "nfl" in draft_id:
            split_string = draft_id.split("/")
            draft_id = split_string[-1]
            if "?" in draft_id:
                split_string = draft_id.split("?")
                draft_id = split_string[0]
        draft_position = form.draft_position.data
        csv_file = form.csv_doc.data

        try:
            # Read CSV data into a DataFrame
            csv_df = read_csv(csv_file)

            # Convert DataFrame to JSON format
            csv_df.set_index('player_id', inplace=True)
            # csv_json = csv_df.to_json(orient='index', indent=4)

            # Write JSON data to a file
            with open("csv_upload.json", "w") as data_file:
                # json.dump(csv_json, data_file, indent=4)
                csv_df.to_json(data_file, orient='index', indent=4)

            # Redirect to success page
            return redirect(url_for('success', draft_id=draft_id, draft_position=draft_position, logged_in=current_user.is_authenticated))

        except Exception as e:
            # Handle any errors that occur during the process
            print("An error occurred:", e)

    return render_template("draft_login.html", form=form, logged_in=current_user.is_authenticated)


@app.route("/draft_login_by_id", methods=["GET", "POST"])
def draft_login_by_id():
    form = SleeperIdForm()
    if form.validate_on_submit():
        yr = datetime.now().year
        session['drafts'] = data.get_drafts(yr, str(form.sleeper_id.data))
        session['user_id'] = data.get_user(str(form.sleeper_id.data))['user_id']
        csv_file = form.csv_doc.data

        try:
            # Read CSV data into a DataFrame
            csv_df = read_csv(csv_file)

            # Convert DataFrame to JSON format
            csv_df.set_index('player_id', inplace=True)
            # csv_json = csv_df.to_json(orient='index', indent=4)

            # Write JSON data to a file
            with open("csv_upload.json", "w") as data_file:
                # json.dump(csv_json, data_file, indent=4)
                csv_df.to_json(data_file, orient='index', indent=4)

            # Redirect to success page
            return redirect(url_for('choose_draft', logged_in=current_user.is_authenticated))

        except Exception as e:
            # Handle any errors that occur during the process
            print("An error occurred:", e)

    return render_template("draft_login_by_id.html", form=form, logged_in=current_user.is_authenticated)


@app.route("/manual_login", methods=["GET", "POST"])
def manual_login():
    form = ManualLoginForm()
    if form.validate_on_submit():
        csv_file = form.csv_doc.data

        try:
            # Read CSV data into a DataFrame
            csv_df = read_csv(csv_file)

            # Convert DataFrame to JSON format
            csv_df.set_index('player_id', inplace=True)
            # csv_json = csv_df.to_json(orient='index', indent=4)

            # Write JSON data to a file
            with open("csv_upload.json", "w") as data_file:
                # json.dump(csv_json, data_file, indent=4)
                csv_df.to_json(data_file, orient='index', indent=4)

            # Redirect to success page
            return redirect(url_for('manual', logged_in=current_user.is_authenticated))

        except Exception as e:
            # Handle any errors that occur during the process
            print("An error occurred:", e)

    return render_template("manual_draft_login.html", form=form, logged_in=current_user.is_authenticated)


@app.route("/check_for_updates/<draft_id>")
def check_for_updates(draft_id):
    global current_state
    parameters = {
        # "draft_id": draft_id
    }

    draft_api_url = "https://api.sleeper.app/v1/draft/" + draft_id + "/picks"
    response = get(draft_api_url, params=parameters)
    response.raise_for_status()
    try:
        new_state = response.json()[-1]['pick_no']
    except IndexError:
        new_state = 'no picks'
    print("New state:", new_state)  # Add print statement to debug
    print("Current state:", current_state)  # Add print statement to debug

    # Compare new state with the current state
    if new_state != current_state:
        print("New pick found.")  # Add print statement to debug
        current_state = new_state
        # If there's an update, return it as JSON response
        print(jsonify({"update_available": True, "new_state": new_state}))
        return jsonify({"update_available": True, "new_state": new_state})

    else:
        # If there's no update, return a response indicating that
        return jsonify({"update_available": False})


@app.route("/draft/<draft_id>/<draft_position>", methods=['GET'])
def success(draft_id, draft_position):
    # additional processing
    draft_status = "Not Found. Verify draft ID and try again."
    picks = []
    draft_info = []
    rbs_drafted = []
    top_rbs = {}
    top_wrs = {}
    top_qbs = {}
    top_tes = {}
    top_ks = {}
    top_defs = {}
    my_rbs = {}
    my_wrs = {}
    my_qbs = {}
    my_tes = {}
    my_ks = {}
    my_defs = {}
    qb1s = 0
    qb2s = 0
    qb3s = 0
    rb1s = 0
    rb2s = 0
    rb3s = 0
    wr1s = 0
    wr2s = 0
    wr3s = 0
    te1s = 0
    te2s = 0
    te3s = 0
    def1s = 0
    def2s = 0
    def3s = 0
    k1s = 0
    k2s = 0
    k3s = 0

    draft_order = {}
    my_team = ""
    # Retrieve the CSV content from the session
    csv_contents = data.get_csv()

    try:
        draft_info = data.get_draft(draft_id)
        draft_order = draft_info.get('draft_order')
        draft_scoring_type = draft_info['metadata']['scoring_type']

        adp_key = "adp_half_ppr"
        pts_key = "pts_half_ppr"
        if draft_scoring_type == "ppr":
            adp_key = "adp_ppr"
            pts_key = "pts_ppr"
        elif draft_scoring_type == "std":
            adp_key = "adp_std"
            pts_key = "pts_std"
        elif draft_scoring_type == "idp":
            adp_key = "adp_idp"
        elif draft_scoring_type == "2qb":
            adp_key = "adp_2qb"
        elif draft_scoring_type == "dynasty_half_ppr":
            adp_key = "adp_dynasty_half_ppr"
        elif draft_scoring_type == "dynasty_std":
            adp_key = "adp_dynasty_std"
            pts_key = "pts_std"
        elif draft_scoring_type == "dynasty_ppr":
            adp_key = "adp_dynasty_ppr"
            pts_key = "pts_ppr"
        elif draft_scoring_type == "dynasty_2qb":
            adp_key = "adp_dynasty_2qb"

        if draft_order is not None:
            for key, value in draft_order.items():
                if value == int(draft_position):
                    my_team = str(key)

        draft_status = draft_info['status'].title()
        if draft_status == "Complete":
            redirect_url = url_for('draft_complete', draft_id=draft_id, draft_position=draft_position, logged_in=current_user.is_authenticated)
            print("Redirect URL:", redirect_url)

            return redirect(url_for('draft_complete', draft_id=draft_id, draft_position=draft_position, logged_in=current_user.is_authenticated))
        picks = data.get_draft_picks(draft_id)
        picks = list(reversed(picks))
        top_players = data.top_players()
        for player, values in top_players.items():  # Assuming top_players is a dictionary
            if player in csv_contents and 'tier' in csv_contents[player] and csv_contents[player]['tier'] is not None:
                tier = csv_contents[player]['tier']
                # Convert tier to integer
                values['tier'] = int(tier)
            else:
                values['tier'] = 99

        rbs_drafted = [player for player in picks if player['metadata']['position'] == "RB"]
        drafted_rb_ids = [player_info.get('player_id') for player_info in rbs_drafted]
        my_rbs = [player for player in rbs_drafted if player['picked_by'] == my_team]
        my_rbs = list(reversed(my_rbs))

        for player in my_rbs:
            id = player['player_id']
            player['tier'] = top_players[id].get('tier')

        print(list(my_rbs))
        top_rbs = {k: v for k, v in top_players.items() if v['position'] == "RB" and k not in drafted_rb_ids}
        sorted_rbs = sorted(top_rbs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_rbs = OrderedDict(sorted_rbs)

        rb1s = len([player for player in top_rbs.values() if player.get('tier') == 1])
        rb2s = len([player for player in top_rbs.values() if player.get('tier') == 2])
        rb3s = len([player for player in top_rbs.values() if player.get('tier') == 3])

        wrs_drafted = [player for player in picks if player['metadata']['position'] == "WR"]
        my_wrs = [player for player in wrs_drafted if player['picked_by'] == my_team]
        my_wrs = list(reversed(my_wrs))

        for player in my_wrs:
            id = player['player_id']
            player['tier'] = top_players[id].get('tier')

        drafted_wr_ids = [player_info.get('player_id') for player_info in wrs_drafted]
        top_wrs = {k: v for k, v in top_players.items() if v['position'] == "WR" and k not in drafted_wr_ids}
        sorted_wrs = sorted(top_wrs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_wrs = OrderedDict(sorted_wrs)

        wr1s = len([player for player in top_wrs.values() if player.get('tier') == 1])
        wr2s = len([player for player in top_wrs.values() if player.get('tier') == 2])
        wr3s = len([player for player in top_wrs.values() if player.get('tier') == 3])

        qbs_drafted = [player for player in picks if player['metadata']['position'] == "QB"]
        my_qbs = [player for player in qbs_drafted if player['picked_by'] == my_team]
        my_qbs = list(reversed(my_qbs))
        for player in my_qbs:
            id = player['player_id']
            player['tier'] = top_players[id].get('tier')

        drafted_qb_ids = [player_info.get('player_id') for player_info in qbs_drafted]
        top_qbs = {k: v for k, v in top_players.items() if v['position'] == "QB" and k not in drafted_qb_ids}
        sorted_qbs = sorted(top_qbs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_qbs = OrderedDict(sorted_qbs)

        qb1s = len([player for player in top_qbs.values() if player.get('tier') == 1])
        qb2s = len([player for player in top_qbs.values() if player.get('tier') == 2])
        qb3s = len([player for player in top_qbs.values() if player.get('tier') == 3])

        tes_drafted = [player for player in picks if player['metadata']['position'] == "TE"]
        my_tes = [player for player in tes_drafted if player['picked_by'] == my_team]
        my_tes = list(reversed(my_tes))
        for player in my_tes:
            id = player['player_id']
            player['tier'] = top_players[id].get('tier')

        drafted_te_ids = [player_info.get('player_id') for player_info in tes_drafted]
        top_tes = {k: v for k, v in top_players.items() if v['position'] == "TE" and k not in drafted_te_ids}
        sorted_tes = sorted(top_tes.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_tes = OrderedDict(sorted_tes)

        te1s = len([player for player in top_tes.values() if player.get('tier') == 1])
        te2s = len([player for player in top_tes.values() if player.get('tier') == 2])
        te3s = len([player for player in top_tes.values() if player.get('tier') == 3])

        ks_drafted = [player for player in picks if player['metadata']['position'] == "K"]
        my_ks = [player for player in ks_drafted if player['picked_by'] == my_team]
        my_ks = list(reversed(my_ks))
        for player in my_ks:
            id = player['player_id']
            player['tier'] = top_players[id].get('tier')

        drafted_k_ids = [player_info.get('player_id') for player_info in ks_drafted]
        top_ks = {k: v for k, v in top_players.items() if v['position'] == "K" and k not in drafted_k_ids}
        sorted_ks = sorted(top_ks.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_ks = OrderedDict(sorted_ks)

        k1s = len([player for player in top_ks.values() if player.get('tier') == 1])
        k2s = len([player for player in top_ks.values() if player.get('tier') == 2])
        k3s = len([player for player in top_ks.values() if player.get('tier') == 3])

        defs_drafted = [player for player in picks if player['metadata']['position'] == "DEF"]
        my_defs = [player for player in defs_drafted if player['picked_by'] == my_team]
        my_defs = list(reversed(my_defs))
        for player in my_defs:
            id = player['player_id']
            player['tier'] = top_players[id].get('tier')

        drafted_def_ids = [player_info.get('player_id') for player_info in defs_drafted]
        top_defs = {k: v for k, v in top_players.items() if v['position'] == "DEF" and k not in drafted_def_ids}
        sorted_defs = sorted(top_defs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_defs = OrderedDict(sorted_defs)

        def1s = len([player for player in top_defs.values() if player.get('tier') == 1])
        def2s = len([player for player in top_defs.values() if player.get('tier') == 2])
        def3s = len([player for player in top_defs.values() if player.get('tier') == 3])

    except:
        return render_template("not_found.html", logged_in=current_user.is_authenticated)

    return render_template("draft_board.html",
                           draft_id=draft_id,
                           draft_position=draft_position,
                           draft_status=draft_status,
                           draft_info=draft_info,
                           draft_picks=picks,
                           rbs_drafted_count=len(rbs_drafted),
                           top_rbs=top_rbs,
                           top_wrs=top_wrs,
                           top_tes=top_tes,
                           top_qbs=top_qbs,
                           top_ks=top_ks,
                           top_defs=top_defs,
                           my_qbs=my_qbs,
                           my_rbs=my_rbs,
                           my_wrs=my_wrs,
                           my_tes=my_tes,
                           my_ks=my_ks,
                           my_defs=my_defs,
                           rb1s=rb1s,
                           rb2s=rb2s,
                           rb3s=rb3s,
                           wr1s=wr1s,
                           wr2s=wr2s,
                           wr3s=wr3s,
                           te1s=te1s,
                           te2s=te2s,
                           te3s=te3s,
                           qb1s=qb1s,
                           qb2s=qb2s,
                           qb3s=qb3s,
                           def1s=def1s,
                           def2s=def2s,
                           def3s=def3s,
                           k1s=k1s,
                           k2s=k2s,
                           k3s=k3s,
                           my_team=my_team,
                           adp_key=adp_key,
                           pts_key=pts_key,
                           logged_in=current_user.is_authenticated
                           )


@app.route("/draft/complete/<draft_id>/<draft_position>", methods=['GET'])
def draft_complete(draft_id, draft_position):
    # additional processing
    draft_status = "Not Found. Verify draft ID and try again."
    picks = []
    draft_info = []
    rbs_drafted = []
    top_rbs = {}
    top_wrs = {}
    top_qbs = {}
    top_tes = {}
    top_ks = {}
    top_defs = {}
    my_rbs = {}
    my_wrs = {}
    my_qbs = {}
    my_tes = {}
    my_ks = {}
    my_defs = {}
    qb1s = 0
    qb2s = 0
    qb3s = 0
    rb1s = 0
    rb2s = 0
    rb3s = 0
    wr1s = 0
    wr2s = 0
    wr3s = 0
    te1s = 0
    te2s = 0
    te3s = 0
    def1s = 0
    def2s = 0
    def3s = 0
    k1s = 0
    k2s = 0
    k3s = 0

    draft_order = {}
    my_team = ""
    # Retrieve the CSV content from the session
    csv_contents = data.get_csv()

    try:
        draft_info = data.get_draft(draft_id)
        draft_order = draft_info['draft_order']
        draft_scoring_type = draft_info['metadata']['scoring_type']

        adp_key = "adp_half_ppr"
        pts_key = "pts_half_ppr"
        if draft_scoring_type == "ppr":
            adp_key = "adp_ppr"
            pts_key = "pts_ppr"
        elif draft_scoring_type == "std":
            adp_key = "adp_std"
            pts_key = "pts_std"
        elif draft_scoring_type == "idp":
            adp_key = "adp_idp"
        elif draft_scoring_type == "2qb":
            adp_key = "adp_2qb"
        elif draft_scoring_type == "dynasty_half_ppr":
            adp_key = "adp_dynasty_half_ppr"
        elif draft_scoring_type == "dynasty_std":
            adp_key = "adp_dynasty_std"
            pts_key = "pts_std"
        elif draft_scoring_type == "dynasty_ppr":
            adp_key = "adp_dynasty_ppr"
            pts_key = "pts_ppr"
        elif draft_scoring_type == "dynasty_2qb":
            adp_key = "adp_dynasty_2qb"

        for key, value in draft_order.items():
            if value == int(draft_position):
                my_team = str(key)

        draft_status = draft_info['status'].title()
        picks = data.get_draft_picks(draft_id)
        picks = list(reversed(picks))
        top_players = data.top_players()
        for player, values in top_players.items():  # Assuming top_players is a dictionary
            if player in csv_contents and 'tier' in csv_contents[player] and csv_contents[player]['tier'] is not None:
                tier = csv_contents[player]['tier']
                # Convert tier to integer
                values['tier'] = int(tier)
            else:
                values['tier'] = 99

        rbs_drafted = [player for player in picks if player['metadata']['position'] == "RB"]
        drafted_rb_ids = [player_info.get('player_id') for player_info in rbs_drafted]
        my_rbs = [player for player in rbs_drafted if player['picked_by'] == my_team]
        my_rbs = list(reversed(my_rbs))

        for player in my_rbs:
            id = player['player_id']
            player['tier'] = top_players[id].get('tier')

        print(list(my_rbs))
        top_rbs = {k: v for k, v in top_players.items() if v['position'] == "RB" and k not in drafted_rb_ids}
        sorted_rbs = sorted(top_rbs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_rbs = OrderedDict(sorted_rbs)

        rb1s = len([player for player in top_rbs.values() if player.get('tier') == 1])
        rb2s = len([player for player in top_rbs.values() if player.get('tier') == 2])
        rb3s = len([player for player in top_rbs.values() if player.get('tier') == 3])

        wrs_drafted = [player for player in picks if player['metadata']['position'] == "WR"]
        my_wrs = [player for player in wrs_drafted if player['picked_by'] == my_team]
        my_wrs = list(reversed(my_wrs))

        for player in my_wrs:
            id = player['player_id']
            player['tier'] = top_players[id].get('tier')

        drafted_wr_ids = [player_info.get('player_id') for player_info in wrs_drafted]
        top_wrs = {k: v for k, v in top_players.items() if v['position'] == "WR" and k not in drafted_wr_ids}
        sorted_wrs = sorted(top_wrs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_wrs = OrderedDict(sorted_wrs)

        wr1s = len([player for player in top_wrs.values() if player.get('tier') == 1])
        wr2s = len([player for player in top_wrs.values() if player.get('tier') == 2])
        wr3s = len([player for player in top_wrs.values() if player.get('tier') == 3])

        qbs_drafted = [player for player in picks if player['metadata']['position'] == "QB"]
        my_qbs = [player for player in qbs_drafted if player['picked_by'] == my_team]
        my_qbs = list(reversed(my_qbs))
        for player in my_qbs:
            id = player['player_id']
            player['tier'] = top_players[id].get('tier')

        drafted_qb_ids = [player_info.get('player_id') for player_info in qbs_drafted]
        top_qbs = {k: v for k, v in top_players.items() if v['position'] == "QB" and k not in drafted_qb_ids}
        sorted_qbs = sorted(top_qbs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_qbs = OrderedDict(sorted_qbs)

        qb1s = len([player for player in top_qbs.values() if player.get('tier') == 1])
        qb2s = len([player for player in top_qbs.values() if player.get('tier') == 2])
        qb3s = len([player for player in top_qbs.values() if player.get('tier') == 3])

        tes_drafted = [player for player in picks if player['metadata']['position'] == "TE"]
        my_tes = [player for player in tes_drafted if player['picked_by'] == my_team]
        my_tes = list(reversed(my_tes))
        for player in my_tes:
            id = player['player_id']
            player['tier'] = top_players[id].get('tier')

        drafted_te_ids = [player_info.get('player_id') for player_info in tes_drafted]
        top_tes = {k: v for k, v in top_players.items() if v['position'] == "TE" and k not in drafted_te_ids}
        sorted_tes = sorted(top_tes.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_tes = OrderedDict(sorted_tes)

        te1s = len([player for player in top_tes.values() if player.get('tier') == 1])
        te2s = len([player for player in top_tes.values() if player.get('tier') == 2])
        te3s = len([player for player in top_tes.values() if player.get('tier') == 3])

        ks_drafted = [player for player in picks if player['metadata']['position'] == "K"]
        my_ks = [player for player in ks_drafted if player['picked_by'] == my_team]
        my_ks = list(reversed(my_ks))
        for player in my_ks:
            id = player['player_id']
            player['tier'] = top_players[id].get('tier')

        drafted_k_ids = [player_info.get('player_id') for player_info in ks_drafted]
        top_ks = {k: v for k, v in top_players.items() if v['position'] == "K" and k not in drafted_k_ids}
        sorted_ks = sorted(top_ks.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_ks = OrderedDict(sorted_ks)

        k1s = len([player for player in top_ks.values() if player.get('tier') == 1])
        k2s = len([player for player in top_ks.values() if player.get('tier') == 2])
        k3s = len([player for player in top_ks.values() if player.get('tier') == 3])

        defs_drafted = [player for player in picks if player['metadata']['position'] == "DEF"]
        my_defs = [player for player in defs_drafted if player['picked_by'] == my_team]
        my_defs = list(reversed(my_defs))
        for player in my_defs:
            id = player['player_id']
            player['tier'] = top_players[id].get('tier')

        drafted_def_ids = [player_info.get('player_id') for player_info in defs_drafted]
        top_defs = {k: v for k, v in top_players.items() if v['position'] == "DEF" and k not in drafted_def_ids}
        sorted_defs = sorted(top_defs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_defs = OrderedDict(sorted_defs)

        def1s = len([player for player in top_defs.values() if player.get('tier') == 1])
        def2s = len([player for player in top_defs.values() if player.get('tier') == 2])
        def3s = len([player for player in top_defs.values() if player.get('tier') == 3])

    except:
        return render_template("not_found.html", logged_in=current_user.is_authenticated)

    return render_template("draft_complete.html",
                           draft_id=draft_id,
                           draft_position=draft_position,
                           draft_status=draft_status,
                           draft_info=draft_info,
                           draft_picks=picks,
                           rbs_drafted_count=len(rbs_drafted),
                           top_rbs=top_rbs,
                           top_wrs=top_wrs,
                           top_tes=top_tes,
                           top_qbs=top_qbs,
                           top_ks=top_ks,
                           top_defs=top_defs,
                           my_qbs=my_qbs,
                           my_rbs=my_rbs,
                           my_wrs=my_wrs,
                           my_tes=my_tes,
                           my_ks=my_ks,
                           my_defs=my_defs,
                           rb1s=rb1s,
                           rb2s=rb2s,
                           rb3s=rb3s,
                           wr1s=wr1s,
                           wr2s=wr2s,
                           wr3s=wr3s,
                           te1s=te1s,
                           te2s=te2s,
                           te3s=te3s,
                           qb1s=qb1s,
                           qb2s=qb2s,
                           qb3s=qb3s,
                           def1s=def1s,
                           def2s=def2s,
                           def3s=def3s,
                           k1s=k1s,
                           k2s=k2s,
                           k3s=k3s,
                           my_team=my_team,
                           adp_key=adp_key,
                           pts_key=pts_key,
                           logged_in=current_user.is_authenticated
                           )


if __name__ == '__main__':
    # Start the scheduler
    start_scheduler()

    # app.run(debug=True)
    app.run()

    try:
        # Keep the main thread alive
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        # Not strictly necessary if daemonic mode is enabled but should be done if possible
        scheduler.shutdown()
