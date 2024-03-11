import uuid
from _datetime import datetime
from requests import get
import data
from flask import Flask, render_template, redirect, url_for, send_file, make_response, session, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FileField, TextAreaField, EmailField
from wtforms.validators import DataRequired, ValidationError
from flask_bootstrap import Bootstrap5
from io import StringIO
import json
from pandas import read_csv
from csv import DictWriter
from collections import OrderedDict
from os import environ

app = Flask(__name__)
app.config['SECRET_KEY'] = environ.get('FLASK_KEY')  # Replace with your secret key
bootstrap = Bootstrap5(app)

# # Load the values from .env
# key = os.environ['KEY']
# endpoint = os.environ['ENDPOINT']
# location = os.environ['LOCATION']


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

        return redirect(url_for("thanks"))
    return render_template('contact.html', form=contact_form)


@app.route("/thanks", methods=["GET"])
def thanks():
    return render_template('thanks.html')


@app.route("/about", methods=["GET"])
def about():
    return render_template('tbd.html')


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
        # TODO Allow for pasting full hyperlink from sleeper and use split to grab just the last portion
        if "nfl" in draft_id:
            split_string = draft_id.split("/")
            draft_id = split_string[-1]
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

    # Retrieve the CSV content from the session
    csv_contents = data.get_csv()

    try:
        draft_info = data.get_draft(draft_id)
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
                values['tier'] = "99"

        rbs_drafted = [player for player in picks if player['metadata']['position'] == "RB"]
        drafted_rb_ids = [player_info.get('player_id') for player_info in rbs_drafted]
        top_rbs = {k: v for k, v in top_players.items() if v['position'] == "RB" and k not in drafted_rb_ids}
        sorted_rbs = sorted(top_rbs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_rbs = OrderedDict(sorted_rbs)

        wrs_drafted = [player for player in picks if player['metadata']['position'] == "WR"]
        drafted_wr_ids = [player_info.get('player_id') for player_info in wrs_drafted]
        top_wrs = {k: v for k, v in top_players.items() if v['position'] == "WR" and k not in drafted_wr_ids}
        sorted_wrs = sorted(top_wrs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_wrs = OrderedDict(sorted_wrs)

        qbs_drafted = [player for player in picks if player['metadata']['position'] == "QB"]
        drafted_qb_ids = [player_info.get('player_id') for player_info in qbs_drafted]
        top_qbs = {k: v for k, v in top_players.items() if v['position'] == "QB" and k not in drafted_qb_ids}
        sorted_qbs = sorted(top_qbs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_qbs = OrderedDict(sorted_qbs)

        tes_drafted = [player for player in picks if player['metadata']['position'] == "TE"]
        drafted_te_ids = [player_info.get('player_id') for player_info in tes_drafted]
        top_tes = {k: v for k, v in top_players.items() if v['position'] == "TE" and k not in drafted_te_ids}
        sorted_tes = sorted(top_tes.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_tes = OrderedDict(sorted_tes)

        ks_drafted = [player for player in picks if player['metadata']['position'] == "K"]
        drafted_k_ids = [player_info.get('player_id') for player_info in ks_drafted]
        top_ks = {k: v for k, v in top_players.items() if v['position'] == "K" and k not in drafted_k_ids}
        sorted_ks = sorted(top_ks.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_ks = OrderedDict(sorted_ks)

        defs_drafted = [player for player in picks if player['metadata']['position'] == "DEF"]
        drafted_def_ids = [player_info.get('player_id') for player_info in defs_drafted]
        top_defs = {k: v for k, v in top_players.items() if v['position'] == "DEF" and k not in drafted_def_ids}
        sorted_defs = sorted(top_defs.items(), key=lambda x: int(x[1].get('tier', float('inf'))))
        top_defs = OrderedDict(sorted_defs)

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
                           top_defs=top_defs
                           )


if __name__ == '__main__':
    app.run()
