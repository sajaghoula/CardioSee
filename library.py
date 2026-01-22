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
import firebase_admin
from firebase_admin import credentials, firestore




lib_bp = Blueprint('lib_bp', __name__)

LABEL_COLORS = {
    4: (255, 165, 0),   # Subcutaneous Tissue → Orange
    2: (0, 255, 0),     # Muscle → Green
    3: (255, 255, 0),   # Abdominal Cavity → Yellow
    1: (255, 0, 0),     # Thoracic Cavity → Red
    5: (139, 69, 19),   # Bones → Brown
    6: (255, 192, 203), # Parotid Glands → Pink
    7: (0, 0, 255),     # Pericardium → Blue
    8: (128, 0, 128),   # Breast Implant → Purple
    9: (0, 255, 255),   # Mediastinum → Cyan
    10: (160, 32, 240), # Brain → Violet
    11: (128, 128, 128),# Spinal Cord → Gray
    12: (255, 140, 0),  # Thyroid → Dark Orange
    13: (0, 128, 0),    # Submandibular → Dark Green
}


def get_images_path():
    """Get the image folder path from Firestore system variables"""
    try:
        # Initialize Firebase if not already initialized
        if not firebase_admin._apps:
            cred = credentials.Certificate("/home/saja/CardioSee/serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
        
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
        return '/home/saja/CardioSee/images/download/'  # fallback




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
        # Get segmentation job for this image
        
        seg_query = db.collection("cardiac_segmentation_jobs") \
              .where("imageId", "==", img_id) \
              .limit(1) \
              .stream()

        data_entry = None
        for d in data_query:
            data_entry = d.to_dict()

        segmentation = None
        for s in seg_query:
            segmentation = s.to_dict()

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


        total_eat_volume = None
        if segmentation:
            total_eat_volume = segmentation.get("analysis_results", {}).get("fat_analysis", {}).get("volume_total_eat_cm3")
        
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
            "segmentation": segmentation,


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
            "total_eat_volume": round(total_eat_volume, 2) if total_eat_volume is not None else None,
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
def get_slice_2(request):
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
    img = resample_to_isotropic(img) 
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
        slice_img = np.flipud(slice_img)   # FIX Y-axis


    elif view == "coronal":
        index = min(index, vol.shape[1] - 1)
        slice_img = vol[:, index, :]
        slice_img = np.flipud(slice_img)   # FIX Y-axis
    
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
        arr = np.flip(arr, axis=1) 
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
    


@lib_bp.route("/get_slice_mapping")
def get_slice_mapping():

    imageId = request.args.get("image_id")

    # Firestore: get the job_id
    db = firestore.client()
    job_docs = db.collection("cardiac_segmentation_jobs") \
        .where("imageId", "==", imageId) \
        .limit(1) \
        .stream()
    job_doc = next(job_docs, None)
    if job_doc is None:
        res = get_slice_2(request)
    else:
        res = get_slice_overlay(request)
        
        
    return res



def apply_mask_overlay(
    rgb,
    mask_slice,
    color,
    alpha=0.4,
    condition="equals",
    label=None
):
    """
    Apply an overlay mask to an RGB image.

    Parameters:
    - rgb: (H, W, 3) uint8 image
    - mask_slice: (H, W) numpy array
    - color: (R, G, B)
    - alpha: transparency
    - condition:
        - "equals" → mask_slice == label
        - "positive" → mask_slice > 0
    - label: required if condition == "equals"
    """

    if condition == "equals":
        if label is None:
            raise ValueError("label must be provided when condition='equals'")
        mask = mask_slice == label
    elif condition == "positive":
        mask = mask_slice > 0
    else:
        raise ValueError("Invalid condition")

    for c in range(3):
        rgb[..., c][mask] = (
            (1 - alpha) * rgb[..., c][mask] + alpha * color[c]
        )

    return rgb



@lib_bp.route("/get_slice_overlay")
def get_slice_overlay(request):
    view = request.args.get("view")
    index = int(request.args.get("index"))
    filename = request.args.get("file")
    imageId = request.args.get("image_id")

    # Firestore: get the job_id
    db = firestore.client()
    job_docs = db.collection("cardiac_segmentation_jobs") \
        .where("imageId", "==", imageId) \
        .limit(1) \
        .stream()
    job_doc = next(job_docs, None)
    if job_doc is None:
        return jsonify({"error": "Segmentation job not found"}), 404
    job_id = job_doc.id

    # Paths
    img_path = os.path.join(IMAGE_FOLDER, filename)
    seg_base = f"/home/saja/CardioSee/cardiac_segmentation_runs/{job_id}/final_outputs"
    multi_path = os.path.join(seg_base, filename.replace(".mha", "_segmented_multiclass.mha"))
    peri_path = os.path.join(seg_base, filename.replace(".mha", "_segmented_pericardium.mha"))
    peri_path2 = os.path.join(seg_base, filename.replace(".mha", "_segmented_pericardium.mha"))
    eat_path = os.path.join(seg_base, filename.replace(".mha", "_segmented_eat.mha"))

    # Load volumes
    img_itk = sitk.ReadImage(img_path)
    img_itk = resample_to_isotropic(img_itk)
    img = sitk.GetArrayFromImage(img_itk)

    multi = convert_to_numpy(multi_path)
    peri = convert_to_numpy(peri_path)
    peri2 = convert_to_numpy(peri_path2)
    eat = convert_to_numpy(eat_path)

    # Extract slice
    if view == "axial":
        slice_img = img[index, :, :]
        slice_multi = multi[index, :, :]
        slice_peri = peri[index, :, :]
        slice_peri2 = peri2[index, :, :]
        slice_eat = eat[index, :, :]

    elif view == "sagittal":
        slice_img = np.flipud(img[:, :, index])
        slice_multi = np.flipud(multi[:, :, index])
        slice_peri = np.flipud(peri[:, :, index])
        slice_peri2 = np.flipud(peri2[:, :, index])
        slice_eat = np.flipud(eat[:, :, index])

    elif view == "coronal":
        slice_img = np.flipud(img[:, index, :])
        slice_multi = np.flipud(multi[:, index, :])
        slice_peri = np.flipud(peri[:, index, :])
        slice_peri2 = np.flipud(peri2[:, index, :])
        slice_eat = np.flipud(eat[:, index, :])

    else:
        return jsonify({"error": "Invalid view"}), 400

    # Normalize base image
    slice_img = (slice_img - slice_img.min()) / (slice_img.ptp() + 1e-8)
    slice_img = (slice_img * 255).astype(np.uint8)
    rgb = np.stack([slice_img] * 3, axis=-1)

    alpha = 0.4

    # --- Multiclass overlay (UNCHANGED behavior) ---
    for label, color in LABEL_COLORS.items():
        rgb = apply_mask_overlay(rgb,  slice_multi, color=color, alpha=alpha,  condition="equals", label=label)

    # --- Pericardium overlays ---
    #rgb = apply_mask_overlay(rgb, slice_peri,   color=(0, 255, 255),  alpha=alpha,condition="positive" )

    #rgb = apply_mask_overlay( rgb,    slice_peri2,   color=(0, 255, 255), alpha=alpha,  condition="positive" )

    # --- EAT overlay ---
    #rgb = apply_mask_overlay( rgb,    slice_eat,   color=(255, 255, 0), alpha=alpha,  condition="positive" )

    

    # Encode to PNG
    pil_img = Image.fromarray(rgb.astype(np.uint8))
    buf = BytesIO()
    pil_img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("utf-8")

    return jsonify({"image": encoded})


def convert_to_numpy(image_path):
    image_itk = sitk.ReadImage(image_path)
    image_itk = resample_to_isotropic(image_itk)  # Resample ITK image
    image = sitk.GetArrayFromImage(image_itk)     # Then convert to numpy
    return image



def resample_to_isotropic(img, new_spacing=(1.0, 1.0, 1.0)):
    original_spacing = img.GetSpacing()
    original_size = img.GetSize()

    new_size = [
        int(round(osz * ospc / nspc))
        for osz, ospc, nspc in zip(original_size, original_spacing, new_spacing)
    ]

    resampler = sitk.ResampleImageFilter()
    resampler.SetOutputSpacing(new_spacing)
    resampler.SetSize(new_size)
    resampler.SetOutputDirection(img.GetDirection())
    resampler.SetOutputOrigin(img.GetOrigin())
    resampler.SetInterpolator(sitk.sitkLinear)

    return resampler.Execute(img)
