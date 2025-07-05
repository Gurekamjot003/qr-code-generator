import os
from flask import Flask, render_template, request, redirect, url_for, send_file
import qrcode
import cv2
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO
from sqlalchemy import LargeBinary
import io
from pyzbar.pyzbar import decode
from PIL import Image

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
    image = db.Column(LargeBinary, nullable = False)

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
        
        qr = qrcode.make(text)
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        img = buffer.getvalue()

        new_QR = QRCodeData(content=text, user_id=current_user.id, source='generated', image = img)
        db.session.add(new_QR)
        db.session.commit()

        count = QRCodeData.query.filter_by(user_id=current_user.id).count()
        if count > 10:
            last_qr = QRCodeData.query.filter_by(user_id=current_user.id).order_by(QRCodeData.created_at.asc()).first()
            db.session.delete(last_qr)
            db.session.commit()


        return render_template('generate.html', qr_code_id=new_QR.id)

    return render_template('generate.html')

@app.route('/view_qr/<int:id>')
@login_required
def view_qr(id):
    qr = QRCodeData.query.get_or_404(id)
    if qr.image:
        return send_file(BytesIO(qr.image), mimetype='image/png')   
    return "QR code not found", 404

@app.route('/download/<int:id>')
def download_qr(id):
    qr = QRCodeData.query.get_or_404(id)
    return send_file(BytesIO(qr.image), mimetype='image/png', as_attachment=True, download_name='qr.png')

def read_qr_from_image(image_path):
    img = Image.open(image_path)
    decoded_objs = decode(img)
    return [obj.data.decode('utf-8') for obj in decoded_objs]

@app.route('/read_qr', methods=['GET', 'POST'])
def read():
    decoded_data = []
    if request.method == 'POST':
        image = request.files.get('image')
        if image:
            temp_path = 'temp_uploaded.png'
            image.save(temp_path)
            decoded_data = read_qr_from_image(temp_path)
            os.remove(temp_path)
            decoded_text = ''.join(decoded_data)

            if current_user.is_authenticated:
                qr = qrcode.make(decoded_text)
                buffer = BytesIO()
                qr.save(buffer, format='PNG')
                img = buffer.getvalue()
                new_qr = QRCodeData(content=decoded_text, source='scanned', user_id=current_user.id, image = img)
                db.session.add(new_qr)
                db.session.commit()

                count = QRCodeData.query.filter_by(user_id=current_user.id).count()
                if count > 10:
                    last_qr = QRCodeData.query.filter_by(user_id=current_user.id).order_by(QRCodeData.created_at.asc()).first()
                    db.session.delete(last_qr)
                    db.session.commit()

    return render_template('read.html', results=decoded_data)

@app.route('/my_qrcodes')
@login_required
def my_qrcodes():
    qrcodes = QRCodeData.query.filter_by(user_id=current_user.id).order_by(QRCodeData.created_at.desc()).all()
    return render_template('my_qrcodes.html', qrcodes=qrcodes)

@app.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    qr = QRCodeData.query.get_or_404(id)
    db.session.delete(qr)
    db.session.commit()
    return redirect(url_for('my_qrcodes'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
