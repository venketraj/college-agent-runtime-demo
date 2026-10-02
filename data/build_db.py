"""Creates data/college.db — a fictional student database for the agent demo (deterministic)."""
import random
import sqlite3
from pathlib import Path

DB = Path(__file__).with_name("college.db")

MENTORS = [
    (1, "Dr. K. Meenakshi", "meenakshi.k@demo-college.edu"),
    (2, "Prof. R. Arjun", "arjun.r@demo-college.edu"),
    (3, "Dr. S. Lakshmi", "lakshmi.s@demo-college.edu"),
    (4, "Prof. V. Karthik", "karthik.v@demo-college.edu"),
]
FIRST = ["Aarav", "Diya", "Harish", "Kavya", "Pranav", "Sneha", "Vishal", "Ananya", "Rahul", "Divya",
         "Surya", "Nithya", "Gokul", "Priya", "Arun", "Swetha", "Dinesh", "Keerthana", "Vignesh", "Janani",
         "Sanjay", "Pooja", "Ajay", "Harini", "Manoj", "Deepika", "Naveen", "Sowmya", "Ashwin", "Lavanya",
         "Bharath", "Meera", "Karthik", "Abinaya", "Rohit", "Yamini"]
LAST = ["R", "S", "K", "M", "P", "V", "N", "A", "G", "T"]
SUBJECTS = ["Data Structures", "Operating Systems", "DBMS", "Computer Networks", "Machine Learning"]


def build():
    rng = random.Random(2026)
    DB.unlink(missing_ok=True)
    con = sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE mentors(id INTEGER PRIMARY KEY, name TEXT, email TEXT);
    CREATE TABLE students(roll_no TEXT PRIMARY KEY, name TEXT, year INTEGER, section TEXT,
                          mentor_id INTEGER REFERENCES mentors(id), email TEXT, cgpa REAL, arrears INTEGER);
    CREATE TABLE attendance(roll_no TEXT REFERENCES students(roll_no), subject TEXT,
                            attended INTEGER, total INTEGER);
    """)
    con.executemany("INSERT INTO mentors VALUES (?,?,?)", MENTORS)
    for i, first in enumerate(FIRST):
        roll = f"23CS{i + 1:03d}"
        name = f"{first} {rng.choice(LAST)}"
        mentor = MENTORS[i % 4][0]
        cgpa = round(rng.uniform(6.2, 9.6), 2)
        arrears = rng.choice([0, 0, 0, 0, 1, 2]) if cgpa < 7.5 else 0
        con.execute("INSERT INTO students VALUES (?,?,?,?,?,?,?,?)",
                    (roll, name, 3, "A" if i < 18 else "B", mentor,
                     f"{first.lower()}.{roll.lower()}@student.demo-college.edu", cgpa, arrears))
        low = i in (2, 7, 11, 16, 23, 29, 33)          # a few students fall below 75%
        for subj in SUBJECTS:
            total = 48
            pct = rng.uniform(0.62, 0.74) if (low and rng.random() < 0.6) else rng.uniform(0.78, 0.98)
            con.execute("INSERT INTO attendance VALUES (?,?,?,?)", (roll, subj, round(total * pct), total))
    con.commit()
    n = con.execute("""SELECT COUNT(DISTINCT roll_no) FROM attendance
                       WHERE attended * 100.0 / total < 75""").fetchone()[0]
    con.close()
    print(f"Built {DB.name}: {len(FIRST)} students, {n} below 75% in at least one subject")


if __name__ == "__main__":
    build()
