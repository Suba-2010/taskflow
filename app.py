from flask import Flask, render_template, request, redirect
import sqlite3
import os
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -------- DATABASE --------

def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT,
        profile_pic TEXT
    )
    ''')

    conn.execute('''
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        content TEXT,
        category TEXT,
        anonymous TEXT,
        likes INTEGER DEFAULT 0,
        image TEXT,
        time TEXT,
        solved TEXT DEFAULT 'No'
    )
    ''')

    conn.execute('''
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        username TEXT,
        comment TEXT,
        image TEXT
    )
    ''')
    conn.execute('''
CREATE TABLE IF NOT EXISTS saved_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    post_id INTEGER
)
''')
    conn.execute('''
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    message TEXT,
    is_read INTEGER DEFAULT 0
)
''')

    conn.close()


init_db()


# -------- ROUTES --------

@app.route('/')
def login_page():
    return render_template('login.html')


# REGISTER
@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        u = request.form['username']
        p = request.form['password']

        file = request.files['profile_pic']

        filename = ''

        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db()

        conn.execute(
            "INSERT INTO users (username, password, profile_pic) VALUES (?, ?, ?)",
            (u, p, filename)
        )

        conn.commit()
        conn.close()

        return redirect('/')

    return render_template('register.html')


# LOGIN
@app.route('/login', methods=['POST'])
def login():

    u = request.form['username']
    p = request.form['password']

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (u, p)
    ).fetchone()

    conn.close()

    if user:
        return redirect(f'/index/{u}')

    return 'Invalid Login ❌'

# HOME
# HOME
@app.route('/index/<username>')
def index(username):

    category = request.args.get('category')
    search = request.args.get('search')

    conn = get_db()

    query = "SELECT * FROM posts"
    values = []

    conditions = []

    # CATEGORY FILTER
    if category:
        conditions.append("category=?")
        values.append(category)

    # SEARCH FILTER
    if search:
        conditions.append("content LIKE ?")
        values.append(f"%{search}%")

    # ADD WHERE ONLY IF CONDITIONS EXIST
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    # SHOW LATEST POSTS FIRST
    query += " ORDER BY id DESC"

    posts = conn.execute(query, values).fetchall()

    comments = conn.execute(
        "SELECT * FROM comments ORDER BY id DESC"
    ).fetchall()

    users = conn.execute(
        "SELECT * FROM users"
    ).fetchall()

    # 🏆 TOP HELPERS
    leaders = conn.execute("""
        SELECT username, COUNT(*) as total
        FROM comments
        GROUP BY username
        ORDER BY total DESC
        LIMIT 5
    """).fetchall()

    # ❤️ SAVED POSTS
    saved = conn.execute(
        "SELECT post_id FROM saved_posts WHERE username=?",
        (username,)
    ).fetchall()

    conn.close()

    return render_template(
        'index.html',
        posts=posts,
        comments=comments,
        users=users,
        username=username,
        leaders=leaders,
        saved=saved
    )



# CREATE POST
@app.route('/post/<username>', methods=['POST'])
def post(username):

    content_text = request.form['content']
    category = request.form['category']
    anonymous = request.form.get('anonymous', 'No')

    file = request.files.get('image')
    filename = ''

    if file and file.filename != '':
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    current_time = datetime.now().strftime('%d %b %Y - %I:%M %p')

    conn = get_db()

    conn.execute(
        """
        INSERT INTO posts
        (username, content, category, anonymous, image, time)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            username,
            content_text,
            category,
            anonymous,
            filename,
            current_time
        )
    )

    conn.commit()
    conn.close()

    return redirect(f'/index/{username}')

# LIKE
@app.route('/like/<int:post_id>/<username>')
def like(post_id, username):

    conn = get_db()

    conn.execute(
        "UPDATE posts SET likes = likes + 1 WHERE id=?",
        (post_id,)
    )

    conn.commit()
    conn.close()

    return redirect(f'/index/{username}')


# DELETE POST
@app.route('/delete/<int:post_id>/<username>')
def delete(post_id, username):

    conn = get_db()

    conn.execute(
        "DELETE FROM posts WHERE id=?",
        (post_id,)
    )

    conn.commit()
    conn.close()

    return redirect(f'/index/{username}')

# COMMENT
@app.route('/comment/<int:post_id>/<username>', methods=['POST'])
def comment(post_id, username):
    text = request.form['comment']
    image = request.files.get('image')
    filename = ""

    # Save answer image if uploaded
    if image and image.filename != "":
        from werkzeug.utils import secure_filename
        import os

        filename = secure_filename(image.filename)
        image.save(os.path.join('static/uploads', filename))

    conn = get_db()

    # Insert comment/answer
    conn.execute(
        "INSERT INTO comments (post_id, username, comment, image) VALUES (?, ?, ?, ?)",
        (post_id, username, text, filename)
    )

    # Get post owner
    post = conn.execute(
        "SELECT username FROM posts WHERE id = ?",
        (post_id,)
    ).fetchone()

    # Create notification for the post owner
    if post and post[0] != username:   # Don't notify yourself
        message = f"{username} answered your post 💡"

        conn.execute(
            "INSERT INTO notifications (username, message, is_read) VALUES (?, ?, 0)",
            (post[0], message)
        )

    conn.commit()
    conn.close()

    return redirect(f'/index/{username}')

# DELETE COMMENT
@app.route('/delete_comment/<int:comment_id>/<username>')
def delete_comment(comment_id, username):

    conn = get_db()

    conn.execute(
        "DELETE FROM comments WHERE id=?",
        (comment_id,)
    )

    conn.commit()
    conn.close()

    return redirect(f'/index/{username}')


# SOLVED BADGE
@app.route('/solve/<int:post_id>/<username>')
def solve(post_id, username):

    conn = get_db()

    conn.execute(
        "UPDATE posts SET solved='Yes' WHERE id=?",
        (post_id,)
    )

    conn.commit()
    conn.close()

    return redirect(f'/index/{username}')

@app.route('/save/<int:post_id>/<username>')
def save(post_id, username):

    conn = get_db()

    conn.execute(
        "INSERT INTO saved_posts (username, post_id) VALUES (?, ?)",
        (username, post_id)
    )

    conn.commit()
    conn.close()

    return redirect(f'/index/{username}')

# SHOW NOTIFICATIONS
@app.route('/notifications/<username>')
def notifications(username):
    conn = get_db()

    notifications = conn.execute(
        "SELECT * FROM notifications WHERE username = ? ORDER BY id DESC",
        (username,)
    ).fetchall()

    # Mark as read
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE username = ?",
        (username,)
    )

    conn.commit()
    conn.close()

    return render_template(
        'notifications.html',
        notifications=notifications,
        username=username
    )
@app.route('/profile/<username>')
def profile(username):
    
    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE username=?",
        (username,)
    ).fetchone()

    posts_count = conn.execute(
        "SELECT COUNT(*) FROM posts WHERE username=?",
        (username,)
    ).fetchone()[0]

    answers_count = conn.execute(
        "SELECT COUNT(*) FROM comments WHERE username=?",
        (username,)
    ).fetchone()[0]

    helpful_count = conn.execute(
        "SELECT SUM(likes) FROM posts WHERE username=?",
        (username,)
    ).fetchone()[0]

    conn.close()

    if helpful_count is None:
        helpful_count = 0

    return render_template(
        'profile.html',
        user=user,
        posts_count=posts_count,
        answers_count=answers_count,
        helpful_count=helpful_count,
        username=username
    )

# RUN
if __name__ == '__main__':
    app.run(debug=True)