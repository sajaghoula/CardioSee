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




lib_bp = Blueprint('lib_bp', __name__)

def get_images_path():
    """Get the image folder path from Firestore system variables"""
    try:
        db = firestore.client()
        
        # Query for the images_path variable
        docs = db.collection('SystemVariables')\
                .where('variable', '==', 'images_path')\
                .limit(1)\
                .stream()
        
        for doc in docs:
            data = doc.to_dict()
            return data.get('value', '/home/saja/CardioSee/images/download/')  # Default fallback
        
        
    except Exception as e:
        print(f"Error getting image folder path: {e}")



        
IMAGE_FOLDER = get_images_path()

@lib_bp.route("/library_data", methods=["GET"])
def library_data():
    db = firestore.client()

    image_docs = db.collection("images").where("deleted", "==", False).stream()

    result = []
    for img in image_docs:
        img_data = img.to_dict()
        img_id = img.id

        data_query = db.collection("image_data").where("imageId", "==", img_id).stream()
        data_entry = None
        for d in data_query:
            data_entry = d.to_dict()

        created_at = img_data.get("createdAt")
        if isinstance(created_at, datetime):
            # Convert to YYYY-MM-DD string (date only)
            created_at_date = created_at.date().isoformat()  # e.g., "2025-12-04"
        else:
            created_at_date = None



        stats = data_entry.get("stats", {}) if data_entry else {}
        quality = data_entry.get("quality", {}) if data_entry else {}
        geometry = data_entry.get("geometry", {}) if data_entry else {}
        physical_size = geometry.get("physical_size")
        if physical_size:
            physical_size = tuple(round(v, 2) for v in physical_size)

        

        


        result.append({
            "id": img_id,
            "name": img_data.get("name"),
            "filetype": img_data.get("filetype"),
            "createdBy": get_username(img_data.get("createdBy")),
            "createdAt": created_at_date,
            "metadata": data_entry.get("metadata") if data_entry else {},
            "stats": stats,
            "quality": quality,
            "geometry": geometry,


            "min": stats.get("min"),
            "max": stats.get("max"),
            "mean": round(stats.get("mean"), 3) if stats.get("mean") is not None else None,
            "range": quality.get("intensity_range"),
            "median": stats.get("median"),
            "dark": quality.get("dark"),
            "dominant_tissue": quality.get("dominant_tissue"),
            "physical_size": tuple(round(v, 2) for v in geometry.get("physical_size")),
            "volume_cm3": round(geometry.get("volume_mm3") / 1000, 3) ,
            "cardio": geometry.get("cardio"),
        })

    return jsonify(result)


@lib_bp.route("/load_image_by_name", methods=["GET"])
def load_image_by_name():
    filename = request.args.get("file")

    full_path = os.path.join(IMAGE_FOLDER, filename)


    if not os.path.exists(full_path):
        return jsonify({"error": "File not found"}), 400
    
    # Load .mha file exactly like upload_image did
    img = sitk.ReadImage(full_path)
    arr = sitk.GetArrayFromImage(img)  # depth, height, width
    

    depth, height, width = arr.shape


    return jsonify({
        "depth": depth,
        "height": height,
        "width": width,
    })


def get_username(uid):
    try:
        user = auth.get_user(uid)
        return user.display_name or user.email
    except auth.UserNotFoundError:
        return None
   

@lib_bp.route("/get_slice_2")
def get_slice_2():
    view = request.args.get("view")
    index = request.args.get("index")
    filename = request.args.get("file")
    firstTime = request.args.get("firstTime")

    if not view or not index or not filename:
        return jsonify({"error": "Missing parameters"}), 400

    full_path = os.path.join(IMAGE_FOLDER, filename)

    if not os.path.exists(full_path):
        return jsonify({"error": f"File not found: {filename}"}), 400

    img = sitk.ReadImage(full_path)
    vol = sitk.GetArrayFromImage(img)  # depth, height, width

    # If firstTime is 1, set index to the middle slice of the view
    if firstTime == "1":
        
        if view == "axial":
            index = vol.shape[0] // 2
        elif view == "sagittal":
            index = vol.shape[2] // 2
        elif view == "coronal":
            index = vol.shape[1] // 2
        else:
            return jsonify({"error": "Invalid view"}), 400
    else:
        index = int(index)


    # Make sure index is within bounds
    if view == "axial":
        index = min(index, vol.shape[0] - 1)
        slice_img = vol[index, :, :]
    elif view == "sagittal":
        index = min(index, vol.shape[2] - 1)
        slice_img = vol[:, :, index]
    elif view == "coronal":
        index = min(index, vol.shape[1] - 1)
        slice_img = vol[:, index, :]
    else:
        return jsonify({"error": "Invalid view"}), 400

    # Normalize to 0-255 and convert to PNG
    rng = np.ptp(slice_img)
    if rng == 0:
        slice_img = np.zeros_like(slice_img, dtype=np.uint8)
    else:
        slice_img = ((slice_img - slice_img.min()) / (rng + 1e-8) * 255).astype(np.uint8)

    pil_img = Image.fromarray(slice_img)
    buffer = BytesIO()
    pil_img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode()

    return jsonify({"image": encoded})


@lib_bp.route("/delete_image", methods=["POST"])
def delete_image():
    db = firestore.client()
    data = request.get_json()
    image_id = data.get("id")
    if not image_id:
        return jsonify({"error": "Missing image ID"}), 400

    try:
        doc_ref = db.collection("images").document(image_id)
        # update the "deleted" field to True
        doc_ref.update({"deleted": True})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@lib_bp.route("/load_volume_3d", methods=["GET"])
def load_volume_3d():
    filename = request.args.get("file")

    full_path = os.path.join(IMAGE_FOLDER, filename)

    if not os.path.exists(full_path):
        return jsonify({"error": "File not found"}), 400

    try:
        img = sitk.ReadImage(full_path)
        arr = sitk.GetArrayFromImage(img)  # depth, height, width
        arr = arr.astype(np.float32)

        # Normalize (important for DICOM and most medical images)
        arr = (arr - arr.min()) / (arr.max() - arr.min() + 1e-5)

        # Convert to base64
        arr_bytes = arr.tobytes()
        arr_b64 = base64.b64encode(arr_bytes).decode('utf-8')

        return jsonify({
            "data": arr_b64,
            "shape": arr.shape  # [depth, height, width]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    




