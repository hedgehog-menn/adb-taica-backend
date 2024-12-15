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
