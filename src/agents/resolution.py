import logging
from datetime import datetime
import pytz

from src.models.state import AgentState
from src.db.connection import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)

def get_current_time_with_ms():
    return datetime.now(pytz.timezone('US/Eastern')).strftime('%H:%M:%S.%f')[:-3]

class ConflictResolverAgent:
    def __call__(self, state: AgentState) -> AgentState:
        logger.debug(f"Entering {self.__class__.__name__} call...")
        patient = state["patient"]
        bed_status = state["status"]["BedManager"]
        doctor_status = state["status"]["DoctorScheduler"]
        
        patient.calculate_priority()
        state["logs"].append(f"[{get_current_time_with_ms()}] {self.__class__.__name__} : Calculated priority score : {patient.priority_score}")
        
        conn = get_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            
            if bed_status == "Success" and doctor_status == "Success":
                # Both succeeded -> Commit the case
                cursor.execute("""
                    INSERT INTO ongoing_cases(patient_id, doctor_id, room_number)
                    VALUES ((SELECT patient_id FROM patient_info WHERE email = %s), %s, %s);
                """, (patient.email, state["cache"]["doctor_assigned"][0], state["cache"]["bed_assigned"][0]))
                conn.commit()
                
                state["logs"].append(f"[{get_current_time_with_ms()}] {self.__class__.__name__} : Assigning available doctor and bed to {patient.name}")
                state["status"]["ConflictResolver"] = "Success"
                
            elif bed_status == "Success" and doctor_status == "Failed":
                # Bed success, Doctor fail -> Release Bed and Queue
                cursor.execute("UPDATE rooms SET is_occupied=FALSE WHERE room_number = %s;", (patient.assigned_bed,))
                conn.commit()
                state["logs"].append(f"[{get_current_time_with_ms()}] {self.__class__.__name__} : No doctors available. Releasing bed and queuing application.")
                state["status"]["ConflictResolver"] = "Queued"
                
            elif bed_status == "Failed" and doctor_status == "Success":
                # Doctor success, Bed fail -> Release Doctor and Queue
                cursor.execute("UPDATE doctors SET is_busy=FALSE, busy_from=NULL, busy_till=NULL WHERE doctor_id = %s;", (state["cache"]["doctor_assigned"][0],))
                conn.commit()
                state["logs"].append(f"[{get_current_time_with_ms()}] {self.__class__.__name__} : No beds available. Releasing doctor and queuing application.")
                state["status"]["ConflictResolver"] = "Queued"
                
            else:
                # Both failed
                state["logs"].append(f"[{get_current_time_with_ms()}] {self.__class__.__name__} : No beds and doctors available at this moment. Please try at nearby hospitals.")
                state["status"]["ConflictResolver"] = "Failed"
            
            # Handle queuing logic if needed
            if state["status"]["ConflictResolver"] == "Queued":
                target_room_type = patient.bed_priority[0] if bed_status == "Failed" else state["cache"]["bed_assigned"][1]
                cursor.execute("""
                    INSERT INTO queue VALUES (
                        (SELECT patient_id FROM patient_info WHERE email=%s), %s, %s
                    );
                """, (patient.email, patient.priority_score, target_room_type))
                conn.commit()
                state["status"]["ConflictResolver"] = "Success" # Mark resolution as complete
                
        except Exception as e:
            logger.error(f"Error in ConflictResolver: {e}")
            conn.rollback()
            state["status"]["ConflictResolver"] = "Failed"
        finally:
            if cursor: cursor.close()
            release_db_connection(conn)
            
        return state