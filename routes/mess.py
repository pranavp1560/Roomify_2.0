from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader
import matplotlib

from utils.sentiment import analyze_sentiment
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# ===========================
# NEW DB IMPORTS
# ===========================
from db import messes, students , mess_owners

# ===========================
# Cloudinary Config
# ===========================
cloudinary.config(
    cloud_name="dzqe0yfzf",
    api_key="335187996581477",
    api_secret="4XwZEkqJo0XIeakpf2_dBaCvIuI"
)

mess = Blueprint("mess", __name__, url_prefix="/mess")
sia = SentimentIntensityAnalyzer()

# ======================================================
# MESS OWNER PROFILE
# ======================================================
@mess.route("/profile")
def profile():
    if session.get("role") != "mess_owner":
        flash("Login as Mess Owner!", "warning")
        return redirect(url_for("login", role="mess_owner"))

    owner_id = str(session["user_id"])
    m = messes().find_one({"owner_id": owner_id})

    if m:
        return render_template("mess_profile.html", mess=m, owner=session["user"])
    
    return render_template("mess_page.html", user=session["user"], existing_mess=None)


# ======================================================
# ADD MESS
# ======================================================
@mess.route("/add", methods=["POST"])
def add_mess():
    if session.get("role") != "mess_owner":
        flash("Login required!", "warning")
        return redirect(url_for("login", role="mess_owner"))

    owner_id = str(session["user_id"])
    owner = mess_owners().find_one({"_id": ObjectId(owner_id)})
    
    if messes().find_one({"owner_id": owner_id}):
        flash("Mess already exists!", "info")
        return redirect(url_for("mess.profile"))

    mess_data = {
        "owner_id": owner_id,
        "name": request.form.get("name"),
        "owner_mobile": owner.get("mobile", ""),
        "type": request.form.get("type"),
        "monthly_charge": int(request.form.get("monthly_charge")),
        "address": request.form.get("address"),
        "food_type": request.form.get("food_type"),
        "for_gender": request.form.get("for_gender"),
        "features": request.form.getlist("features"),
        "feature_other": request.form.get("feature_other"),
        "rules": request.form.getlist("rules"),
        "rule_other": request.form.get("rule_other"),
        "images": [],
        "requests": [],
        "hosted_students": [],
        "reviews": []
    }

    messes().insert_one(mess_data)
    flash("Mess added successfully!", "success")
    return redirect(url_for("mess.profile"))


# ======================================================
# EDIT MESS
# ======================================================
@mess.route("/edit/<mess_id>", methods=["GET", "POST"])
def edit_mess(mess_id):
    owner_id = str(session.get("user_id"))
    m = messes().find_one({"_id": ObjectId(mess_id)})

    if not m:
        flash("Mess not found!", "danger")
        return redirect(url_for("mess.profile"))

    if request.method == "POST":
        updated = {
            "name": request.form.get("name"),
            "type": request.form.get("type"),
            "monthly_charge": int(request.form.get("monthly_charge")),
            "address": request.form.get("address"),
            "food_type": request.form.get("food_type"),
            "for_gender": request.form.get("for_gender"),
            "features": request.form.getlist("features"),
            "feature_other": request.form.get("feature_other"),
            "rules": request.form.getlist("rules"),
            "rule_other": request.form.get("rule_other")
        }

        messes().update_one({"_id": ObjectId(mess_id)}, {"$set": updated})
        flash("Mess updated successfully!", "success")
        return redirect(url_for("mess.profile"))

    return render_template("edit_mess.html", mess=m)


# ======================================================
# UPLOAD MESS IMAGE
# ======================================================
@mess.route("/upload_image/<mess_id>", methods=["POST"])
def upload_mess_image(mess_id):
    image = request.files.get("image")
    if not image:
        flash("No image selected", "danger")
        return redirect(url_for("mess.profile"))

    upload = cloudinary.uploader.upload(image)
    image_url = upload.get("secure_url")

    messes().update_one(
        {"_id": ObjectId(mess_id)},
        {"$push": {"images": image_url}}
    )

    flash("Image uploaded!", "success")
    return redirect(url_for("mess.profile"))


# ======================================================
# DELETE MESS IMAGE
# ======================================================
@mess.route("/delete_image/<mess_id>", methods=["POST"])
def delete_mess_image(mess_id):
    image_url = request.form.get("image_url")

    messes().update_one(
        {"_id": ObjectId(mess_id)},
        {"$pull": {"images": image_url}}
    )

    flash("Image deleted!", "success")
    return redirect(url_for("mess.profile"))


# ======================================================
# APPLY FOR MESS
# ======================================================
@mess.route("/apply/<mess_id>", methods=["POST"])
def apply_mess(mess_id):

    if session.get("role") != "student":
        flash("Login as student!", "warning")
        return redirect(url_for("login", role="student"))

    student = session["user"]
    student_id = str(session["user_id"])

    m = messes().find_one({"_id": ObjectId(mess_id)})

    if not m:
        flash("Mess not found!", "danger")
        return redirect(url_for("student_page"))

    # 🔥 CHECK: already hosted
    for h in m.get("hosted_students", []):
        if h["student_id"] == student_id:
            flash("You are already enrolled in this mess!", "info")
            return redirect(url_for("student.mess_details", mess_id=mess_id))

    # 🔥 CHECK: already applied
    for req in m.get("requests", []):
        if req["student_id"] == student_id and req["status"] == "pending":
            flash("You have already applied for this mess!", "info")
            return redirect(url_for("student.mess_details", mess_id=mess_id))

    request_entry = {
        "_id": ObjectId(),
        "student_id": student_id,
        "student_name": student["name"],
        "student_mobile": student["mobile"],
        "status": "pending"
    }

    messes().update_one(
        {"_id": ObjectId(mess_id)},
        {"$push": {"requests": request_entry}}
    )

    flash("Application sent successfully!", "success")
    return redirect(url_for("student.mess_details", mess_id=mess_id))


# ======================================================
# VIEW REQUESTS
# ======================================================
@mess.route("/requests")
def view_requests():
    owner_id = str(session["user_id"])
    m = messes().find_one({"owner_id": owner_id})

    enriched = []
    for req in m.get("requests", []):
        st = students().find_one({"_id": ObjectId(req["student_id"])})

        enriched.append({
            "_id": req["_id"],
            "status": req["status"],
            
            "student_info": {
                "name": st.get("name"),
                "mobile": st.get("mobile"),
                "address": st.get("student_info", {}).get("address"),
                "college": st.get("student_info", {}).get("college"),
                "aadhaar_file": st.get("student_info", {}).get("aadhaar_file"),
                "college_id_file": st.get("student_info", {}).get("college_id_file"),
            } if st else {}
                    })

    return render_template("mess_requests.html", mess=m, requests=enriched)


# ======================================================
# ACCEPT REQUEST
# ======================================================
@mess.route("/requests/accept/<mess_id>/<request_id>", methods=["POST"])
def accept_request(mess_id, request_id):
    m = messes().find_one({"_id": ObjectId(mess_id)})

    req = next((r for r in m.get("requests", []) if str(r["_id"]) == request_id), None)

    if not req:
        flash("Request not found!", "danger")
        return redirect(url_for("mess.view_requests"))

    student_id = req["student_id"]

    # Add to hosted_students
    student = students().find_one({"_id": ObjectId(req["student_id"])})

    hosted_entry = {
            "student_id": req["student_id"],
            "name": student.get("name"),
            "mobile": student.get("mobile"),
            "college": student.get("student_info", {}).get("college"),
            "rent_paid": False,
            "payment_mode": None,
            "rent_paid_date": None,
            "hosted_date": datetime.now().strftime("%Y-%m-%d"),
            "aadhaar_file": student.get("student_info", {}).get("aadhaar_file"),
            "college_id_file": student.get("student_info", {}).get("college_id_file")
        }

    messes().update_one(
            {"_id": ObjectId(mess_id)},
            {"$push": {"hosted_students": hosted_entry}}
        )

    # Remove from requests
    messes().update_one(
        {"_id": ObjectId(mess_id)},
        {"$pull": {"requests": {"_id": ObjectId(request_id)}}}
    )

    flash("Request accepted!", "success")
    return redirect(url_for("mess.view_requests"))


# ======================================================
# REJECT REQUEST
# ======================================================
@mess.route("/requests/reject/<mess_id>/<request_id>", methods=["POST"])
def reject_request(mess_id, request_id):
    messes().update_one(
        {"_id": ObjectId(mess_id)},
        {"$pull": {"requests": {"_id": ObjectId(request_id)}}}
    )

    flash("Request rejected!", "info")
    return redirect(url_for("mess.view_requests"))


# ======================================================
# HOSTED STUDENTS
# ======================================================
@mess.route("/hosted")
def hosted_students():
    owner_id = str(session["user_id"])
    m = messes().find_one({"owner_id": owner_id})

    hosted_full = []

    for h in m.get("hosted_students", []):
        student_doc = students().find_one({"_id": ObjectId(h["student_id"])})

        hosted_full.append({
            "student_id": h.get("student_id"),
            "name": h.get("name"),
            "mobile": h.get("mobile"),
            "college": h.get("college"),
            "rent_paid": h.get("rent_paid"),
            "payment_mode": h.get("payment_mode"),
            "rent_paid_date": h.get("rent_paid_date"),
            "hosted_date": h.get("hosted_date"),
            "aadhaar_file": h.get("aadhaar_file"),
            "college_id_file": h.get("college_id_file"),
        })

    return render_template("mess_hosted.html", mess=m, hosted=hosted_full)

#  remove_hosted
@mess.route("/hosted/remove/<mess_id>/<student_id>", methods=["POST"])
def remove_hosted(mess_id, student_id):
    messes().update_one(
        {"_id": ObjectId(mess_id)},
        {"$pull": {"hosted_students": {"student_id": student_id}}}
    )
    flash("Student removed!", "info")
    return redirect(url_for("mess.hosted_students"))

from datetime import datetime

@mess.route("/update-rent/<mess_id>/<student_id>", methods=["POST"])
def update_rent_status(mess_id, student_id):
    rent_paid = request.form.get("rent_paid") == "true"
    payment_mode = request.form.get("payment_mode")

    update = {
        "hosted_students.$.rent_paid": rent_paid,
        "hosted_students.$.payment_mode": payment_mode
    }

    if rent_paid:
        update["hosted_students.$.rent_paid_date"] = datetime.now().strftime("%Y-%m-%d")
    else:
        update["hosted_students.$.rent_paid_date"] = None

    messes().update_one(
        {
            "_id": ObjectId(mess_id),
            "hosted_students.student_id": student_id
        },
        {"$set": update}
    )

    flash("Updated!", "success")
    return redirect(url_for("mess.hosted_students"))


@mess.route("/send-reminder")
def send_reminder_all():
    owner_id = str(session["user_id"])
    m = messes().find_one({"owner_id": owner_id})

    unpaid = [s for s in m.get("hosted_students", []) if not s.get("rent_paid")]

    if not unpaid:
        flash("No unpaid students!", "info")
        return redirect(url_for("mess.hosted_students"))

    numbers = ",".join(["91" + s["mobile"] for s in unpaid])

    msg = "Please pay your mess fees."

    return redirect(f"https://wa.me/{numbers}?text={msg}")
# ======================================================
# MESS DETAILS PAGE
# ======================================================
@mess.route("/<mess_id>")
def details(mess_id):
    m = messes().find_one({"_id": ObjectId(mess_id)})
    if not m:
        flash("Mess not found!", "danger")
        return redirect(url_for("student.dashboard"))
    return render_template("mess_details.html", mess=m)


# ======================================================
# ADD REVIEW
# ======================================================
@mess.route("/review/<mess_id>", methods=["POST"])
def add_review(mess_id):
    student_id = str(session["user_id"])
    student_name = session["user"]["name"]

    rating = int(request.form.get("rating"))
    comment = request.form.get("comment")

    m = messes().find_one({"_id": ObjectId(mess_id)})

    sentiment = analyze_sentiment(comment, rating)

    review = {
        "_id": ObjectId(),
        "student_id": student_id,
        "student_name": student_name,
        "rating": rating,
        "comment": comment,
        "sentiment": sentiment["sentiment"],
        "sentiment_score": sentiment["final_score"],
        "date": datetime.now().strftime("%Y-%m-%d")
    }

    messes().update_one({"_id": ObjectId(mess_id)}, {"$push": {"reviews": review}})

    flash("Review added!", "success")
    return redirect(url_for("mess.details", mess_id=mess_id))


# ======================================================
# SENTIMENT PAGE
# ======================================================
@mess.route("/sentiment/<mess_id>")
def mess_sentiment(mess_id):
    m = messes().find_one({"_id": ObjectId(mess_id)})
    reviews = m.get("reviews", [])

    positive = negative = neutral = 0

    for r in reviews:
        score = sia.polarity_scores(r["comment"])["compound"]
        if score >= 0.05: positive += 1
        elif score <= -0.05: negative += 1
        else: neutral += 1

    return render_template(
        "mess_sentiment.html",
        mess=m,
        total=len(reviews),
        positive=positive,
        neutral=neutral,
        negative=negative
    )


# ======================================================
# SENTIMENT CHART
# ======================================================
@mess.route("/sentiment_chart/<mess_id>")
def mess_sentiment_chart(mess_id):
    m = messes().find_one({"_id": ObjectId(mess_id)})
    reviews = m.get("reviews", [])

    positive = negative = neutral = 0

    for r in reviews:
        score = sia.polarity_scores(r["comment"])["compound"]
        if score >= 0.05: positive += 1
        elif score <= -0.05: negative += 1
        else: neutral += 1

    labels = ["Positive", "Neutral", "Negative"]
    sizes = [positive, neutral, negative]

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.pie(sizes, labels=labels, autopct="%1.1f%%")
    ax.set_title("Mess Sentiment Distribution")

    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close()

    return Response(buffer.getvalue(), mimetype="image/png")
