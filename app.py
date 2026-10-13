import os
import random
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'oncestore_secret_key_change_in_production'

# Flask-Mail Config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = 'onestore2026@gmail.com'
app.config['MAIL_PASSWORD'] = 'zvfn oidu jzqk kefd'

mail = Mail(app)

# Folder & Database Setup
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///oncestore.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    files = db.relationship('UserFile', backref='owner', lazy=True)

class UserFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

with app.app_context():
    db.create_all()

# Helper Function: Send OTP Email
def send_otp_email(to_email, otp):
    print(f"\n==========================================")
    print(f"DEBUG OTP FOR {to_email}: {otp}")
    print(f"==========================================\n")
    
    msg = Message('OnceStore - Email Verification OTP', sender=app.config['MAIL_USERNAME'], recipients=[to_email])
    msg.body = f'Aapka OnceStore verification OTP yeh hai: {otp}\nKripya is OTP ko kisi ke sath share na karein.'
    mail.send(msg)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Username already exists!')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already exists!')
            return redirect(url_for('register'))

        # OTP generate karke session me store karna
        otp = str(random.randint(100000, 999999))
        session['signup_data'] = {
            'username': username,
            'email': email,
            'password_hash': generate_password_hash(password),
            'otp': otp
        }

        print(f"\n[DEBUG REGISTER OTP]: {otp}\n")

        try:
            send_otp_email(email, otp)
            flash('OTP aapke email par bhej diya gaya hai. Kripya verify karein!')
        except Exception as e:
            flash(f'Mail server busy hai. Aapka Emergency OTP yeh hai: {otp}')

        return redirect(url_for('verify_otp'))

    return render_template('register.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'signup_data' not in session:
        return redirect(url_for('register'))

    if request.method == 'POST':
        user_otp = request.form['otp']
        stored_data = session['signup_data']

        if user_otp == stored_data['otp']:
            new_user = User(
                username=stored_data['username'],
                email=stored_data['email'],
                password_hash=stored_data['password_hash'],
                is_verified=True
            )
            db.session.add(new_user)
            db.session.commit()

            session.pop('signup_data', None)
            flash('Email verified successfully! Ab aap login kar sakte hain.')
            return redirect(url_for('login'))
        else:
            flash('Galat OTP! Kripya sahi OTP daalein.')

    return render_template('verify_otp.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        # Direct password check karke login karana (Bina OTP ke)
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            
            flash('Login successful!')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!')

    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected!')
            return redirect(url_for('dashboard'))

        file = request.files['file']
        if file.filename == '':
            flash('No file selected!')
            return redirect(url_for('dashboard'))

        filename = secure_filename(file.filename)
        saved_filename = f"{user.id}_{filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], saved_filename))

        new_file = UserFile(filename=saved_filename, user_id=user.id)
        db.session.add(new_file)
        db.session.commit()
        flash('File uploaded successfully!')
        return redirect(url_for('dashboard'))

    return render_template('dashboard.html', user=user)

@app.route('/view/<path:filename>')
def view_file(filename):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    file_record = UserFile.query.filter_by(filename=filename, user_id=session['user_id']).first()
    if not file_record:
        abort(403)
        
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=False)

@app.route('/download/<path:filename>')
def download_file(filename):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    file_record = UserFile.query.filter_by(filename=filename, user_id=session['user_id']).first()
    if not file_record:
        abort(403)
        
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/delete/<path:filename>', methods=['POST'])
def delete_file(filename):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    file_record = UserFile.query.filter_by(filename=filename, user_id=session['user_id']).first()
    if not file_record:
        abort(403)

    db.session.delete(file_record)
    db.session.commit()

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    flash('File deleted successfully!')
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)