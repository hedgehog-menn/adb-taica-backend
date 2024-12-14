from flask import Flask, jsonify
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
    with driver.session() as session:
        # result = session.run('MATCH (u:University) RETURN u.UniversityName, u.geoPoint')
        # universities = [{
        #     'name': record['u.UniversityName'],
        #     'point': record['u.geoPoint']
        # } for record in result]
        # return jsonify(universities)
        result = session.run('MATCH (u:University) RETURN u')
        universities = [dict(record["u"]) for record in result]
        return jsonify(universities)

@app.route('/api/students')
def get_students():
    with driver.session() as session:
        result = session.run('MATCH (s:Student) RETURN s')
        students = [dict(record["s"]) for record in result]
        return jsonify(students)

@app.route('/api/taiwan-regions')
def get_taiwan_regions():
    # Load the GeoJSON data
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
