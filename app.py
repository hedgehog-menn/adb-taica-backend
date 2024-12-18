# Install these lib before running
# pip install flask flask-cors neo4j-driver shapely python-dotenv
# if using `conda install` change "neo4j-driver" -to-> "neo4j-python-driver"

from flask import Flask, request, jsonify
from neo4j import GraphDatabase
from flask_cors import CORS
import json
from shapely.geometry import Point, shape
from functools import lru_cache
import os
from dotenv import load_dotenv

app = Flask(__name__)
CORS(app)

load_dotenv()
neo4j_uri = os.getenv('NEO4J_URI')
neo4j_username = os.getenv('NEO4J_USERNAME')
neo4j_password = os.getenv('NEO4J_PASSWORD')


# Update with your Neo4j credentials
driver = GraphDatabase.driver(
    # 'bolt://localhost:7687',
    neo4j_uri,
    auth=(neo4j_username, neo4j_password)
)

@app.route('/api/universities')
def get_universities():
   uni_id = request.args.get('id', '')
   name = request.args.get('name', '')

   query = '''
   MATCH (u:University)
   WHERE
       (SIZE($id) = 0 OR u.UniversityID = $id) AND
       (SIZE($name) = 0 OR u.UniversityName CONTAINS $name)
   RETURN u
   '''

   with driver.session() as session:
       result = session.run(query, {
           'id': uni_id,
           'name': name
       })
       universities = [dict(record["u"]) for record in result]
       return jsonify(universities)

@app.route('/api/students')
def get_students():
    email = request.args.get('email', '')
    phone = request.args.get('phone', '')
    student_id = request.args.get('id', '')
    name = request.args.get('name', '')

    query = '''
    MATCH (s:Student)
    WHERE
        (SIZE($email) = 0 OR s.Email CONTAINS $email) AND
        (SIZE($phone) = 0 OR s.PhoneNumber CONTAINS $phone) AND
        (SIZE($id) = 0 OR s.StudentID = $id) AND
        (SIZE($name) = 0 OR s.StudentName CONTAINS $name)
    RETURN s
    '''

    with driver.session() as session:
        result = session.run(query, {
            'email': email,
            'phone': phone,
            'id': student_id,
            'name': name
        })
        students = [dict(record["s"]) for record in result]
        return jsonify(students)

@app.route('/api/departments')
def get_departments():
    with driver.session() as session:
        result = session.run('MATCH (d:Department) RETURN d')
        departments = [dict(record["d"]) for record in result]
        return jsonify(departments)

@app.route('/api/taiwan-regions')
def get_taiwan_regions():
    with open('tw.json', 'r') as f:
        return jsonify(json.load(f))

@lru_cache()
def load_regions():
    with open('tw.json', 'r') as f:
        geojson = json.load(f)
        regions = {}
        for feature in geojson['features']:
            regions[feature['properties']['name']] = shape(feature['geometry'])
        return regions

@app.route('/api/students-by-region')
def get_students_by_region():
    try:
        regions = load_regions()

        with driver.session() as session:
            result = session.run("MATCH (s:Student) RETURN s.geoPoint as point")
            student_counts = {name: 0 for name in regions.keys()}

            for record in result:
                point_data = record["point"]
                if point_data:
                    try:
                        # Parse Neo4j point format
                        coords = str(point_data).replace('POINT(', '').replace(')', '').split()
                        pt = Point(float(coords[0]), float(coords[1]))

                        for region_name, region_shape in regions.items():
                            if region_shape.contains(pt):
                                student_counts[region_name] += 1
                                break
                    except Exception as e:
                        print(f"Point error: {e}, point: {point_data}")
                        continue

            return jsonify(student_counts)
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/master-courses')
def get_master_courses():
   course_id = request.args.get('id', '')
   name = request.args.get('name', '')
   credit = request.args.get('credit', '')
   licensing = request.args.get('licensing', '')
   professor = request.args.get('professor', '')

   query = '''
   MATCH (c:MasterCourse)
   WHERE
       (SIZE($id) = 0 OR c.CourseID = $id) AND
       (SIZE($name) = 0 OR c.CourseName CONTAINS $name) AND
       (SIZE($credit) = 0 OR c.Credit = toInteger($credit)) AND
       (SIZE($licensing) = 0 OR c.LicensingType CONTAINS $licensing) AND
       (SIZE($professor) = 0 OR c.ProfessorName CONTAINS $professor)
   RETURN c
   '''

   with driver.session() as session:
       result = session.run(query, {
           'id': course_id,
           'name': name,
           'credit': credit,
           'licensing': licensing,
           'professor': professor
       })
       courses = [dict(record["c"]) for record in result]
       return jsonify(courses)

@app.route('/api/satellite-courses')
def get_satellite_courses():
    course_id = request.args.get('id', '')
    name = request.args.get('name', '')
    professor = request.args.get('professor', '')

    query = '''
    MATCH (c:SatelliteCourse)
    WHERE
        (SIZE($id) = 0 OR c.SCourseID = $id) AND
        (SIZE($name) = 0 OR c.CourseName CONTAINS $name) AND
        (SIZE($professor) = 0 OR c.ProfessorName CONTAINS $professor)
    RETURN c
    '''

    with driver.session() as session:
        result = session.run(query, {
            'id': course_id,
            'name': name,
            'professor': professor
        })
        courses = [dict(record["c"]) for record in result]
        return jsonify(courses)

# Semester Enrollment
@app.route('/api/semester-enrollment')
def get_semester_enrollment():
    year = request.args.get('year', '')
    semester = request.args.get('semester', '')

    if not year or not semester:
        return jsonify({"error": "Year and semester parameters are required"}), 400

    semester_id = f"S{year}{semester}"

    query = '''
    MATCH (s:Student)-[:ENROLLED_IN]->(e:Enrollment)-[:FOR]->(sem:Semester {SemesterID: $semesterId}),
         (e)-[:FOR]->(c)
    RETURN
        s.StudentID AS StudentID,
        e.EnrollmentID AS EnrollmentID,
        e.EnrollmentStatus AS Status,
        e.Grade AS Grade,
        e.StandardizedGPA AS GPA,
        c.CourseName AS CourseName
    ORDER BY s.StudentID
    '''

    with driver.session() as session:
        result = session.run(query, {'semesterId': semester_id})
        enrollments = [dict(record) for record in result]
        return jsonify(enrollments)

@app.route('/api/university-total-students')
def get_university_total_students():
    query = '''
    MATCH (u:University)-[:REGISTERED_AT]-(sr:StudentRegistration)<-[:HAS_REGISTRATION]-(s:Student)
    RETURN u.UniversityName AS UniversityName, count(s) AS TotalStudents;
    '''
    with driver.session() as session:
        result = session.run(query)
        body = [dict(record) for record in result]
        return jsonify(body)

@app.route('/api/university-student-status')
def get_university_student_status():
    # Get filter parameters from request with empty string defaults
    student_id = request.args.get('student_id', '')
    student_name = request.args.get('student_name', '')
    university_name = request.args.get('university', '')
    registration_status = request.args.get('status', '')

    # Build the WHERE clause dynamically based on provided parameters
    conditions = []
    params = {}

    if student_id:
        conditions.append("s.StudentID = $student_id")
        params['student_id'] = student_id
    
    if student_name:
        conditions.append("s.StudentName CONTAINS $student_name")
        params['student_name'] = student_name
    
    if university_name:
        conditions.append("u.UniversityName CONTAINS $university_name")
        params['university_name'] = university_name
    
    if registration_status:
        conditions.append("sr.RegistrationStatus = $registration_status")
        params['registration_status'] = registration_status

    # Construct the final query
    query = '''
    MATCH (s:Student)-[:HAS_REGISTRATION]->(sr:StudentRegistration)-[:REGISTERED_AT]->(u:University)
    '''

    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)

    query += '''
    RETURN
        s.StudentID AS StudentID,
        s.StudentName AS StudentName,
        u.UniversityName AS UniversityName,
        sr.RegistrationStatus AS RegistrationStatus
    '''
    with driver.session() as session:
        result = session.run(query, params)
        body = [dict(record) for record in result]
        return jsonify(body)

@app.route('/api/course-approvement')
def get_course_approvement():
    query = '''
    MATCH (mc:MasterCourse)-[:APPROVED_BY]->(approval:Approval)
    RETURN
        mc.CourseID AS CourseID,
        mc.CourseName AS CourseName,
        approval.CentralOfficeApproval AS CentralOfficeApproval,
        approval.CommitteeApproval AS CommitteeApproval
    '''
    with driver.session() as session:
        result = session.run(query)
        body = [dict(record) for record in result]
        return jsonify(body)

@app.route('/api/student-credits')
def get_student_credits():
    student_id = request.args.get('id', '')
    
    if not student_id:
        return jsonify({"error": "id (Student ID) parameter is required"}), 400

    query = '''
    MATCH (s:Student {StudentID: $student_id})-[:ENROLLED_IN]->(e:Enrollment {EnrollmentStatus: "Completed"})-[:FOR]->(sem:Semester {SemesterID: "S2024F"}),
        (e)-[:FOR]->(c)
    RETURN 
        s.StudentID AS StudentID,
        s.StudentName AS StudentName,
        SUM(c.Credit) AS TotalCompletedCredits;
    '''

    with driver.session() as session:
        result = session.run(query, {'student_id': student_id})
        credits = [dict(record) for record in result]
        return jsonify(credits)

@app.route('/api/course-announcement')
def get_course_announcement():
    course_id = request.args.get('id', '')
    title = request.args.get('title', '')
    type = request.args.get('type', '')
    date = request.args.get('date', '')

    query = '''
    MATCH (course)-[:HAS_ANNOUNCEMENT]->(announcement:NTUCoolLearningResource)
    WHERE
        (SIZE($course_id) = 0 OR course.CourseID = $course_id) AND
        (SIZE($type) = 0 OR announcement.AnnouncementType = $type) AND
        (SIZE($date) = 0 OR announcement.publishDate = date($date))
    RETURN 
        course.CourseID AS CourseID, 
        course.CourseName AS Course, 
        announcement.title AS Title, 
        announcement.AnnouncementType AS Type, 
        toString(announcement.publishDate) AS Date
    ORDER BY announcement.publishDate DESC
    '''

    with driver.session() as session:
        result = session.run(query, {
            'course_id': course_id,
            'type': type,
            'date': date
        })
        announcements = [dict(record) for record in result]
        return jsonify(announcements)

@app.route('/api/exam-schedule')
def get_exam_schedule():
    course_id = request.args.get('course_id', '')
    exam_date = request.args.get('exam_date', '')

    query = '''
    MATCH (exam:Exam)-[:HELD_IN]->(u:University), (exam)-[:FOR_COURSE]->(c)
    WHERE
        (SIZE($course_id) = 0 OR c.CourseID = $course_id) AND
        (SIZE($exam_date) = 0 OR exam.ExamDate = date($exam_date))
    RETURN 
        c.CourseID AS CourseID,
        c.CourseName as CourseName,
        toString(exam.ExamDate) AS Date,
        exam.RoomID AS Room,
        u.UniversityName AS University,
        u.Address AS Address,
        u.geoPoint AS geoPoint
    '''

    with driver.session() as session:
        result = session.run(query, {
            'course_id': course_id,
            'exam_date': exam_date
        })
        exams = [dict(record) for record in result]
        return jsonify(exams)

# Average Student's GPA by Region
@app.route('/api/students-gpa-by-region')
def get_students_gpa_by_region():
    course_id = request.args.get('course_id', '')
    semester_id = request.args.get('semester_id', '')
    
    try:
        regions = load_regions()
        course_info = {}
        
        match_clause = """
        MATCH (s:Student)-[:ENROLLED_IN]->(e:Enrollment)
        """
        
        if semester_id:
            match_clause += "MATCH (e)-[:FOR]->(semester:Semester) "
            
        if course_id:
            match_clause += "MATCH (e)-[:FOR]->(c:MasterCourse) "
            
        where_clause = "WHERE e.StandardizedGPA IS NOT NULL "
        
        if semester_id:
            where_clause += "AND semester.SemesterID = $semester_id "
            
        if course_id:
            where_clause += "AND c.CourseID = $course_id "
            return_clause = "RETURN s.geoPoint as point, e.StandardizedGPA as gpa, c.CourseID as courseId, c.CourseName as courseName"
        else:
            return_clause = "RETURN s.geoPoint as point, e.StandardizedGPA as gpa"
            
        query = match_clause + where_clause + return_clause

        with driver.session() as session:
            result = session.run(query, {'course_id': course_id, 'semester_id': semester_id})
            
            gpa_sums = {name: 0.0 for name in regions.keys()}
            student_counts = {name: 0 for name in regions.keys()}

            for record in result:
                point_data = record["point"]
                gpa = record["gpa"]
                
                if course_id and not course_info:
                    course_info = {
                        'courseId': record["courseId"],
                        'courseName': record["courseName"]
                    }
                
                if point_data and gpa:
                    try:
                        coords = str(point_data).replace('POINT(', '').replace(')', '').split()
                        pt = Point(float(coords[0]), float(coords[1]))

                        for region_name, region_shape in regions.items():
                            if region_shape.contains(pt):
                                gpa_sums[region_name] += float(gpa)
                                student_counts[region_name] += 1
                                break
                    except Exception as e:
                        print(f"Point error: {e}, point: {point_data}")
                        continue

            avg_gpas = {
                region: round(gpa_sums[region] / student_counts[region], 2) 
                if student_counts[region] > 0 else 0 
                for region in regions.keys()
            }

            response = {
                'averageGPA': avg_gpas,
                'studentCounts': student_counts
            }
            
            if course_info:
                response['courseInfo'] = course_info

            return jsonify(response)
            
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

# Student's Certification Check
@app.route('/api/student-certificates')
def get_student_certificates():
    student_id = request.args.get('id')
    issue_date = request.args.get('date')

    query = '''
    MATCH (s:Student)
    WHERE s.StudentID = $student_id OR $student_id IS NULL
    MATCH (s)-[:RECEIVES]->(c:Certificate)-[:FOR]->(p:Program)  
    WHERE toString(c.IssuedDate) = $issue_date OR $issue_date IS NULL
    RETURN 
        s.StudentID AS StudentID,
        s.StudentName AS StudentName, 
        c.CertificateName AS CertificateName,
        toString(c.IssuedDate) AS IssuedDate,
        p.ProgramName AS ProgramName
    ORDER BY s.StudentID, c.IssuedDate DESC;
    '''

    with driver.session() as session:
        result = session.run(query, {
            'student_id': student_id,
            'issue_date': issue_date
        })
        certificates = [dict(record) for record in result]
        return jsonify(certificates)

@app.route('/api/programs')
def get_programs():
    program_id = request.args.get('program_id')
    program_name = request.args.get('program_name')

    query = '''
    MATCH (mc:MasterCourse)-[:APPROVED_BY]->(a:Approval)-[:APPROVED_FOR]->(p:Program)
    WHERE 
        (p.ProgramID = $program_id OR $program_id IS NULL) AND
        (p.ProgramName CONTAINS $program_name OR $program_name IS NULL)
    RETURN 
        mc.CourseName AS CourseName,
        a.ApprovalID AS ApprovalID,
        a.CentralOfficeApproval AS CentralApproval,
        a.CommitteeApproval AS CommitteeApproval, 
        p.ProgramID AS ProgramID,
        p.ProgramName AS ProgramName
    ORDER BY p.ProgramID, mc.CourseName;
    '''

    with driver.session() as session:
        result = session.run(query, {
            'program_id': program_id,
            'program_name': program_name
        })
        courses = [dict(record) for record in result]
        return jsonify(courses)

# Custom queries
@app.route('/api/custom-query', methods=['POST'])
def execute_custom_query():
    try:
        data = request.get_json()
        query = data.get('query')
        params = data.get('params', {})

        if not query:
            return jsonify({"error": "Query is required"}), 400

        # Only block actual write operations
        dangerous_operations = ['CREATE', 'DELETE', 'REMOVE', 'MERGE', 'DROP']
        query_upper = query.upper()
        if any(op in query_upper.split() for op in dangerous_operations):
            return jsonify({"error": "Write operations are not allowed"}), 403

        def serialize_value(value):
            if hasattr(value, '__class__'):
                if value.__class__.__name__ == 'Node':
                    return dict(value)
                elif value.__class__.__name__ == 'Date':
                    return value.isoformat()
            return value

        with driver.session() as session:
            result = session.run(query, params)
            records = []
            for record in result:
                if len(record.keys()) == 1 and record[0].__class__.__name__ == 'Node':
                    records.append(dict(record[0]))
                else:
                    record_dict = {key: serialize_value(value) for key, value in record.items()}
                    records.append(record_dict)
            return jsonify(records)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
