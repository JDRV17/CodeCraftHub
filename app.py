"""
CodeCraftHub - Course Tracking REST API

This Flask application provides CRUD operations for courses and stores
course data in a local JSON file named courses.json.

Run the application with:

    python app.py
"""

from datetime import datetime
from pathlib import Path
import json

from flask import Flask, jsonify, request


# Create the Flask application
app = Flask(__name__)

# Store courses.json in the same folder as this app.py file
DATA_FILE = Path(__file__).parent / "courses.json"

# Allowed course status values
VALID_STATUSES = {
    "Not Started",
    "In Progress",
    "Completed",
}


class StorageError(Exception):
    """Custom error used when the JSON file cannot be read or written."""


def ensure_data_file_exists():
    """
    Create courses.json automatically if it does not already exist.

    The file starts with an empty JSON list because courses will be stored
    as a list of objects.
    """
    if not DATA_FILE.exists():
        try:
            DATA_FILE.write_text("[]", encoding="utf-8")
        except OSError as error:
            raise StorageError(
                f"Unable to create data file: {error}"
            ) from error


def load_courses():
    """
    Read and return all courses from courses.json.

    Returns:
        list: A list of course dictionaries.

    Raises:
        StorageError: If the file cannot be read or contains invalid JSON.
    """
    ensure_data_file_exists()

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            courses = json.load(file)
    except json.JSONDecodeError as error:
        raise StorageError(
            "courses.json contains invalid JSON."
        ) from error
    except OSError as error:
        raise StorageError(
            f"Unable to read courses.json: {error}"
        ) from error

    # The JSON file should contain a list of courses
    if not isinstance(courses, list):
        raise StorageError(
            "courses.json must contain a JSON list."
        )

    return courses


def save_courses(courses):
    """
    Save the list of courses to courses.json.

    Args:
        courses (list): The courses to save.

    Raises:
        StorageError: If the file cannot be written.
    """
    try:
        with DATA_FILE.open("w", encoding="utf-8") as file:
            json.dump(courses, file, indent=4)
    except OSError as error:
        raise StorageError(
            f"Unable to write to courses.json: {error}"
        ) from error


def get_next_course_id(courses):
    """
    Generate the next course ID.

    IDs start at 1. If there are no courses, the first ID is 1.
    Otherwise, the new ID is one greater than the current highest ID.
    """
    if not courses:
        return 1

    highest_id = max(course["id"] for course in courses)
    return highest_id + 1


def validate_date_format(target_date):
    """
    Check that a date uses the exact YYYY-MM-DD format.

    Returns:
        bool: True if valid, otherwise False.
    """
    if not isinstance(target_date, str):
        return False

    # fromisoformat validates both the date and its values
    try:
        parsed_date = datetime.strptime(target_date, "%Y-%m-%d")

        # This extra check ensures values such as 2026-1-1 are rejected
        return parsed_date.strftime("%Y-%m-%d") == target_date
    except ValueError:
        return False


def validate_course_data(data):
    """
    Validate data submitted for a course.

    Returns:
        list: A list of validation error messages.
    """
    errors = []

    if not isinstance(data, dict):
        return ["Request body must be a JSON object."]

    # These fields are required when creating or replacing a course
    required_fields = [
        "name",
        "description",
        "target_date",
        "status",
    ]

    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
        elif data[field] is None:
            errors.append(f"Field cannot be null: {field}")

    # Do not validate the remaining values if required fields are missing
    if errors:
        return errors

    # Name must be a non-empty string
    if not isinstance(data["name"], str) or not data["name"].strip():
        errors.append("name must be a non-empty string.")

    # Description must be a non-empty string
    if (
        not isinstance(data["description"], str)
        or not data["description"].strip()
    ):
        errors.append("description must be a non-empty string.")

    # target_date must use YYYY-MM-DD format
    if not validate_date_format(data["target_date"]):
        errors.append(
            "target_date must use YYYY-MM-DD format."
        )

    # Status must be one of the allowed values
    if data["status"] not in VALID_STATUSES:
        errors.append(
            "status must be one of: "
            "Not Started, In Progress, Completed."
        )

    return errors


def find_course_by_id(courses, course_id):
    """
    Find a course by its integer ID.

    Returns:
        dict or None: The matching course, if found.
    """
    return next(
        (course for course in courses if course["id"] == course_id),
        None,
    )


def error_response(message, status_code):
    """Return a consistent JSON error response."""
    return jsonify({"error": message}), status_code


@app.errorhandler(404)
def handle_not_found(error):
    """Handle requests to routes that do not exist."""
    return error_response("Endpoint not found.", 404)


@app.errorhandler(405)
def handle_method_not_allowed(error):
    """Handle HTTP methods that are not supported by an endpoint."""
    return error_response("HTTP method not allowed.", 405)


@app.route("/api/courses", methods=["POST"])
def create_course():
    """
    Create a new course.

    Endpoint:
        POST /api/courses
    """
    # Check that the request contains JSON
    if not request.is_json:
        return error_response(
            "Request must use Content-Type: application/json.",
            400,
        )

    data = request.get_json(silent=True)

    if data is None:
        return error_response(
            "Request body contains invalid JSON.",
            400,
        )

    # Validate all required course fields
    validation_errors = validate_course_data(data)

    if validation_errors:
        return jsonify({"errors": validation_errors}), 400

    try:
        courses = load_courses()

        # Build a new course object
        new_course = {
            "id": get_next_course_id(courses),
            "name": data["name"].strip(),
            "description": data["description"].strip(),
            "target_date": data["target_date"],
            "status": data["status"],
            # Store a UTC timestamp in ISO 8601 format
            "created_at": datetime.utcnow().isoformat() + "Z",
        }

        courses.append(new_course)
        save_courses(courses)

        return jsonify(new_course), 201

    except StorageError as error:
        return error_response(str(error), 500)


@app.route("/api/courses", methods=["GET"])
@app.route("/api/courses/", methods=["GET"])
def get_all_courses():
    """
    Get all courses.

    Endpoints:
        GET /api/courses
        GET /api/courses/
    """
    try:
        courses = load_courses()
        return jsonify(courses), 200

    except StorageError as error:
        return error_response(str(error), 500)


@app.route("/api/courses/<int:course_id>", methods=["GET"])
def get_course(course_id):
    """
    Get one course by ID.

    Endpoint:
        GET /api/courses/<course_id>
    """
    try:
        courses = load_courses()
        course = find_course_by_id(courses, course_id)

        if course is None:
            return error_response("Course not found.", 404)

        return jsonify(course), 200

    except StorageError as error:
        return error_response(str(error), 500)


@app.route("/api/courses/<int:course_id>", methods=["PUT"])
def update_course(course_id):
    """
    Update an existing course.

    This PUT endpoint expects all required course fields:
    name, description, target_date, and status.

    Endpoint:
        PUT /api/courses/<course_id>
    """
    if not request.is_json:
        return error_response(
            "Request must use Content-Type: application/json.",
            400,
        )

    data = request.get_json(silent=True)

    if data is None:
        return error_response(
            "Request body contains invalid JSON.",
            400,
        )

    # PUT replaces the editable course data, so all required fields
    # must be included in the request.
    validation_errors = validate_course_data(data)

    if validation_errors:
        return jsonify({"errors": validation_errors}), 400

    try:
        courses = load_courses()
        course = find_course_by_id(courses, course_id)

        if course is None:
            return error_response("Course not found.", 404)

        # Update the editable fields
        course["name"] = data["name"].strip()
        course["description"] = data["description"].strip()
        course["target_date"] = data["target_date"]
        course["status"] = data["status"]

        # Keep the original ID and created_at timestamp unchanged
        save_courses(courses)

        return jsonify(course), 200

    except StorageError as error:
        return error_response(str(error), 500)


@app.route("/api/courses/<int:course_id>", methods=["DELETE"])
def delete_course(course_id):
    """
    Delete a course by ID.

    Endpoint:
        DELETE /api/courses/<course_id>
    """
    try:
        courses = load_courses()
        course = find_course_by_id(courses, course_id)

        if course is None:
            return error_response("Course not found.", 404)

        courses.remove(course)
        save_courses(courses)

        return jsonify(
            {
                "message": "Course deleted successfully.",
                "course": course,
            }
        ), 200

    except StorageError as error:
        return error_response(str(error), 500)


if __name__ == "__main__":
    # Ensure the JSON file exists before starting the server
    try:
        ensure_data_file_exists()
    except StorageError as error:
        print(f"Startup error: {error}")
        raise SystemExit(1)

    # debug=True is useful during development.
    # Do not use debug mode in production.
    app.run(debug=True)