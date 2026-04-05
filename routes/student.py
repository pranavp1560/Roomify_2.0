from flask import Blueprint, render_template, request, session, flash, redirect, url_for, jsonify
from bson.objectid import ObjectId
from PIL import Image
from io import BytesIO
import cloudinary
import cloudinary.uploader
from datetime import datetime
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# ===========================
# NEW DB IMPORTS
# ===========================
from db import students, rooms, messes, room_owners, users

# ===========================
# Cloudinary Config
# ===========================
cloudinary.config(
    cloud_name="dzqe0yfzf",
    api_key="335187996581477",
    api_secret="4XwZEkqJo0XIeakpf2_dBaCvIuI"
)

student = Blueprint("student", __name__, url_prefix="/student")
sia = SentimentIntensityAnalyzer()

# =====================================================
# STUDENT DASHBOARD
# =====================================================
# @student.route("/dashboard")
# def dashboard():
#     if "user_id" not in session or session.get("role") != "student":
#         flash("Please login as student first.", "warning")
#         return redirect(url_for("login", role="student"))

#     rooms_list = list(rooms().find())
#     messes_list = list(messes().find())

#     return render_template(
#         "student_page.html",
#         user=session["user"],
#         rooms=rooms_list,
#         messes=messes_list
#     )

@student.route("/dashboard")
def dashboard():

    reset_monthly_payments()

    if session.get("role") != "student":
        flash("Login required.", "warning")
        return redirect(url_for("login", role="student"))

    student_id = str(session["user_id"])

    user = students().find_one({"_id": ObjectId(student_id)})

    # =========================
    # HOSTED ROOM
    # =========================
    room = rooms().find_one({"hosted_students.student_id": student_id})

    hosted = None
    upi_link = None

    if room:
        for s in room.get("hosted_students", []):
            if s["student_id"] == student_id:

                hosted = {
                    "room_name": room.get("name"),
                    "rent": room.get("rent"),
                    "rent_paid": s.get("rent_paid"),
                    "rent_paid_date": s.get("rent_paid_date")
                }

                # UPI for room
                upi = room.get("upi_id")
                rent = room.get("rent")

                if upi and rent:
                    upi_link = f"upi://pay?pa={upi}&pn=RoomOwner&am={rent}&cu=INR"

                break

    # =========================
    # 🔥 HOSTED MESS (NEW)
    # =========================
    mess = messes().find_one({"hosted_students.student_id": student_id})

    hosted_mess = None
    upi_mess_link = None

    if mess:
        for s in mess.get("hosted_students", []):
            if s["student_id"] == student_id:

                hosted_mess = {
                    "mess_name": mess.get("name"),
                    "monthly_charge": mess.get("monthly_charge"),
                    "paid": s.get("paid"),
                    "paid_date": s.get("paid_date")
                }

                # UPI for mess (if you store it)
                upi = mess.get("upi_id")
                amount = mess.get("monthly_charge")

                if upi and amount:
                    upi_mess_link = f"upi://pay?pa={upi}&pn=MessOwner&am={amount}&cu=INR"

                break

    return render_template(
        "student_dashboard.html",
        user=user,
        hosted=hosted,
        hosted_mess=hosted_mess,   # 🔥 NEW
        upi_link=upi_link,
        upi_mess_link=upi_mess_link  # 🔥 NEW
    )



# =====================================================
# SEARCH
# =====================================================
@student.route("/search")
def search():
    if session.get("role") != "student":
        flash("Login first.", "warning")
        return redirect(url_for("login", role="student"))

    query = request.args.get("q", "").lower()
    selected_types = request.args.getlist("type")
    price_filters = request.args.getlist("price")

    room_query = {}
    mess_query = {}

    # TEXT SEARCH
    if query:
        room_query["$or"] = [
            {"name": {"$regex": query, "$options": "i"}},
            {"address": {"$regex": query, "$options": "i"}},
        ]
        mess_query["$or"] = [
            {"name": {"$regex": query, "$options": "i"}},
            {"type": {"$regex": query, "$options": "i"}},
        ]

    # FILTERS
    include_rooms = not selected_types or "room" in selected_types
    include_messes = not selected_types or "mess" in selected_types

    # PRICE FILTER
    if "below2000" in price_filters and "above2000" not in price_filters:
        room_query["rent"] = {"$lt": 2000}
        mess_query["monthly_charge"] = {"$lt": 2000}
    elif "above2000" in price_filters and "below2000" not in price_filters:
        room_query["rent"] = {"$gte": 2000}
        mess_query["monthly_charge"] = {"$gte": 2000}

    rooms_list = []
    if include_rooms:
        for r in rooms().find(room_query):
            reviews = r.get("reviews", [])
            avg_rating = round(sum(int(x["rating"]) for x in reviews) / len(reviews), 1) if reviews else 0
            r["avg_rating"] = avg_rating
            print("ROOM REVIEWS:", r.get("reviews"))
            rooms_list.append(r)

    messes_list = []
    if include_messes:
        for m in messes().find(mess_query):

            reviews = m.get("reviews", [])
            avg_rating = round(sum(int(x["rating"]) for x in reviews) / len(reviews), 1) if reviews else 0
            m["avg_rating"] = avg_rating
            messes_list.append(m)

    return render_template("student_page.html",
                           user=session["user"],
                           rooms=rooms_list,
                           messes=messes_list)
# =====================================================
# ROOM DETAILS
# =====================================================
# @student.route("/room/<room_id>")
# def room_details(room_id):
#     room = rooms().find_one({"_id": ObjectId(room_id)})
#     if not room:
#         flash("Room not found!", "danger")
#         return redirect(url_for("student.dashboard"))

#     owner = room_owners().find_one({"_id": ObjectId(room["owner_id"])})
#     owner_mobile = owner.get("mobile") if owner else ""

#     reviews = room.get("reviews", [])
#     avg_rating = round(sum(int(r["rating"]) for r in reviews) / len(reviews), 1) if reviews else None

#     return render_template(
#         "room_details.html",
#         room=room,
#         avg_rating=avg_rating,
#         owner_mobile=owner_mobile
#     )

@student.route("/room/<room_id>")
def room_details(room_id):
    room = rooms().find_one({"_id": ObjectId(room_id)})
    if not room:
        flash("Room not found!", "danger")
        return redirect(url_for("student.dashboard"))

    # Fetch owner from room_owners collection (correct DB)
    owner = room_owners().find_one({"_id": ObjectId(room["owner_id"])})

    owner_mobile = owner.get("mobile") if owner else "0000000000"

    reviews = room.get("reviews", [])
    avg_rating = (
        round(sum(int(r["rating"]) for r in reviews) / len(reviews), 1)
        if reviews else None
    )

    return render_template(
        "room_details.html",
        room=room,
        avg_rating=avg_rating,
        owner_mobile=owner_mobile
    )




# =====================================================
# MESS DETAILS
# =====================================================
@student.route("/mess/<mess_id>")
def mess_details(mess_id):
    m = messes().find_one({"_id": ObjectId(mess_id)})
    if not m:
        flash("Mess not found!", "danger")
        return redirect(url_for("student.dashboard"))
    return render_template("mess_details.html", mess=m)


# =====================================================
# STUDENT PROFILE
# =====================================================
@student.route("/profile")
def profile():
    if session.get("role") != "student":
        flash("Login required.", "warning")
        return redirect(url_for("login", role="student"))

    db_user = students().find_one({"_id": ObjectId(session["user_id"])})
    return render_template("student_profile.html", user=db_user)


# =====================================================
# UPDATE PROFILE
# =====================================================
@student.route("/update_profile", methods=["POST"])
def update_profile():
    if session.get("role") != "student":
        flash("Login required.", "warning")
        return redirect(url_for("login", role="student"))

    user_id = session["user_id"]
    old = students().find_one({"_id": ObjectId(user_id)})
    old_info = old.get("student_info", {}) if old else {}

    # Form data
    name = request.form.get("name")
    mobile = request.form.get("mobile")
    address = request.form.get("address")
    college = request.form.get("college")

    # Aadhaar file
    aadhaar_file = request.files.get("aadhaar")
    aadhaar_url = old_info.get("aadhaar_file")
    if aadhaar_file and aadhaar_file.filename:
        upload = cloudinary.uploader.upload(aadhaar_file, resource_type="auto")
        aadhaar_url = upload["secure_url"]

    # College ID file
    college_id = request.files.get("college_id")
    college_url = old_info.get("college_id_file")
    if college_id and college_id.filename:
        upload = cloudinary.uploader.upload(college_id, resource_type="auto")
        college_url = upload["secure_url"]

    # Save updated info
    students().update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "verification_status": "pending",
            "student_info": {
                "name": name,
                "mobile": mobile,
                "address": address,
                "college": college,
                "aadhaar_file": aadhaar_url,
                "college_id_file": college_url
            },
            "updated_on": datetime.now().strftime("%Y-%m-%d %H:%M")
        }}
    )

    flash("Profile saved successfully!", "success")

    room_id = session.pop("pending_room_application", None)

    if room_id:
        return redirect(url_for("room.apply_room", room_id=room_id))

    return redirect(url_for("student.dashboard"))


# =====================================================
# SENTIMENT VIEWER
# =====================================================
@student.route("/sentiment/view/<item_type>/<item_id>")
def view_sentiment_student(item_type, item_id):
    if session.get("role") != "student":
        flash("Login first.", "warning")
        return redirect(url_for("login", role="student"))

    # ROOM
    if item_type == "room":
        item = rooms().find_one({"_id": ObjectId(item_id)})
        if not item:
            flash("Room not found!", "danger")
            return redirect(url_for("student.dashboard"))
        reviews = item.get("reviews", [])
        chart_url = url_for("room.sentiment_chart", room_id=item_id)

    # MESS
    elif item_type == "mess":
        item = messes().find_one({"_id": ObjectId(item_id)})
        if not item:
            flash("Mess not found!", "danger")
            return redirect(url_for("student.dashboard"))
        reviews = item.get("reviews", [])
        chart_url = url_for("mess.mess_sentiment_chart", mess_id=item_id)

    else:
        flash("Invalid selection.", "danger")
        return redirect(url_for("student.dashboard"))

    # Calculate sentiment
    positive = neutral = negative = 0
    total_rating = 0

    for r in reviews:
        score = sia.polarity_scores(r["comment"])["compound"]
        if score >= 0.05: positive += 1
        elif score <= -0.05: negative += 1
        else: neutral += 1
        total_rating += int(r["rating"])

    total_reviews = len(reviews)
    avg_rating = round(total_rating / total_reviews, 2) if total_reviews else 0

    return render_template(
        "view_sentiment_student.html",
        item=item,
        item_type=item_type,
        positive=positive,
        negative=negative,
        neutral=neutral,
        avg_rating=avg_rating,
        total=total_reviews,
        chart_url=chart_url
    )



def reset_monthly_payments():
    today = datetime.now()
    current_month = today.strftime("%Y-%m")

    reset_done = False   # 🔥 track if reset happened

    # =========================
    # ROOM RESET
    # =========================
    for room in rooms().find():
        updated = False

        for s in room.get("hosted_students", []):
            last_paid = s.get("rent_paid_date", "")

            if not last_paid.startswith(current_month):
                if s.get("rent_paid"):   # only reset if previously paid
                    s["rent_paid"] = False
                    updated = True
                    reset_done = True

        if updated:
            rooms().update_one(
                {"_id": room["_id"]},
                {"$set": {"hosted_students": room["hosted_students"]}}
            )

    # =========================
    # MESS RESET
    # =========================
    for mess in messes().find():
        updated = False

        for s in mess.get("hosted_students", []):
            last_paid = s.get("paid_date", "")

            if not last_paid.startswith(current_month):
                if s.get("paid"):
                    s["paid"] = False
                    updated = True
                    reset_done = True

        if updated:
            messes().update_one(
                {"_id": mess["_id"]},
                {"$set": {"hosted_students": mess["hosted_students"]}}
            )

    # 🔥 ADD POPUP HERE
    if reset_done:
        flash("New month started! Please pay your rent/mess fee.", "info")
