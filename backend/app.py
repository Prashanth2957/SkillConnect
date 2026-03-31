from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session, send_file
)
from ml.predictor import predict_career
import os
import sqlite3
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import pdfplumber
import docx

# ================= APP SETUP =================
app = Flask(__name__)
app.secret_key = "mysecretkey"

# Like & comment storage
likes = {}
comments = {}

DB_PATH = "database/users.db"
UPLOAD_FOLDER = "static/uploads"
RESUME_FOLDER = "static/resumes"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESUME_FOLDER, exist_ok=True)

# ================= DATABASE =================
def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        phone TEXT,
        linkedin TEXT,
        github TEXT,
        password TEXT,
        resume_file TEXT,
        resume_score INTEGER DEFAULT 0,
        activity_score INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS projects(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT,
        description TEXT,
        link TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS connections(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        follower_id INTEGER,
        following_id INTEGER,
        created_at TEXT,
        UNIQUE(follower_id, following_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS activities(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= SCORE + ACTIVITY =================
def update_resume_score(user_id, score=20):
    conn = get_db()
    conn.execute(
        "UPDATE users SET resume_score = resume_score + ? WHERE id=?",
        (score, user_id)
    )
    conn.commit()
    conn.close()

def update_activity_score(user_id, score=5):
    conn = get_db()
    conn.execute(
        "UPDATE users SET activity_score = activity_score + ? WHERE id=?",
        (score, user_id)
    )
    conn.commit()
    conn.close()

def log_activity(user_id, action):
    conn = get_db()
    conn.execute(
        "INSERT INTO activities (user_id, action, created_at) VALUES (?,?,?)",
        (user_id, action, datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()
    conn.close()

# ================= HOME =================
@app.route("/")
def home():
    user_info = None
    if "user_id" in session:
        conn = get_db()
        user_info = conn.execute(
            "SELECT name,email,phone,linkedin,github FROM users WHERE id=?",
            (session["user_id"],)
        ).fetchone()
        conn.close()
    return render_template("home.html", user_info=user_info)

# ================= AUTH =================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO users(name,email,phone,linkedin,github,password)
                VALUES (?,?,?,?,?,?)
            """, (
                request.form["name"],
                request.form["email"],
                request.form["phone"],
                request.form.get("linkedin", ""),
                request.form.get("github", ""),
                request.form["password"]
            ))
            conn.commit()
            conn.close()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            conn.close()
            return "Email already exists. Try another email."
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (request.form["email"], request.form["password"])
        ).fetchone()
        conn.close()

        if user:
            session.clear()
            session["user_id"] = user[0]
            session["user"] = user[1]
            return redirect(url_for("home"))

        return "Invalid credentials"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# ================= RESUME ANALYZER =================
@app.route("/analyze")
def analyze():
    return render_template("analyze.html")

@app.route("/analyze-result", methods=["POST"])
def analyze_result():
    result = predict_career(request.form.get("resume", ""))
    if "user_id" in session:
        update_resume_score(session["user_id"])
        log_activity(session["user_id"], "Analyzed resume")
    return jsonify(result)

@app.route("/analyze-file", methods=["POST"])
def analyze_file():
    file = request.files.get("resume_file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    text = ""

    try:
        if file.filename.endswith(".pdf"):
            with pdfplumber.open(file) as pdf:
                for page in pdf.pages:
                    if page.extract_text():
                        text += page.extract_text()
        elif file.filename.endswith(".docx"):
            doc = docx.Document(file)
            for p in doc.paragraphs:
                text += p.text
        else:
            return jsonify({"error": "Unsupported format"}), 400

        result = predict_career(text)

        if "user_id" in session:
            update_resume_score(session["user_id"])
            log_activity(session["user_id"], "Analyzed resume file")

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ================= RESUME BUILDER =================
@app.route("/resume-builder")
def resume_builder():
    return render_template("resume_builder.html")

@app.route("/build-resume", methods=["POST"])
def build_resume():
    session["resume_data"] = dict(request.form)
    return render_template("resume_preview.html", data=session["resume_data"])

@app.route("/download-resume")
def download_resume():
    data = session.get("resume_data", {})
    file_path = "resume.pdf"

    c = canvas.Canvas(file_path, pagesize=A4)
    text = c.beginText(40, 800)

    for k, v in data.items():
        text.textLine(f"{k.upper()}: {v}")
        text.textLine("")

    c.drawText(text)
    c.save()

    return send_file(file_path, as_attachment=True)

# ================= UPLOAD RESUME =================
@app.route("/upload-resume", methods=["GET", "POST"])
def upload_resume():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        file = request.files.get("resume")

        if file:
            filename = f"user_{session['user_id']}_resume.pdf"
            filepath = os.path.join(RESUME_FOLDER, filename)

            file.save(filepath)

            conn = get_db()
            conn.execute(
                "UPDATE users SET resume_file=? WHERE id=?",
                (filename, session["user_id"])
            )
            conn.commit()
            conn.close()

            log_activity(session["user_id"], "Uploaded resume")
            return redirect(url_for("candidate_profile", user_id=session["user_id"]))

    return render_template("upload_resume.html")

# ================= PROJECTS =================
@app.route("/add-project", methods=["GET", "POST"])
def add_project():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        conn = get_db()
        conn.execute("""
            INSERT INTO projects(user_id,title,description,link,created_at)
            VALUES (?,?,?,?,?)
        """, (
            session["user_id"],
            request.form["title"],
            request.form["description"],
            request.form["link"],
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))
        conn.commit()
        conn.close()

        update_activity_score(session["user_id"], 10)
        log_activity(session["user_id"], "Added project")
        return redirect(url_for("projects"))

    return render_template("add_project.html")

@app.route("/projects")
def projects():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    data = conn.execute("""
        SELECT title, description, link
        FROM projects
        WHERE user_id=?
        ORDER BY id DESC
    """, (session["user_id"],)).fetchall()
    conn.close()

    return render_template("projects.html", projects=data)

# ================= GALLERY =================
@app.route("/gallery")
def gallery():
    if "user_id" not in session:
        return redirect(url_for("login"))

    uid = session["user_id"]

    files = [
        f for f in os.listdir(UPLOAD_FOLDER)
        if f.startswith(f"user_{uid}_")
    ]

    return render_template(
        "gallery.html",
        files=files,
        likes=likes,
        comments=comments
    )

@app.route("/upload", methods=["POST"])
def upload():
    if "user_id" not in session:
        return redirect(url_for("login"))

    file = request.files.get("file")
    if not file:
        return redirect(url_for("gallery"))

    filename = f"user_{session['user_id']}_" + file.filename
    file.save(os.path.join(UPLOAD_FOLDER, filename))

    update_activity_score(session["user_id"], 5)
    log_activity(session["user_id"], "Uploaded certificate")

    return redirect(url_for("gallery"))

# ================= FEED =================
@app.route("/feed")
def feed():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    feed_data = conn.execute("""
        SELECT users.name, activities.action, activities.created_at
        FROM activities
        JOIN connections ON activities.user_id = connections.following_id
        JOIN users ON users.id = activities.user_id
        WHERE connections.follower_id=?
        ORDER BY activities.id DESC
    """, (session["user_id"],)).fetchall()
    conn.close()

    return render_template("feed.html", feed=feed_data)

# ================= FOLLOW / UNFOLLOW =================
@app.route("/follow/<int:user_id>")
def follow(user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["user_id"] == user_id:
        return redirect(url_for("candidate_profile", user_id=user_id))

    conn = get_db()

    existing = conn.execute("""
        SELECT 1 FROM connections
        WHERE follower_id=? AND following_id=?
    """, (session["user_id"], user_id)).fetchone()

    if not existing:
        conn.execute("""
            INSERT INTO connections (follower_id, following_id, created_at)
            VALUES (?, ?, ?)
        """, (
            session["user_id"],
            user_id,
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))
        conn.commit()

        update_activity_score(session["user_id"], 2)
        log_activity(session["user_id"], "Followed user")

    conn.close()
    return redirect(url_for("candidate_profile", user_id=user_id))

@app.route("/unfollow/<int:user_id>")
def unfollow(user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    conn.execute("""
        DELETE FROM connections
        WHERE follower_id=? AND following_id=?
    """, (session["user_id"], user_id))
    conn.commit()
    conn.close()

    log_activity(session["user_id"], "Unfollowed user")

    return redirect(url_for("candidate_profile", user_id=user_id))

# ================= FOLLOWERS =================
@app.route("/followers/<int:user_id>")
def followers(user_id):
    conn = get_db()

    users = conn.execute("""
        SELECT users.id, users.name, users.email
        FROM connections
        JOIN users ON users.id = connections.follower_id
        WHERE connections.following_id=?
        ORDER BY users.name
    """, (user_id,)).fetchall()

    conn.close()
    return render_template("followers.html", users=users, title="Followers")

# ================= FOLLOWING =================
@app.route("/following/<int:user_id>")
def following(user_id):
    conn = get_db()

    users = conn.execute("""
        SELECT users.id, users.name, users.email
        FROM connections
        JOIN users ON users.id = connections.following_id
        WHERE connections.follower_id=?
        ORDER BY users.name
    """, (user_id,)).fetchall()

    conn.close()
    return render_template("followers.html", users=users, title="Following")

# ================= SUGGESTIONS =================
@app.route("/suggestions")
def suggestions():
    if "user_id" not in session:
        return redirect(url_for("login"))

    uid = session["user_id"]
    conn = get_db()

    users = conn.execute("""
        SELECT DISTINCT u.id, u.name
        FROM connections c1
        JOIN connections c2 ON c1.following_id = c2.follower_id
        JOIN users u ON u.id = c2.following_id
        WHERE c1.follower_id = ?
          AND u.id NOT IN (
              SELECT following_id FROM connections WHERE follower_id = ?
          )
          AND u.id != ?
        LIMIT 10
    """, (uid, uid, uid)).fetchall()

    conn.close()
    return render_template("suggestions.html", users=users)

# ================= SEARCH =================
@app.route("/search")
def search():
    q = request.args.get("q", "")
    conn = get_db()

    users = conn.execute("""
        SELECT id,name,email
        FROM users
        WHERE name LIKE ? OR email LIKE ?
    """, (f"%{q}%", f"%{q}%")).fetchall()

    conn.close()
    return render_template("search_results.html", results=users)

# ================= ADMIN =================
@app.route("/admin/signup", methods=["GET", "POST"])
def admin_signup():
    if request.method == "POST":
        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO admins(name,email,password)
                VALUES (?,?,?)
            """, (
                request.form["name"],
                request.form["email"],
                request.form["password"]
            ))
            conn.commit()
            conn.close()
            return redirect(url_for("admin_login"))
        except sqlite3.IntegrityError:
            conn.close()
            return "Admin email already exists. Try another email."

    return render_template("admin_signup.html")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        conn = get_db()
        admin = conn.execute("""
            SELECT * FROM admins
            WHERE email=? AND password=?
        """, (
            request.form["email"],
            request.form["password"]
        )).fetchone()
        conn.close()

        if admin:
            session["admin"] = admin[1]
            session["admin_id"] = admin[0]
            return redirect(url_for("admin_dashboard"))

        return "Invalid admin credentials"

    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    session.pop("admin_id", None)
    return redirect(url_for("home"))

@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()
    users = conn.execute("""
        SELECT id,name,email,phone,linkedin,github,resume_file,resume_score,activity_score,
        (resume_score+activity_score) AS total_score
        FROM users
        ORDER BY total_score DESC
    """).fetchall()
    conn.close()

    return render_template("admin_dashboard.html", users=users)

# ================= CANDIDATE PROFILE =================
@app.route("/candidate/<int:user_id>")
def candidate_profile(user_id):
    conn = get_db()

    user = conn.execute("""
        SELECT name,email,phone,linkedin,github,resume_score,activity_score,resume_file
        FROM users WHERE id=?
    """, (user_id,)).fetchone()

    if not user:
        conn.close()
        return "User not found"

    viewer = session.get("user_id")

    # Check if logged-in user follows this profile
    is_following = False
    if viewer and viewer != user_id:
        check_follow = conn.execute("""
            SELECT 1 FROM connections
            WHERE follower_id=? AND following_id=?
        """, (viewer, user_id)).fetchone()

        if check_follow:
            is_following = True

    # Privacy: owner or follower can view projects/certificates
    can_view = False
    if viewer == user_id:
        can_view = True
    else:
        relation = conn.execute("""
            SELECT 1 FROM connections
            WHERE follower_id=? AND following_id=?
        """, (viewer, user_id)).fetchone()

        if relation:
            can_view = True

    projects = []
    certificates = []

    if can_view:
        projects = conn.execute("""
            SELECT title,description,link
            FROM projects
            WHERE user_id=?
            ORDER BY id DESC
        """, (user_id,)).fetchall()

        certificates = [
            f for f in os.listdir(UPLOAD_FOLDER)
            if f.startswith(f"user_{user_id}_")
        ]

    followers_count = conn.execute("""
        SELECT COUNT(*) FROM connections WHERE following_id=?
    """, (user_id,)).fetchone()[0]

    following_count = conn.execute("""
        SELECT COUNT(*) FROM connections WHERE follower_id=?
    """, (user_id,)).fetchone()[0]

    conn.close()

    return render_template(
        "candidate_profile.html",
        user=user,
        projects=projects,
        certificates=certificates,
        followers_count=followers_count,
        following_count=following_count,
        user_id=user_id,
        can_view=can_view,
        is_following=is_following
    )

# ================= CHATBOT =================
@app.route("/chatbot", methods=["POST"])
def chatbot():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"reply": "No message received."})

        user_msg = data.get("message", "").strip().lower()

        if any(word in user_msg for word in ["login", "log in", "sign in"]):
            reply = "To login, click the Login button in the navbar and enter your registered email and password."

        elif any(word in user_msg for word in ["signup", "sign up", "register", "create account", "new account"]):
            reply = "To create a new account, click Signup in the navbar, fill in your details, and submit the form."

        elif any(word in user_msg for word in ["resume", "cv"]):
            if any(word in user_msg for word in ["upload", "where", "add"]):
                reply = "Login first, then on the Home page you will see the 'Upload Resume' card. Choose your PDF resume and click Upload Resume."
            elif any(word in user_msg for word in ["analyze", "analysis", "check"]):
                reply = "Go to Resume Analyzer section and either paste your resume text or upload a PDF/DOCX file for analysis."
            elif any(word in user_msg for word in ["build", "create", "make"]):
                reply = "Go to Resume Builder, fill your details, preview the resume, and download it as PDF."
            else:
                reply = "You can upload, analyze, or build a resume using the Resume tools available on the Home page."

        elif any(word in user_msg for word in ["project", "projects"]):
            if any(word in user_msg for word in ["add", "upload", "create", "post"]):
                reply = "To add a project, login first, then open Add Project section, fill title, description, and project link, then submit."
            elif any(word in user_msg for word in ["view", "see", "show"]):
                reply = "To view projects, open the Projects section. Your own projects are always visible to you. Other users' projects are visible only if you follow them."
            else:
                reply = "Projects help users showcase their work. You can add and view projects from the Projects section."

        elif any(word in user_msg for word in ["certificate", "certificates", "gallery", "achievement", "achievements"]):
            if any(word in user_msg for word in ["upload", "add", "post"]):
                reply = "To upload a certificate, login first, go to Gallery section, choose a file, and upload it."
            elif any(word in user_msg for word in ["view", "see", "show"]):
                reply = "Your own certificates are visible to you. Other users' certificates are visible only if you follow them."
            else:
                reply = "Gallery section is used for certificates and achievements upload/view."

        elif any(word in user_msg for word in ["follow", "following", "followers", "connect", "connection"]):
            if "unfollow" in user_msg:
                reply = "To unfollow a user, open their profile and click the Unfollow button."
            else:
                reply = "To follow someone, open their profile and click the Follow button. After following, you can view their projects and certificates."

        elif any(word in user_msg for word in ["search", "find", "look for"]):
            reply = "Use the search bar in the navbar to search users by name or email."

        elif any(word in user_msg for word in ["admin", "administrator"]):
            reply = "Admin can manage users, view resumes, projects, certificates, and rankings."

        elif any(word in user_msg for word in ["profile", "account"]):
            reply = "Each user has a profile containing personal details, resume score, activity score, projects, followers, following, and certificates."

        elif any(word in user_msg for word in ["score", "resume score", "activity score", "ranking"]):
            reply = "Resume Score increases when users analyze/upload resumes. Activity Score increases when users add projects, upload certificates, or follow others."

        elif any(word in user_msg for word in ["help", "support", "issue", "problem", "trouble"]):
            reply = "I can help you with login, signup, resume upload, resume analysis, resume builder, projects, certificates, follow system, admin dashboard, and search."

        elif any(word in user_msg for word in ["hi", "hello", "hey"]):
            reply = "Hello 👋 I am your AI Help Assistant. Ask me anything about this portfolio platform."

        else:
            reply = (
                "I didn't fully understand that. Try asking:\n"
                "- How to upload resume?\n"
                "- How to login?\n"
                "- How to add project?\n"
                "- How to upload certificate?\n"
                "- How to follow users?\n"
                "- What can admin do?"
            )

        return jsonify({"reply": reply})

    except Exception as e:
        print("Chatbot Error:", e)
        return jsonify({"reply": "⚠️ Something went wrong on the server."}), 500

# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)