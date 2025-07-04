import os
from flask import Flask, render_template, request, redirect, url_for, send_file
import qrcode
import cv2  # ✅ Use OpenCV instead of pyzbar
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///qrcodes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class QRCodeData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    source = db.Column(db.String(10), default="generated")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    qrcodes = db.relationship('QRCodeData', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

with app.app_context():
    db.create_all()

STATIC_FOLDER = 'static'
QR_CODE_DIR = os.path.join(STATIC_FOLDER, 'qrcodes')
app.config['UPLOAD_FOLDER'] = QR_CODE_DIR
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def getting_started():
    return render_template('starting_page.html')

@app.route('/Home', methods=['GET', 'POST'])
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error="Email already registered.")
        
        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('home'))
        return render_template('login.html', error="Invalid credentials.")
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/generate_qr', methods=['GET', 'POST'])
@login_required
def generate():
    if request.method == 'POST':
        text = request.form['text']
        if len(text) == 0:
            return render_template('generate.html', error="Please enter some text")
        
        new_QR = QRCodeData(content=text, user_id=current_user.id, source='generated')
        db.session.add(new_QR)
        db.session.commit()

        count = QRCodeData.query.filter_by(user_id=current_user.id).count()
        if count > 10:
            last_qr = QRCodeData.query.filter_by(user_id=current_user.id).order_by(QRCodeData.created_at.asc()).first()
            delete_from_static_and_db(last_qr)

        filename = f"{new_QR.id}_{new_QR.user_id}qr.png"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        qr = qrcode.make(text)
        qr.save(filepath)

        return render_template('generate.html', qr_code_url=filename)

    return render_template('generate.html')

@app.route('/download/<filename>')
def download_qr(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(filepath, as_attachment=True)

# ✅ Updated to use OpenCV instead of pyzbar
def read_qr_from_image(image_path):
    img = cv2.imread(image_path)
    detector = cv2.QRCodeDetector()
    data, bbox, _ = detector.detectAndDecode(img)
    return [data] if data else []

@app.route('/read_qr', methods=['GET', 'POST'])
def read():
    decoded_data = []
    if request.method == 'POST':
        image = request.files.get('image')
        if image:
            filename = image.filename
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)
            decoded_data = read_qr_from_image(image_path)
            decoded_text = ''.join(decoded_data)

            if current_user.is_authenticated:
                new_qr = QRCodeData(content=decoded_text, source='scanned', user_id=current_user.id)
            else:
                new_qr = QRCodeData(content=decoded_text, source='scanned')

            db.session.add(new_qr)
            db.session.commit()

            if current_user.is_authenticated:
                count = QRCodeData.query.filter_by(user_id=current_user.id).count()
                if count > 10:
                    last_qr = QRCodeData.query.filter_by(user_id=current_user.id).order_by(QRCodeData.created_at.asc()).first()
                    delete_from_static_and_db(last_qr)

            filename = f"{new_qr.id}_{new_qr.user_id}qr.png"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            qr = qrcode.make(decoded_text)
            qr.save(filepath)
           
    return render_template('read.html', results=decoded_data)

@app.route('/my_qrcodes')
@login_required
def my_qrcodes():
    qrcodes = QRCodeData.query.filter_by(user_id=current_user.id).order_by(QRCodeData.created_at.desc()).all()
    return render_template('my_qrcodes.html', qrcodes=qrcodes)

def delete_from_static_and_db(qr):
    filename = f"{qr.id}_{qr.user_id}qr.png"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    db.session.delete(qr)
    db.session.commit()

@app.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    qr = QRCodeData.query.get_or_404(id)
    delete_from_static_and_db(qr)
    return redirect(url_for('my_qrcodes'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
