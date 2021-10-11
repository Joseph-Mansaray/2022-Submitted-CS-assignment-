import os

import re
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd


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
# allows use of usd, lookup and float functions from python and helpers.py
app.jinja_env.globals.update(usd=usd, lookup=lookup, float=float)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():

    # using rounded floats for currency, which is wrong. Should always use int and multiply by 100.
    rows = db.execute("SELECT symbol, name, round(SUM(shares), 2) FROM purchases WHERE id=:idNum GROUP BY symbol", idNum=session["user_id"])

    fundslist = db.execute("SELECT cash FROM users WHERE id=:idNum", idNum=session["user_id"])
    for row in fundslist:
        funds = row["cash"]

    # gets current price by looking up current stock price and multiplying by amount of shares bought
    total = 0
    for row in rows:
        total += (float(lookup(row["symbol"])["price"])*row["round(SUM(shares), 2)"])

    combinedTotal = funds + total

    return render_template("portfolio.html", rows=rows, cash=usd(funds), combinedTotal=usd(combinedTotal))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    if request.method == "POST":

        symbol = request.form.get("symbol").upper()

        if lookup(symbol) == None:
            return apology("error: please check stock symbol and number of shares")

        price = float(lookup(symbol)["price"])
        company = lookup(symbol)["name"]
        shares = float(request.form.get("shares"))
        purchaseTotal = float(price)*shares
        iden = session["user_id"]
        total = price*shares

        if shares <= 0:
            return apology("invalid number of shares")

        # fetch cash from database
        funds = db.execute("SELECT cash FROM users WHERE id=:idNum", idNum=iden)
        for row in funds:
            funds1 = row
        funds2 = funds1["cash"]

        # check that user has enough funds to buy stock
        if purchaseTotal > funds2:
            return apology("not enough cash available")

        else:
            # add the purchased stock to their account ('purchases' sql database table)
            buy = db.execute("INSERT INTO purchases(symbol, name, price, shares, total, id, timestamp) VALUES (:symbol, :name, :price, :shares, :total, :iden, CURRENT_TIMESTAMP)", symbol=symbol, name=company, price=price, shares=shares, total=total, iden=iden)
            # subtract from cash
            db.execute("UPDATE users SET cash = :newvalue WHERE id = :iden", newvalue=(funds2-purchaseTotal), iden=iden)
            # display purchase info
            flash('Bought!')
            return redirect("/")

    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():

    # using rounded floats for currency, which is wrong. Should always use int and multiply by 100.
    rows = db.execute("SELECT * FROM purchases WHERE id=:idNum", idNum=session["user_id"])

    return render_template("history.html", rows=rows)

    # TODO
    # create a 'sort by' function
    # allow for multiple pages

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

    if request.method == "POST":

        # use lookup(symbol) to fetch quote and return a python dict
        symbol = request.form.get("quote")
        quoteDict = lookup(symbol)

        if quoteDict == None:
            return apology("invalid stock symbol")

        else:
            # display the python dictionary
            return render_template("quoted.html", companyName=quoteDict["name"], price=usd(float(quoteDict["price"])), symbol=quoteDict["symbol"])

    else:
        return render_template("quote.html")

    return apology("TODO4")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # checks: all fields have been filled. username is unique. passwords match.
        username = request.form.get("username")
        password = request.form.get("psw")
        confpassword = request.form.get("confpassword")
        usernames = db.execute("SELECT * FROM users WHERE username=:eg", eg=username.lower())

        if username == '':
            return apology("PLEASE INPUT A USERNAME", 403)
        if password == '':
            return apology("PLEASE INPUT A PASSWORD", 403)
        if confpassword == '':
            return apology("PLEASE CONFIRM YOUR PASSWORD", 403)

        # if username not unique, display correct apology message:
        if len(usernames) != 0:
            return apology("SORRY, USERNAME ALREADY TAKEN")

        # TODO
        # password length must be 8 or more
        # must include letters, numbers, symbols

        if confpassword != password:
            return apology("PASSWORDS DO NOT MATCH")

        # hash user's password
        hashpw = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)

        # insert new user into database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hashpw)", username=username, hashpw=hashpw)

        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":

        symbol = request.form.get("symbol")

        if lookup(symbol) == None:
            return apology("error: please check stock symbol and number of shares")

        price = float(lookup(symbol)["price"])
        company = lookup(symbol)["name"]
        shares = float(request.form.get("shares"))
        sellTotal = float(price)*shares
        iden = session["user_id"]
        total = price*shares

        if shares <= 0:
            return apology("invalid number of shares")

        funds = db.execute("SELECT cash FROM users WHERE id=:idNum", idNum=iden)
        for row in funds:
            funds1 = row
        funds2 = funds1["cash"]

        sharesHeld = db.execute("SELECT symbol, round(SUM(shares), 2) FROM purchases WHERE id=:iden AND symbol=:symbol GROUP BY symbol", iden=iden, symbol=symbol)

        for row in sharesHeld:
            if shares > row["round(SUM(shares), 2)"]:
                return apology("you don't own that many shares")

        else:
            sell = db.execute("INSERT INTO purchases(symbol, name, price, shares, total, id, timestamp) VALUES (:symbol, :name, :price, :shares, :total, :iden, CURRENT_TIMESTAMP)", symbol=symbol, name=company, price=price, shares=shares*-1, total=total, iden=iden)
            db.execute("UPDATE users SET cash = :newvalue WHERE id = :iden", newvalue=(funds2+sellTotal), iden=iden)
            # display purchase info
            flash('Sold!')

            return redirect("/")

    else:
        rows = db.execute("SELECT symbol, name, round(SUM(shares), 2) FROM purchases WHERE id=:iden GROUP BY symbol", iden=session["user_id"])

        return render_template("sell.html", rows=rows)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


# TODO
# optimise code as much as possible
# implement a 'personal touch'