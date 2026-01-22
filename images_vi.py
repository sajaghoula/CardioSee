from flask import Blueprint, request, jsonify
from skimage.measure import shannon_entropy
from scipy.stats import skew, kurtosis
from skimage.filters import sobel
from skimage import measure
import SimpleITK as sitk
from io import BytesIO
import nibabel as nib
from PIL import Image
import pyvista as pv
import numpy as np
import pydicom
import base64
import os

from firebase_admin import firestore
from firebase_admin import auth
from datetime import datetime



image_bp = Blueprint('image_bp', __name__)


# Store the loaded volume in memory (for simplicity)
volume_store = {}
z_threshold = 300

import SimpleITK as sitk
import tempfile
import os

def nifti_to_mha(file):
    """
    Convert NIfTI (.nii / .nii.gz) to MHA
    Returns a file-like object
    """
    with tempfile.NamedTemporaryFile(suffix=".nii.gz", delete=False) as tmp_nifti:
        file.save(tmp_nifti.name)
        nifti_path = tmp_nifti.name

    image = sitk.ReadImage(nifti_path)

    mha_tmp = tempfile.NamedTemporaryFile(suffix=".mha", delete=False)
    sitk.WriteImage(image, mha_tmp.name)

    os.unlink(nifti_path)  # cleanup

    return open(mha_tmp.name, "rb")



def dicom_to_mha(file):
    """
    Convert DICOM (.dcm) to MHA
    Assumes a single DICOM file or same-series upload
    """
    with tempfile.TemporaryDirectory() as dicom_dir:
        dicom_path = os.path.join(dicom_dir, file.filename)
        file.save(dicom_path)

        reader = sitk.ImageSeriesReader()
        series_ids = reader.GetGDCMSeriesIDs(dicom_dir)

        if not series_ids:
            raise ValueError("No DICOM series found")

        series_files = reader.GetGDCMSeriesFileNames(dicom_dir, series_ids[0])
        reader.SetFileNames(series_files)

        image = reader.Execute()

        mha_tmp = tempfile.NamedTemporaryFile(suffix=".mha", delete=False)
        sitk.WriteImage(image, mha_tmp.name)

        return open(mha_tmp.name, "rb")


@image_bp.route('/upload_image', methods=['POST'])
def upload_image():
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    filename = file.filename.lower()

    if filename.endswith((".nii", ".nii.gz")):
        mha_file = nifti_to_mha(file)

    elif filename.endswith(".dcm"):
        mha_file = dicom_to_mha(file)

    elif filename.endswith(".mha"):
        mha_file = file

    else:
        return jsonify({"error": "Unsupported file type"}), 400

    return prepare_mha(mha_file)




# Return a single slice on demand
@image_bp.route('/get_slice', methods=['GET'])
def get_slice():
    view = request.args.get('view')  # axial / sagittal / coronal
    index = int(request.args.get('index', 0))

    vol = volume_store.get('volume')
    if vol is None:
        return jsonify({"error": "No volume loaded"}), 400

    # Extract requested slice
    if view == "axial":
        if index >= vol.shape[0]:
            index = vol.shape[0] - 1
        slice_img = vol[index, :, :]
    elif view == "sagittal":
        if index >= vol.shape[2]:
            index = vol.shape[2] - 1
        slice_img = vol[:, :, index]
        slice_img = np.flipud(slice_img) # FIX Y-axis


    elif view == "coronal":
        if index >= vol.shape[1]:
            index = vol.shape[1] - 1
        slice_img = vol[:, index, :]
        slice_img = np.flipud(slice_img) # FIX Y-axis
    else:
        return jsonify({"error": "Invalid view"}), 400

    # Normalize and convert to base64 PNG
    slice_img = normalize_slice(slice_img)
    b64 = array_to_base64(slice_img)
    return jsonify({"image": b64})


@image_bp.route('/upload_info', methods=['POST'])
def upload_info():

    db = firestore.client()

    file = request.files.get("file")

    if not file:
        return jsonify({"error": "No file uploaded"}), 400



    filename = file.filename
    extension = filename.split(".")[-1].lower()

    auth_header = request.headers.get("Authorization", None)
    id_token = auth_header.split(" ")[1]
    decoded = auth.verify_id_token(id_token, clock_skew_seconds=5)

    user_uid = decoded["uid"]
    user_email = decoded.get("email")
    user_name = decoded.get("name")


    info = extract_image_info(file)


    image_doc = {
        "name": filename,
        "filetype": extension,
        "createdBy": user_uid,
        "createdAt": datetime.utcnow(),
        "deleted": False
    }
    image_ref = db.collection("images").add(image_doc)
    image_id = image_ref[1].id 

    data_doc = {
        "imageId": image_id,
        "metadata": info.get("metadata", {}),
        "stats": info.get("statistics", {}),
        "geometry": info.get("geometry", {}),
        "quality": info.get("quality", {}),
        "createdAt": datetime.utcnow(),
        "createdBy": user_uid
    }



    db.collection("image_data").add(data_doc)


    # ✅ Only return 1 on success
    return jsonify({"success": 1})


def normalize_slice(slice_array):
    slice_array = slice_array.astype(np.float32)
    slice_array -= slice_array.min()
    if slice_array.max() != 0:
        slice_array /= slice_array.max()
    slice_array *= 255
    return slice_array.astype(np.uint8)


def array_to_base64(arr):
    arr = np.clip(arr, 0, np.max(arr))  # remove negatives
    arr = (arr / arr.max() * 255).astype(np.uint8) if arr.max() > 0 else arr

    img = Image.fromarray(arr)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def prepare_nifti(file, filename):

    temp_path = f"/tmp/{filename}"
    file.save(temp_path)

    img = nib.load(temp_path)
    vol = img.get_fdata()
    vol = np.nan_to_num(vol)  # remove NaNs
    vol = vol.astype(np.float32)

    # Reorder NIfTI to (Z,Y,X)
    if vol.ndim == 3:
        vol = np.transpose(vol, (2, 1, 0))

    volume_store["volume"] = vol


    # --- OPTIONAL: downsample volume for JS 3D viewer ---
    max_size = 128  # max dimension for web performance
    max_xy = 50
    factor_x = max(1, vol.shape[2] // max_xy)
    factor_y = max(1, vol.shape[1] // max_xy)
    factor = max(1, max(vol.shape) // max_size)
    vol_small = vol[::factor, ::factor_y, ::factor_x]  
    vol_small = vol[::factor_x, ::factor, ::factor_y]  
    vol_list = vol_small.tolist()



    # vol = your 3D numpy array
    verts, faces, normals, values = measure.marching_cubes(vol, level=50)

    # Convert faces to PyVista format
    faces_pv = np.hstack([np.full((faces.shape[0], 1), 3), faces]).astype(np.int64)
    faces_pv = faces_pv.flatten()


    # Plot 3D in a new tap:


    # Create PyVista mesh
    # mesh = pv.PolyData(verts, faces_pv)

    # Render
    # plotter = pv.Plotter()
    # plotter.add_mesh(mesh, color='white')
    # plotter.show()



    return jsonify({
        "depth": vol.shape[0],
        "height": vol.shape[1],
        "width": vol.shape[2],
        "type": "nifti",
        "volume_3d": vol_list,
        "downsample_factor": factor,
        "downsample_factorx": factor_x,
        "downsample_factory": factor_y
    })


def prepare_dicom(file):

        ds = pydicom.dcmread(file)
        vol = ds.pixel_array

        if vol.ndim == 2:
            vol = vol[np.newaxis, :, :]

        volume_store["volume"] = vol

        # --- OPTIONAL: downsample volume for JS 3D viewer ---
        max_size = 128  # max dimension for web performance
        max_xy = 256
        factor_x = max(1, vol.shape[2] // max_xy)
        factor_y = max(1, vol.shape[1] // max_xy)
        factor = max(1, max(vol.shape) // max_size)
        vol_small = vol[::factor, ::factor_y, ::factor_x]  
        vol_list = vol_small.tolist()


        # vol = your 3D numpy array
        verts, faces, normals, values = measure.marching_cubes(vol, level=50)

        # Convert faces to PyVista format
        faces_pv = np.hstack([np.full((faces.shape[0], 1), 3), faces]).astype(np.int64)
        faces_pv = faces_pv.flatten()


        # Plot 3D in a new Tap


        # Create PyVista mesh
        # mesh = pv.PolyData(verts, faces_pv)

        # Render
        # plotter = pv.Plotter()
        # plotter.add_mesh(mesh, color='white')
        # plotter.show()



        return jsonify({
            "depth": vol.shape[0],
            "height": vol.shape[1],
            "width": vol.shape[2],
            "type": "dicom",
            "volume_3d": vol_list,
            "downsample_factor": factor,
            "downsample_factorx": factor_x,
            "downsample_factory": factor_y
        })



import os
import numpy as np
import SimpleITK as sitk
import tempfile

def prepare_mha(file):
    """
    Accepts either:
    - Flask FileStorage (has .filename, .save)
    - Python file object (BufferedReader)
    """

    # -------------------------
    # Determine temp path
    # -------------------------
    if hasattr(file, "filename"):  # Flask upload
        temp_path = f"/tmp/{file.filename}"
        file.save(temp_path)

    else:  # Python file object (from conversion)
        temp_path = tempfile.NamedTemporaryFile(suffix=".mha", delete=False).name
        with open(temp_path, "wb") as f:
            f.write(file.read())

    # -------------------------
    # Read MHA
    # -------------------------
    img = sitk.ReadImage(temp_path)

    img = resample_to_isotropic(img)


    vol = sitk.GetArrayFromImage(img).astype(np.float32)
    vol = np.nan_to_num(vol)

    if vol.ndim == 2:
        vol = vol[np.newaxis, :, :]

    volume_store["volume"] = vol


    return jsonify({
        "depth": vol.shape[0],
        "height": vol.shape[1],
        "width": vol.shape[2],
        "type": "mha"
    })



def extract_image_info(file):
    filename = file.filename.lower()
    spacing = 0

    info = {
        "image_type": None,
        "modality": None,
        "metadata": {},
        "statistics": {},
        "geometry": {},
        "quality": {}
    }

    # -------------------------
    # DICOM
    # -------------------------
    if filename.endswith(".dcm"):
        ds = pydicom.dcmread(file)
        vol = ds.pixel_array
        if vol.ndim == 2:
            vol = vol[np.newaxis, :, :]

        info["image_type"] = "DICOM"
        info["modality"] = getattr(ds, "Modality", "unknown")

        # Metadata
        dicom_meta = {}
        for elem in ds:
            if elem.tag == (0x7FE0, 0x0010):  # PixelData
                continue
            if elem.VR == "SQ":
                continue
            dicom_meta[str(elem.tag)] = str(elem.value)

        info["metadata"] = dicom_meta


    # -------------------------
    # MHA / MHD
    # -------------------------
    elif filename.endswith(".mha") or filename.endswith(".mhd"):
        temp_path = f"/tmp/{filename}"
        file.save(temp_path)
        img = sitk.ReadImage(temp_path)
        vol = sitk.GetArrayFromImage(img).astype(np.float32)

        info["image_type"] = "MHA"
        spacing = img.GetSpacing()

        # Metadata
        info["metadata"] = {
            "spacing": spacing,
            "origin": img.GetOrigin(),
            "direction": img.GetDirection()
        }

    # -------------------------
    # NIfTI
    # -------------------------
    elif filename.endswith(".nii") or filename.endswith(".nii.gz"):
        temp_path = f"/tmp/{filename}"
        file.save(temp_path)
        img = nib.load(temp_path)
        vol = img.get_fdata().astype(np.float32)

        info["image_type"] = "NIFTI"

        # Metadata
        info["metadata"] = {
            "affine": img.affine.tolist(),
            "header": {k: str(v) for k, v in dict(img.header).items()}
        }

    else:
        return {"error": "Unsupported file type"}



    # Normalize shape
    vol = np.nan_to_num(vol)
    if vol.ndim == 2:
        vol = vol[np.newaxis, :, :]

    # ------------------------------
    # Statistics
    # ------------------------------
    flat = vol.flatten()
    shape = vol.shape

    info["statistics"] = {
        "shape": shape,
        "min": float(np.min(vol)),
        "max": float(np.max(vol)),
        "mean": float(np.mean(vol)),
        "median": float(np.median(vol)),
        "std": float(np.std(vol)),
        "var": float(np.var(vol)),
        "p25": float(np.percentile(vol, 25)),
        "p75": float(np.percentile(vol, 75)),
        "histogram": np.histogram(flat, bins=50)[0].tolist()
    }

    # ------------------------------
    # Geometry
    # ------------------------------
    coords = np.argwhere(vol > 0)

    size_info = calculate_physical_size(spacing, shape)

    info["geometry"] = {
        "bounding_box": None,
        "center_of_mass": None
    }

    if coords.size > 0:
        info["geometry"] = {
            "bounding_box": {
                "min": coords.min(axis=0).tolist(),
                "max": coords.max(axis=0).tolist()
            },
            "center_of_mass": coords.mean(axis=0).tolist(),
            "physical_size" : size_info["physical_size"],
            "volume_mm3" : size_info["volume_mm3"],
            "cardio" : size_info["cardio"],
        }


    # ------------------------------
    # Quality metrics
    # ------------------------------

    intensity_range = info["statistics"]["max"] - info["statistics"]["min"]

    gradient = sobel(vol.astype(np.float64))


    dark_info = analyze_image_median(info["statistics"]["median"])
    



    info["quality"] = {
        "SNR": float(np.mean(flat) / (np.std(flat) + 1e-8)),
        "CNR": float((np.max(flat) - np.min(flat)) / (np.std(flat) + 1e-8)),
        "entropy": float(shannon_entropy(vol)),
        "sharpness": float(np.mean(gradient)),
        "skewness": float(skew(flat)),
        "kurtosis": float(kurtosis(flat)),
        "intensity_range" : intensity_range,
        "dark": dark_info["dark"],               
        "dominant_tissue": dark_info["dominant_tissue"]
    }

    return info


def save_image_record(db, name, filetype, user):
    doc_ref = db.collection("images").document()
    image_id = doc_ref.id

    doc_ref.set({
        "pk": image_id,
        "name": name,
        "fileType": filetype,
        "createdBy": user,
        "creationDateTime": datetime.utcnow().isoformat(),
        "deleted": False
    })

    return image_id


def analyze_image_median(median_hu):
    """
    Determine if an image is dark and what tissue type dominates based on median HU.

    Parameters:
        median_hu (float): median intensity of the image in Hounsfield Units (HU)

    Returns:
        dict: {
            "dark": 0 or 1,
            "dominant_tissue": str
        }
    """
    # Determine darkness
    # Threshold: median < -700 HU considered dark
    dark = 1 if median_hu < -700 else 0

    # Determine dominant tissue
    if median_hu < -900:
        tissue = "Air-dominant"
    elif -900 <= median_hu < -500:
        tissue = "Lung"
    elif -500 <= median_hu < -100:
        tissue = "Fat / low-density tissue"
    elif -100 <= median_hu < 0:
        tissue = "Fat–water transition"
    elif 0 <= median_hu < 50:
        tissue = "Soft tissue / water"
    elif 50 <= median_hu <= 300:
        tissue = "Dense soft tissue / enhanced structures"
    else:  # median_hu > 300
        tissue = "Bone / calcification"

    return {"dark": dark, "dominant_tissue": tissue}


def calculate_physical_size(spacing, shape):
    """
    Calculate the physical size of a 3D image.

    Parameters:
        spacing (tuple/list): voxel spacing in mm (x, y, z)
        shape (tuple/list): volume shape in voxels (z, y, x)

    Returns:
        tuple: physical size in mm (x_size, y_size, z_size)
    """
    # Note: shape order = (z, y, x), spacing order = (x, y, z)
    size_x = shape[2] * spacing[0]  # x dimension
    size_y = shape[1] * spacing[1]  # y dimension
    size_z = shape[0] * spacing[2]  # z dimension

    # Compute total volume
    volume = size_x * size_y * size_z

    # Classify cardio
    cardio = 1 if size_z <= z_threshold else 0

    return {
        "physical_size": (size_x, size_y, size_z),
        "volume_mm3": volume,
        "cardio": cardio
    }


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
