import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
import joblib

data = {
    "resume": [
        "python machine learning data science",
        "java spring boot backend developer",
        "html css javascript frontend developer",
        "cloud aws devops docker kubernetes",
        "data analyst excel powerbi sql"
    ],
    "job": [
        "Data Scientist",
        "Backend Developer",
        "Frontend Developer",
        "DevOps Engineer",
        "Data Analyst"
    ]
}

df = pd.DataFrame(data)

vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(df["resume"])
y = df["job"]

model = MultinomialNB()
model.fit(X, y)

joblib.dump(model, "../model/resume_model.pkl")
joblib.dump(vectorizer, "../model/vectorizer.pkl")

print("Model trained successfully")
