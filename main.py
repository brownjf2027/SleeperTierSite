from _datetime import datetime
from collections import OrderedDict
from csv import DictWriter
from io import StringIO
from os import environ

import sqlalchemy.exc
from flask import Flask, render_template, redirect, url_for, make_response, jsonify
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from pandas import read_csv
from requests import get
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from wtforms import StringField, SubmitField, FileField, TextAreaField, EmailField
from wtforms.validators import DataRequired, ValidationError

import data

app = Flask(__name__)
app.config['SECRET_KEY'] = environ.get('FLASK_KEY')  # Replace with your secret key
bootstrap = Bootstrap5(app)


# # Load the values from .env
# key = os.environ['KEY']
# endpoint = os.environ['ENDPOINT']
# location = os.environ['LOCATION']


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

class Feedback(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str]
    feedback: Mapped[str]


# TODO USER Authentication for saving rankings
# class User(db.Model):
#     __tablename__ = 'users'
#
#     user_id = db.Column(db.Integer, primary_key=True)
#     username = db.Column(db.String(100), unique=True, nullable=False)
#     password_hash = db.Column(db.String(255), nullable=False)  # Store hashed passwords securely

# TODO Potential Addition: Storing Ranking Sheet or Multiple Sheets
# class RankingSheet(db.Model):
#     __tablename__ = 'ranking_sheets'
#
#     sheet_id = db.Column(db.Integer, primary_key=True)
#     user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
#     file_name = db.Column(db.String(255), nullable=False)
#     file_path = db.Column(db.String(255), nullable=False)  # Store file path or reference if stored externally
#     upload_timestamp = db.Column(db.TIMESTAMP, nullable=False)
#
#     user = db.relationship('User', backref=db.backref('ranking_sheets', lazy=True))
#
#
# class NFLPlayer(db.Model):
#     __tablename__ = 'nfl_players'
#
#     player_id = db.Column(db.Integer, primary_key=True)
#     player_name = db.Column(db.String(100), nullable=False)
#     team = db.Column(db.String(100), nullable=False)
#     position = db.Column(db.String(50), nullable=False)
#     # Add more columns as needed
#
#
# class RankingSheetPlayerRanking(db.Model):
#     __tablename__ = 'ranking_sheet'
#
#     sheet_id = db.Column(db.Integer, db.ForeignKey('ranking_sheets.sheet_id'), primary_key=True)
#     player_id = db.Column(db.Integer, db.ForeignKey('nfl_players.player_id'), primary_key=True)
#     ranking = db.Column(db.Integer, nullable=False)
#
#     ranking_sheet = db.relationship('RankingSheet', backref=db.backref('player_rankings', lazy=True))
#     player = db.relationship('NFLPlayer', backref=db.backref('ranking_sheets', lazy=True))
db_up = True
try:
    with app.app_context():
        db.create_all()
except sqlalchemy.exc.OperationalError:
    print("not available")
    db_up = False


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


class ContactForm(FlaskForm):
    name = StringField('Name')
    email = EmailField('Email *', validators=[DataRequired()])
    suggestion = TextAreaField('Suggestion *', validators=[DataRequired()])
    submit = SubmitField('Submit')


def send_contact(name, email, suggestion):
    pass


def get_current_date():
    return {'current_year': datetime.today().strftime('%Y')}


app.context_processor(get_current_date)
current_state = None


@app.route("/")
def home():
    return render_template('index.html')


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

        return redirect(url_for("thanks"))
    return render_template('contact.html', form=contact_form)


@app.route("/thanks", methods=["GET"])
def thanks():
    return render_template('thanks.html')


@app.route("/about", methods=["GET"])
def about():
    return render_template('about.html')


@app.route("/manual", methods=["GET"])
def manual():
    return render_template('tbd.html')


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
def login():
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
            return redirect(url_for('success', draft_id=draft_id, draft_position=draft_position))

        except Exception as e:
            # Handle any errors that occur during the process
            print("An error occurred:", e)

    return render_template("login.html", form=form)


@app.route("/check_for_updates/<draft_id>")
def check_for_updates(draft_id):
    global current_state
    parameters = {
        # "draft_id": draft_id
    }

    draft_api_url = "https://api.sleeper.app/v1/draft/" + draft_id + "/picks"
    response = get(draft_api_url, params=parameters)
    response.raise_for_status()
    new_state = response.json()[-1]['pick_no']
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
        if draft_order is not None:
            for key, value in draft_order.items():
                if value == int(draft_position):
                    my_team = str(key)

        draft_status = draft_info['status'].title()
        if draft_status == "Complete":
            redirect_url = url_for('draft_complete', draft_id=draft_id, draft_position=draft_position)
            print("Redirect URL:", redirect_url)

            return redirect(url_for('draft_complete', draft_id=draft_id, draft_position=draft_position))
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
        return render_template("not_found.html")

    return render_template("success.html",
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
        return render_template("not_found.html")

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
                           )


if __name__ == '__main__':
    # app.run(debug=True)
    app.run()
