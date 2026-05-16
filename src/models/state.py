from typing import TypedDict, List
import pytz
from datetime import datetime

def get_current_est_time():
    est = pytz.timezone('US/Eastern')
    return datetime.now(est)

class Patient:
    def __init__(self, name, vitals, email, gender, age, symptoms, symptom_duration):
        self.name = name
        self.symptoms = symptoms
        self.symptom_duration = symptom_duration
        self.email = email
        self.phone = None
        self.age = age
        self.vitals = vitals
        self.gender = gender
        self.mood = None
        self.triage_level = None
        self.department = None
        self.assigned_doctor = None
        self.assigned_bed = None
        self.bed_priority = None
        self.priority_score = 0.0
        self.entry_time = get_current_est_time()
        self.treatment_completed = False
        self.treatment_end_time = None

    def calculate_priority(self):
        triage_weight = 10
        # Default to 5 (lowest priority) if triage_level isn't set yet to avoid math errors
        triage_score = (self.triage_level or 5) * triage_weight
        
        if self.age >= 50:
            age_score = 8
        elif self.age < 15:
            age_score = 5
        else:
            age_score = 0
            
        hr = self.vitals.get("heart_rate", 80)
        bp_sys = self.vitals.get("blood_pressure", {}).get("systolic", 120)
        bp_dia = self.vitals.get("blood_pressure", {}).get("diastolic", 80)
        
        hr_dev = max(hr - 100, 60 - hr, 0)
        bp_sys_dev = abs(bp_sys - 120) if bp_sys > 140 or bp_sys < 90 else 0
        bp_dia_dev = abs(bp_dia - 80) if bp_dia > 90 or bp_dia < 60 else 0
        vital_score = (hr_dev + bp_sys_dev + bp_dia_dev) * 0.7
        
        duration_score = self.symptom_duration * 0.2
        
        self.priority_score = round(triage_score + age_score + vital_score + duration_score, 1)

    def to_dict(self):
        self.calculate_priority()
        return {
            "name": self.name,
            "symptoms": self.symptoms,
            "symptom_duration": self.symptom_duration,
            "contact_number": self.phone,
            "age": self.age,
            "email": self.email,
            "gender": self.gender,
            "mood": self.mood,
            "triage_level": self.triage_level,
            "department": self.department,
            "assigned_doctor": self.assigned_doctor,
            "assigned_bed": self.assigned_bed,
            "priority_score": self.priority_score,
            "treatment_completed": self.treatment_completed,
            "treatment_end_time": self.treatment_end_time.strftime('%H:%M:%S.%f')[:-3] if self.treatment_end_time else None,
            "entry_time": self.entry_time.strftime('%H:%M:%S.%f')[:-3]
        }

class AgentState(TypedDict):
    patient: Patient
    logs: List[str]
    status: dict
    cache: dict