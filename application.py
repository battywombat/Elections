import os
import sqlite3

from flask import Flask, request, render_template, g, session

from create_database import create_database

application = Flask(__name__)

DATABASE_PATH = 'legislature.db'
MODTIME_FILE = '.dbtime'

def write_modtime(fp):
    with open(MODTIME_FILE, 'w') as mfile:
        mfile.write(str(os.path.getmtime(fp)))

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
    districts = db.execute('SELECT district_id FROM districts').fetchall()
    for district_id, in districts:
        if district_id.startswith('SD'):
            start_support[0][district_id] = []
        elif district_id.startswith("HD"):
            start_support[1][district_id] = []
    return start_support

BILL_ID_QUERY = '''SELECT bill_id FROM bill_on WHERE id=?'''
ROLLCALL_QUERY = '''SELECT roll_call_id, date, description FROM rollcalls
                    WHERE bill_id=?
                    AND description LIKE "%Passed%"'''
VOTES_QUERY = """SELECT sponsor_id, vote FROM votes WHERE roll_call_id=?"""
ROLLCALL_COUNT_QUERY = '''SELECT COUNT(*) FROM votes where roll_call_id=?'''
FAVORING_QUERY = '''SELECT COUNT(*) FROM votes WHERE roll_call_id=? AND vote=?'''
OPPOSING_QUERY = '''SELECT COUNT(*) FROM votes WHERE roll_call_id=? AND vote!=?'''
TERM_QUERY = '''SELECT district FROM term WHERE sponsor_id=? and start<=? and end>=?'''
POPULATION_QUERY = '''SELECT population FROM districts WHERE district_id=?'''
TOTAL_POPULATION_QUERY = '''SELECT SUM(population) FROM districts WHERE district_id LIKE ?'''
DISTRICT_DIFFERENCE_QUERY = '''SELECT b.bill_id FROM bills b WHERE
                    EXISTS(SELECT r.roll_call_id FROM rollcalls r WHERE
                    b.bill_id=r.bill_id
                    AND r.description LIKE "%Passed%" 
                    AND EXISTS(SELECT v1.roll_call_id FROM votes v1, votes v2 WHERE 
                        r.roll_call_id=v1.roll_call_id 
                        AND v2.sponsor_id IN(SELECT sponsor_id FROM term t
                                              WHERE v2.sponsor_id=t.sponsor_id
                                              AND t.district=?)
                        AND v1.sponsor_id IN(SELECT sponsor_id FROM term t
                                            WHERE v1.sponsor_id=t.sponsor_id 
                                            AND t.district=?) 
                        AND v1.vote!=v2.vote))
                    AND b.bill_id IN(SELECT bill_id FROM bill_on)'''
INSERT_USER_QUERY = '''INSERT INTO people VALUES(1, "USER")'''
INSERT_USER_TERM_QUERY = '''INSERT INTO term(sponsor_id, district) VALUES(1,"USER")'''
INSERT_VOTES_QUERY = '''INSERT INTO votes VALUES(?,?,?)'''
DELETE_VOTES_QUERY = '''DELETE FROM votes WHERE sponsor_id=?'''
DELETE_USER_QUERY = '''DELETE FROM people WHERE sponsor_id=?'''
DELETE_TERM_QUERY = '''DELETE FROM term where sponsor_id=?'''
SELECT_BILLS = '''SELECT question_text FROM bill_on WHERE bill_id=?'''
VOTE_ON_QUERY = '''SELECT p.name, v.vote FROM people p, votes v WHERE
                   p.sponsor_id=v.sponsor_id
                   AND v.roll_call_id IN(SELECT roll_call_id FROM rollcalls r WHERE r.bill_id=? AND r.description LIKE "%Passed%")
                   AND p.sponsor_id=?'''
VOTE_FROM_QUERY = '''SELECT sponsor_id, vote FROM votes WHERE '''
BILL_ON_QUERY = '''SELECT id FROM bill_on WHERE bill_id=?'''

def generate_results(question_answers):
    db = get_db()
    vote_percents = start_vote_percent()
    senate, house = vote_percents
    cantfind = set()
    for question, answer in question_answers.items():
        bill, = db.execute(BILL_ID_QUERY, (question,)).fetchone()
        rollcurs = db.execute(ROLLCALL_QUERY, (bill,))
        if not rollcurs.rowcount:
            # print('no votes on bill {}'.format(bill))
            continue
        for rollcall, date, description in rollcurs:
            votes = db.execute(VOTES_QUERY, (rollcall,))
            for congressman, vote in votes:
                try:
                    districtt, = db.execute(TERM_QUERY, (congressman, date, date))
                except ValueError as err:
                    cantfind.add(congressman)
                    continue
                district = districtt[0]
                # count, = db.execute(ROLLCALL_COUNT_QUERY, (rollcall,)).fetchone()
                # oppose, = db.execute(OPPOSING_QUERY, (rollcall, vote)).fetchone()
                # modif = (oppose/(count-1))/2
                # if not modif:
                #     # print("No one opposing the bill {}, so we're skipping it".format(bill))
                #     continue
                # if vote == answer:
                #     modif += .5
                # if district.startswith("SD"):
                #     senate[district].append(modif)
                # else:
                #     house[district].append(modif)
                modif = 1 if vote == answer else 0
                if district.startswith("SD"):
                    senate[district].append(modif)
                else:
                    house[district].append(modif)
    for district in house:
        if len(house[district]):
            house[district] = sum(house[district])/len(house[district])
        else:
            house[district] = .5
    for district in senate:
        if len(senate[district]):
            senate[district] = sum(senate[district])/len(senate[district])
        else:
            senate[district] = .5
    print(cantfind)
    return vote_percents

def calc_vote_total(vote_percent):
    db = get_db()
    senate_voters = 0
    senate_total, = db.execute(TOTAL_POPULATION_QUERY, ("SD%",)).fetchone()
    house_voters = 0
    house_total, = db.execute(TOTAL_POPULATION_QUERY, ("HD%",)).fetchone()
    senate, house = vote_percent
    for district, percent in senate.items():
        population, = db.execute(POPULATION_QUERY, (district,)).fetchone()
        senate_voters += population*percent
    for district, percent in house.items():
        population, = db.execute(POPULATION_QUERY, (district,)).fetchone()
        house_voters += population*percent
    return (senate_voters/senate_total, house_voters/house_total)

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
        district_results = generate_results(question_answers)
        totals = calc_vote_total(district_results)
        session['answers'] = question_answers
        session['district_results'] = district_results
        session['totals'] = totals
        return render_template('results.html', district_results=district_results, totals=totals)

@application.route("/towin", methods=['POST'])
def to_win():
    if 'district' not in request.form:
        return "Error: no district!"
    if 'answers' not in session:
        return "No active session!"
    db = get_db()
    district = request.form['district']
    question_answers = session['answers']
    db.execute(INSERT_USER_QUERY)
    db.execute(INSERT_USER_TERM_QUERY)
    for question, answer in question_answers.items():
        bill, = db.execute(BILL_ID_QUERY, (question,)).fetchone()
        rollcurs = db.execute(ROLLCALL_QUERY, (bill,))
        if not rollcurs.rowcount:
            continue
        for rollcall, _, _ in rollcurs:
            db.execute(INSERT_VOTES_QUERY, (rollcall, 1, answer))
    bills = db.execute(DISTRICT_DIFFERENCE_QUERY, ("USER", district))
    db.execute(DELETE_TERM_QUERY, (1,))
    db.execute(DELETE_VOTES_QUERY, (1,))
    db.execute(DELETE_USER_QUERY, (1,))
    result = []
    for bill, in bills:
        question, = db.execute(SELECT_BILLS, (bill,)).fetchone()
        bill_on, = db.execute(BILL_ON_QUERY, (bill,)).fetchone()
        my_answer = question_answers[str(bill_on)]
        result.append((question, 1 if my_answer == 2 else 1))
    print(result)
    return render_template('towin.html', bills=result)

@application.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

application.secret_key = "%s" % os.urandom(24)

if __name__ == '__main__':
    print('database okay, running server...')
    application.run(debug=True)
