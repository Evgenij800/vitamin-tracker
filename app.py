import os
import sqlite3
from flask import Flask, render_template, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'vitamin_tracker_secret_key_2026'
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT DEFAULT '',
            gender TEXT DEFAULT 'Не указан',
            age INTEGER DEFAULT 25,
            health_goals TEXT DEFAULT 'Общее укрепление',
            onboarding_completed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Vitamins tracker table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vitamins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            time_of_day TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Survey reports table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS surveys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            answers TEXT NOT NULL,
            report_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Analyses PDF table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Укажите email и пароль'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Пароль должен содержать не менее 6 символов'}), 400
        
    hashed_pw = generate_password_hash(password)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (email, password) VALUES (?, ?)', (email, hashed_pw))
        user_id = cursor.lastrowid
        conn.commit()
        
        # Add welcome notification
        cursor.execute('INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)',
                       (user_id, 'Добро пожаловать!', 'Рады приветствовать вас в умном трекере здоровья. Пройдите опрос и добавьте первые витамины.'))
        conn.commit()
        
        session['user_id'] = user_id
        
        cursor.execute('SELECT id, email, full_name, gender, age, health_goals, onboarding_completed FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        
        return jsonify({
            'message': 'Регистрация успешна',
            'user': {
                'id': user[0],
                'email': user[1],
                'full_name': user[2],
                'gender': user[3],
                'age': user[4],
                'health_goals': user[5],
                'onboarding_completed': user[6]
            }
        })
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Пользователь с таким email уже существует'}), 400
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Укажите email и пароль'}), 400
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, email, password, full_name, gender, age, health_goals, onboarding_completed FROM users WHERE email = ?', (email,))
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(user[2], password):
        session['user_id'] = user[0]
        return jsonify({
            'message': 'Успешный вход',
            'user': {
                'id': user[0],
                'email': user[1],
                'full_name': user[3],
                'gender': user[4],
                'age': user[5],
                'health_goals': user[6],
                'onboarding_completed': user[7]
            }
        })
    return jsonify({'error': 'Неверный email или пароль'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Выход выполнен'})

@app.route('/api/user', methods=['GET', 'PUT'])
def user_profile():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if request.method == 'PUT':
        data = request.json
        full_name = data.get('full_name', '')
        gender = data.get('gender', 'Не указан')
        age = data.get('age', 25)
        health_goals = data.get('health_goals', '')
        onboarding_completed = data.get('onboarding_completed', 1)
        
        cursor.execute('''
            UPDATE users SET full_name = ?, gender = ?, age = ?, health_goals = ?, onboarding_completed = ?
            WHERE id = ?
        ''', (full_name, gender, age, health_goals, onboarding_completed, user_id))
        conn.commit()
        
    cursor.execute('SELECT id, email, full_name, gender, age, health_goals, onboarding_completed FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
        
    return jsonify({
        'user': {
            'id': user[0],
            'email': user[1],
            'full_name': user[2],
            'gender': user[3],
            'age': user[4],
            'health_goals': user[5],
            'onboarding_completed': user[6]
        }
    })

@app.route('/api/vitamins', methods=['GET', 'POST'])
def vitamins_endpoint():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        data = request.json
        name = data.get('name', '').strip()
        dosage = data.get('dosage', '').strip()
        time_of_day = data.get('time_of_day', 'Утро').strip()
        date = data.get('date', '').strip()
        
        if not name or not dosage or not date:
            return jsonify({'error': 'Заполните все обязательные поля'}), 400
            
        cursor.execute('''
            INSERT INTO vitamins (user_id, name, dosage, time_of_day, status, date)
            VALUES (?, ?, ?, ?, 'pending', ?)
        ''', (user_id, name, dosage, time_of_day, date))
        conn.commit()
        
    cursor.execute('SELECT id, name, dosage, time_of_day, status, date FROM vitamins WHERE user_id = ? ORDER BY date DESC, id DESC', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    vitamins = [{
        'id': r[0],
        'name': r[1],
        'dosage': r[2],
        'time_of_day': r[3],
        'status': r[4],
        'date': r[5]
    } for r in rows]
    
    return jsonify({'vitamins': vitamins})

@app.route('/api/vitamins/<int:vitamin_id>', methods=['PUT', 'DELETE'])
def vitamin_detail(vitamin_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if request.method == 'PUT':
        data = request.json
        status = data.get('status', 'pending')
        cursor.execute('UPDATE vitamins SET status = ? WHERE id = ? AND user_id = ?', (status, vitamin_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Статус обновлен'})
        
    if request.method == 'DELETE':
        cursor.execute('DELETE FROM vitamins WHERE id = ? AND user_id = ?', (vitamin_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Витамин удален'})

@app.route('/api/survey', methods=['GET', 'POST'])
def survey_endpoint():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        data = request.json
        answers = data.get('answers', {})
        
        # Generate basic report based on answers
        sleep = answers.get('sleep', '')
        energy = answers.get('energy', '')
        stress = answers.get('stress', '')
        goal = answers.get('goal', '')
        
        report_parts = ["<h3>Ваш базовый отчёт и рекомендации по здоровью</h3>"]
        report_parts.append(главный_текст := "<p>На основе ваших ответов мы подготовили персональные рекомендации для поддержания баланса и бодрости:</p>")
        
        recommendations = []
        if 'Меньше 6' in sleep or 'Плохо' in str(sleep):
            recommendations.append("<li><strong>Магний B6 и Мелатонин:</strong> Помогут улучшить качество сна, снизить ночное напряжение и нормализовать циркадные ритмы.</li>")
        if 'Низкий' in energy or 'Усталость' in str(energy):
            recommendations.append("<li><strong>Витамин D3 (2000 МЕ) + Омега-3:</strong> Способствуют повышению уровня энергии, поддержке иммунитета и когнитивных функций.</li>")
        if 'Высокий' in stress or 'Часто' in str(stress):
            recommendations.append("<li><strong>L-теанин и Витамины группы B:</strong> Эффективны для снижения уровня стресса и поддержки нервной системы при нагрузках.</li>")
            
        if not recommendations:
            recommendations.append("<li><strong>Мультивитаминный комплекс + Витамин D3:</strong> Отличный базовый набор для поддержания текущего уровня энергии и профилактики.</li>")
            recommendations.append("<li><strong>Омега-3 жирные кислоты:</strong> Для здоровья сердечно-сосудистой системы и сосудов.</li>")
            
        report_parts.append("<ul>" + "".join(recommendations) + "</ul>")
        report_parts.append("<p>Рекомендуем сдать базовые анализы крови (общий анализ, ферритин, витамин D) перед началом приема добавок и проконсультироваться со специалистом.</p>")
        
        report_html = "".join(report_parts)
        
        import json
        cursor.execute('INSERT INTO surveys (user_id, answers, report_text) VALUES (?, ?, ?)',
                       (user_id, json.dumps(answers, ensure_ascii=False), report_html))
        conn.commit()
        
        # Also add a notification
        cursor.execute('INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)',
                       (user_id, 'Новый отчёт готов', 'Ваш персональный отчёт по здоровью на основе опроса успешно сформирован!'))
        conn.commit()
        
    cursor.execute('SELECT id, answers, report_text, created_at FROM surveys WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,))
    survey = cursor.fetchone()
    conn.close()
    
    if not survey:
        return jsonify({'survey': None})
        
    return jsonify({
        'survey': {
            'id': survey[0],
            'answers': survey[1],
            'report_text': survey[2],
            'created_at': survey[3]
        }
    })

@app.route('/api/analyses', methods=['GET', 'POST'])
def analyses_endpoint():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'Файл не найден'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Файл не выбран'}), 400
            
        if file and file.filename.lower().endswith('.pdf'):
            filename = secure_filename(file.filename)
            import time
            stored_filename = f"{user_id}_{int(time.time())}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], stored_filename)
            file.save(filepath)
            
            cursor.execute('INSERT INTO analyses (user_id, filename, stored_filename) VALUES (?, ?, ?)',
                           (user_id, filename, stored_filename))
            conn.commit()
        else:
            return jsonify({'error': 'Разрешена загрузка только PDF файлов'}), 400
            
    cursor.execute('SELECT id, filename, stored_filename, uploaded_at FROM analyses WHERE user_id = ? ORDER BY id DESC', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    analyses = [{
        'id': r[0],
        'filename': r[1],
        'stored_filename': r[2],
        'uploaded_at': r[3]
    } for r in rows]
    
    return jsonify({'analyses': analyses})

@app.route('/api/analyses/<int:analysis_id>', methods=['DELETE', 'GET'])
def analysis_detail(analysis_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT stored_filename, filename FROM analyses WHERE id = ? AND user_id = ?', (analysis_id, user_id))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return jsonify({'error': 'Файл не найден'}), 404
        
    stored_filename, filename = row[0], row[1]
    
    if request.method == 'GET':
        conn.close()
        return send_from_directory(app.config['UPLOAD_FOLDER'], stored_filename, as_attachment=True, download_name=filename)
        
    if request.method == 'DELETE':
        cursor.execute('DELETE FROM analyses WHERE id = ? AND user_id = ?', (analysis_id, user_id))
        conn.commit()
        conn.close()
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], stored_filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            
        return jsonify({'message': 'Файл удален'})

@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, message, is_read, created_at FROM notifications WHERE user_id = ? ORDER BY id DESC', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    notifications = [{
        'id': r[0],
        'title': r[1],
        'message': r[2],
        'is_read': r[3],
        'created_at': r[4]
    } for r in rows]
    
    return jsonify({'notifications': notifications})

@app.route('/api/notifications/<int:notif_id>/read', methods=['PUT'])
def mark_notification_read(notif_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?', (notif_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Прочитано'})

@app.route('/api/session', methods=['GET'])
def check_session():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'user': None})
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, email, full_name, gender, age, health_goals, onboarding_completed FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return jsonify({'user': None})
        
    return jsonify({
        'user': {
            'id': user[0],
            'email': user[1],
            'full_name': user[2],
            'gender': user[3],
            'age': user[4],
            'health_goals': user[5],
            'onboarding_completed': user[6]
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
