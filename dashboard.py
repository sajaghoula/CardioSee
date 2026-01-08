from flask import Flask, request, jsonify, send_file, Blueprint
from firebase_admin import firestore, auth
from datetime import datetime
import SimpleITK as sitk
from flask import Flask, request, jsonify, send_file
import numpy as np
import os
from io import BytesIO




dashboard_bp = Blueprint('dashboard_bp', __name__)

@dashboard_bp.route("/get_image_counts")
def get_image_counts():
    try:
        db = firestore.client()
        images_ref = db.collection("image_data")
        docs = images_ref.stream()

        total = 0
        cardio_count = 0

        for doc in docs:
            total += 1
            data = doc.to_dict()
            if data.get("geometry", {}).get("cardio") == True:
                cardio_count += 1

        return jsonify({
            "total": total,
            "cardio": cardio_count
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/get_tissue_distribution")
def get_tissue_distribution():
    try:
        db = firestore.client()
        images_ref = db.collection("image_data")
        docs = images_ref.stream()

        tissue_counts = {}  # dict to store counts per tissue

        for doc in docs:
            data = doc.to_dict()
            dominant_tissue = data.get("quality", {}).get("dominant_tissue")
            if dominant_tissue:
                tissue_counts[dominant_tissue] = tissue_counts.get(dominant_tissue, 0) + 1

        return jsonify(tissue_counts)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/get_intensity_counts")
def get_intensity_counts():
    try:
        db = firestore.client()
        images_ref = db.collection("image_data")
        docs = images_ref.stream()

        low_count = 0
        high_count = 0

        for doc in docs:
            data = doc.to_dict()
            intensity_flag = data.get("quality", {}).get("dark")  # still using your field
            if intensity_flag == 1:
                low_count += 1
            else:
                high_count += 1

        return jsonify({
            "low": low_count,
            "high": high_count
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500





@dashboard_bp.route("/get_median_volume")
def get_median_volume():
    try:
        db = firestore.client()
        images_ref = db.collection("image_data")
        docs = images_ref.stream()

        volumes_mm3 = []

        for doc in docs:
            data = doc.to_dict()
            volume = data.get("geometry", {}).get("volume_mm3")
            if volume is not None:
                volumes_mm3.append(volume)

        if not volumes_mm3:
            return jsonify({"median_cm3": 0})

        median_mm3 = float(np.median(volumes_mm3))
        median_cm3 = median_mm3 / 1000  # convert mm³ → cm³

        return jsonify({"median_cm3": round(median_cm3, 2)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
