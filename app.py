from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3

app = Flask(__name__)
app.secret_key = "taskflow_secret_key"


# -----------------------------
# Database Initialization
# -----------------------------
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'Staff'
    )
""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        created_by TEXT
    )
""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        title TEXT NOT NULL,
        description TEXT,
        assigned_to TEXT,
        status TEXT DEFAULT 'To Do'
    )
""")
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS invitations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        invited_user TEXT,
        invited_by TEXT,
        status TEXT DEFAULT 'Pending'
    )
""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        sender TEXT,
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
    conn.commit()
    conn.close()


# Initialize database when app starts
init_db()


# -----------------------------
# Routes
# -----------------------------

# Home Route
@app.route('/')
def home():
    return redirect('/login')


# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        try:
            c.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, password, role)
            )
            conn.commit()
            conn.close()
            return redirect('/login')
        except:
            conn.close()
            return "Username already exists!"

    return render_template('register.html')

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Clear any previous session first
    session.clear()

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        )

        user = c.fetchone()
        conn.close()

        if user:
            # Save fresh session data
            session['username'] = user[1]   # username
            session['role'] = user[3]       # role

            return redirect('/dashboard')
        else:
            return "Invalid username or password!"

    return render_template('login.html')

# Dashboard
# Replace your entire dashboard() function with this

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/login')

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # --------------------------------------------------
    # Get Projects:
    # 1. Projects created by the user
    # 2. Projects the user accepted invitations for
    # --------------------------------------------------
    c.execute("""
        SELECT DISTINCT projects.*
        FROM projects
        LEFT JOIN invitations
            ON projects.id = invitations.project_id
        WHERE projects.created_by = ?
           OR (
                invitations.invited_user = ?
                AND invitations.status = 'Accepted'
              )
        ORDER BY projects.id DESC
    """, (
        session['username'],
        session['username']
    ))
    projects = c.fetchall()

    # --------------------------------------------------
    # Get Pending Invitations
    # --------------------------------------------------
    c.execute("""
        SELECT *
        FROM invitations
        WHERE invited_user = ?
          AND status = 'Pending'
        ORDER BY id DESC
    """, (session['username'],))
    invitations = c.fetchall()

    # --------------------------------------------------
    # Total Tasks (all accessible projects)
    # --------------------------------------------------
    c.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE project_id IN (
            SELECT DISTINCT projects.id
            FROM projects
            LEFT JOIN invitations
                ON projects.id = invitations.project_id
            WHERE projects.created_by = ?
               OR (
                    invitations.invited_user = ?
                    AND invitations.status = 'Accepted'
                  )
        )
    """, (
        session['username'],
        session['username']
    ))
    total_tasks = c.fetchone()[0]

    # --------------------------------------------------
    # Completed Tasks
    # --------------------------------------------------
    c.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE status = 'Done'
          AND project_id IN (
            SELECT DISTINCT projects.id
            FROM projects
            LEFT JOIN invitations
                ON projects.id = invitations.project_id
            WHERE projects.created_by = ?
               OR (
                    invitations.invited_user = ?
                    AND invitations.status = 'Accepted'
                  )
        )
    """, (
        session['username'],
        session['username']
    ))
    completed_tasks = c.fetchone()[0]

    # --------------------------------------------------
    # Team Members
    # Count all accepted invited users in projects
    # created by the current manager + the manager.
    # For staff users, show only 1 (themselves).
    # --------------------------------------------------
    if session['role'] == 'Manager':
        c.execute("""
            SELECT COUNT(DISTINCT invited_user)
            FROM invitations
            WHERE status = 'Accepted'
              AND project_id IN (
                    SELECT id
                    FROM projects
                    WHERE created_by = ?
              )
        """, (session['username'],))

        accepted_members = c.fetchone()[0]
        total_members = accepted_members + 1   # Manager + accepted members
    else:
        total_members = 1   # Staff user only

    conn.close()

    # --------------------------------------------------
    # Render Dashboard
    # --------------------------------------------------
    return render_template(
        'dashboard.html',
        username=session['username'],
        projects=projects,
        invitations=invitations,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        total_members=total_members
    )

@app.route('/create_project', methods=['POST'])
def create_project():
    if 'username' not in session:
        return redirect('/login')

    name = request.form['name']
    description = request.form['description']

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute(
        "INSERT INTO projects (name, description, created_by) VALUES (?, ?, ?)",
        (name, description, session['username'])
    )

    conn.commit()
    conn.close()

    return redirect('/dashboard')
@app.route('/delete_project/<int:project_id>')
def delete_project(project_id):
    if 'username' not in session:
        return redirect('/login')

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute(
        "DELETE FROM projects WHERE id=? AND created_by=?",
        (project_id, session['username'])
    )

    conn.commit()
    conn.close()

    return redirect('/dashboard')
# OPEN PROJECT
@app.route('/project/<int:project_id>')
def project(project_id):
    if 'username' not in session:
        return redirect('/login')

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Project details
    c.execute("SELECT * FROM projects WHERE id=?", (project_id,))
    project = c.fetchone()

    # Accepted team members
    c.execute("""
        SELECT invited_user
        FROM invitations
        WHERE project_id=?
        AND status='Accepted'
    """, (project_id,))
    members = c.fetchall()

    # Tasks
    c.execute("""
        SELECT * FROM tasks
        WHERE project_id=?
        ORDER BY id DESC
    """, (project_id,))
    tasks = c.fetchall()

    # Progress
    c.execute("SELECT COUNT(*) FROM tasks WHERE project_id=?", (project_id,))
    total_tasks = c.fetchone()[0]

    c.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE project_id=? AND status='Done'
    """, (project_id,))
    completed_tasks = c.fetchone()[0]

    progress = int((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0
    c.execute("""
    SELECT id, sender, message, created_at
    FROM messages
    WHERE project_id = ?
    ORDER BY id ASC
""", (project_id,))
    messages = c.fetchall()
    conn.close()

    return render_template(
        'project.html',
        project=project,
        members=members,
        tasks=tasks,
        progress=progress,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        messages=messages,
        username=session['username']
    )
# CREATE TASK
@app.route('/create_task/<int:project_id>', methods=['POST'])
def create_task(project_id):
    if 'username' not in session:
        return redirect('/login')

    title = request.form['title']
    description = request.form['description']
    assigned_to = request.form['assigned_to']
    status = request.form['status']

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        INSERT INTO tasks
        (project_id, title, description, assigned_to, status)
        VALUES (?, ?, ?, ?, ?)
    """, (project_id, title, description, assigned_to, status))

    conn.commit()
    conn.close()

    return redirect(f'/project/{project_id}')


# DELETE TASK
@app.route('/delete_task/<int:task_id>/<int:project_id>')
def delete_task(task_id, project_id):
    if 'username' not in session:
        return redirect('/login')

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("DELETE FROM tasks WHERE id=?", (task_id,))

    conn.commit()
    conn.close()

    return redirect(f'/project/{project_id}')
# EDIT TASK
@app.route('/edit_task/<int:task_id>/<int:project_id>', methods=['POST'])
def edit_task(task_id, project_id):
    if 'username' not in session:
        return redirect('/login')

    title = request.form['title']
    description = request.form['description']
    assigned_to = request.form['assigned_to']
    status = request.form['status']

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        UPDATE tasks
        SET title=?, description=?, assigned_to=?, status=?
        WHERE id=?
    """, (title, description, assigned_to, status, task_id))

    conn.commit()
    conn.close()

    return redirect(f'/project/{project_id}')

@app.route('/invite_member/<int:project_id>', methods=['POST'])
def invite_member(project_id):
    if 'username' not in session:
        return redirect('/login')

    invited_user = request.form['invited_user']

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Check if user exists
    c.execute("SELECT * FROM users WHERE username=?", (invited_user,))
    user = c.fetchone()

    if user:
        # Prevent duplicate invitations
        c.execute("""
            SELECT * FROM invitations
            WHERE project_id=? AND invited_user=?
        """, (project_id, invited_user))

        existing = c.fetchone()

        if not existing:
            c.execute("""
                INSERT INTO invitations
                (project_id, invited_user, invited_by)
                VALUES (?, ?, ?)
            """, (
                project_id,
                invited_user,
                session['username']
            ))
            conn.commit()

    conn.close()
    return redirect('/dashboard')
# Accept Invitation
@app.route('/accept_invitation/<int:invitation_id>')
def accept_invitation(invitation_id):
    if 'username' not in session:
        return redirect('/login')

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Update invitation status to Accepted
    c.execute("""
        UPDATE invitations
        SET status='Accepted'
        WHERE id=?
        AND invited_user=?
    """, (invitation_id, session['username']))

    conn.commit()
    conn.close()

    return redirect('/dashboard')


# Reject Invitation
@app.route('/reject_invitation/<int:invitation_id>')
def reject_invitation(invitation_id):
    if 'username' not in session:
        return redirect('/login')

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Update invitation status to Rejected
    c.execute("""
        UPDATE invitations
        SET status='Rejected'
        WHERE id=?
        AND invited_user=?
    """, (invitation_id, session['username']))

    conn.commit()
    conn.close()

    return redirect('/dashboard')

@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect('/login')

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Count projects created by the user
    c.execute(
        "SELECT COUNT(*) FROM projects WHERE created_by=?",
        (session['username'],)
    )
    total_projects = c.fetchone()[0]

    # Count tasks assigned to the user
    c.execute(
        "SELECT COUNT(*) FROM tasks WHERE assigned_to=?",
        (session['username'],)
    )
    total_tasks = c.fetchone()[0]

    # Count completed tasks assigned to the user
    c.execute(
        "SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status='Done'",
        (session['username'],)
    )
    completed_tasks = c.fetchone()[0]

    conn.close()

    return render_template(
        'profile.html',
        username=session['username'],
        total_projects=total_projects,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks
    )
@app.route('/notifications')
def notifications():
    if 'username' not in session:
        return redirect('/login')

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Pending invitations
    c.execute("""
        SELECT projects.name,
               invitations.invited_by,
               invitations.status
        FROM invitations
        JOIN projects ON projects.id = invitations.project_id
        WHERE invitations.invited_user=?
        ORDER BY invitations.id DESC
    """, (session['username'],))

    notifications = c.fetchall()
    conn.close()

    return render_template(
        'notifications.html',
        username=session['username'],
        notifications=notifications
    )

@app.route('/send_message/<int:project_id>', methods=['POST'])
def send_message(project_id):
    if 'username' not in session:
        return redirect('/login')

    message = request.form['message']

    if message.strip():
        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("""
            INSERT INTO messages (project_id, sender, message)
            VALUES (?, ?, ?)
        """, (project_id, session['username'], message))

        conn.commit()
        conn.close()

    return redirect(f'/project/{project_id}')
# Delete Chat Message
@app.route('/delete_message/<int:message_id>/<int:project_id>')
def delete_message(message_id, project_id):
    # User must be logged in
    if 'username' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Delete only if the message belongs to the logged-in user
    c.execute("""
        DELETE FROM messages
        WHERE id = ?
        AND sender = ?
    """, (message_id, session['username']))

    conn.commit()
    conn.close()

    # Redirect back to the project page
    return redirect(f'/project/{project_id}')
# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# Run App
if __name__ == '__main__':
    app.run(debug=True)