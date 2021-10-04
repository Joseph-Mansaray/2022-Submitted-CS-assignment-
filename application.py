import os
from datetime import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
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

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # get all stocks realated to userId
    stocks = db.execute(f"SELECT * FROM stocks WHERE userId={session['user_id']}")
    # calcualte the sum of stocks prices
    totalStocksPrice = db.execute(f"SELECT SUM(total) FROM stocks WHERE userID = {session['user_id']}")[0]['SUM(total)']
    if totalStocksPrice:
        totalStocksPrice = round(totalStocksPrice, 2)
    # get remaining cash for the user
    cash = db.execute(f"SELECT * FROM users WHERE id={session['user_id']}")[0]['cash']
    cash = round(cash, 2)
    # ensure that sum of stocks prices is valid number, if not assign it to 0
    if not totalStocksPrice:
        totalStocksPrice = 0
    # ensure that cash is valid number, if not assign it to 0
    if not cash:
        cash = 0
    # retun portfolio page
    return render_template("index.html", stocks=stocks, totalStocksPrice=totalStocksPrice, cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # if user reached page via post, by submitting form
    if request.method == "POST":
        # insure that symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Ensure password was submitted
        elif not request.form.get("shares"):
            return apology("must provide shares", 400)

        # get values realted to this symbol from API
        q = lookup(request.form.get("symbol"))

        # insure that symbol is valid
        if not q:
            return apology("Invalid symbol", 400)

        # get user cash
        cash = db.execute(f"SELECT * FROM users WHERE id={session['user_id']}")[0]["cash"]
        cash = round(cash, 2)

        # get price from api
        price = round(float(q["price"]), 2)

        # get shares from user input
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Invalid shares not int", 400)

        if shares < 0:
            return apology("Invalid shares", 400)

        # calcuate total price
        total = round((price * shares), 2)

        # insure that there is enough balance
        if total <= cash:
            # update balance
            db.execute(f"UPDATE users SET cash = cash - {total} WHERE id={session['user_id']}")

            # search for same symbol and userId
            try:
                search = db.execute("SELECT * FROM stocks WHERE userId= :userId AND symbol= :symbol ", userId=session['user_id'], symbol = q["symbol"])
            except:
                search = 0
            # if symbol does not exists for same userId
            if not search:
                insert = db.execute("INSERT INTO stocks (userId, symbol, name, shares, price, total) VALUES ( :userId, :symbol, :name, :shares, :price, :total)",
                userId=session['user_id'], symbol = q["symbol"], name=q["name"],
                shares = shares, price = price, total= total)

            # else update
            else:
                db.execute(f"UPDATE stocks SET shares = shares + {shares}, total = total + {total} WHERE userId= :userId AND symbol= :symbol " , userId=session['user_id'], symbol = q["symbol"])

            # add to histoy
            db.execute("INSERT INTO history (userId, symbol, shares, price, time) VALUES (:userId, :symbol, :shares, :price, :time)",
            userId=session['user_id'], symbol = q["symbol"], shares = shares, price = price, time = str(datetime.now()))

            return redirect("/")
        else:
            return apology("not enough balance", 400)
    # else show the buy form
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    history = db.execute(f"SELECT * FROM history WHERE userId={session['user_id']}")

    return render_template("history.html", history = history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

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
    """Get stock quote."""
    if request.method == "POST":
        q = lookup(request.form.get("symbol"))
        if q:
            return render_template("quote_success.html", name=q["name"], symbol=q["symbol"], price=q["price"])
        else:
            return apology("invalid symbol", 400)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    #user reached via post (by submitting form)
    if request.method == "POST":
        # insure that username was provided
        if not request.form.get("username"):
            return apology("Must provide username", 400)
        # insure that password was provided
        elif not request.form.get("password"):
            return apology("Must provide password", 400)
        # insure that verification was provided
        elif not request.form.get("confirmation"):
            return apology("Must confirm password", 400)
        # insure that password and verification are the same
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("password and confirmation must be the same", 400)
        # hash the password
        hashed_password = generate_password_hash(request.form.get("password"))


        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hashed)",
        username = request.form.get("username"), hashed = hashed_password)

        # check for database execute failure
        if not result:
            return apology("username already exists", 400)

        # log in
        session["user_id"] = result

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # insure that symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Ensure password was submitted
        elif not request.form.get("shares"):
            return apology("must provide shares", 400)

        # get values realted to this symbol from API
        q = lookup(request.form.get("symbol"))

        # insure that symbol is valid
        if not q:
            return apology("Invalid symbol", 400)

        # get user cash
        cash = db.execute(f"SELECT * FROM users WHERE id={session['user_id']}")[0]["cash"]
        cash = round(cash, 2)

        # get price from api
        price = float(q["price"])
        price = round(price, 2)

        # get shares from user input
        shares = int(request.form.get("shares"))

        # get numbers of shares the user have
        current_shares = db.execute(f"SELECT * FROM stocks WHERE userId={session['user_id']} AND symbol = :symbol", symbol = q['symbol'])[0]["shares"]

        # insure user have enough shares
        if shares > current_shares:
            return apology("Too much shares", 400)

        else:
            if shares > 0:
                # calcuate total price
                total = round((price * shares), 2)

                db.execute(f"UPDATE users SET cash = cash + {total} WHERE id={session['user_id']}")
                db.execute(f"UPDATE stocks SET shares = shares - {shares}, total = {total} WHERE userId={session['user_id']} AND symbol = :symbol", symbol = q['symbol'])
                c = db.execute(f"SELECT * FROM stocks WHERE userId={session['user_id']} AND symbol = :symbol", symbol = q['symbol'])[0]["shares"]
                if not c:
                    db.execute(f"DELETE FROM stocks WHERE userId={session['user_id']} AND symbol = :symbol", symbol = q['symbol'])

                # add to history
                db.execute("INSERT INTO history (userId, symbol, shares, price, time) VALUES (:userId, :symbol, :shares, :price, :time)",
                userId=session['user_id'], symbol = q["symbol"], shares = -(shares), price = price, time = str(datetime.now()))

            return redirect("/")
    else:
        return render_template("sell.html", raws=db.execute(f"SELECT * FROM stocks WHERE userId={session['user_id']}"))


def errorhandler(e):
    """Handle error"""
    return apology(e, 400)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
    