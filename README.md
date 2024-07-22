Site is now live at: https://sleepertiers.com/

This was a fun project that replaces some APIs I was doing in Excel with VBA to make my fantasy drafts in Sleeper.com more efficient and easy. 

It was a way for me to practice the following:
- Flask for Web Development in Python along with HTML
- Boostrap and additional CSS for custom styling

## Updates for July 2024:
- Abiilty to find drafts by Sleeper username
- For live drafts on Sleeper projected points now matches scoring method of the draft (ppr, half-ppr, std, etc.)
- For live drafts on Sleeper, ADP is now included with color-coding based on when the player will likely fall: red for within next round, yellow for within 2 rounds.
- Manual draft tracker added.
- Some other CSS updates for display/readability.

# Behind-the-scenes:
- Admin login, which could be repurposed for user logins if people wanted to be able to save their own tier sheets to the site.
- Admin: feedback management and viewing within the site.

![example](https://github.com/brownjf2027/SleeperTierSite/blob/master/static/images/example.png)

## License
This project is licensed under the BSD-3-Clause license. See the [LICENSE](LICENSE) file for details.

Libraries utilized and associated licenses:

MIT License:
- APScheduler
- beautifulsoup4
- Bootstrap
- Bootstrap-flask
- Flask-Login
- SQLAlchemy
- gunicorn

BSD-3-Clause license:
- WTForms
- flask-wtf
- flask_sqlalchemy
- Werkzeug
- Pandas

Apache-2.0 license:
- requests

LGPL-2.1 license:
- pymssql
