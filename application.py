import os
import string
import requests # For the Goodreads API
import json # For the Goodreads API

from datetime import datetime
from flask import Flask, session, url_for, render_template, redirect, request, jsonify #ADS understood
from flask_session import Session # ADS understood
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

# ADS: Taken from CS50 Finance distribution code
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

# ADS: Taken from CS50 Finance distribution code for @login_required functionality
from functools import wraps

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False # ADS understood
app.config["SESSION_TYPE"] = "filesystem" # ADS understood
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

# ADS: Copied from CS50 Finance Distribution Code
def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function



@app.route("/")
@login_required
def index():
    #return redirect(url_for('login'))
    users = db.execute("SELECT * FROM users").fetchall()
    return render_template("index.html", users=users, user=session["user_id"])



@app.route("/login", methods=["GET", "POST"])
def login():
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("error.html", message="Username not provided.")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("error.html", message="Password not provided.")

        # Query database for username
        user = db.execute("SELECT * FROM users WHERE username = :username", {"username":request.form.get("username")}).fetchone()

        # Ensure username exists and password is correct
        if user is None:
            return render_template("error.html", message="Username does not exist.")

        # Ensure username exists and password is correct
        if not check_password_hash(user.hash, request.form.get("password")):
            return render_template("error.html", message="Invalid username and/or password")
        
        # Remember which user has logged in
        session["user_id"] = user.id

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        if not request.form.get("username"):
            return render_template("error.html", message="Username not provided.")
        elif not request.form.get("email"):
            return render_template("error.html", message="Email not provided")
        elif not request.form.get("password1"):
            return render_template("error.html", message="Password1 not provided.")
        elif not request.form.get("password2"):
            return render_template("error.html", message="Password2 not provided.")
        elif request.form.get("password1") != request.form.get("password2"):
            return render_template("error.html", message="Passwords do not match.")

        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password1")
        hash = generate_password_hash(password)

        db.execute("INSERT INTO users (username, email, hash) VALUES (:username, :email, :hash)", {"username":username, "email":email, "hash":hash})
        db.commit()

        return redirect("/")

    else:
        return render_template("register.html")



@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    if not request.form.get("search"):
        return render_template("error.html", message="Empty search field.")
    else:
        search = request.form.get("search")

    # If search input looks like ISBN then search DB for ISBN
    if search.strip().isdigit():
        books = db.execute("SELECT * FROM books WHERE isbn LIKE :isbn", {"isbn":search.strip()+'%'}).fetchall()
    # Else search for author and title
    else:
        books = db.execute("SELECT * FROM books WHERE lower(title) LIKE :title OR lower(author) LIKE :author", {"title":'%'+search.strip().lower()+'%', "author":'%'+search.strip().lower()+'%'}).fetchall()

    if not books:
        return render_template("error.html", message="No results found.")
    else:
        return render_template("search_results.html", books=books)



@app.route("/search/<string:isbn>")
@login_required
def book(isbn):
    # Goodreads API key
    key = 'bkr5UsWPk5iPuXcOzUjDw'

    # Query DB for title, author, year details
    db_data = db.execute('SELECT * FROM books WHERE isbn = :isbn', {"isbn":isbn}).fetchone()

    # Query DB for review data
    db_review = db.execute('SELECT reviews.*, users.username FROM reviews JOIN users ON users.id = user_id WHERE book_isbn = :isbn', {"isbn":isbn}).fetchall()

    # Request Goodreads API for review data
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": key, "isbns": isbn})
    obj = json.loads(res.text)
    goodreads_data = obj["books"][0]

    # Create dict of values needed for HTML book page
    book =  {
            "title": db_data.title,
            "author": db_data.author,
            "year": db_data.year,
            "isbn": db_data.isbn,
            "review_count": goodreads_data["ratings_count"],
            "average_score": goodreads_data["average_rating"],
    }
     
    return render_template("book.html", book=book, reviews=db_review)
    


@app.route("/review", methods=["POST"])
@login_required
def process_review():
    isbn = request.form.get("isbn")
    rating = request.form.get("rating")
    review = request.form.get("review")

    # Check if user has previously left a review for this book
    db_review = db.execute('SELECT * FROM reviews WHERE (book_isbn = :isbn AND user_id = :user_id)', {"isbn":isbn, "user_id":session["user_id"]}).fetchall()
    if len(db_review) > 0:
        return render_template("error.html", message="You have already reviewed this book.")

    db.execute('INSERT INTO reviews (user_id, book_isbn, rating, review, datetime) VALUES (:user_id, :book_isbn, :rating, :review, current_timestamp)', {"user_id": session["user_id"], "book_isbn": isbn, "rating": rating, "review": review})
    db.commit()

    return redirect(url_for('book', isbn=isbn))



@app.route("/api/<string:isbn>")
@login_required
def api(isbn):
    # Make sure flight exists.

    # Goodreads API key
    key = 'bkr5UsWPk5iPuXcOzUjDw'

    # Query DB for title, author, year details
    db_data = db.execute('SELECT * FROM books WHERE isbn = :isbn', {"isbn":isbn}).fetchone()
    if not db_data:
        return render_template("error.html", message="ISBN does not exist")

    # Query DB for review data
    db_review = db.execute('SELECT reviews.*, users.username FROM reviews JOIN users ON users.id = user_id WHERE book_isbn = :isbn', {"isbn":isbn}).fetchall()

    # Request Goodreads API for review data
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": key, "isbns": isbn})
    obj = json.loads(res.text)
    goodreads_data = obj["books"][0]

    # Create dict of values needed for HTML book page
    return jsonify({
            "title": db_data.title,
            "author": db_data.author,
            "year": db_data.year,
            "isbn": db_data.isbn,
            "review_count": goodreads_data["ratings_count"],
            "average_score": goodreads_data["average_rating"],
    })


@app.route("/logout") # WORKS!!
def logout():
    # Forget any user_id
    session.clear()
    return render_template("login.html")