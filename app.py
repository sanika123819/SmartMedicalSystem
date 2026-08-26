from flask import Flask, render_template, request, redirect, session
import sqlite3
import os

from datetime import datetime
from collections import deque

app = Flask(__name__)


def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS patients")
    c.execute("DROP TABLE IF EXISTS appointments")
    c.execute('''CREATE TABLE patients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, age TEXT, gender TEXT, phone TEXT, email TEXT UNIQUE, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS appointments (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_email TEXT, doctor TEXT, date TEXT, time TEXT)''')
    conn.commit()
    conn.close()

init_db()
app.secret_key = "smart_medical_secret_key"

DATABASE = "database.db"


# ---------------- DATABASE CONNECTION ----------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- CREATE DATABASE ----------------

def create_database():

    conn = get_db()
    cursor = conn.cursor()

    # Patient table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            phone TEXT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Doctor table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            doctor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialization TEXT NOT NULL,
            phone TEXT,
            available_time TEXT
        )
    """)

    # Appointment table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            doctor_id INTEGER,
            date TEXT,
            time TEXT,
            status TEXT,
            FOREIGN KEY(patient_id) REFERENCES patients(patient_id),
            FOREIGN KEY(doctor_id) REFERENCES doctors(doctor_id)
        )
    """)

    # Symptom history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS symptom_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            symptoms TEXT,
            possible_condition TEXT,
            checked_at TEXT,
            FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
        )
    """)

    # Insert doctors only if table is empty
    cursor.execute("SELECT COUNT(*) FROM doctors")
    count = cursor.fetchone()[0]

    if count == 0:

        doctors = [
            ("Dr. Patil", "General Physician",
             "9876543210", "10:00 AM - 1:00 PM"),

            ("Dr. Shah", "Dermatologist",
             "9876543211", "11:00 AM - 2:00 PM"),

            ("Dr. Joshi", "Cardiologist",
             "9876543212", "2:00 PM - 5:00 PM"),

            ("Dr. More", "Dentist",
             "9876543213", "10:00 AM - 4:00 PM"),

            ("Dr. Kulkarni", "Gastroenterologist",
             "9876543214", "3:00 PM - 6:00 PM")
        ]

        cursor.executemany("""
            INSERT INTO doctors
            (name, specialization, phone, available_time)
            VALUES (?, ?, ?, ?)
        """, doctors)

    conn.commit()
    conn.close()


# ---------------- SYMPTOM DATA ----------------

symptom_data = {

    "fever": {
        "conditions": ["Flu", "Viral Infection"],
        "doctor": "General Physician"
    },

    "cough": {
        "conditions": ["Cold", "Flu"],
        "doctor": "General Physician"
    },

    "headache": {
        "conditions": ["Migraine", "Flu"],
        "doctor": "General Physician"
    },

    "cold": {
        "conditions": ["Common Cold", "Flu"],
        "doctor": "General Physician"
    },

    "sore throat": {
        "conditions": ["Throat Infection", "Cold"],
        "doctor": "General Physician"
    },

    "stomach pain": {
        "conditions": ["Indigestion", "Gastritis"],
        "doctor": "Gastroenterologist"
    },

    "vomiting": {
        "conditions": ["Gastritis", "Food Infection"],
        "doctor": "Gastroenterologist"
    },

    "skin rash": {
        "conditions": ["Skin Allergy", "Dermatitis"],
        "doctor": "Dermatologist"
    },

    "tooth pain": {
        "conditions": ["Dental Problem"],
        "doctor": "Dentist"
    }
}


# ---------------- APPOINTMENT QUEUE ----------------

appointment_queue = deque()


# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        age = request.form["age"]
        gender = request.form["gender"]
        phone = request.form["phone"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                INSERT INTO patients
                (name, age, gender, phone, email, password)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, age, gender, phone, email, password))

            conn.commit()
            conn.close()

            return redirect("/login")

        except sqlite3.IntegrityError:

            conn.close()

            return "Email already registered."

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()

        patient = conn.execute("""
            SELECT * FROM patients
            WHERE email = ? AND password = ?
        """, (email, password)).fetchone()

        conn.close()

        if patient:

            session["patient_id"] = patient["id"]
            session["patient_name"] = patient["name"]

            return redirect("/dashboard")

        else:

            return "Invalid email or password."

    return render_template("login.html")


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    if "patient_id" not in session:
        return redirect("/login")

    return render_template(
        "dashboard.html",
        name=session["patient_name"]
    )


# ---------------- SYMPTOM CHECKER ----------------

@app.route("/symptoms", methods=["GET", "POST"])
def symptoms():

    if "patient_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        selected_symptoms = request.form.getlist("symptoms")

        # SET - remove duplicate symptoms
        unique_symptoms = set(selected_symptoms)

        conditions = set()
        doctors = set()

        for symptom in unique_symptoms:

            if symptom in symptom_data:

                conditions.update(
                    symptom_data[symptom]["conditions"]
                )

                doctors.add(
                    symptom_data[symptom]["doctor"]
                )

        if not conditions:

            result = "No matching condition found."
            suggested_doctor = "General Physician"

        else:

            result = ", ".join(conditions)
            suggested_doctor = ", ".join(doctors)

        # Save history
        conn = get_db()

        conn.execute("""
            INSERT INTO symptom_history
            (patient_id, symptoms, possible_condition, checked_at)
            VALUES (?, ?, ?, ?)
        """, (
            session["patient_id"],
            ", ".join(unique_symptoms),
            result,
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))

        conn.commit()
        conn.close()

        return render_template(
            "symptoms.html",
            result=result,
            suggested_doctor=suggested_doctor
        )

    return render_template(
        "symptoms.html",
        result=None
    )


# ---------------- FIND DOCTOR ----------------

@app.route("/doctors", methods=["GET", "POST"])
def doctors():

    if "patient_id" not in session:
        return redirect("/login")

    conn = get_db()

    if request.method == "POST":

        specialization = request.form["specialization"]

        doctor_list = conn.execute("""
            SELECT * FROM doctors
            WHERE specialization = ?
        """, (specialization,)).fetchall()

    else:

        doctor_list = conn.execute("""
            SELECT * FROM doctors
        """).fetchall()

    conn.close()

    return render_template(
        "doctors.html",
        doctors=doctor_list
    )


# ---------------- BOOK APPOINTMENT ----------------

@app.route("/book/<int:doctor_id>", methods=["GET", "POST"])
def book_appointment(doctor_id):

    if "patient_id" not in session:
        return redirect("/login")

    conn = get_db()

    doctor = conn.execute("""
        SELECT * FROM doctors
        WHERE doctor_id = ?
    """, (doctor_id,)).fetchone()

    if request.method == "POST":

        date = request.form["date"]
        time = request.form["time"]

        # Check whether slot already exists
        existing = conn.execute("""
            SELECT * FROM appointments
            WHERE doctor_id = ?
            AND date = ?
            AND time = ?
            AND status = 'Confirmed'
        """, (doctor_id, date, time)).fetchone()

        if existing:

            conn.close()

            return "This appointment slot is already booked."

        # Add patient to queue
        appointment_queue.append(
            session["patient_id"]
        )

        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO appointments
            (patient_id, doctor_id, date, time, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session["patient_id"],
            doctor_id,
            date,
            time,
            "Confirmed"
        ))

        conn.commit()

        appointment_id = cursor.lastrowid

        conn.close()

        return render_template(
            "appointment.html",
            success=True,
            appointment_id=appointment_id,
            doctor=doctor,
            date=date,
            time=time
        )

    conn.close()

    return render_template(
        "appointment.html",
        doctor=doctor,
        success=False
    )


# ---------------- APPOINTMENT HISTORY ----------------

@app.route("/history")
def history():

    if "patient_id" not in session:
        return redirect("/login")

    conn = get_db()

    appointments = conn.execute("""
        SELECT
            appointments.appointment_id,
            doctors.name,
            doctors.specialization,
            appointments.date,
            appointments.time,
            appointments.status
        FROM appointments

        JOIN doctors
        ON appointments.doctor_id = doctors.doctor_id

        WHERE appointments.patient_id = ?

        ORDER BY appointments.date, appointments.time
    """, (session["patient_id"],)).fetchall()

    conn.close()

    return render_template(
        "history.html",
        appointments=appointments
    )


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":

    create_database()

    app.run(debug=True)
    
