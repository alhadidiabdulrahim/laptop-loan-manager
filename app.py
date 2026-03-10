from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file, flash
import sqlite3
import hashlib
import json
import csv
import io
import os
from datetime import datetime, date
from functools import wraps

app = Flask(__name__)
app.secret_key = 'it-laptop-manager-secret-2024'

DB_PATH = 'laptop_loans.db'

# ─── Database Setup ───────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'viewer',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS laptops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_number TEXT UNIQUE NOT NULL,
        brand TEXT NOT NULL,
        model TEXT NOT NULL,
        serial_number TEXT UNIQUE NOT NULL,
        purchase_date TEXT,
        status TEXT DEFAULT 'available',
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        laptop_asset_number TEXT NOT NULL,
        employee_id TEXT NOT NULL,
        employee_name TEXT NOT NULL,
        department TEXT,
        loan_date TEXT NOT NULL,
        expected_return_date TEXT NOT NULL,
        return_date TEXT,
        reason TEXT NOT NULL,
        status TEXT DEFAULT 'loaned',
        condition_notes TEXT,
        created_by TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (laptop_asset_number) REFERENCES laptops(asset_number)
    )''')
    try:
        c.execute('ALTER TABLE loans ADD COLUMN created_by TEXT')
    except Exception:
        pass
    
    # Create superadmin only (default password: admin — change after first login)
    admin_hash = hashlib.sha256('admin'.encode()).hexdigest()
    c.execute('INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)',
              ('admin', admin_hash, 'superadmin'))
    
    conn.commit()
    conn.close()

def generate_asset_number():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT asset_number FROM laptops ORDER BY id DESC LIMIT 1')
    row = c.fetchone()
    conn.close()
    if row:
        last_num = int(row['asset_number'].split('-')[1])
        return f'LAP-{str(last_num + 1).zfill(4)}'
    return 'LAP-0001'

# ─── Auth ──────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') not in ('admin', 'superadmin'):
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username=? AND password_hash=?',
                            (username, pw_hash)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

def superadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'superadmin':
            return jsonify({'error': 'Superadmin access required'}), 403
        return f(*args, **kwargs)
    return decorated

# ─── Pages ─────────────────────────────────────────────────────────

@app.route('/')
@login_required
def dashboard():
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) as c FROM laptops').fetchone()['c']
    loaned = conn.execute("SELECT COUNT(*) as c FROM laptops WHERE status='loaned'").fetchone()['c']
    available = conn.execute("SELECT COUNT(*) as c FROM laptops WHERE status='available'").fetchone()['c']
    today = date.today().isoformat()
    overdue = conn.execute(
        "SELECT COUNT(*) as c FROM loans WHERE status='loaned' AND expected_return_date < ?",
        (today,)
    ).fetchone()['c']
    recent_loans = conn.execute('''
        SELECT l.*, la.brand, la.model FROM loans l
        JOIN laptops la ON l.laptop_asset_number = la.asset_number
        ORDER BY l.created_at DESC LIMIT 5
    ''').fetchall()
    conn.close()
    return render_template('dashboard.html',
        total=total, loaned=loaned, available=available,
        overdue=overdue, recent_loans=recent_loans)

@app.route('/laptops')
@login_required
def laptops_page():
    return render_template('laptops.html')

@app.route('/loans')
@login_required
def loans_page():
    return render_template('loans.html')

@app.route('/users')
@superadmin_required
def users_page():
    conn = get_db()
    users = conn.execute('SELECT id, username, role, created_at FROM users ORDER BY id').fetchall()
    conn.close()
    return render_template('users.html', users=users)

@app.route('/api/users', methods=['POST'])
@superadmin_required
def add_user():
    data = request.get_json()
    if not data.get('username') or not data.get('password') or not data.get('role'):
        return jsonify({'error': 'Username, password, and role are required'}), 400
    pw_hash = hashlib.sha256(data['password'].encode()).hexdigest()
    conn = get_db()
    try:
        conn.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                     (data['username'], pw_hash, data['role']))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Username already exists'}), 400

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@superadmin_required
def update_user(user_id):
    data = request.get_json()
    conn = get_db()
    if data.get('password'):
        pw_hash = hashlib.sha256(data['password'].encode()).hexdigest()
        conn.execute('UPDATE users SET role=?, password_hash=? WHERE id=?',
                     (data['role'], pw_hash, user_id))
    else:
        conn.execute('UPDATE users SET role=? WHERE id=?', (data['role'], user_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@superadmin_required
def delete_user(user_id):
    if user_id == session.get('user_id'):
        return jsonify({'error': 'Cannot delete your own account'}), 400
    conn = get_db()
    conn.execute('DELETE FROM users WHERE id=?', (user_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/users/change-password', methods=['POST'])
@superadmin_required
def change_own_password():
    data = request.get_json()
    current_pw = data.get('current_password', '')
    new_pw = data.get('new_password', '')
    if not current_pw or not new_pw:
        return jsonify({'error': 'Both fields required'}), 400
    if len(new_pw) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    current_hash = hashlib.sha256(current_pw.encode()).hexdigest()
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id=? AND password_hash=?',
                        (session['user_id'], current_hash)).fetchone()
    if not user:
        conn.close()
        return jsonify({'error': 'Current password is incorrect'}), 400
    new_hash = hashlib.sha256(new_pw.encode()).hexdigest()
    conn.execute('UPDATE users SET password_hash=? WHERE id=?', (new_hash, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/label/<asset_number>')
@login_required
def label_page(asset_number):
    conn = get_db()
    laptop = conn.execute('SELECT * FROM laptops WHERE asset_number=?', (asset_number,)).fetchone()
    conn.close()
    if not laptop:
        return "Laptop not found", 404
    return render_template('label.html', laptop=laptop)

# ─── API: Laptops ──────────────────────────────────────────────────

@app.route('/api/laptops', methods=['GET'])
@login_required
def get_laptops():
    conn = get_db()
    q = request.args.get('q', '')
    status_filter = request.args.get('status', '')
    query = 'SELECT * FROM laptops WHERE 1=1'
    params = []
    if q:
        query += ' AND (asset_number LIKE ? OR serial_number LIKE ? OR brand LIKE ? OR model LIKE ?)'
        params += [f'%{q}%'] * 4
    if status_filter:
        query += ' AND status=?'
        params.append(status_filter)
    query += ' ORDER BY id DESC'
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/laptops', methods=['POST'])
@admin_required
def add_laptop():
    data = request.get_json()
    asset_number = generate_asset_number()
    conn = get_db()
    try:
        conn.execute('''INSERT INTO laptops (asset_number, brand, model, serial_number, purchase_date, notes)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (asset_number, data['brand'], data['model'], data['serial_number'],
                      data.get('purchase_date'), data.get('notes')))
        conn.commit()
        laptop = conn.execute('SELECT * FROM laptops WHERE asset_number=?', (asset_number,)).fetchone()
        conn.close()
        return jsonify({'success': True, 'laptop': dict(laptop)})
    except sqlite3.IntegrityError as e:
        conn.close()
        return jsonify({'error': 'Serial number already exists'}), 400

@app.route('/api/laptops/<asset_number>', methods=['GET'])
@login_required
def get_laptop(asset_number):
    conn = get_db()
    laptop = conn.execute('SELECT * FROM laptops WHERE asset_number=?', (asset_number,)).fetchone()
    conn.close()
    if not laptop:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(laptop))

@app.route('/api/laptops/<asset_number>', methods=['PUT'])
@admin_required
def update_laptop(asset_number):
    data = request.get_json()
    conn = get_db()
    conn.execute('''UPDATE laptops SET brand=?, model=?, serial_number=?, purchase_date=?, notes=?
                    WHERE asset_number=?''',
                 (data['brand'], data['model'], data['serial_number'],
                  data.get('purchase_date'), data.get('notes'), asset_number))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/laptops/<asset_number>', methods=['DELETE'])
@admin_required
def delete_laptop(asset_number):
    conn = get_db()
    laptop = conn.execute('SELECT * FROM laptops WHERE asset_number=?', (asset_number,)).fetchone()
    if laptop['status'] == 'loaned':
        conn.close()
        return jsonify({'error': 'Cannot delete a loaned laptop'}), 400
    conn.execute('DELETE FROM laptops WHERE asset_number=?', (asset_number,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ─── API: Loans ────────────────────────────────────────────────────

@app.route('/api/loans', methods=['GET'])
@login_required
def get_loans():
    conn = get_db()
    q = request.args.get('q', '')
    status_filter = request.args.get('status', '')
    query = '''SELECT l.*, la.brand, la.model, la.serial_number FROM loans l
               JOIN laptops la ON l.laptop_asset_number = la.asset_number WHERE 1=1'''
    params = []
    if q:
        query += ''' AND (l.laptop_asset_number LIKE ? OR l.employee_id LIKE ?
                    OR l.employee_name LIKE ? OR la.serial_number LIKE ?)'''
        params += [f'%{q}%'] * 4
    if status_filter:
        query += ' AND l.status=?'
        params.append(status_filter)
    query += ' ORDER BY l.id DESC'
    rows = conn.execute(query, params).fetchall()
    today = date.today().isoformat()
    result = []
    for r in rows:
        d = dict(r)
        d['overdue'] = (d['status'] == 'loaned' and d['expected_return_date'] < today)
        result.append(d)
    conn.close()
    return jsonify(result)

@app.route('/api/loans', methods=['POST'])
@admin_required
def create_loan():
    data = request.get_json()
    conn = get_db()
    laptop = conn.execute('SELECT * FROM laptops WHERE asset_number=?',
                          (data['laptop_asset_number'],)).fetchone()
    if not laptop:
        conn.close()
        return jsonify({'error': 'Laptop not found'}), 404
    if laptop['status'] != 'available':
        conn.close()
        return jsonify({'error': 'Laptop is not available'}), 400
    conn.execute('''INSERT INTO loans (laptop_asset_number, employee_id, employee_name,
                    department, loan_date, expected_return_date, reason, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                 (data['laptop_asset_number'], data['employee_id'], data['employee_name'],
                  data.get('department'), data['loan_date'], data['expected_return_date'],
                  data['reason'], session.get('username')))
    conn.execute("UPDATE laptops SET status='loaned' WHERE asset_number=?",
                 (data['laptop_asset_number'],))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/loans/<int:loan_id>/return', methods=['POST'])
@admin_required
def return_laptop(loan_id):
    data = request.get_json()
    conn = get_db()
    loan = conn.execute('SELECT * FROM loans WHERE id=?', (loan_id,)).fetchone()
    if not loan:
        conn.close()
        return jsonify({'error': 'Loan not found'}), 404
    if loan['status'] == 'returned':
        conn.close()
        return jsonify({'error': 'Already returned'}), 400
    return_date = data.get('return_date', date.today().isoformat())
    conn.execute('''UPDATE loans SET status='returned', return_date=?, condition_notes=?
                    WHERE id=?''',
                 (return_date, data.get('condition_notes'), loan_id))
    conn.execute("UPDATE laptops SET status='available' WHERE asset_number=?",
                 (loan['laptop_asset_number'],))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/loans/<int:loan_id>', methods=['DELETE'])
@superadmin_required
def delete_loan(loan_id):
    conn = get_db()
    loan = conn.execute('SELECT * FROM loans WHERE id=?', (loan_id,)).fetchone()
    if not loan:
        conn.close()
        return jsonify({'error': 'Not found'}), 404
    if loan['status'] == 'loaned':
        conn.execute("UPDATE laptops SET status='available' WHERE asset_number=?",
                     (loan['laptop_asset_number'],))
    conn.execute('DELETE FROM loans WHERE id=?', (loan_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ─── Export ────────────────────────────────────────────────────────

@app.route('/api/export/loans')
@login_required
def export_loans():
    conn = get_db()
    rows = conn.execute('''SELECT l.id, l.laptop_asset_number, la.brand, la.model, la.serial_number,
                           l.employee_id, l.employee_name, l.department, l.loan_date,
                           l.expected_return_date, l.return_date, l.reason, l.status,
                           l.condition_notes FROM loans l
                           JOIN laptops la ON l.laptop_asset_number = la.asset_number
                           ORDER BY l.id DESC''').fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Asset Number', 'Brand', 'Model', 'Serial Number', 'Employee ID',
                     'Employee Name', 'Department', 'Loan Date', 'Expected Return',
                     'Return Date', 'Reason', 'Status', 'Condition Notes'])
    for r in rows:
        writer.writerow(list(r))
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'loan_history_{date.today().isoformat()}.csv'
    )

@app.route('/api/export/inventory')
@login_required
def export_inventory():
    conn = get_db()
    rows = conn.execute('SELECT * FROM laptops ORDER BY asset_number').fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Asset Number', 'Brand', 'Model', 'Serial Number', 'Purchase Date', 'Status', 'Notes', 'Created At'])
    for r in rows:
        writer.writerow([r['asset_number'], r['brand'], r['model'], r['serial_number'],
                         r['purchase_date'], r['status'], r['notes'], r['created_at']])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'laptop_inventory_{date.today().isoformat()}.csv'
    )

# ─── Stats API ─────────────────────────────────────────────────────

@app.route('/api/stats')
@login_required
def get_stats():
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) as c FROM laptops').fetchone()['c']
    loaned = conn.execute("SELECT COUNT(*) as c FROM laptops WHERE status='loaned'").fetchone()['c']
    available = conn.execute("SELECT COUNT(*) as c FROM laptops WHERE status='available'").fetchone()['c']
    today = date.today().isoformat()
    overdue = conn.execute(
        "SELECT COUNT(*) as c FROM loans WHERE status='loaned' AND expected_return_date < ?",
        (today,)
    ).fetchone()['c']
    conn.close()
    return jsonify({'total': total, 'loaned': loaned, 'available': available, 'overdue': overdue})

if __name__ == '__main__':
    init_db()
    print("\n🖥️  Laptop Loan Manager started!")
    print("   URL: http://localhost:5000")
    app.run(debug=True, port=5000)
