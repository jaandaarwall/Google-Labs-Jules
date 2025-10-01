import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

app = Flask(__name__)
# Determine the absolute path for the database file
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'study.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Models ---
class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    sessions = db.relationship('StudySession', backref='subject', lazy=True, cascade="all, delete-orphan")
    goals = db.relationship('Goal', backref='subject', lazy=True, cascade="all, delete-orphan")

class StudySession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    target_minutes = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date, nullable=False)

# --- Routes ---
@app.route('/')
def index():
    subjects = Subject.query.all()
    return render_template('index.html', subjects=subjects)

@app.route('/add_subject', methods=['POST'])
def add_subject():
    name = request.form.get('name')
    if name:
        new_subject = Subject(name=name)
        db.session.add(new_subject)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/add_session/<int:subject_id>', methods=['POST'])
def add_session(subject_id):
    duration = request.form.get('duration')
    if duration:
        new_session = StudySession(subject_id=subject_id, duration_minutes=int(duration))
        db.session.add(new_session)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/add_goal/<int:subject_id>', methods=['POST'])
def add_goal(subject_id):
    target_minutes = request.form.get('target_minutes')
    end_date_str = request.form.get('end_date')
    if target_minutes and end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        new_goal = Goal(subject_id=subject_id, target_minutes=int(target_minutes), end_date=end_date)
        db.session.add(new_goal)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/subject/<int:subject_id>')
def subject_details(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    for goal in subject.goals:
        # Filter sessions that fall within the goal's date range
        # using date() to compare date part of datetime with date objects
        sessions_in_range = [
            s for s in subject.sessions
            if goal.start_date <= s.date.date() <= goal.end_date
        ]
        total_duration = sum(s.duration_minutes for s in sessions_in_range)

        if goal.target_minutes > 0:
            goal.progress = (total_duration / goal.target_minutes) * 100
        else:
            goal.progress = 0

    return render_template('subject_details.html', subject=subject)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)