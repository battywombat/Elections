
DROP TABLE IF EXISTS bills;
CREATE TABLE bills (
    bill_number VARCHAR(10),
    bill_id INT PRIMARY KEY,
    year INT,
    title TEXT
);

DROP TABLE IF EXISTS history;
CREATE TABLE history (
    bill_id INT REFERENCES bills(bill_id),
    date DATE,
    action VARCHAR(500)
);

DROP TABLE IF EXISTS people;
CREATE TABLE people (
    sponsor_id INT PRIMARY KEY,
    sponsor_name VARCHAR(25)
);

DROP TABLE IF EXISTS term;
CREATE TABLE term (
    sponsor_id INT,
    district VARCHAR(5),
    party VARCHAR(30),
    start DATE,
    end DATE,
    FOREIGN KEY(sponsor_id) REFERENCES people(sponsor_id)
    FOREIGN KEY(district) REFERENCES districts(district_id)
);

DROP TABLE IF EXISTS rollcalls;
CREATE TABLE rollcalls (
    bill_id INT,
    roll_call_id INT PRIMARY KEY,
    date DATE,
    description TEXT,
    yea INT,
    nay INT,
    nv INT,
    FOREIGN KEY(bill_id) REFERENCES bills(bill_id)
);

DROP TABLE IF EXISTS votes;
CREATE TABLE votes (
    roll_call_id INT,
    sponsor_id INT,
    vote INT,
    FOREIGN KEY(roll_call_id) REFERENCES rollcalls(roll_call_id),
    FOREIGN KEY(sponsor_id) REFERENCES people(sponsor_id)
);

DROP TABLE IF EXISTS sponsors;
CREATE TABLE sponsors (
    bill_id INT REFERENCES bills(bill_id),
    sponsor_id INT REFERENCES people(sponsor_id)
);

DROP TABLE IF EXISTS districts;
CREATE TABLE districts (
    district_id VARCHAR(5) PRIMARY KEY,
    population INT
);

DROP TABLE IF EXISTS issues;
CREATE TABLE issues (
    issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_name TEXT
);

DROP TABLE IF EXISTS bill_on;
CREATE TABLE bill_on (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id INT,
    bill_id INT,
    favorability INT,
    question_text TEXT,
    FOREIGN KEY(issue_id) REFERENCES issues(issue_id),
    FOREIGN KEY(bill_id) REFERENCES bills(bill_id)
);

DROP TABLE IF EXISTS users;
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT
);

DROP TABLE IF EXISTS user_votes;
CREATE TABLE user_votes (
    user_id INTEGER,
    question_id INTEGER,
    question_vote INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(question_id) REFERENCES bill_on(id)
);

