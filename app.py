import os
import hashlib
import mysql.connector
import uuid
from flask import Flask, jsonify, render_template, request, redirect, send_file, url_for, send_from_directory, flash, session, make_response
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db_connection
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors 
from reportlab.lib.units import inch 
from io import BytesIO
from flask_mail import Mail, Message
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Base upload folder
BASE_UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')

# Subfolders for different file types
UPLOAD_FOLDER_INTERNSHIPS = os.path.join(BASE_UPLOAD_FOLDER, 'internships')
UPLOAD_FOLDER_ACHIEVEMENTS = os.path.join(BASE_UPLOAD_FOLDER, 'achievements')
UPLOAD_FOLDER_PHOTOS = os.path.join(BASE_UPLOAD_FOLDER, 'photos')  

# Allowed file types
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

# Check folders exist
os.makedirs(UPLOAD_FOLDER_INTERNSHIPS, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_ACHIEVEMENTS, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_PHOTOS, exist_ok=True)

# Store in app config
app.config['UPLOAD_FOLDER_BASE'] = BASE_UPLOAD_FOLDER
app.config['UPLOAD_FOLDER_INTERNSHIPS'] = UPLOAD_FOLDER_INTERNSHIPS
app.config['UPLOAD_FOLDER_ACHIEVEMENTS'] = UPLOAD_FOLDER_ACHIEVEMENTS
app.config['UPLOAD_FOLDER_PHOTOS'] = UPLOAD_FOLDER_PHOTOS
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS

# Flask-Mail Configuration 
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'premrajrajput1345@gmail.com'  
app.config['MAIL_PASSWORD'] = 'okno nogi wvdw lbab'     
app.config['MAIL_DEFAULT_SENDER'] = 'premrajrajput1345@gmail.com'

mail = Mail(app)

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER_INTERNSHIPS, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_ACHIEVEMENTS, exist_ok=True)

# Utility
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_email(subject, recipients, body):
    try:
        msg = Message(subject=subject, recipients=recipients, body=body)
        mail.send(msg)
        print(f" Email sent to {recipients}")
    except Exception as e:
        print(f" Email sending failed: {e}")

def get_all_students_with_files():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        print("[OK] DB connection successful")
    except Exception as err:
        print(f"[ERROR] DB connection failed: {err}")

    # Get all students
    cursor.execute("SELECT id, name, year FROM students")
    students = cursor.fetchall()

    # Get internships
    cursor.execute("SELECT student_id, file_name FROM internships")
    internships = cursor.fetchall()

    # Get achievements
    cursor.execute("SELECT student_id, file_name FROM achievements")
    achievements = cursor.fetchall()

    # Organize files by student_id
    internship_map = {}
    for item in internships:
        internship_map.setdefault(item['student_id'], []).append(item['file_name'])

    achievement_map = {}
    for item in achievements:
        achievement_map.setdefault(item['student_id'], []).append(item['file_name'])

    # Combine into student profile
    student_profiles = []
    for student in students:
        sid = student['id']
        student_profiles.append({
            'name': student['name'],
            'year': student['year'],
            'internships': internship_map.get(sid, []),
            'achievements': achievement_map.get(sid, [])
        })

    cursor.close()
    conn.close()
    return student_profiles

# Home
@app.route('/')
def home():
    return render_template('index.html')

# About Page
@app.route('/about')
def about():
    return render_template('about.html')

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE email = %s", (email,))
        student = cursor.fetchone()
        cursor.close()
        conn.close()

        if student and check_password_hash(student['password'], password):
            session['user'] = {
                'id': student['id'],
                'name': student['name'],
                'email': student['email'],
                'dob': student['dob'],
                'gender': student['gender'],
                'year': student['year'],
                'photo': student['photo']
            }
            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid email or password.')
            return redirect(url_for('login'))

    return render_template('login.html')

# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        gender = request.form['gender']
        dob = request.form['dob']
        year = request.form['year']
        password = request.form['password']

        hashed_password = generate_password_hash(password)

        photo = request.files['photo']
        filename = 'default-profile.png'

        if photo and allowed_file(photo.filename):
            filename = secure_filename(photo.filename)
            photo_path = os.path.join(app.config['UPLOAD_FOLDER_PHOTOS'], filename)
            photo.save(photo_path)

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO students (name, email, password, dob, gender, year, photo)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (name, email, hashed_password, dob, gender, year, filename))
            conn.commit()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            flash(f"Database error: {err}")
            return redirect(url_for('register'))
        finally:
            cursor.close()
            conn.close()

    return render_template('register.html')

# Profile Photo
@app.route('/uploads/<filename>')
def serve_profile_photo(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER_PHOTOS'], filename)


# Student Dashboard
@app.route('/student-dashboard')
def student_dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    email = session['user']['email']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch full user info
    cursor.execute("SELECT * FROM students WHERE email = %s", (email,))
    student = cursor.fetchone()

    if not student:
        return redirect(url_for('login'))  

    student_id = student['id']

    cursor.execute("SELECT * FROM internships WHERE student_id = %s", (student_id,))
    internships = cursor.fetchall()

    cursor.execute("SELECT * FROM achievements WHERE student_id = %s", (student_id,))
    achievements = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'student_dashboard.html',
        user=student,
        internships=internships,
        achievements=achievements
    )

# Admin Login
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admins WHERE email = %s AND password = %s", (email, password))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        if admin:
            session['admin_id'] = admin['id']
            return redirect('/admin/dashboard')
        else:
            flash("Invalid email or password.")
            return redirect('/admin/login')
    return render_template('admin_login.html')

# admin register
@app.route('/admin/register', methods=['GET', 'POST'])
def admin_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Password hashing
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO admins (name, email, password)
                VALUES (%s, %s, %s)
            """, (name, email, hashed_password))
            conn.commit()
            return redirect('/admin/login')
        except mysql.connector.Error as err:
            flash(f'Error: {err}', 'danger')
            return redirect('/admin/register')
        finally:
            cursor.close()
            conn.close()

    return render_template('admin_register.html')

#admin dashboard
@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect('/admin/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Handle form submission for approvals
    if request.method == 'POST':
        approved_type = request.form.get('type')  # 'internship' or 'achievement'
        filename = request.form.get('filename')
        student_email = request.form.get('email')

        if approved_type == 'internship':
            cursor.execute("UPDATE internships SET approved = 1 WHERE filename = %s", (filename,))
        elif approved_type == 'achievement':
            cursor.execute("UPDATE achievements SET approved = 1 WHERE filename = %s", (filename,))
        
        conn.commit()

        # Send email
        send_email(student_email, f"Your {approved_type} file has been approved", 
                   f"Hi,\n\nYour {approved_type} submission '{filename}' has been approved by the admin.\n\nCSESA Victory Hub Team")

        flash(f"{approved_type.capitalize()} file approved and email sent to student.")

    # Fetch student data
    cursor.execute("SELECT * FROM students")
    students_raw = cursor.fetchall()

    student_profiles = []
    for student in students_raw:
        student_id = student['id']
        name = student['name']
        year = student['year']
        gender = student['gender']
        dob = student['dob']
        photo = student['photo']

        cursor.execute("SELECT filename FROM internships WHERE student_id = %s", (student_id,))
        internships = [row['filename'] for row in cursor.fetchall()]

        cursor.execute("SELECT filename FROM achievements WHERE student_id = %s", (student_id,))
        achievements = [row['filename'] for row in cursor.fetchall()]

        student_profiles.append({
            'id': student_id,
            'name': name,
            'year': year,
            'gender': gender,
            'dob': dob,
            'photo': photo,
            'internships': internships,
            'achievements': achievements
        })

    # Table view data
    cursor.execute("""
        SELECT students.name AS student_name, students.email, internships.filename AS internship_file, internships.approved
        FROM internships JOIN students ON internships.student_id = students.id
    """)
    internships_table = cursor.fetchall()

    cursor.execute("""
        SELECT students.name AS student_name, students.email, achievements.filename AS achievement_file, achievements.approved
        FROM achievements JOIN students ON achievements.student_id = students.id
    """)
    achievements_table = cursor.fetchall()

    # Unread notifications
    cursor.execute("""
        SELECT notifications.*, students.name AS student_name
        FROM notifications
        JOIN students ON notifications.student_id = students.id
        WHERE is_read = FALSE
        ORDER BY timestamp DESC
    """)
    notifications = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('admin_dashboard.html',
                           students=student_profiles,
                           internships=internships_table,
                           achievements=achievements_table,
                           notifications=notifications)

# Upload Internship
@app.route('/upload-internship', methods=['POST'])
def upload_internship():
    file = request.files.get('internship_pdf')
    year = request.form.get('year')
    title = request.form.get('title')

    if not file or file.filename == '':
        flash('No file selected.')
        return redirect(url_for('student_dashboard'))

    if file and allowed_file(file.filename):
        unique_filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER_INTERNSHIPS'], unique_filename)
        file.save(save_path)

        # Debug check to ensure year and title are strings, not dicts
        if isinstance(year, dict) or isinstance(title, dict):
            flash('Invalid form data: year or title is a dictionary.')
            return redirect(url_for('student_dashboard'))

        # Ensure year and title are stripped of whitespace
        year = year.strip()
        title = title.strip()

        conn = get_db_connection()
        cursor = conn.cursor()
        student_email = session['user']['email']

        # Get student info
        cursor.execute("SELECT id, name FROM students WHERE email = %s", (student_email,))
        student = cursor.fetchone()

        if student:
            student_id, student_name = student

            # Insert into internships table
            cursor.execute(
                "INSERT INTO internships (student_id, filename, year, title) VALUES (%s, %s, %s, %s)",
                (student_id, unique_filename, year, title)
            )

            # Insert into notifications table
            cursor.execute(
                "INSERT INTO notifications (student_id, type, title, year) VALUES (%s, %s, %s, %s)",
                (student_id, 'internship', title, year)
            )

            conn.commit()

            # Send email to admin
            send_email(
                subject=' New Internship Uploaded',
                recipients=['premarchanarajput0405@gmail.com'],
                body=f'{student_name} uploaded a new internship titled "{title}" for Year: {year}.'
            )

            flash('Internship uploaded successfully!')
        else:
            flash('Student not found.')

        cursor.close()
        conn.close()
        return redirect(url_for('student_dashboard'))

    flash('Invalid file type. Only PDF allowed.')
    return redirect(url_for('student_dashboard'))

# Upload Achievement
@app.route('/upload-achievement', methods=['POST'])
def upload_achievement():
    file = request.files.get('achievement_pdf')
    year = request.form.get('year')
    title = request.form.get('title')

    if not file or file.filename == '':
        flash('No file selected.')
        return redirect(url_for('student_dashboard'))

    if file and allowed_file(file.filename):
        unique_filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER_ACHIEVEMENTS'], unique_filename)
        file.save(save_path)

        conn = get_db_connection()
        cursor = conn.cursor()
        student_email = session['user']['email']
        cursor.execute("SELECT id, name FROM students WHERE email = %s", (student_email,))
        student = cursor.fetchone()
        if student:
            student_id, student_name = student
            cursor.execute(
                "INSERT INTO achievements (student_id, filename, year, title) VALUES (%s, %s, %s, %s)",
                (student_id, unique_filename, year, title)
            )
            cursor.execute(
                "INSERT INTO notifications (student_id, type, title, year) VALUES (%s, %s, %s, %s)",
                (student_id, 'achievement', title, year)
            )
            conn.commit()

            # Send email to admin
            send_email(
                subject=' New Achievement Uploaded',
                recipients=['premarchanarajput0405@gmail.com'],
                body=f'{student_name} uploaded a new achievement titled "{title}" for Year: {year}.'
            )

        cursor.close()
        conn.close()

        flash('Achievement uploaded successfully!')
        return redirect(url_for('student_dashboard'))

    flash('Invalid file type. Only PDF allowed.')
    return redirect(url_for('student_dashboard'))

# Admin View File
@app.route('/admin/view/<category>/<filename>')
def admin_view_file(category, filename):
    folder = app.config['UPLOAD_FOLDER_INTERNSHIPS'] if category == 'internships' else app.config['UPLOAD_FOLDER_ACHIEVEMENTS']
    return send_from_directory(folder, filename)

# Check Updates
@app.route('/admin/check_updates')
def check_updates():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS count FROM internships")
    internships_count = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM achievements")
    achievements_count = cursor.fetchone()['count']

    conn.close()

    return jsonify({
        'internships': internships_count,
        'achievements': achievements_count
    })

# Admin Approve Files
@app.route('/approve-files', methods=['POST'])
def approve_files():
    conn = get_db_connection()
    cursor = conn.cursor()

    approved_internships = request.form.getlist('approved_internships')
    approved_achievements = request.form.getlist('approved_achievements')

    #  Approve internships
    for internship_id in approved_internships:
        cursor.execute("UPDATE internships SET approved = TRUE WHERE id = %s", (internship_id,))
        
        cursor.execute("""
            SELECT students.email, students.name FROM students
            JOIN internships ON students.id = internships.student_id
            WHERE internships.id = %s
        """, (internship_id,))
        student = cursor.fetchone()
        
        if student:
            send_approval_email(student[0], student[1], 'Internship')
        else:
            app.logger.warning(f"[Approval] No student found for internship ID: {internship_id}")
        flash('Selected files approved and notifications sent successfully.', 'success')

    #  Approve achievements
    for achievement_id in approved_achievements:
        cursor.execute("UPDATE achievements SET approved = TRUE WHERE id = %s", (achievement_id,))
        
        cursor.execute("""
            SELECT students.email, students.name FROM students
            JOIN achievements ON students.id = achievements.student_id
            WHERE achievements.id = %s
        """, (achievement_id,))
        student = cursor.fetchone()
        
        if student:
            send_approval_email(student[0], student[1], 'Achievement')
        else:
            app.logger.warning(f"[Approval] No student found for achievement ID: {achievement_id}")
    conn.commit()
    cursor.close()
    conn.close()

    flash('Selected files approved and notifications sent successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

# sending approval email function
def send_approval_email(email, name, category):
    try:
        msg = Message(
            subject=f"{category} Approved - CSESA",
            sender='premrajrajput1345@gmail.com',
            recipients=[email]
        )
        msg.body = f"Hello {name},\n\nYour {category.lower()} submission has been approved by the admin.\n\nRegards,\nCSESA Team"
        mail.send(msg)
        print(f" Approval email sent to {email}")
    except Exception as e:
        print(f" Failed to send approval email to {email}: {e}")

# Generate report  
@app.route('/generate_report/<int:student_id>')
def generate_report(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get student info
    cursor.execute("SELECT name, email, year, photo FROM students WHERE id = %s", (student_id,))
    student = cursor.fetchone()

    if not student:
        cursor.close()
        conn.close()
        return "Student not found", 404

    student_name, student_email, student_year, photo_filename = student

    # Internships and Achievements
    cursor.execute("SELECT title, filename, year FROM internships WHERE student_id = %s", (student_id,))
    internships = cursor.fetchall()

    cursor.execute("SELECT title, filename, year FROM achievements WHERE student_id = %s", (student_id,))
    achievements = cursor.fetchall()

    cursor.close()
    conn.close()

    # PDF Generation
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CenterHeading', alignment=1, fontSize=16, spaceAfter=12))

    # Title
    story.append(Paragraph(f"<b>Student Report</b>", styles['CenterHeading']))
    story.append(Spacer(1, 12))

    # Profile Photo
    if photo_filename:
        photo_path = os.path.join(app.config['UPLOAD_FOLDER_PHOTOS'], photo_filename)
        if os.path.exists(photo_path):
            try:
                img = Image(photo_path, width=2 * inch, height=2 * inch)
                img.hAlign = 'CENTER'
                story.append(img)
                story.append(Spacer(1, 12))
            except Exception as e:
                print(f"Error loading photo: {e}")

    # Basic Info
    story.append(Paragraph(f"<b>Name:</b> {student_name}", styles['Normal']))
    story.append(Paragraph(f"<b>Email:</b> {student_email}", styles['Normal']))
    story.append(Paragraph(f"<b>Year:</b> {student_year}", styles['Normal']))
    story.append(Spacer(1, 16))

    # Internships
    story.append(Paragraph("<b>Internships</b>", styles['Heading2']))
    story.append(Spacer(1, 6))
    if internships:
        data = [['Title', 'File', 'Year']] + [
            [title, os.path.basename(filename), year] for title, filename, year in internships
        ]
        table = Table(data, colWidths=[180, 180, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007ACC')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.8, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("No internships uploaded.", styles['Normal']))
    story.append(Spacer(1, 18))

    # Achievements
    story.append(Paragraph("<b>Achievements</b>", styles['Heading2']))
    story.append(Spacer(1, 6))
    if achievements:
        data = [['Title', 'File', 'Year']] + [
            [title, os.path.basename(filename), year] for title, filename, year in achievements
        ]
        table = Table(data, colWidths=[180, 180, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E8B57')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.8, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("No achievements uploaded.", styles['Normal']))
    story.append(Spacer(1, 24))

    # Final build
    doc.build(story)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{student_name.replace(' ', '_')}_Report.pdf",
        mimetype='application/pdf'
    )

# Logout
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0')
