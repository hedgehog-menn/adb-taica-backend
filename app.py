# Install these lib before running
# pip install flask flask-cors neo4j-python-driver shapely

from flask import Flask, request, jsonify
from neo4j import GraphDatabase
from flask_cors import CORS
import json
from shapely.geometry import Point, shape
from functools import lru_cache

app = Flask(__name__)
CORS(app)

# Update with your Neo4j credentials
driver = GraphDatabase.driver(
    'bolt://localhost:7687',
    auth=('neo4j', '12345678')
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
    with driver.session() as session:
        result = session.run('MATCH (c:MasterCourse) RETURN c')
        courses = [dict(record["c"]) for record in result]
        return jsonify(courses)

@app.route('/api/satellite-courses')
def get_satellite_courses():
    with driver.session() as session:
        result = session.run('MATCH (c:SatelliteCourse) RETURN c')
        courses = [dict(record["c"]) for record in result]
        return jsonify(courses)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
