import os
import json
import PIL.Image
import google.generativeai as genai
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import bcrypt

app = Flask(__name__)
app.secret_key = 'super_advanced_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nutri.db'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- AI SETUP ---
# --- AI SETUP ---
GEMINI_API_KEY = 'YOUR_GEMINI_KEY_HERE'  # Keep it as a placeholder!
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.5-flash')
# --- DATABASE SETUP ---
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    meals = db.relationship('MealLog', backref='user', lazy=True)

class MealLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    food_name = db.Column(db.String(100), nullable=False)
    calories = db.Column(db.Integer, nullable=False)
    protein = db.Column(db.Integer, nullable=False)
    carbs = db.Column(db.Integer, nullable=False)
    fat = db.Column(db.Integer, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# --- ROUTES ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'].encode('utf-8')
        hashed = bcrypt.hashpw(password, bcrypt.gensalt())
        
        new_user = User(username=username, password=hashed)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('dashboard'))
    return render_template('login.html', action="Register")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and bcrypt.checkpw(request.form['password'].encode('utf-8'), user.password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid credentials')
    return render_template('login.html', action="Login")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    meals = MealLog.query.filter_by(user_id=current_user.id).all()
    # Calculate totals for our analytics charts
    totals = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
    for meal in meals:
        totals["calories"] += meal.calories
        totals["protein"] += meal.protein
        totals["carbs"] += meal.carbs
        totals["fat"] += meal.fat
    return render_template('dashboard.html', meals=meals, totals=totals)

@app.route('/scan', methods=['POST'])
@login_required
def scan_image():
    if 'food_image' not in request.files:
        return redirect(url_for('dashboard'))
    file = request.files['food_image']
    if file.filename != '':
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        try:
            img = PIL.Image.open(filepath)
            # The Upgraded AI Intelligence Prompt
            prompt = """
            Analyze this food. Respond ONLY with valid JSON in this exact format (use integers for macros, no letters):
            {
                "name": "Food Name", 
                "calories": 300, 
                "protein": 15, 
                "carbs": 30, 
                "fat": 10,
                "warnings": "List any common allergens like nuts, dairy, gluten.",
                "coach_tip": "Give a 1-sentence tip on how to make this healthier or its benefits."
            }
            """
            response = model.generate_content([prompt, img])
            raw_text = response.text.replace('```json', '').replace('```', '').strip()
            ai_result = json.loads(raw_text)
            
            # Save to database
            new_meal = MealLog(
                user_id=current_user.id,
                food_name=ai_result['name'],
                calories=ai_result['calories'],
                protein=ai_result['protein'],
                carbs=ai_result['carbs'],
                fat=ai_result['fat']
            )
            db.session.add(new_meal)
            db.session.commit()
            
            return render_template('result.html', type='food', data=ai_result)
        except Exception as e:
            return f"Error: {str(e)}"
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)