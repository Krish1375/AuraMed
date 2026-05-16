import logging
from langgraph.graph import StateGraph, END

from src.models.state import AgentState, Patient
from src.agents.analyzer import MentalHealthAnalyzerAgent
from src.agents.triage import EmergencyTriageAgent
from src.agents.scheduling import DoctorSchedulerAgent, BedManagerAgent
from src.agents.resolution import ConflictResolverAgent

logger = logging.getLogger(__name__)

def build_graph():
    """Compiles the LangGraph workflow for patient triage."""
    graph = StateGraph(AgentState)
    
    # Add our modular nodes
    graph.add_node("mood", MentalHealthAnalyzerAgent())
    graph.add_node("triage", EmergencyTriageAgent())
    graph.add_node("doctor", DoctorSchedulerAgent())
    graph.add_node("bed", BedManagerAgent())
    graph.add_node("checker", ConflictResolverAgent())
    
    # Define the strict edge flow
    graph.set_entry_point("mood")
    graph.add_edge("mood", "triage")
    graph.add_edge("triage", "doctor")
    graph.add_edge("doctor", "bed")
    graph.add_edge("bed", "checker")
    graph.add_edge("checker", END)
    
    return graph.compile()

# Create a singleton instance for our Streamlit UI to import later
smart_hospital_graph = build_graph()

def run_patient_flow(name, vitals, email, gender, age, symptoms, symptom_duration):
    """Initializes the state and kicks off the graph execution."""
    patient = Patient(name, vitals, email, gender, age, symptoms, symptom_duration)
    
    initial_state = {
        "patient": patient,
        "logs": [],
        "status": {
            "MoodAnalyzer": "Pending",
            "EmergencyTriage": "Pending",
            "DoctorScheduler": "Pending",
            "BedManager": "Pending",
            "ConflictResolver": "Pending"
        },
        "cache": {}
    }
    
    logger.info(f"Starting workflow for patient: {name}")
    return smart_hospital_graph.invoke(initial_state)