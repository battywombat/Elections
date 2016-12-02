import os
import sqlite3

from flask import Flask, request, render_template, g

from create_database import create_database

application = Flask(__name__)

DATABASE_PATH = 'legislature.db'
MODTIME_FILE = '.dbtime'

def write_modtime(fp):
    with open(MODTIME_FILE, 'w') as f:
        f.write(str(os.path.getmtime(fp)))

if not os.path.exists(MODTIME_FILE) or not os.path.exists(DATABASE_PATH):
    print('creating new database...')
    create_database(DATABASE_PATH)
    write_modtime(DATABASE_PATH)
else:
    with open(MODTIME_FILE, 'r') as f:
        last_modtime = float(f.read())
    current_modtime = os.path.getmtime(DATABASE_PATH)
    if current_modtime > last_modtime:
        print('creating new database')
        create_database(DATABASE_PATH)
        write_modtime(DATABASE_PATH)

def get_db():
    if not hasattr(g, 'db'):
        g.db = sqlite3.connect(DATABASE_PATH)
    return g.db

def query_questions(questionid):
    db = get_db()
    curs = db.execute("SELECT * FROM bill_on where id=?", (questionid,))
    return curs.fetchall()[0]

def get_questions():
    db = get_db()
    curs = db.execute('''SELECT id, question_text FROM bill_on''')
    return curs.fetchall()

def start_vote_percent():
    db = get_db()
    start_support = ({}, {}) # senate, house
    districts = db.execute('SELECT * FROM districts').fetchall()
    for district_id, population in districts:
        if district_id.startswith('SD'):
            start_support[0][district_id] = .5
        elif district_id.startswith("HD"):
            start_support[1][district_id] = .5
        else:
            return "ERROR!"
    return start_support

BILL_ID_QUERY = '''SELECT bill_id FROM bill_on WHERE id=?'''
ROLLCALL_QUERY = '''SELECT roll_call_id, date FROM rollcalls WHERE bill_id=?'''
VOTES_QUERY = """SELECT sponsor_id, vote FROM votes WHERE roll_call_id=?"""
ROLLCALL_COUNT_QUERY = '''SELECT COUNT(*) FROM votes where roll_call_id=?'''
FAVORING_QUERY = '''SELECT COUNT(*) FROM votes WHERE roll_call_id=? AND vote=?'''
OPPOSING_QUERY = '''SELECT COUNT(*) FROM votes WHERE roll_call_id=? AND vote!=?'''
TERM_QUERY = '''SELECT district FROM term WHERE sponsor_id=? and start<? and end>?'''
DISTRICT_QUERY = '''SELECT district_id from districts where '''

def generate_results(question_answers):
    db = get_db()
    vote_percents = start_vote_percent()
    senate, house = vote_percents
    for question, answer in question_answers.items():
        bill, = db.execute(BILL_ID_QUERY, (question,)).fetchone()
        rollcurs = db.execute(ROLLCALL_QUERY, (bill,))
        if not rollcurs.rowcount:
            print('no votes on bill {}'.format(bill))
            continue
        for rollcall, date in rollcurs:
            votes = db.execute(VOTES_QUERY, (rollcall,))
            for congressman, vote in votes:
                district, = db.execute(TERM_QUERY, (congressman, date, date)).fetchone()
                count, = db.execute(ROLLCALL_COUNT_QUERY, (rollcall,)).fetchone()
                oppose, = db.execute(OPPOSING_QUERY, (rollcall, vote)).fetchone()
                if vote == answer:
                    modif = (count/oppose)/2 + .5
                else:
                    modif = (count/oppose)/2
                if district.startswith("SD"):
                    senate[district] *= modif
                else:
                    house[district] *= modif
    return vote_percents

@application.route("/", methods=['POST', 'GET'])
def main():
    if request.method == 'GET':
        questions = get_questions()
        return render_template('index.html', questions=questions)
    elif request.method == 'POST':
        question_answers = {}
        for answer in request.form:
            question_id = int(answer)
            question_answers[question_id] = int(request.form[answer])
        voting_results = generate_results(question_answers)
        return str(voting_results)

@application.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

if __name__ == '__main__':
    print('database okay, running server...')
    application.run(debug=True)
