import os
import json
import logging
from datetime import datetime
import pytz
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from src.models.state import AgentState

logger = logging.getLogger(__name__)


def get_current_time_with_ms():
    return datetime.now(pytz.timezone("US/Eastern")).strftime("%H:%M:%S.%f")[:-3]


class EmergencyTriageAgent:
    def __init__(self):
        self._GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        self.llm = ChatGroq(
            api_key=self._GROQ_API_KEY, model_name="llama-3.3-70b-versatile"
        )

    def __call__(self, state: AgentState) -> AgentState:
        logger.debug(f"Entering {self.__class__.__name__} call...")
        patient = state["patient"]
        bp = patient.vitals.get("blood_pressure", {})
        hr = patient.vitals.get("heart_rate", 80)

        # Stricter prompt to prevent markdown and conversational filler
        prompt = f"""Assign triage_level (1-5) and department based on:
        - Symptoms: {patient.symptoms}
        - BP: {bp.get('systolic', 120)}/{bp.get('diastolic', 80)}
        - HR: {hr}
        - Mood: {patient.mood}
        - Age: {patient.age}
        - Duration: {patient.symptom_duration}h
        
        CRITICAL INSTRUCTION: Return ONLY a raw JSON dictionary. Do not use markdown blocks, backticks, or any conversational text.
        Format EXACTLY like this:
        {{"triage_level": 1, "department": "Cardiology"}}
        
        Return value of department MUST be one of: ["Cardiology","Pediatrics","Neurology","Dentist"]"""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            logger.debug("Got triage level from the LLM...")

            # Clean up potential markdown formatting just in case Llama ignores instructions
            raw_content = (
                response.content.replace("```json", "").replace("```", "").strip()
            )

            if "{" in raw_content:
                json_str = raw_content[
                    raw_content.find("{") : raw_content.rfind("}") + 1
                ]
                triage_info = json.loads(json_str)

                if "triage_level" in triage_info and "department" in triage_info:
                    patient.triage_level = triage_info["triage_level"]
                    patient.department = triage_info["department"]

                    state["logs"].append(
                        f"[{get_current_time_with_ms()}] {self.__class__.__name__} : Level {patient.triage_level} -> {patient.department}"
                    )
                    state["status"]["EmergencyTriage"] = "Success"
        except Exception as e:
            logger.error(f"Error estimating the triage...\n{e}")
            state["logs"].append(
                f"[{get_current_time_with_ms()}] {self.__class__.__name__} : Error estimating the triage : {str(e)}"
            )
            state["status"]["EmergencyTriage"] = "Failed"

        return state
