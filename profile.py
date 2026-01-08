from flask import Flask, request, jsonify, send_file, Blueprint
from firebase_admin import firestore, auth
from datetime import datetime
import SimpleITK as sitk
from flask import Flask, request, jsonify, send_file
import numpy as np
import os
from PIL import Image
import base64
from io import BytesIO
import pyvista as pv
import nibabel as nib
import pydicom




profile_bp = Blueprint('profile_bp', __name__)

@profile_bp.route("/get_profile_info")
def get_profile_info():
    try:
        # 🔹 Get the ID token from cookie
        token = request.cookies.get("idToken")
        if not token:
            return jsonify({"error": "Missing token"}), 401

        # 🔹 Verify the token and get decoded info
        decoded = auth.verify_id_token(token)
        uid = decoded["uid"]
        email = decoded.get("email")  # email of the logged-in user

        # 🔹 Fetch the profile document using UID
        doc = firestore.client().collection("profile_info").document(uid).get()
        if not doc.exists:
            return jsonify({"error": "Profile not found"}), 404

        info = doc.to_dict()

        # 🔹 Combine token info + profile info
        response = {
            "uid": uid,
            "email": email,
            **info  # merge all profile fields
        }

        return jsonify(response)

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"error": str(e)}), 500