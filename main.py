from flask import Flask, request, render_template, jsonify, redirect, url_for
from bson.objectid import ObjectId
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from qrcode_generator import generate_qr_code_as_base64

# Let's go babies
# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# MongoDB connection
CONNECTION_STRING = os.getenv("MONGO_URI")
client = MongoClient(CONNECTION_STRING)

# Access the specified database and collection
db = client["Kurukshetra"]  # Database name
collection = db["EEs"]  # Collection name


@app.route("/")
def main():
    return render_template("upload_form.html")  # Render the HTML form


@app.route("/upload", methods=["POST"])
def upload():
    try:
        # Get form data
        participant_name = request.form["name"]
        email = request.form["email"]
        phone_number = request.form["phone"]
        file = request.files["file"]

        # Read the file
        image_binary = file.read()

        # Create participant data without the QR code
        participant_data = {
            "user_image_name": file.filename,
            "data": image_binary,
            "name": participant_name,
            "email": email,
            "phone": phone_number,
            "status": "Not Entered Yet",  # Default status
        }

        # Insert participant data into MongoDB
        result = collection.insert_one(participant_data)

        # Construct the URL for the QR code
        qr_code_data = f"http://localhost:5000/participant/{str(result.inserted_id)}"

        # Path to the logo
        logo_path = "./static/new-kuru.png"  # Update this to your actual logo path

        # Generate QR code as base64
        qr_code_base64 = generate_qr_code_as_base64(qr_code_data, logo_path)

        # Update participant data with the generated QR code
        collection.update_one(
            {"_id": result.inserted_id}, {"$set": {"qr_code": qr_code_base64}}
        )

        # Redirect to confirmation page
        return redirect(
            url_for("user_added_confirmation", participant_id=result.inserted_id)
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/participant/<participant_id>", methods=["GET"])
def participant_details(participant_id):
    """
    Route to view the details of a participant by ID.
    """
    try:
        participant_data = collection.find_one({"_id": ObjectId(participant_id)})
    except Exception as e:
        return jsonify({"error": "Invalid ObjectId format"}), 400

    if not participant_data:
        return jsonify({"error": "Participant not found"}), 404

    return render_template("participant_details.html", participant=participant_data)


@app.route("/update_status/<participant_id>", methods=["POST"])
def update_status(participant_id):
    """
    Route to update the status of a participant without requiring a password.
    """
    status = request.form["status"]

    try:
        # Validate the status
        if status not in ["In Campus", "Outside Campus"]:
            return jsonify({"error": "Invalid status"}), 400

        collection.update_one(
            {"_id": ObjectId(participant_id)}, {"$set": {"status": status}}
        )
        return redirect(url_for("dashboard"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/status/<status>", methods=["GET"])
def status_page(status):
    return render_template("status_page.html", status=status)


@app.route("/get_image/<participant_id>", methods=["GET"])
def get_image(participant_id):
    """
    Route to retrieve and display the participant's image.
    """
    try:
        participant_data = collection.find_one({"_id": ObjectId(participant_id)})
    except Exception as e:
        return jsonify({"error": "Invalid ObjectId format"}), 400

    if not participant_data or "data" not in participant_data:
        return jsonify({"error": "Image not found"}), 404

    return app.response_class(
        participant_data["data"],
        mimetype="image/jpeg",  # Adjust the MIME type based on the image format
    )


@app.route("/wipe", methods=["GET", "POST"])
def wipe_database():
    """
    Route to wipe the database. This functionality has been retained in case you need it.
    """
    if request.method == "POST":
        collection.delete_many({})
        return redirect(url_for("main"))

    return render_template("wipe_page.html", error=None)


@app.route("/user_added/<participant_id>", methods=["GET"])
def user_added_confirmation(participant_id):
    # Get participant data from MongoDB
    participant_data = collection.find_one({"_id": ObjectId(participant_id)})

    if not participant_data:
        return jsonify({"error": "Participant not found"}), 404

    # Get the base64 QR code data from the participant document
    qr_code_base64 = participant_data.get("qr_code", None)

    # Render the confirmation page with the QR code
    return render_template(
        "user_added.html", participant_id=participant_id, qr_code=qr_code_base64
    )


@app.route("/dashboard", methods=["GET"])
def dashboard():
    """
    Route to view the dashboard with all participants.
    """
    participants = list(collection.find())
    in_campus = collection.count_documents({"status": "In Campus"})
    outside_campus = collection.count_documents({"status": "Outside Campus"})
    total_participants = len(participants)

    return render_template(
        "dashboard.html",
        participants=participants,
        in_campus=in_campus,
        outside_campus=outside_campus,
        total_participants=total_participants,
    )


if __name__ == "__main__":
    app.run(debug=True)
