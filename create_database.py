#!/usr/bin/env python3
import csv
import datetime
import os
import sqlite3
import sys
import legislature_districts

DATA_ROOT = './data'

SENATE_DISTRICTS = [x for x in range(1, 34)]
HOUSE_DISTRICTS = [x for x in range(1, 100)]
ISSUES = [
    (1, "Guns"),
    (2, "Abortion"),
    (3, "Drugs"),
    (4, "Environment")
]

BILLS_TO_ISSUES = {
    1:[("SB184", 2007, 1, "Do you believe people should be allowed to use deadly force on unknown persons within their own property?"), 
       ("HB234", 2013, 2, "Should potential gun buyers be compelled to complete a full criminal background check?"),
       ("SB17", 2011, 1, "Sholud it be legal to carry a gun in a public place such as a school, restaurant or bar?")],
    2:[("HB200", 2013, 2, "Should a physican be required to carry out an ultrasound of a pregnant woman no less than 48 hours before carrying out an abortion?"),
       ("HB294", 2015, 2, "Should the state defund Planned Parenthood, an organization that provides low income women with abortions and other reproductive care?"),
       ("HB64", 2015, 2, "Should medicaid funds be prevented from use for abortions?")],
    3:[("HB523", 2015, 1, "Should doctors be allowed to perscribe marijuana as a pain killer?"),
       ("HB171", 2015, 1, "Should the amount of herion required to be legally classified as a major drug offendor be reduced?")],
    4:[("SB221", 2007, 1, "Should Ohio have a set of guidelines for energy usage for businesses to target clean energy?"),
       ("HB310", 2013, 2, "If there was a set of such guidelines, should they be repealed?")
      ]
}

def main():
    create_database('legislature.db')

def create_database(fp):
    conn = sqlite3.connect(fp)
    conn.executescript(open('schema.sql').read())
    add_rawdata(conn)
    add_sponsor_info(conn)
    make_issues(conn)
    make_districts(conn)
    conn.commit()
    connect_bills_to_issues(conn)
    conn.commit()
    conn.close()

def make_districts(conn):
    for x in SENATE_DISTRICTS:
        conn.execute("INSERT INTO districts VALUES(?,?)", ("SD"+str(x), 344035))
    for x in HOUSE_DISTRICTS:
        conn.execute("INSERT INTO districts VALUES(?,?)", ("HD"+str(x), 116530))

def make_issues(conn):
    for issue in ISSUES:
        conn.execute("INSERT INTO issues VALUES(?,?)", issue)

def connect_bills_to_issues(conn):
    for i in BILLS_TO_ISSUES:
        for bill in BILLS_TO_ISSUES[i]:
            curs = conn.execute("SELECT bill_id FROM bills "
                                "WHERE bill_number=? and year LIKE ?", (bill[0], bill[1]))
            c = curs.fetchall()
            if len(c) > 1:
                print("too many responses for ", bill, ": ", c)
                sys.exit(1)
            elif len(c) < 1:
                print("No responses for ", bill)
                sys.exit(1)
            conn.execute("INSERT INTO bill_on(issue_id, bill_id, favorability, question_text) "
                         "VALUES(?,?,?,?)", (i, c[0][0], bill[2], bill[3]))

def add_rawdata(conn):
    for folder in os.listdir(DATA_ROOT):
        add_year_folder(conn, folder)

def add_year_folder(conn, folder):
    start, end = folder.split("-")
    path = os.path.join(DATA_ROOT, folder)
    for fp in os.listdir(path):
        if fp == 'bills.csv':
            with open(os.path.join(path, fp), 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row[0] == 'bill_number':
                        continue
                    try:
                        conn.execute('INSERT INTO bills VALUES (?, ?, ?, ?);',
                                     (row[0], row[1], start, row[2]))
                    except sqlite3.IntegrityError as e:
                        print(e.args)
                        print(row)
                        sys.exit(1)
        elif fp == 'history.csv':
            with open(os.path.join(path, fp), 'r') as f:
                d = csv.DictReader(f)
                to_db = [(i['bill_id'], i['date'], i['action']) for i in d]
                conn.executemany('INSERT INTO history VALUES (?,?,?)', to_db)
        elif fp == 'people.csv':
            with open(os.path.join(path, fp), 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row[0] == 'sponsor_id':
                        continue
                    try:
                        conn.execute('INSERT INTO people VALUES (?, ?)', (row[0], row[1]))
                    except sqlite3.IntegrityError as e:
                        curs = conn.execute('SELECT sponsor_id FROM people '
                                            'WHERE sponsor_id=?', (row[0],))
                        if len(curs.fetchall()) > 0:
                            continue  # already inserted into database
                        print(e.args[0])
                        print(row)
                        sys.exit(1)
        elif fp == 'rollcalls.csv':
            with open(os.path.join(path, fp), 'r') as f:
                d = csv.DictReader(f)
                to_db = [(i['bill_id'], i['roll_call_id'], i['date'],
                          i['description'], i['yea'], i['nay'], i['nv']) for i in d]
                conn.executemany('INSERT INTO rollcalls VALUES(?,?,?,?,?,?,?)', to_db)
        elif fp == 'sponsors.csv':
            with open(os.path.join(path, fp), 'r') as f:
                d = csv.DictReader(f)
                to_db = [(i['bill_id'], i['sponsor_id']) for i in d]
                conn.executemany('INSERT INTO sponsors VALUES(?,?)', to_db)
        elif fp == 'votes.csv':
            with open(os.path.join(path, fp), 'r') as f:
                d = csv.DictReader(f)
                to_db = [(i['roll_call_id'], i['sponsor_id'], i['vote']) for i in d]
                conn.executemany("INSERT INTO votes VALUES(?,?,?)", to_db)

CUTOFF_DATE = datetime.date(2007, 1, 3)
def add_sponsor_info(conn):
    term_data = legislature_districts.get_map()
    for l in term_data:
        for term in term_data[l]:
            if len(term) < 4:  # missing some date information
                term = (term[0], term[1], None, term[2])
            if term[3] == 'present' or  term[3] < CUTOFF_DATE:
                continue
            c = conn.execute('SELECT sponsor_id FROM people WHERE sponsor_name=?', (l,))
            t = c.fetchall()
            if len(t) < 1:
                lastname = l.split(' ')[-1].strip()
                c = conn.execute('SELECT sponsor_id FROM people WHERE sponsor_name LIKE ?',
                                 ("%"+lastname,))
                t = c.fetchall()
                if len(t) < 1:
                    print("error: cant find ", l, "With info: ", term)
                    continue
            if len(t) > 1:
                print("too many names: ", l, ' With ids: ', t, ' info: ', term_data[l])
                sys.exit(1)
            conn.execute("INSERT INTO term VALUES(?,?,?,?,?)", t[0] + term)


if __name__ == '__main__':
    main()