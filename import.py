import os
import csv

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

# Read CSV file
with open('books.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        db.execute("INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)", 
                    {"isbn": row['isbn'], "title": row['title'], "author": row['author'], "year":row['year']})
    db.commit()