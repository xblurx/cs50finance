import os
import re

from cs50 import SQL
from datetime import datetime
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
from sqlhandler import SqlHandler

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")
db_worker = SqlHandler("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    return db_worker.get_current_stocks(session["username"], session["user_id"])


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if request.form["submit_button"] == "buy":

            ticker = request.form.get("ticker")
            if lookup(ticker) is None:
                return apology('Incorrect share ticker', 403)

            cash_left = db.execute("SELECT cash FROM users WHERE username = ?", session["username"])

            try:
                amount_to_pay = float(request.form.get("amount")) * float(lookup(ticker)["price"])
            except ValueError:
                return apology("Amount must be a number", 405)

            current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            shares = request.form.get("amount")
            if int(shares) < 0 or re.match(r'\d+', shares) is None:
                return apology("Positive numbers only", 406)

            if float(cash_left[0]['cash']) < amount_to_pay:
                return apology("Money's gone, huh", 401)

            is_owned = db.execute("SELECT ticker FROM holdings WHERE user_id = ? AND ticker = ?", session["user_id"],
                                  ticker)

            try:
                if len(is_owned) == 0:
                    return db_worker.first_purchase(username=session["username"],
                                                    user_id=session["user_id"],
                                                    ticker=ticker,
                                                    amount=shares,
                                                    date=current_date
                                                    )
                else:
                    return db_worker.other_purchases(username=session["username"],
                                                     user_id=session["user_id"],
                                                     ticker=ticker,
                                                     amount=shares,
                                                     date=current_date
                                                     )
            except:
                return apology("holdings update error", 102)

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return db_worker.show_history(user_id=session["user_id"])


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        quote = request.form.get('quote')
        quote_data = lookup(quote)
        if quote_data is None:
            return apology("Incorrect share ticker", 403)
        else:
            return render_template(
                "quoted.html",
                name=quote_data['name'],
                symbol=quote_data['symbol'],
                price=usd(quote_data['price'])
            )
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        users = [value.get('username') for value in db.execute("SELECT username FROM users")]
        user = request.form.get("username")
        pwd = request.form.get("password")
        pwd_match = request.form.get("password_match")

        if user in users:
            return apology("username exists", 403)
        elif pwd != pwd_match:
            return apology("passwords don't match", 403)
        else:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)",
                       user, generate_password_hash(pwd))
            return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        user_stocks = [value.get('ticker') for value in db.execute("""SELECT DISTINCT ticker
                                                                    FROM holdings
                                                                    JOIN users ON holdings.user_id = users.id
                                                                    WHERE username = ?""",
                                                                   session["username"])]
        return render_template("sell.html", data=user_stocks)

    else:
        if db_worker.get_current_stocks(session["username"], session["user_id"]) == "Empty":
            return render_template("index.html")

        else:
            user_db_id = db.execute("SELECT id FROM users WHERE username = ?", session["username"])[0]['id']
            ticker = request.form.get("ticker")

            try:
                amount_to_pay = float(request.form.get("amount")) * float(lookup(ticker)["price"])
            except ValueError:
                return apology("Amount value should be an integer")

            current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            shares = request.form.get("amount")
            if int(shares) < 0 or re.match(r'\d+', shares) is None:
                return apology("Positive numbers only", 406)

            if int(shares) > int(db.execute("SELECT shares FROM holdings WHERE ticker = ? AND user_id = ?",
                                            ticker,
                                            user_db_id)[0]["shares"]):
                return apology("Not enough stocks in your portfolio", 309)

            stock = lookup(request.form.get("ticker"))["price"]
            amount_to_gain = float(shares) * stock

            db_worker.sell_stocks(username=session["username"],
                                  user_db_id=user_db_id,
                                  ticker=ticker,
                                  amount=shares,
                                  to_pay=amount_to_pay,
                                  to_gain=amount_to_gain,
                                  date=current_date
                                  )
            return db_worker.get_current_stocks(session["username"], session["user_id"])


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
