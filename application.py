import os
import sqlite3

from flask import Flask, request, render_template, g

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
ROLLCALL_QUERY = '''SELECT roll_call_id, date, description FROM rollcalls WHERE bill_id=?'''
VOTES_QUERY = """SELECT sponsor_id, vote FROM votes WHERE roll_call_id=?"""
ROLLCALL_COUNT_QUERY = '''SELECT COUNT(*) FROM votes where roll_call_id=?'''
FAVORING_QUERY = '''SELECT COUNT(*) FROM votes WHERE roll_call_id=? AND vote=?'''
OPPOSING_QUERY = '''SELECT COUNT(*) FROM votes WHERE roll_call_id=? AND vote!=?'''
TERM_QUERY = '''SELECT district FROM term WHERE sponsor_id=? and start<=? and end>=?'''
POPULATION_QUERY = '''SELECT population FROM districts WHERE district_id=?'''
TOTAL_POPULATION_QUERY = '''SELECT SUM(population) FROM districts WHERE district_id LIKE ?'''
# Get all rollcalls where the districts representative voted differently from the user: district, user vote
REPRESENTED_QUERY = '''SELECT sponsor_id FROM sponsors s WHERE
                       EXISTS(SELECT district_id FROM term WHERE sponsor_id=s.sponsor_id AND
                                                              district_id=?)'''
REP_BILLS_QUERY = '''SELECT * FROM bills b WHERE
                     '''
REP_VOTED_ON_QUERY = '''SELECT * FROM rollcalls r WHERE
                        EXISTS(SELECT * FROM votes v where v.roll_call_id = r.roll_call_id and sponsor_id=?)
                        '''
BILL_FROM_ROLLCALL_QUERY = '''SELECT * from bills b WHERE b.bill_id IN(SELECT bill_id FROM rollcalls r WHERE
                              EXISTS(SELECT * FROM votes v where v.roll_call_id = r.roll_call_id
                              AND sponsor_id IN(SELECT sponsor_id FROM sponsors s WHERE
                              EXISTS(SELECT district_id FROM term t WHERE t.sponsor_id=s.sponsor_id
                              AND district_id=?))))'''
BILLS_IN_QUERY = '''SELECT * FROM bills b WHERE 
                    b.bill_id IN()
                    AND b.bill_id IN(SELECT bill_id FROM bill_on)'''

def generate_results(question_answers):
    db = get_db()
    vote_percents = start_vote_percent()
    senate, house = vote_percents
    for question, answer in question_answers.items():
        bill, = db.execute(BILL_ID_QUERY, (question,)).fetchone()
        rollcurs = db.execute(ROLLCALL_QUERY, (bill,))
        if not rollcurs.rowcount:
            # print('no votes on bill {}'.format(bill))
            continue
        for rollcall, date, description in rollcurs:
            if "Amendment" in description or "Failed" in description:
                continue
            votes = db.execute(VOTES_QUERY, (rollcall,))
            for congressman, vote in votes:
                try:
                    districtt, = db.execute(TERM_QUERY, (congressman, date, date))
                except ValueError as err:
                    # print("error unpacking values: {}".format(err))
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
            house[district] = 0
    for district in senate:
        if len(senate[district]):
            senate[district] = sum(senate[district])/len(senate[district])
        else:
            senate[district] = 0
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
        return render_template('results.html', district_results=district_results, totals=totals)

@application.route("/unlike", methods=['POST'])
def unlike_queries():
    db = get_db()
    district_id = int(request.form['district_id'])
    represented = db.execute(REPRESENTED_QUERY, (district_id,))
    for sponsor in represented:
        pass



@application.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

if __name__ == '__main__':
    print('database okay, running server...')
    application.run(debug=True)
