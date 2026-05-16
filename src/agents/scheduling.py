import logging
import random
from datetime import datetime, timedelta
import pytz

from src.models.state import AgentState
from src.db.connection import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)

def get_current_time_with_ms():
    return datetime.now(pytz.timezone('US/Eastern')).strftime('%H:%M:%S.%f')[:-3]

def get_block_duration(triage_level):
    return timedelta(minutes=max(1, triage_level or 5))

class DoctorSchedulerAgent:
    def __call__(self, state: AgentState) -> AgentState:
        logger.debug(f"Entering {self.__class__.__name__} call...")
        patient = state["patient"]
        dept = patient.department
        now = datetime.now(pytz.timezone('US/Eastern'))
        
        conn = get_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            logger.debug(f"Attempting to fetch available {dept} specialist doctors...")
            
            # Using parameterized query for safety
            cursor.execute("SELECT * FROM get_available_doctors(%s);", (dept,))
            available = cursor.fetchall()
            
            if available:
                assigned_doctor_details = random.choice(available)
                patient.assigned_doctor = assigned_doctor_details[1]
                state["cache"]["doctor_assigned"] = assigned_doctor_details
                
                block_duration = get_block_duration(patient.triage_level)
                blocked_until = now + block_duration
                
                state["cache"]["doctor_blocked_from"] = now
                state["cache"]["doctor_blocked_until"] = blocked_until
                
                logger.debug("Attempting to allocate doctor...")
                cursor.execute("""
                    UPDATE doctors SET is_busy = TRUE,
                                       busy_from = %s, 
                                       busy_till = %s
                                       WHERE doctor_id = %s;
                """, (now, blocked_until, assigned_doctor_details[0]))
                conn.commit()
                
                state["status"]["DoctorScheduler"] = "Success"
                state["logs"].append(f"[{get_current_time_with_ms()}] {self.__class__.__name__} : Assigned {patient.assigned_doctor} to {patient.name}")
            else:
                logger.debug("No doctors available...")
                state["logs"].append(f"[{get_current_time_with_ms()}] {self.__class__.__name__} : No {dept} doctor available.")
                state["status"]["DoctorScheduler"] = "Failed"
                
        except Exception as e:
            logger.error(f"Error in DoctorScheduler: {e}")
            conn.rollback()
            state["status"]["DoctorScheduler"] = "Failed"
        finally:
            if cursor: cursor.close()
            release_db_connection(conn)
            
        return state

class BedManagerAgent:
    def __call__(self, state: AgentState) -> AgentState:
        logger.debug(f"Entering {self.__class__.__name__} call...")
        patient = state["patient"]
        level = patient.triage_level or 5
        
        if level >= 5:
            patient.bed_priority = ["ICU", "Emergency"]
        elif level in [3, 4]:
            patient.bed_priority = ["Ward", "Emergency"]
        else:
            patient.bed_priority = ["Normal", "Ward", "Emergency"]
        
        conn = get_db_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            for bed_type in patient.bed_priority:
                logger.debug(f"Attempting to find available bed in {bed_type}...")
                cursor.execute("SELECT * FROM get_available_rooms(%s)", (bed_type,))
                available_bed_details = cursor.fetchall()
                
                if available_bed_details:
                    patient.assigned_bed = available_bed_details[0][0]
                    state["cache"]["bed_assigned"] = available_bed_details[0]
                    
                    cursor.execute("""
                        UPDATE rooms SET is_occupied = TRUE WHERE room_number = %s;
                    """, (available_bed_details[0][0],))
                    conn.commit()
                    
                    state["logs"].append(f"[{get_current_time_with_ms()}] {self.__class__.__name__} : {patient.name} assigned to {bed_type} bed {patient.assigned_bed} (triage {level})")
                    state["status"]["BedManager"] = "Success"
                    return state        
            
            logger.debug("No beds found...")
            state["logs"].append(f"[{get_current_time_with_ms()}] {self.__class__.__name__} : No beds available for {patient.name}")
            state["status"]["BedManager"] = "Failed"
            
        except Exception as e:
            logger.error(f"Error in BedManager: {e}")
            conn.rollback()
            state["status"]["BedManager"] = "Failed"
        finally:
            if cursor: cursor.close()
            release_db_connection(conn)
            
        return state