import os
import json
import logging
from datetime import datetime
import pytz
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from src.models.state import AgentState
from src.db.connection import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)


def get_current_time_with_ms():
    return datetime.now(pytz.timezone("US/Eastern")).strftime("%H:%M:%S.%f")[:-3]


def adjust_mood_based_on_vitals(patient, detected_mood):
    symptoms_str = " ".join(patient.symptoms).lower()
    if (
        patient.vitals.get("heart_rate", 80) > 120
        or patient.vitals.get("blood_pressure", {}).get("diastolic", 80) < 80
    ):
        return "panicked"
    elif "cardiac arrest" in symptoms_str:
        return "panicked"
    elif "mild cough" in symptoms_str and patient.vitals.get("heart_rate", 80) < 100:
        return "calm"
    return detected_mood


class MentalHealthAnalyzerAgent:
    def __init__(self):
        self._GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        self.llm = ChatGroq(
            api_key=self._GROQ_API_KEY, model_name="llama-3.3-70b-versatile"
        )

    def __call__(self, state: AgentState) -> AgentState:
        logger.debug(f"Entering {self.__class__.__name__} call...")
        patient = state["patient"]
        blood_pressure = patient.vitals.get("blood_pressure", {})
        systolic = blood_pressure.get("systolic", 120)
        diastolic = blood_pressure.get("diastolic", 80)

        # 1. Database Insertion with Connection Pool
        conn = get_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            # Note: Parameterized queries are generally safer for SQL injection,
            # but we are keeping your exact SQL logic for this iteration.
            query = f"""
                INSERT INTO patient_info(patient_name, email, phone, gender, symptoms, symptoms_duration, vitals)
                VALUES ('{patient.name}', '{patient.email}', NULL, '{patient.gender}',
                '{", ".join(patient.symptoms)}','{patient.symptom_duration}','{str(patient.vitals).replace("'","\"")}');
            """
            cursor.execute(query)
            conn.commit()
            logger.debug("Patient information inserted successfully...")
        except Exception as e:
            logger.error(f"Failed to insert patient: {e}")
            conn.rollback()
        finally:
            if cursor:
                cursor.close()
            release_db_connection(conn)

        # 2. LLM Invocation
        prompt = f"""Analyze patient's emotional state based on:
        - Vitals: BP {systolic}/{diastolic}, HR {patient.vitals.get("heart_rate", 80)}
        - Symptoms: {patient.symptoms}
        - Duration: {patient.symptom_duration} hours
        - Age: {patient.age}
        Return JSON: {{ "mood": "chosen_mood" }}"""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            logger.debug("Got mood estimate from LLM...")

            if "{" in response.content:
                mood_info = json.loads(
                    response.content[
                        response.content.find("{") : response.content.rfind("}") + 1
                    ]
                )
                if "mood" in mood_info:
                    detected_mood = adjust_mood_based_on_vitals(
                        patient, mood_info["mood"]
                    )
                    patient.mood = detected_mood

                    mood_emoji = {
                        "calm": "😌",
                        "frustrated": "😖",
                        "anxious": "😥",
                        "stressed": "😧",
                        "confused": "😵‍💫",
                        "panicked": "🫨",
                    }
                    emoji = mood_emoji.get(patient.mood, "")

                    state["logs"].append(
                        f"[{get_current_time_with_ms()}] {self.__class__.__name__} : Detected Mood is {patient.mood} {emoji}"
                    )
                    state["status"]["MoodAnalyzer"] = "Success"
        except Exception as e:
            logger.error(f"Error estimating the mood...\n{e}")
            state["logs"].append(
                f"[{get_current_time_with_ms()}] {self.__class__.__name__} : {str(e)}"
            )
            state["status"]["MoodAnalyzer"] = "Failed"

        return state
