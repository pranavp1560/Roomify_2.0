from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader
from utils.sentiment import analyze_sentiment
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime
import base64, io, os
from PIL import Image
import numpy as np


# ===========================
# NEW DB IMPORTS (correct)
# ===========================
from db import room_owners, rooms, students, users

# ===========================
# CLOUDINARY CONFIG
# ===========================
cloudinary.config(
    cloud_name="dzqe0yfzf",
    api_key="335187996581477",
    api_secret="4XwZEkqJo0XIeakpf2_dBaCvIuI"
)

room_bp = Blueprint("room", __name__, url_prefix="/rooms")

sia = SentimentIntensityAnalyzer()

# ====================================================
# ROOM OWNER PROFILE PAGE
# ====================================================
# @room_bp.route("/profile")
# def profile():
#     if not session.get("user_id") or session.get("role") != "room_owner":
#         flash("Please login as Room Owner first", "warning")
#         return redirect(url_for("login", role="room_owner"))

#     owner_id = str(session["user_id"])
#     room = rooms().find_one({"owner_id": owner_id})
    

#     if room:

#         # NEW DATABASE STRUCTURE
#         total = room.get("capacity", 0) or 0
#         hosted = len(room.get("hosted_students", []))
#         available = max(total - hosted, 0)

#         rooms().update_one(
#             {"_id": room["_id"]},
#             {"$set": {"available": available}}
#         )

#         room["available"] = available

#         return render_template("room_profile.html", room=room, owner=session["user"])

#     return render_template("room_page.html", user=session["user"])

@room_bp.route("/profile")
def profile():
    if not session.get("user_id") or session.get("role") != "room_owner":
        flash("Please login as Room Owner first", "warning")
        return redirect(url_for("login", role="room_owner"))

    owner_id = str(session["user_id"])
    owner = users().find_one({"_id": ObjectId(owner_id)})   # ⭐ add this

    room = rooms().find_one({"owner_id": owner_id})

    if room:
        total = room.get("capacity", 0) or 0
        hosted = len(room.get("hosted_students", []))
        available = max(total - hosted, 0)

        rooms().update_one(
            {"_id": room["_id"]},
            {"$set": {"available": available}}
        )

        room["available"] = available

        return render_template("room_profile.html", room=room, owner=owner)

    return render_template("room_page.html", user=session["user"], owner=owner)


# ====================================================
# ADD ROOM
# ====================================================
@room_bp.route("/add", methods=["POST"])
def add_room():
    if not session.get("user_id"):
        flash("Please login", "warning")
        return redirect(url_for("login", role="room_owner"))

    owner_id = str(session["user_id"])

    # Check if owner already created a room
    if rooms().find_one({"owner_id": owner_id}):
        flash("Room already exists!", "warning")
        return redirect(url_for("room.profile"))

    # Fetch owner from room_owners DB
    owner = room_owners().find_one({"_id": ObjectId(owner_id)})

    if not owner:
        flash("Owner not found in database!", "danger")
        return redirect(url_for("room.profile"))

    room_data = {
        "owner_id": owner_id,
        "owner_mobile": owner.get("mobile", ""),  
        "name": request.form.get("name"),
        "rent": int(request.form.get("rent")),
        "upi_id": request.form.get("upi_id"),
        "capacity": int(request.form.get("capacity")),
        "available": int(request.form.get("available")),
        "address": request.form.get("address"),
        "for_gender": request.form.get("for_gender"),
        "room_type": request.form.get("room_type"),
        "features": request.form.getlist("features"),
        "rules": request.form.getlist("rules"),
        "images": []
    }

    rooms().insert_one(room_data)
    flash("Room added successfully!", "success")
    return redirect(url_for("room.profile"))


# ====================================================
# EDIT ROOM
# ====================================================
@room_bp.route("/edit/<room_id>", methods=["GET", "POST"])
def edit_room(room_id):
    room = rooms().find_one({"_id": ObjectId(room_id)})
    
    if request.method == "POST":
        updated = {
            "name": request.form.get("name"),
            "rent": int(request.form.get("rent")),
            "upi_id": request.form.get("upi_id"),
            "capacity": int(request.form.get("capacity") or 0),
            "available": int(request.form.get("available") or 0),
            "address": request.form.get("address"),
            "for_gender": request.form.get("for_gender"),
            "room_type": request.form.get("room_type"),
            "features": request.form.getlist("features"),
            "rules": request.form.getlist("rules"),
            "owner_mobile": request.form.get("owner_mobile")
        }


        rooms().update_one({"_id": ObjectId(room_id)}, {"$set": updated})
        flash("Room updated!", "success")
        return redirect(url_for("room.profile"))

    return render_template("edit_room.html", room=room)


# ====================================================
# UPLOAD ROOM IMAGE
# ====================================================
@room_bp.route("/upload_image/<room_id>", methods=["POST"])
def upload_image(room_id):
    image = request.files.get("image")
    if not image:
        flash("No image selected", "danger")
        return redirect(url_for("room.profile"))

    upload = cloudinary.uploader.upload(image)
    image_url = upload.get("secure_url")

    rooms().update_one(
        {"_id": ObjectId(room_id)},
        {"$push": {"images": image_url}}
    )

    flash("Image uploaded!", "success")
    return redirect(url_for("room.profile"))


# ====================================================
# DELETE ROOM IMAGE
# ====================================================
@room_bp.route("/delete_image/<room_id>", methods=["POST"])
def delete_image(room_id):
    image_url = request.form.get("image_url")

    rooms().update_one(
        {"_id": ObjectId(room_id)},
        {"$pull": {"images": image_url}}
    )

    flash("Image deleted!", "success")
    return redirect(url_for("room.profile"))


# ====================================================
# APPLY FOR ROOM
# ====================================================
# @room_bp.route("/apply/<room_id>", methods=["POST"])
# def apply_room(room_id):
#     if session.get("role") != "student":
#         flash("Login as student", "warning")
#         return redirect(url_for("login", role="student"))

#     student_id = str(session["user_id"])
#     student = session["user"]

#     request_entry = {
#         "_id": ObjectId(),
#         "student_id": student_id,
#         "student_name": student.get("name"),
#         "student_mobile": student.get("mobile"),
#         "status": "pending"
#     }

#     rooms().update_one(
#         {"_id": ObjectId(room_id)},
#         {"$push": {"requests": request_entry}}
#     )

#     flash("Request sent!", "success")
#     return redirect(url_for("student.room_details", room_id=room_id))

@room_bp.route("/apply/<room_id>", methods=["GET","POST"])
def apply_room(room_id):

    if session.get("role") != "student":
        flash("Login as student first", "warning")
        return redirect(url_for("login", role="student"))

    student_id = str(session["user_id"])
    student = students().find_one({"_id": ObjectId(student_id)})

    # If profile not completed
    if not student.get("student_info"):
        flash("Please complete your profile before applying.", "warning")
        session["pending_room_application"] = room_id
        return redirect(url_for("student.profile"))

    request_entry = {
        "_id": ObjectId(),
        "student_id": student_id,
        "student_info": student.get("student_info", {}),
        "status": "pending",
        "applied_on": datetime.now().strftime("%Y-%m-%d")
    }

    rooms().update_one(
        {"_id": ObjectId(room_id)},
        {"$push": {"requests": request_entry}}
    )

    flash("Room request sent successfully!", "success")
    return redirect(url_for("student.room_details", room_id=room_id))


# ====================================================
# VIEW REQUESTS
# ====================================================
@room_bp.route("/requests")
def requests_page():
    owner_id = str(session["user_id"])
    room = rooms().find_one({"owner_id": owner_id})

    enriched = []

    for req in room.get("requests", []):
        st = students().find_one({"_id": ObjectId(req["student_id"])})

        if st:
            info = st.get("student_info", {})

            student_info = {
                "name": info.get("name"),
                "mobile": info.get("mobile"),
                "college": info.get("college"),
                "address": info.get("address"),
                "aadhaar_file": info.get("aadhaar_file"),
                "college_id_file": info.get("college_id_file")
            }
        else:
            student_info = {}

        enriched.append({
            "_id": req["_id"],
            "student_info": student_info
        })

    return render_template("room_requests.html", room=room, requests=enriched)


# ====================================================
# ACCEPT REQUEST
# ====================================================
@room_bp.route("/requests/accept/<room_id>/<request_id>", methods=["POST"])
def accept(room_id, request_id):
    room = rooms().find_one({"_id": ObjectId(room_id)})
    
    req = next((r for r in room.get("requests", []) if str(r["_id"]) == request_id), None)

    student_obj = students().find_one({"_id": ObjectId(req["student_id"])})
    info = student_obj.get("student_info", {})

    
    hosted_entry = {
        "student_id": str(student_obj["_id"]),
        "name": info.get("name"),
        "mobile": info.get("mobile"),
        "college": info.get("college"),
        "address": info.get("address"),
        "aadhaar_file": info.get("aadhaar_file"),
        "college_id_file": info.get("college_id_file"),
        "hosted_date": datetime.now().strftime("%d-%m-%Y"),
        "rent_paid": False,
        "payment_mode": "",
        "payment_locked": False
    }

    rooms().update_one(
        {"_id": ObjectId(room_id)},
        {"$push": {"hosted_students": hosted_entry}}
    )

    rooms().update_one(
        {"_id": ObjectId(room_id)},
        {"$pull": {"requests": {"_id": ObjectId(request_id)}}}
    )

    flash("Request accepted!", "success")
    return redirect(url_for("room.requests_page"))


# ====================================================
# REJECT REQUEST
# ====================================================
@room_bp.route("/requests/reject/<room_id>/<request_id>", methods=["POST"])
def reject(room_id, request_id):
    rooms().update_one(
        {"_id": ObjectId(room_id)},
        {"$pull": {"requests": {"_id": ObjectId(request_id)}}}
    )
    flash("Request rejected!", "info")
    return redirect(url_for("room.requests_page"))


# ====================================================
# HOSTED STUDENTS
# ====================================================
@room_bp.route("/hosted")
def hosted_students():
    owner_id = str(session["user_id"])
    room = rooms().find_one({"owner_id": owner_id})
    hosted = room.get("hosted_students", [])

    return render_template("hosted_students.html", room=room, hosted_students=hosted)


# ====================================================
# ADD REVIEW
# ====================================================
@room_bp.route("/review/<room_id>", methods=["POST"])
def add_review(room_id):
    student_id = str(session["user_id"])
    comment = request.form.get("comment")
    rating = int(request.form.get("rating"))

    room = rooms().find_one({"_id": ObjectId(room_id)})

    review = {
        "_id": ObjectId(),
        "student_id": student_id,
        "rating": rating,
        "comment": comment,
        "sentiment": analyze_sentiment(comment, rating),
        "date": datetime.now().strftime("%Y-%m-%d")
    }

    rooms().update_one(
        {"_id": ObjectId(room_id)},
        {"$push": {"reviews": review}}
    )

    flash("Review added!", "success")
    return redirect(url_for("student.room_details", room_id=room_id))


# ====================================================
# SENTIMENT ANALYSIS PAGE
# ====================================================
@room_bp.route("/sentiment/<room_id>")
def sentiment(room_id):
    room = rooms().find_one({"_id": ObjectId(room_id)})
    reviews = room.get("reviews", [])

    positive = negative = neutral = 0

    for r in reviews:
        score = sia.polarity_scores(r["comment"])["compound"]
        if score >= 0.05: positive += 1
        elif score <= -0.05: negative += 1
        else: neutral += 1

    return render_template(
        "room_sentiment.html",
        room=room,
        positive=positive,
        negative=negative,
        neutral=neutral,
        total=len(reviews)
    )


# ====================================================
# SENTIMENT PIE CHART
# ====================================================
@room_bp.route("/sentiment_chart/<room_id>")
def sentiment_chart(room_id):
    room = rooms().find_one({"_id": ObjectId(room_id)})
    reviews = room.get("reviews", [])

    positive = negative = neutral = 0

    for r in reviews:
        score = sia.polarity_scores(r["comment"])["compound"]
        if score >= 0.05: positive += 1
        elif score <= -0.05: negative += 1
        else: neutral += 1

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.pie([positive, neutral, negative], labels=["Positive", "Neutral", "Negative"], autopct='%1.1f%%')
    ax.set_title("Sentiment Analysis")

    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close()

    return Response(buffer.getvalue(), mimetype='image/png')


# ====================================================
# UPDATE RENT STATUS
# ====================================================
@room_bp.route("/rent/update/<room_id>/<student_id>", methods=["POST"])
def update_rent(room_id, student_id):
    rent_paid = request.form.get("rent_paid") == "true"
    payment_mode = request.form.get("payment_mode")

    update_data = {
        "hosted_students.$.rent_paid": rent_paid,
        "hosted_students.$.payment_mode": payment_mode
    }

    if rent_paid:
        update_data["hosted_students.$.rent_paid_date"] = datetime.now().strftime("%d-%m-%Y")

    rooms().update_one(
        {"_id": ObjectId(room_id), "hosted_students.student_id": student_id},
        {"$set": update_data}
    )

    flash("Rent updated!", "success")
    return redirect(url_for("room.hosted_students"))


@room_bp.route("/remove_student/<room_id>/<student_id>", methods=["POST"])
def remove_student(room_id, student_id):

    rooms().update_one(
        {"_id": ObjectId(room_id)},
        {"$pull": {"hosted_students": {"student_id": student_id}}}
    )

    flash("Student removed successfully!", "success")
    return redirect(url_for("room.hosted_students"))


@room_bp.route("/send_reminder_all")
def send_reminder_all():

    owner_id = str(session["user_id"])
    room = rooms().find_one({"owner_id": owner_id})

    if not room:
        flash("Room not found", "danger")
        return redirect(url_for("room.hosted_students"))

    unpaid_students = []

    for s in room.get("hosted_students", []):
        if not s.get("rent_paid"):
            unpaid_students.append({
                "name": s.get("name"),
                "mobile": s.get("mobile")
            })

    return render_template("send_reminder.html", students=unpaid_students)
