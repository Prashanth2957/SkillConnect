import joblib
import re

# ================= LOAD ML MODELS =================
model = joblib.load("model/resume_model.pkl")
vectorizer = joblib.load("model/vectorizer.pkl")

# ================= ROLE RULES =================
ROLE_RULES = {
    "Data Scientist": ["python", "machine learning", "ml", "data science", "pandas", "numpy"],
    "Backend Developer": ["java", "spring", "api", "mysql", "sql"],
    "Frontend Developer": ["html", "css", "javascript", "react", "ui"],
    "DevOps Engineer": ["aws", "docker", "kubernetes", "ci/cd"],
    "Data Analyst": ["excel", "power bi", "tableau", "sql"],

    # 🔥 NEW ROLES
    "Full Stack Java Developer": ["java", "spring", "html", "css", "javascript", "sql"],
    "Full Stack Web Developer": ["html", "css", "javascript", "react", "node", "express", "mongodb"],
    "AI/ML Engineer": ["python", "machine learning", "deep learning", "tensorflow", "pytorch"]
}

# ================= SALARY BASE =================
SALARY_BASE = {
    "Data Scientist": 8,
    "Backend Developer": 6,
    "Frontend Developer": 5,
    "DevOps Engineer": 10,
    "Data Analyst": 5,

    # 🔥 NEW
    "Full Stack Java Developer": 7,
    "Full Stack Web Developer": 6,
    "AI/ML Engineer": 9
}

# ================= REQUIRED SKILLS FOR ROLES =================
COURSE_SKILLS = {
    "Data Scientist": ["machine learning", "statistics", "deep learning"],
    "Backend Developer": ["spring boot", "microservices", "rest api"],
    "Frontend Developer": ["react", "ui/ux", "advanced javascript"],
    "DevOps Engineer": ["aws", "docker", "kubernetes"],
    "Data Analyst": ["excel", "power bi", "sql"],

    # 🔥 NEW
    "Full Stack Java Developer": ["spring boot", "react", "system design"],
    "Full Stack Web Developer": ["node js", "react", "mongodb"],
    "AI/ML Engineer": ["deep learning", "nlp", "model deployment"]
}

# ================= ROLE DECISION (RULE BASED) =================
def decide_role(text):
    text = text.lower()
    scores = {role: 0 for role in ROLE_RULES}

    for role, skills in ROLE_RULES.items():
        for skill in skills:
            if skill in text:
                scores[role] += 2

    best_role = max(scores, key=scores.get)

    if scores[best_role] == 0:
        return None
    return best_role

# ================= CGPA EXTRACTION =================
def extract_cgpa(text):
    match = re.search(r"cgpa[:\s]*([0-9]\.?[0-9]?)", text.lower())
    return float(match.group(1)) if match else None

# ================= PROJECT COUNT =================
def count_projects(text):
    return text.lower().count("project")

# ================= SALARY LOGIC =================
def calculate_salary(role, cgpa, projects):
    base = SALARY_BASE.get(role, 5)

    if cgpa:
        if cgpa >= 8:
            base += 2
        elif cgpa >= 7:
            base += 1

    if projects >= 3:
        base += 2
    elif projects >= 1:
        base += 1

    return f"₹{base} – {base+4} LPA"

# ================= SKILL GAP =================
def missing_skills(text, role):
    text = text.lower()
    required = COURSE_SKILLS.get(role, [])
    missing = []

    for skill in required:
        if skill not in text:
            missing.append(skill)

    return missing

# ================= MAIN PREDICTION FUNCTION =================
def predict_career(resume_text):

    text = resume_text.lower()

    # 1️⃣ Rule-based role detection
    smart_role = decide_role(text)

    # 2️⃣ ML-based role detection (backup)
    X = vectorizer.transform([resume_text])
    ml_role = model.predict(X)[0]

    # 3️⃣ Final Role Selection
    role = smart_role if smart_role else ml_role

    # 4️⃣ Extract intelligence
    cgpa = extract_cgpa(text)
    projects = count_projects(text)

    # 5️⃣ Salary calculation
    salary = calculate_salary(role, cgpa, projects)

    # 6️⃣ Missing skills → courses
    gaps = missing_skills(text, role)
    courses = [f"{s.title()} Course" for s in gaps]
    if not courses:
        courses = ["Advanced Career Development"]

    return {
        "prediction": role,
        "salary": salary,
        "courses": courses,
        "cgpa": cgpa,
        "projects": projects
    }
