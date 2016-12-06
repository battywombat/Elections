import os
import sqlite3
import datetime

from flask import Flask, request, render_template, g, session, redirect

from create_database import create_database

application = Flask(__name__)

DATABASE_PATH = 'legislature.db'
MODTIME_FILE = '.dbtime'

def write_modtime(fp):
    with open(MODTIME_FILE, 'w') as mfile:
        mfile.write(str(os.path.getmtime(fp)))

# if not os.path.exists(MODTIME_FILE) or not os.path.exists(DATABASE_PATH):
#     print('creating new database...')
#     create_database(DATABASE_PATH)
#     write_modtime(DATABASE_PATH)
# else:
#     with open(MODTIME_FILE, 'r') as f:
#         last_modtime = float(f.read())
#     current_modtime = os.path.getmtime(DATABASE_PATH)
#     if current_modtime > last_modtime:
#         print('creating new database')
#         create_database(DATABASE_PATH)
#         write_modtime(DATABASE_PATH)

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
ROLLCALL_QUERY = '''SELECT roll_call_id, date FROM rollcalls
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
                        AND v1.roll_call_id=v2.roll_call_id
                        AND v2.sponsor_id IN(SELECT sponsor_id FROM term t
                                              WHERE v2.sponsor_id=t.sponsor_id
                                              AND t.district=?)
                        AND v1.sponsor_id IN(SELECT sponsor_id FROM term t
                                            WHERE v1.sponsor_id=t.sponsor_id 
                                            AND t.district=?) 
                        AND v1.vote!=v2.vote))
                    AND b.bill_id IN(SELECT bill_id FROM bill_on)'''
INSERT_PEOPLE_QUERY = '''INSERT INTO people VALUES(1, "USER")'''
INSERT_PEOPLE_TERM_QUERY = '''INSERT INTO term(sponsor_id, district) VALUES(1,"USER")'''
INSERT_VOTES_QUERY = '''INSERT INTO votes VALUES(?,?,?)'''
DELETE_VOTES_QUERY = '''DELETE FROM votes WHERE sponsor_id=?'''
DELETE_USER_QUERY = '''DELETE FROM people WHERE sponsor_id=?'''
DELETE_TERM_QUERY = '''DELETE FROM term where sponsor_id=?'''
SELECT_BILLS = '''SELECT question_text FROM bill_on WHERE bill_id=?'''
VOTE_FROM_QUERY = '''SELECT sponsor_id, vote FROM votes WHERE '''
BILL_ON_BY_ID_QUERY = '''SELECT id FROM bill_on WHERE bill_id=?'''
DISTRICTS_SIMILAR_QUERY = '''SELECT question_text FROM bill_on b WHERE
                    EXISTS(SELECT r.roll_call_id FROM rollcalls r WHERE
                    b.bill_id=r.bill_id
                    AND r.description LIKE "%Passed%" 
                    AND EXISTS(SELECT v1.roll_call_id FROM votes v1, votes v2 WHERE 
                        r.roll_call_id=v1.roll_call_id 
                        AND v1.roll_call_id=v2.roll_call_id
                        AND v2.sponsor_id IN(SELECT sponsor_id FROM term t
                                              WHERE v2.sponsor_id=t.sponsor_id
                                              AND t.district=?)
                        AND v1.sponsor_id IN(SELECT sponsor_id FROM term t
                                            WHERE v1.sponsor_id=t.sponsor_id 
                                            AND t.district=?) 
                        AND v1.vote=v2.vote))'''

LIKE_DISTRICTS_QUERY = '''SELECT v.bill_id, v.title FROM districts d JOIN
                          (SELECT b.bill_id, b.title FROM bills b WHERE
                            EXISTS(SELECT r.roll_call_id FROM rollcalls r WHERE
                            b.bill_id=r.bill_id
                            AND r.description LIKE "%Passed%" 
                            AND EXISTS(SELECT v1.roll_call_id FROM votes v1, votes v2 WHERE 
                                r.roll_call_id=v1.roll_call_id 
                                AND v2.sponsor_id IN(SELECT sponsor_id FROM term t
                                                    WHERE v2.sponsor_id=t.sponsor_id
                                                    AND t.district="HD12")
                                AND v1.sponsor_id IN(SELECT sponsor_id FROM term t
                                                    WHERE v1.sponsor_id=t.sponsor_id 
                                                    AND t.district=d.district) 
                                AND v1.vote=v2.vote))
                            AND b.bill_id IN(SELECT bill_id FROM bill_on)) AS v 
                            GROUP BY v.bill_id ORDER BY COUNT(v.bill_id) DESC LIMIT 10'''
DISTRICTS_QUERY = '''SELECT district_id FROM districts WHERE district_id LIKE ?'''
BILL_ON_QUERY = '''SELECT id, bill_id from bill_on'''
YEA_QUERY = '''SELECT yea FROM rollcalls WHERE description LIKE "%House Passed%" AND bill_id=?'''
NAY_QUERY = '''SELECT nay FROM rollcalls WHERE description LIKE "%House Passed%" AND bill_id=?'''
REPS_QUERY = '''SELECT p.sponsor_name, t.party, t.start, t.end FROM term t
                JOIN people p ON p.sponsor_id=t.sponsor_id AND t.district=?'''
DISTRICT_INFO_QUERY = '''SELECT * FROM districts WHERE district_id=?'''
QUESTION_QUERY = '''SELECT question_text FROM bill_on WHERE bill_id=?'''
QUESTION_TEXT_QUERY = '''SELECT question_text FROM bill_on WHERE id=?'''
INSERT_USER_QUERY = '''INSERT INTO users(name) VALUES(?)'''
INSERT_USER_VOTES_QUERY = '''INSERT INTO user_votes VALUES(?,?,?)'''
USERS_QUERY = '''SELECT * FROM users'''
USER_VOTES_QUERY = '''SELECT question_id, question_vote FROM user_votes WHERE user_id=?'''
USER_NAME_QUERY = '''SELECT name FROM users WHERE id=?'''

def generate_results(question_answers):
    db = get_db()
    vote_percents = start_vote_percent()
    senate, house = vote_percents
    for question, answer in question_answers.items():
        bill, = db.execute(BILL_ID_QUERY, (question,)).fetchone()
        rollcalls = db.execute(ROLLCALL_QUERY, (bill,))
        if not rollcalls.rowcount:
            continue
        for rollcall, date in rollcalls:
            votes = db.execute(VOTES_QUERY, (rollcall,))
            for congressman, vote in votes:
                districtt = db.execute(TERM_QUERY, (congressman, date, date)).fetchone()
                if not districtt:
                    continue
                district = districtt[0]
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

@application.route("/", methods=['GET'])
def main():
    questions = get_questions()
    return render_template('index.html', questions=questions)

@application.route("/results", methods=['POST'])
def results():
    question_answers = {}
    for answer in request.form:
        question_id = int(answer)
        question_answers[question_id] = int(request.form[answer])
    return calc_results(question_answers)

def calc_results(question_answers):
    district_results = generate_results(question_answers)
    totals = calc_vote_total(district_results)
    sorted_results = sorted(district_results[1].items(), key=lambda x: int(x[0][2:]))
    session['answers'] = question_answers
    session['district_results'] = district_results
    session['totals'] = totals
    return render_template('results.html', question_answers=question_answers,
                           district_results=sorted_results, totals=totals)

@application.route("/towin", methods=['POST'])
def to_win():
    if 'district' not in request.form:
        return "Error: no district!"
    if 'answers' not in session:
        return "No active session!"
    db = get_db()
    district = request.form['district']
    question_answers = session['answers']
    db.execute(INSERT_PEOPLE_QUERY)
    db.execute(INSERT_PEOPLE_TERM_QUERY)
    for question, answer in question_answers.items():
        bill, = db.execute(BILL_ID_QUERY, (question,)).fetchone()
        rollcurs = db.execute(ROLLCALL_QUERY, (bill,))
        if not rollcurs.rowcount:
            continue
        for rollcall, _ in rollcurs:
            db.execute(INSERT_VOTES_QUERY, (rollcall, 1, answer))
    db.commit()
    bills = db.execute(DISTRICT_DIFFERENCE_QUERY, ("USER", district))
    db.execute(DELETE_TERM_QUERY, (1,))
    db.execute(DELETE_VOTES_QUERY, (1,))
    db.execute(DELETE_USER_QUERY, (1,))
    db.commit()
    result = []
    for bill, in bills:
        question, = db.execute(SELECT_BILLS, (bill,)).fetchone()
        bill_on, = db.execute(BILL_ON_BY_ID_QUERY, (bill,)).fetchone()
        my_answer = question_answers[str(bill_on)]
        result.append((question, 1 if my_answer == 2 else 2))
    return render_template('towin.html', bills=result)

def find_similar(district, similar=True):
    if 'district' not in request.form:
        return 'no district requested!'
    db = get_db()
    district = request.form['district']
    if district.startswith("SD"):
        districts = db.execute(DISTRICTS_QUERY, ("SD%",))
    elif district.startswith("HD"):
        districts = db.execute(DISTRICTS_QUERY, ("HD%",))
    else:
        return "Invalid district type: {}".format(district)
    similarities = {}
    for otherdistrict, in districts:
        same = db.execute(DISTRICTS_SIMILAR_QUERY, (district, otherdistrict))
        similarities[otherdistrict] = same.fetchall()
    result = []
    count = 0
    for matches in sorted(similarities.items(), reverse=similar, key=lambda x: len(x[1])):
        if matches[0] == district:
            continue
        result.append(matches)
        count += 1
        if count > 10:
            break
    return render_template('similar.html', maindistrict=district,
                           districts=result, agree=similar)

@application.route('/similar', methods=['POST'])
def similar():
    if 'district' not in request.form:
        return 'no district requested'
    return find_similar(request.form['district'])


@application.route("/unsimilar", methods=["POST"])
def unsimilar():
    if 'district' not in request.form:
        return 'no district requested!'
    return find_similar(request.form['district'], False)

def optimize_vote(bill_id):
    db = get_db()
    yeacurs = db.execute(YEA_QUERY, (bill_id,))
    yeatup = yeacurs.fetchone()
    if not yeatup:
        yea = 0
    else:
        yea = yeatup[0]
    naycurs = db.execute(NAY_QUERY, (bill_id,))
    naytup = naycurs.fetchone()
    if not naytup:
        nay = 0
    else:
        nay = naytup[0]
    return 1 if yea > nay else 2

@application.route("/winning", methods=["GET"])
def random_win():
    db = get_db()
    bills = db.execute(BILL_ON_QUERY)
    question_answers = {}
    for question, bill in bills:
        vote = optimize_vote(bill)
        question_answers[question] = vote
    return calc_results(question_answers)

@application.route("/districts/<districtid>", methods=["GET"])
def get_district(districtid):
    db = get_db()
    district_info = db.execute(DISTRICT_INFO_QUERY, (districtid,)).fetchone()
    reps = db.execute(REPS_QUERY, (districtid,)).fetchall()
    sorted_reps = sorted(reps, key=lambda x: datetime.datetime.strptime(x[3], "%Y-%m-%d"))
    return render_template("district.html", district_info=district_info, reps=sorted_reps)

@application.route("/users/<userid>")
def get_user(userid):
    db = get_db()
    name, = db.execute(USER_NAME_QUERY, (userid,)).fetchone()
    votes = db.execute(USER_VOTES_QUERY, (userid,))
    answers = []
    for question_id, vote in votes:
        question_text, = db.execute(QUESTION_TEXT_QUERY, (question_id,)).fetchone()
        answers.append((question_text, vote))
    return render_template('user.html', name=name, answers=answers)

@application.route("/adduservote", methods=["POST"])
def add_user_vote():
    if 'name' not in request.form:
        return "Couldn't add your results without a name"
    name = request.form['name']
    db = get_db()
    curs = db.execute(INSERT_USER_QUERY, (name,))
    user_id = curs.lastrowid
    for question, answer in session['answers'].items():
        curs = db.execute(INSERT_USER_VOTES_QUERY, (user_id, question, answer))
    db.commit()
    return redirect('/users/{}'.format(user_id))

def user_similar_count(user, answers):
    db = get_db()
    votes = db.execute(USER_VOTES_QUERY, (user,))
    return len([question for question, answer in votes if answers[str(question)] == answer])

@application.route("/similarusers", methods=['GET'])
def similar_users():
    if 'answers' not in session:
        return "No active session at this time"
    db = get_db()
    answers = session['answers']
    users = db.execute(USERS_QUERY)
    rankings = []
    for user_id, user_name in users:
        rankings.append((user_name, user_id, user_similar_count(user_id, answers)))
    rankings.sort(key=lambda x: x[2], reverse=True)
    return render_template('rankings.html', rankings=rankings)

@application.route("/reset", methods=["GET"])
def reset():
    if 'answers' in session:
        del session['answers']
    if 'district_results' in session:
        del session['district_results']
    if 'totals' in session:
        del session['totals']
    return redirect('/')

@application.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

@application.template_filter("date")
def datefilter(date):
    if not date:
        return 'Unknown'
    dateobj = datetime.datetime.strptime(date, "%Y-%m-%d")
    return dateobj.strftime("%B %d, %Y")

@application.template_filter("district")
def district(district_id):
    if district_id.startswith("SD"):
        house = "Senate"
    else:
        house = "House"
    return "{} District {}".format(house, district_id[2:])

@application.template_filter("question")
def question_filter(question_id):
    db = get_db()
    question, = db.execute(QUESTION_TEXT_QUERY, (question_id,))
    return question[0]

@application.template_filter("answer")
def answer_filter(answer):
    return "Yes" if answer == 1 else "No"

@application.context_processor
def inject_globals():
    return dict(
        author="Paul Warner",
        email="pew22@scarletmail.rutgers.edu",
        sources=[
            ("Ohio State Assembly", "https://www.legislature.ohio.gov/"),
            ("LegiScan", "https://legiscan.com/OH"),
            ("Wikipedia", "https://wikipedia.org")
        ]
    )

application.secret_key = "%s" % os.urandom(24)

if __name__ == '__main__':
    print('database okay, running server...')
    application.run(debug=True)
