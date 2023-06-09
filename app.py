import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

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


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    company = db.execute(
        "SELECT symbol, price, SUM(qty) AS qty, date FROM purchases WHERE symbol IN (SELECT DISTINCT(symbol) FROM purchases WHERE user_id = (?)) GROUP BY symbol", session["user_id"])
    currentPrice = db.execute(
        "SELECT symbol FROM purchases WHERE symbol IN (SELECT DISTINCT(symbol) FROM purchases WHERE user_id = (?)) GROUP BY symbol", session["user_id"])
    count = 0
    for x in currentPrice:
        count += 1
    cPrice = {}
    i = 0
    while i < count:
        currentPrice = db.execute(
            "SELECT symbol FROM purchases WHERE symbol IN (SELECT DISTINCT(symbol) FROM purchases WHERE user_id = (?)) GROUP BY symbol", session["user_id"])
        cPrice[i] = currentPrice[i]["symbol"]
        cPrice[i] = lookup(cPrice[i])
        cPrice[i] = cPrice[i]["price"]
        i += 1
    shares = db.execute("SELECT * FROM users INNER JOIN purchases ON id=user_id WHERE user_id = (?)", session["user_id"])
    funds = db.execute("SELECT * FROM users WHERE id = (?)", session["user_id"])

    return render_template("index.html", shares=shares, company=company, cPrice=cPrice, count=count, funds=funds)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))
        if quote == None:
            return apology("Inavlid Symbol", 400)
        symbol = request.form.get("symbol")
        symbol = symbol.upper()
        id = session["user_id"]
        try:
            quantity = float(request.form.get("shares"))
        except ValueError:
            quantity = -1
        if quantity < 1 or int(quantity) != quantity:
            return apology("Inavlid Amount", 400)
        price = quote["price"]
        cost = quantity * price
        rows = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        funds = rows[0]["cash"]
        if funds < cost:
            return apology("Not enough funds", 400)
        balance = funds - cost
        purchased = 'PURCHASED'
        db.execute("INSERT INTO purchases (symbol, price, qty, user_id, type, date) VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))",
                   symbol, price, quantity, id, purchased)
        db.execute("UPDATE users SET cash = (?) WHERE id = (?)", balance, id)
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    company = db.execute("SELECT * FROM purchases")
    return render_template("history.html", company=company)


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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        quote = lookup(symbol)
        if quote == None:
            return apology("Inavlid Symbol", 400)
        return render_template("quoted.html", quote=quote)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        # Check username has been filled out
        if not request.form.get("username"):
            return apology("Username required", 400)

        # Check database for username
        check = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # If username already exists
        if len(check) != 0:
            return apology("Username already exists", 400)

        # Check password has been entered
        if not request.form.get("password"):
            return apology("Please enter a password", 400)

        # Check confirmation has been entered
        if not request.form.get("confirmation"):
            return apology("Please confirm password", 400)

        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Check password and confirmation match
        if password != confirmation:
            return apology("Passwords do not match", 400)

        username = request.form.get("username")
        passhash = generate_password_hash((request.form.get("password")), method='pbkdf2:sha256', salt_length=8)

        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, passhash)

        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))
        if quote == None:
            return apology("Inavlid Symbol", 400)
        symbol = request.form.get("symbol")
        symbol = symbol.upper()
        id = session["user_id"]
        quantity = float(request.form.get("shares"))
        if quantity < 1:
            return apology("Inavlid Amount", 400)
        price = quote["price"]
        cost = quantity * price
        rows = db.execute("SELECT SUM(qty) AS qty FROM purchases WHERE symbol = (?) AND user_id = (?)", symbol, session["user_id"])
        qty = rows[0]["qty"]
        if quantity > qty:
            return apology("Not enough shares", 400)
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        funds = cash[0]["cash"]
        balance = funds + cost
        quantity = quantity - (quantity * 2)
        db.execute("INSERT INTO purchases (symbol, price, qty, user_id, type, date) VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))",
                   symbol, price, quantity, id, 'SOLD')
        db.execute("UPDATE users SET cash = (?) WHERE id = (?)", balance, id)
        return redirect("/")
    else:
        company = db.execute("SELECT DISTINCT(symbol) FROM purchases WHERE user_id = (?)", session["user_id"])
        return render_template("sell.html", company=company)


@app.route("/funds", methods=["GET", "POST"])
@login_required
def funds():
    """Add Funds to account"""
    if request.method == "POST":
        funds = db.execute("SELECT cash FROM users WHERE id = (?)", session["user_id"])
        cash = funds[0]["cash"]
        amount = int(request.form.get("amount"))
        newCash = cash + amount
        db.execute("UPDATE users SET cash = (?) WHERE id = (?)", newCash, session["user_id"])
        return redirect("/")
    else:
        return render_template("funds.html")
