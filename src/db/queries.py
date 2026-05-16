from src.db.connection import get_db_connection, release_db_connection
import logging

logger = logging.getLogger(__name__)

def get_beds():
    conn = get_db_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        query = """
            SELECT DISTINCT type,
                    (SELECT COUNT(*) FROM rooms r1 WHERE r1.type = r.type AND is_occupied = FALSE) available,
                    (SELECT COUNT(*) FROM rooms r1 WHERE r1.type = r.type AND is_occupied = TRUE) blocked 
            FROM rooms r;
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        output = {}
        for data in rows:
            output[data[0]] = data[1:]
        return output
    finally:
        if cursor: 
            cursor.close()
        release_db_connection(conn)

def get_doctor_status():
    conn = get_db_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        logger.debug("Getting doctor status update...")
        query = "SELECT refresh_data();"
        cursor.execute(query)
        conn.commit()
        
        query = """
            SELECT
                d.name doctor_name,
                d.specialist department,
                (CASE WHEN d.is_busy=TRUE THEN 'BUSY' ELSE 'AVAILABLE' END) status,
                (CASE WHEN d.is_busy=TRUE THEN p.patient_name ELSE NULL END) with_patient,
                (CASE WHEN d.is_busy=TRUE THEN ROUND(EXTRACT(EPOCH FROM (d.busy_till - CURRENT_TIMESTAMP)) / 60,2) ELSE NULL END) time_remaining,
                (CASE WHEN d.is_busy=TRUE THEN d.busy_till ELSE NULL END) finish_time,
                (CASE WHEN d.is_busy=TRUE THEN d.busy_from ELSE NULL END) start_time
            FROM doctors d
            LEFT JOIN ongoing_cases oc
            ON d.doctor_id = oc.doctor_id
            LEFT JOIN patient_info p
            ON oc.patient_id = p.patient_id;
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Cleaned up dict mapping using zip
        cols = ["doctor_name","department","status","with_patient","time_remaining","finish_time","start_time"]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        if cursor: 
            cursor.close()
        release_db_connection(conn)