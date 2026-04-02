from flask import current_app

# =========================
# CORE DATABASE COLLECTIONS
# =========================

def users():
    return current_app.core_db.users

def students():
    return current_app.core_db.students

def room_owners():
    return current_app.core_db.room_owners

def mess_owners():
    return current_app.core_db.mess_owners

def payments():
    return current_app.core_db.payments

def reviews():
    return current_app.core_db.reviews

def room_allocations():
    return current_app.core_db.room_allocations

def mess_subscriptions():
    return current_app.core_db.mess_subscriptions


# =========================
# ASSETS DATABASE COLLECTIONS
# =========================

def rooms():
    return current_app.assets_db.rooms

def messes():
    return current_app.assets_db.messes
