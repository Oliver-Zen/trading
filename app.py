import datetime
import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, _abs, str_to_dict

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd
app.jinja_env.filters["_abs"] = _abs

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""

    if request.method == "GET":

        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]['cash']

        # Retrieve stocks owned
        stocks = db.execute("SELECT symbol, SUM(shares) AS shares FROM purchase_and_sale WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0", session['user_id']) # list of dict

        # Add current stock's information
        stock_total_value = 0
        for stock in stocks:
            info = lookup(stock['symbol'])
            stock['name'] = info['name']
            stock['price'] = info['price'] # float
            stock['value'] = stock['shares'] * stock['price']
            stock_total_value += stock['value']

        # Compute grand value
        grand_value = cash + stock_total_value

        user_name = db.execute("SELECT username FROM users WHERE id = ?", session['user_id'])[0]['username']

        return render_template("index.html", user_name=user_name, cash=cash, stocks=stocks, stock_total_value=stock_total_value, grand_value=grand_value)

    else:

        # Ensure shares input exists
        if not request.form.get("shares"):
            return apology("empty shares input", 400)

        # Ensure shares input is a positive integer
        elif not request.form.get("shares").isnumeric():
            return apology("shares input must be positive integer", 400)

        # Shares to buy/sell
        shares = int(request.form.get("shares"))

        # If user buys
        if request.form.get("symbol_buy") and not request.form.get("symbol_sell"):
            symbol = request.form.get("symbol_buy")
            price = lookup(symbol)['price']

            # Ensure user can afford
            cost_or_return = shares * price
            cash = db.execute("SELECT cash FROM users WHERE id = ?", session['user_id'])[0]['cash'] # db.execute returns a list of dict
            if cash < cost_or_return:
                return apology("can not afford", 403)

            # Confirm payment
            info = lookup(symbol)
            rest = cash - cost_or_return
            return render_template("confirm_purchase.html", info=info, shares=shares, cost_or_return=cost_or_return, cash=cash, rest=rest)

        # If user sells
        elif request.form.get("symbol_sell") and not request.form.get("symbol_buy"):
            symbol = request.form.get("symbol_sell")

            # Ensure own enough shares
            shares_owned = db.execute("SELECT symbol, SUM(shares) AS shares FROM purchase_and_sale WHERE user_id = ? AND symbol = ? GROUP BY symbol", session['user_id'], symbol)[0]["shares"]
            if shares_owned < shares:
                return apology("do not own enough shares", 403)

            # Confirm sale
            info = lookup(symbol)
            price = lookup(symbol)['price'] # float
            shares = int(shares)
            cost_or_return = shares * price
            cash = db.execute("SELECT cash FROM users WHERE id = ?", session['user_id'])[0]['cash'] # db.execute returns a list of dict
            rest = cash + cost_or_return
            return render_template("confirm_sale.html", info=info, shares=shares, cost_or_return=cost_or_return, cash=cash, rest=rest)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        # Ensure symbol input exists
        if not request.form.get("symbol"):
            return apology("empty symbol input", 400)

        # Ensure symbol is valid
        elif lookup(request.form.get("symbol")) is None:
            return apology("type valid symbol", 400)

        # Ensure shares input exists
        elif not request.form.get("shares"):
            return apology("empty shares input", 400)

        # Ensure shares input is a positive integer
        elif not request.form.get("shares").isnumeric():
            return apology("shares input must be positive integer", 400)

        # Ensure user can afford
        shares = int(request.form.get("shares"))
        price = lookup(request.form.get("symbol"))['price'] # float
        cost_or_return = shares * price
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session['user_id'])[0]['cash'] # db.execute returns a list of dict
        if cash < cost_or_return:
            return apology("can not afford", 403)

        # Confirm payment
        info = lookup(request.form.get("symbol"))
        rest = cash - cost_or_return
        return render_template("confirm_purchase.html", info=info, shares=shares, cost_or_return=cost_or_return, cash=cash, rest=rest)

    else:
        return render_template("buy.html")


@app.route("/confirm_purchase", methods=["GET", "POST"])
@login_required
def confirm_purchase():

    if request.method == "POST":

        info = request.form.get("info") # info here is somehow string, rather than dict
        shares = int(request.form.get("shares"))
        cost_or_return = float(request.form.get("cost_or_return"))
        cash = float(request.form.get("cash"))
        rest = float(request.form.get("rest"))

        info = str_to_dict(info)

        # # Keep track of purchase
        db.execute("INSERT INTO purchase_and_sale (user_id, symbol, price, shares, cost_or_return, datetime) VALUES (?, ?, ?, ?, ?, ?)",
                   session["user_id"], info['symbol'], float(info['price']), shares, cost_or_return,  datetime.datetime.now())

        # Update currest cash
        db.execute("UPDATE users SET cash = ? WHERE id = ?", rest, session["user_id"])

        return redirect("/")

    else:
        return redirect("/") #

@app.route("/confirm_sale", methods=["GET", "POST"])
@login_required
def confirm_sale():

    if request.method == "POST":

        info = request.form.get("info") # info here is somehow string, rather than dict
        shares = int(request.form.get("shares"))
        cost_or_return = float(request.form.get("cost_or_return"))
        cash = float(request.form.get("cash"))
        rest = float(request.form.get("rest"))

        info = str_to_dict(info)

        # Keep track of sale
        db.execute("INSERT INTO purchase_and_sale (user_id, symbol, price, shares, cost_or_return, datetime) VALUES (?, ?, ?, ?, ?, ?)",
                   session["user_id"], info['symbol'], float(info['price']), -1 * shares, cost_or_return,  datetime.datetime.now())

        # Update currest cash
        db.execute("UPDATE users SET cash = ? WHERE id = ?", rest, session["user_id"])

        return redirect("/")

    else:
        return redirect("/")


@app.route("/history", methods=["GET", "POST"])
@login_required
def history():
    """Show history of transactions"""

    user_name = db.execute("SELECT username FROM users WHERE id = ?", session['user_id'])[0]['username']
    transactions = db.execute("SELECT * FROM purchase_and_sale WHERE user_id = ? ORDER BY datetime", session['user_id'])

    if request.method == "POST":
        return render_template("history.html", user_name=user_name)#, transactions=transactions)

    else:
        return render_template("history.html", user_name=user_name, transactions=transactions)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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


@app.route("/account", methods=["GET", "POST"])
def change_pwd():

    if request.method == "POST":

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure password was confirmed
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 403)

        # Ensure confirmation matched password
        elif request.form.get("confirmation") != request.form.get("password"):
            return apology("passwords do not match", 403)

        # Check password

        # Update password
        db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(request.form.get("password")), session['user_id'])

        return redirect("/")

    else:

        user_name = db.execute("SELECT username FROM users WHERE id = ?", session['user_id'])[0]['username']

        return render_template("account.html", user_name=user_name)


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        # Lookup stock's symbol
        info = lookup(request.form.get("symbol"))

        # Ensure valid symbol
        if info is None:
            return apology("not a valid symbol")

        return render_template("quoted.html", info=info)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password was confirmed
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)

        # Ensure confirmation matched password
        elif request.form.get("confirmation") != request.form.get("password"):
            return apology("passwords do not match", 400)

        # Ensure user had not resigtered before
        name_checker = db.execute("SELECT username FROM users WHERE username = ?", request.form.get("username"))
        if len(name_checker) != 0:
            return apology("already registered", 400)

        # Query the database to INSERT the new user
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")))

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

     # Retrieve stocks owned
    stocks = db.execute("SELECT symbol, SUM(shares) AS shares FROM purchase_and_sale WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0", session['user_id']) # list of dict

    # Create a list to contain all stock symbols
    # Create a dict to check shares (symbol:shares pairs)
    symbols = []
    to_sell = {}
    for stock in stocks:
        symbols.append(stock['symbol'])
        to_sell[stock['symbol']] = stock['shares']

    if request.method == "POST":

        # Ensure own stock(s)
        if len(symbols) == 0:
            return apology("Do not own any stocks", 400)

        # Ensure shares input exists
        elif not request.form.get("shares"):
            return apology("empty shares input", 400)

        # Ensure shares input is a positive integer
        elif not request.form.get("shares").isnumeric():
            return apology("shares input must be positive integer", 400)

        shares = int(request.form.get("shares"))

        # Ensure own enough shares
        if to_sell[request.form.get("symbol")] < shares:
            return apology("do not own enough shares", 400)

        # Confirm sale
        info = lookup(request.form.get("symbol"))
        price = lookup(request.form.get("symbol"))['price'] # float
        cost_or_return = shares * price
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session['user_id'])[0]['cash'] # db.execute returns a list of dict
        rest = cash + cost_or_return
        return render_template("confirm_sale.html", info=info, shares=shares, cost_or_return=cost_or_return, cash=cash, rest=rest)

    else:

        return render_template("sell.html", symbols=symbols)
