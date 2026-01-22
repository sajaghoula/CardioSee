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
import SimpleITK as sitk
from firebase_admin import firestore
from firebase_admin import auth
from datetime import datetime

import os
import sys

import os
import shutil
import threading
from pathlib import Path
from datetime import datetime
import subprocess

import firebase_admin
from firebase_admin import firestore, auth

# Your existing imports for nibabel, SimpleITK, numpy, etc.
import nibabel as nib
import numpy as np
import SimpleITK as sitk
from skimage.morphology import convex_hull_image

import numpy as np
import nibabel as nib
from pathlib import Path
from firebase_admin import firestore
from typing import Dict, Any
import logging

# Set up logging to track issues
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


os.environ['nnUNet_results'] = '/home/saja/CardioSee/segmentation/nnunet/nnUNet_results'
os.environ['nnUNet_raw'] = '/home/saja/CardioSee/segmentation/nnunet/nnUNet_raw'
os.environ['nnUNet_preprocessed'] = '/home/saja/CardioSee/segmentation/nnunet/nnUNet_preprocessed'



# --- Utility functions from your pipeline ---
def convert_to_nifti(input_path: Path, output_dir: Path) -> Path:
    output_path = output_dir / f"{input_path.stem}.nii.gz"
    if input_path.name.endswith(".nii.gz"):
        shutil.copy(input_path, output_path)
        return output_path
    image = sitk.ReadImage(str(input_path))
    sitk.WriteImage(image, str(output_path))
    return output_path

def binarize_segmentation(input_path: Path, output_path: Path, label_id: int):
    img = nib.load(input_path)
    data = np.asanyarray(img.dataobj)
    mask = (data == label_id).astype(np.uint8)
    new_img = nib.Nifti1Image(mask, img.affine, img.header)
    nib.save(new_img, output_path)

def apply_convex_hull(input_path: Path, output_path: Path):
    image = sitk.ReadImage(str(input_path))
    array = sitk.GetArrayFromImage(image)
    filled = np.zeros_like(array)
    for i, slice_2d in enumerate(array):
        if np.any(slice_2d):
            filled[i] = convex_hull_image(slice_2d > 0)
    final_img = sitk.GetImageFromArray(filled.astype(array.dtype))
    final_img.CopyInformation(image)
    sitk.WriteImage(final_img, output_path)

def run_command(command: list[str]):
    subprocess.run(command, check=True)


# Add this function definition before run_segmentation_job
def extract_labels(input_path: Path, output_path: Path, labels_to_keep: list):
    """
    Extract specific labels from a multi-label segmentation.
    
    Args:
        input_path: Path to the full segmentation NIfTI file
        output_path: Path to save the extracted labels
        labels_to_keep: List of label IDs to keep (e.g., [7, 9])
    """
    img = nib.load(input_path)
    data = img.get_fdata()
    
    # Create mask with only selected labels
    mask = np.zeros_like(data, dtype=np.uint8)
    for i, label in enumerate(labels_to_keep, start=1):
        mask[data == label] = i  # Renumber as 1,2,3...
    
    # Save
    new_img = nib.Nifti1Image(mask, img.affine, img.header)
    nib.save(new_img, output_path)
    logger.info(f"Extracted labels {labels_to_keep} to {output_path.name}")
    return output_path

# --- Main function to run segmentation for a job ---
def run_segmentation_job(jobId: str, image_doc: dict, multiclass_model_id: int, pericardium_model_id: int):
    """
    Runs CADS → nnU-Net pipeline for a given uploaded image.
    Updates Firestore with status and output paths.
    """
    db = firestore.client()

    try:
        # --- 1. Setup paths ---
        uploads_dir = Path("/home/saja/CardioSee/images/download")
        runs_dir = Path("cardiac_segmentation_runs") / jobId
        temp_dir = runs_dir / "temp"
        final_dir = runs_dir / "final_outputs"
        temp_dir.mkdir(parents=True, exist_ok=True)
        final_dir.mkdir(exist_ok=True)

        # Input file path
        filename = image_doc["name"]
        input_file = uploads_dir / filename

        # Update job status
        job_ref = db.collection("cardiac_segmentation_jobs").document(jobId)
        job_ref.update({"status": "running", "startedAt": datetime.utcnow()})

        # --- 2. Convert to NIfTI ---
        nifti_input_dir = temp_dir / "0_nifti_inputs"
        nifti_input_dir.mkdir(exist_ok=True)
        nifti_file = convert_to_nifti(input_file, nifti_input_dir)
        
        logger.info(f"Converted to NIfTI: {nifti_file}")

        # --- 3. CADS initial prediction ---
        cads_dir = temp_dir / "1_cads_initial"
        cads_dir.mkdir(exist_ok=True)

        # Force correct naming for CADS
        case_id = "case001"
        nnunet_input = nifti_input_dir / f"{case_id}_0000.nii.gz"
        
        # Remove if exists and move the converted file
        if nnunet_input.exists():
            nnunet_input.unlink()
        shutil.move(nifti_file, nnunet_input)
        logger.info(f"Renamed input to: {nnunet_input}")

        # Run CADS
        logger.info("Starting CADS prediction...")
        run_command([
            "python", "CADS/cads/scripts/predict_images.py",
            "-in", str(nifti_input_dir),
            "-out", str(cads_dir),
            "-task", "559",
        ])
        logger.info("CADS prediction completed")

        # Check CADS output
        cads_output_raw = cads_dir / case_id / f"{case_id}_part_559.nii.gz"
        if not cads_output_raw.exists():
            # Try alternative naming pattern
            cads_output_raw = cads_dir / case_id / f"{case_id}.nii.gz"
            if not cads_output_raw.exists():
                # List files to debug
                files = list((cads_dir / case_id).glob("*"))
                logger.error(f"CADS output not found. Available files: {files}")
                raise FileNotFoundError(f"CADS output not found in {cads_dir/case_id}")

        logger.info(f"Found CADS output: {cads_output_raw}")
        
        # Rename to case001_0001.nii.gz (in same folder as input)
        cads_output = nifti_input_dir / f"{case_id}_0001.nii.gz"
        shutil.copy(cads_output_raw, cads_output)
        logger.info(f"Copied CADS output to: {cads_output}")

        # --- 4. Binarize Pericardium ---
        pericardium_bin = temp_dir / "2_initial_pericardium.nii.gz"
        binarize_segmentation(cads_output, pericardium_bin, label_id=7)
        logger.info(f"Created binarized pericardium: {pericardium_bin}")

        # --- 5. Prepare 2-channel inputs ---
        prep_multi = temp_dir / "3_prep_multiclass"
        prep_peri = temp_dir / "3_prep_pericardium"
        prep_multi.mkdir(parents=True, exist_ok=True)
        prep_peri.mkdir(parents=True, exist_ok=True)

        # Copy files for multiclass prediction
        shutil.copy(nnunet_input, prep_multi / f"{case_id}_0000.nii.gz")
        shutil.copy(cads_output, prep_multi / f"{case_id}_0001.nii.gz")
        
        # Copy files for pericardium refinement
        shutil.copy(nnunet_input, prep_peri / f"{case_id}_0000.nii.gz")
        shutil.copy(pericardium_bin, prep_peri / f"{case_id}_0001.nii.gz")
        
        logger.info("Prepared 2-channel inputs for nnUNet")

        # --- 6. Run nnU-Net refinement (MULTICLASS) ---
        refined_multi_dir = temp_dir / "4_refined_multiclass"
        refined_multi_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Starting multiclass nnUNet refinement...")
        run_command([
            "nnUNetv2_predict", "-i", str(prep_multi), "-o", str(refined_multi_dir),
            "-d", str(multiclass_model_id), "-c", "2d", "-f", "all",
            "-device", "cpu",
            "--disable_tta",
            "-step_size", "1.0"
        ])
        logger.info("Multiclass refinement completed")
        
        # Copy to final output
        multiclass_final = refined_multi_dir / f"{case_id}.nii.gz"
        if multiclass_final.exists():
            shutil.copy(multiclass_final, final_dir / "refined_multiclass.nii.gz")
            logger.info(f"Saved multiclass to: {final_dir / 'refined_multiclass.nii.gz'}")
        else:
            # Try to find the output file
            nifti_files = list(refined_multi_dir.glob("*.nii.gz"))
            if nifti_files:
                shutil.copy(nifti_files[0], final_dir / "refined_multiclass.nii.gz")
                logger.info(f"Saved multiclass from: {nifti_files[0]}")
            else:
                raise FileNotFoundError(f"No nnUNet output found in {refined_multi_dir}")

        # # --- 7. Run nnU-Net refinement (PERICARDIUM) ---
        # refined_peri_dir = temp_dir / "4_refined_pericardium"
        # refined_peri_dir.mkdir(parents=True, exist_ok=True)
        
        # logger.info("Starting pericardium nnUNet refinement...")
        # run_command([
        #     "nnUNetv2_predict", "-i", str(prep_peri), "-o", str(refined_peri_dir),
        #     "-d", str(pericardium_model_id), "-c", "2d", "-f", "all",
        #     "-device", "cpu",
        #     "--disable_tta",
        #     "-step_size", "1.0"
        # ])
        # logger.info("Pericardium refinement completed")
        
        # refined_peri = refined_peri_dir / f"{case_id}.nii.gz"
        # if not refined_peri.exists():
        #     nifti_files = list(refined_peri_dir.glob("*.nii.gz"))
        #     if nifti_files:
        #         refined_peri = nifti_files[0]
        #         logger.info(f"Using pericardium file: {refined_peri}")
        #     else:
        #         raise FileNotFoundError(f"No pericardium output found in {refined_peri_dir}")

        # # --- 8. Post-process pericardium ---
        # final_pericardium = final_dir / "refined_pericardium_filled.nii.gz"
        # apply_convex_hull(refined_peri, final_pericardium)
        # logger.info(f"Applied convex hull: {final_pericardium}")

        # --- 9. Convert to MHA ---
        original_name = input_file.stem
        
        # Convert multiclass
        multiclass_nifti = final_dir / "refined_multiclass.nii.gz"
        multiclass_mha = final_dir / f"{original_name}_segmented_multiclass.mha"
        if multiclass_nifti.exists():
            img = sitk.ReadImage(str(multiclass_nifti))
            sitk.WriteImage(img, str(multiclass_mha))
            logger.info(f"Converted to MHA: {multiclass_mha}")
        else:
            raise FileNotFoundError(f"Multiclass nifti not found: {multiclass_nifti}")

        # # Convert pericardium
        # pericardium_nifti = final_dir / "refined_pericardium_filled.nii.gz"
        # pericardium_mha = final_dir / f"{original_name}_segmented_pericardium.mha"
        # if pericardium_nifti.exists():
        #     img = sitk.ReadImage(str(pericardium_nifti))
        #     sitk.WriteImage(img, str(pericardium_mha))
        #     logger.info(f"Converted to MHA: {pericardium_mha}")
        # else:
        #     raise FileNotFoundError(f"Pericardium nifti not found: {pericardium_nifti}")

        # # --- 10. Analyze ALL Metrics ---
        # try:
        #     # Save original CT for analysis
        #     ct_for_analysis = final_dir / f"{original_name}_ct.nii.gz"
        #     shutil.copy(nnunet_input, ct_for_analysis)
            
        #     logger.info("Starting metrics calculation...")
        #     all_metrics = calculate_all_metrics(
        #         ct_nifti_path=ct_for_analysis,
        #         pericardium_nifti_path=pericardium_nifti,
        #         multiclass_nifti_path=multiclass_nifti
        #     )
            
        #     analysis_results = all_metrics
        #     logger.info("Metrics calculation completed")
            
        # except Exception as e:
        #     logger.error(f"Combined analysis failed: {e}")
        #     analysis_results = {"error": str(e), "status": "failed"}

        # --- 11. DELETE all .nii.gz files from final_dir ---
        nii_files = list(final_dir.glob("*.nii.gz"))
        for nii_file in nii_files:
            try:
                nii_file.unlink()
                logger.info(f"Deleted NIfTI file: {nii_file.name}")
            except Exception as e:
                logger.warning(f"Could not delete {nii_file.name}: {e}")

        # --- 12. Cleanup temp files ---
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temp directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Could not clean temp dir: {e}")

        # --- 13. SINGLE Firestore update with all results ---
        update_data = {
            "status": "finished",
            "finishedAt": datetime.utcnow(),
            "outputDir": str(final_dir),
            "output_files": {
                "multiclass_segmentation": str(multiclass_mha),
                #"pericardium_segmentation": str(pericardium_mha),
            }
        }

        # # Add analysis results if successful
        # if "error" not in analysis_results:
        #     update_data["analysis_results"] = {
        #         **analysis_results,
        #         "status": "completed",
        #         "analyzed_at": datetime.utcnow(),
        #         "analysis_version": "1.0"
        #     }
        # else:
        #     update_data["analysis_results"] = analysis_results

        job_ref.update(update_data)
        logger.info(f"Job {jobId} completed successfully!")

    except Exception as e:
        logger.error(f"Job {jobId} failed: {e}", exc_info=True)
        job_ref.update({
            "status": "failed",
            "error": str(e),
            "finishedAt": datetime.utcnow()
        })














# --- Main function to run segmentation for a job ---
def run_segmentation_job_opt(jobId: str, image_doc: dict, multiclass_model_id: int, pericardium_model_id: int):
    """
    Runs CADS → nnU-Net pipeline for a given uploaded image.
    Pericardium refinement is TEMPORARILY DISABLED.
    Updates Firestore with status and output paths.
    """
    db = firestore.client()

    try:
        # --- 1. Setup paths ---
        uploads_dir = Path("/home/saja/CardioSee/images/download")
        runs_dir = Path("cardiac_segmentation_runs") / jobId
        temp_dir = runs_dir / "temp"
        final_dir = runs_dir / "final_outputs"
        temp_dir.mkdir(parents=True, exist_ok=True)
        final_dir.mkdir(exist_ok=True)

        # Input file path
        filename = image_doc["name"]
        input_file = uploads_dir / filename

        # Update job status
        job_ref = db.collection("cardiac_segmentation_jobs").document(jobId)
        job_ref.update({"status": "running", "startedAt": datetime.utcnow()})

        # --- 2. Convert to NIfTI ---
        nifti_input_dir = temp_dir / "0_nifti_inputs"
        nifti_input_dir.mkdir(exist_ok=True)
        nifti_file = convert_to_nifti(input_file, nifti_input_dir)
        logger.info(f"Converted to NIfTI: {nifti_file}")

        # --- 3. CADS initial prediction ---
        cads_dir = temp_dir / "1_cads_initial"
        cads_dir.mkdir(exist_ok=True)

        case_id = "case001"
        nnunet_input = nifti_input_dir / f"{case_id}_0000.nii.gz"
        if nnunet_input.exists():
            nnunet_input.unlink()
        shutil.move(nifti_file, nnunet_input)
        logger.info(f"Renamed input to: {nnunet_input}")

        logger.info("Starting CADS prediction...")
        run_command([
            "python", "CADS/cads/scripts/predict_images.py",
            "-in", str(nifti_input_dir),
            "-out", str(cads_dir),
            "-task", "559",
        ])
        logger.info("CADS prediction completed")

        cads_output_raw = cads_dir / case_id / f"{case_id}_part_559.nii.gz"
        if not cads_output_raw.exists():
            cads_output_raw = cads_dir / case_id / f"{case_id}.nii.gz"
            if not cads_output_raw.exists():
                files = list((cads_dir / case_id).glob("*"))
                raise FileNotFoundError(f"CADS output not found. Files: {files}")

        logger.info(f"Found CADS output: {cads_output_raw}")
        cads_output = nifti_input_dir / f"{case_id}_0001.nii.gz"
        shutil.copy(cads_output_raw, cads_output)

        # ------------------------------------------------------------------
        # --- 4. Pericardium binarization (DISABLED) ------------------------
        # ------------------------------------------------------------------
        # pericardium_bin = temp_dir / "2_initial_pericardium.nii.gz"
        # binarize_segmentation(cads_output, pericardium_bin, label_id=7)
        # logger.info(f"Created binarized pericardium: {pericardium_bin}")

        # --- 5. Prepare 2-channel inputs (ONLY multiclass kept) ---
        prep_multi = temp_dir / "3_prep_multiclass"
        prep_multi.mkdir(parents=True, exist_ok=True)

        shutil.copy(nnunet_input, prep_multi / f"{case_id}_0000.nii.gz")
        shutil.copy(cads_output, prep_multi / f"{case_id}_0001.nii.gz")
        logger.info("Prepared 2-channel inputs for multiclass nnUNet")

        # ------------------------------------------------------------------
        # --- 6. Run nnU-Net refinement (MULTICLASS) -------------------------
        # ------------------------------------------------------------------
        refined_multi_dir = temp_dir / "4_refined_multiclass"
        refined_multi_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Starting multiclass nnUNet refinement...")
        run_command([
            "nnUNetv2_predict",
            "-i", str(prep_multi),
            "-o", str(refined_multi_dir),
            "-d", str(multiclass_model_id),
            "-c", "2d",
            "-f", "all",
            "-device", "cpu",
            "--disable_tta",
            "-step_size", "1.0",
        ])
        logger.info("Multiclass refinement completed")

        multiclass_final = refined_multi_dir / f"{case_id}.nii.gz"
        if multiclass_final.exists():
            shutil.copy(multiclass_final, final_dir / "refined_multiclass.nii.gz")
        else:
            nifti_files = list(refined_multi_dir.glob("*.nii.gz"))
            if not nifti_files:
                raise FileNotFoundError("No nnUNet multiclass output found")
            shutil.copy(nifti_files[0], final_dir / "refined_multiclass.nii.gz")

        # ------------------------------------------------------------------
        # --- 7. Pericardium nnU-Net refinement (DISABLED) ------------------
        # ------------------------------------------------------------------
        # refined_peri_dir = temp_dir / "4_refined_pericardium"
        # refined_peri_dir.mkdir(parents=True, exist_ok=True)
        # run_command([
        #     "nnUNetv2_predict",
        #     "-i", str(prep_peri),
        #     "-o", str(refined_peri_dir),
        #     "-d", str(pericardium_model_id),
        #     "-c", "2d",
        #     "-f", "all",
        #     "-device", "cpu",
        #     "--disable_tta",
        # ])

        # ------------------------------------------------------------------
        # --- 8. Pericardium post-processing (DISABLED) ---------------------
        # ------------------------------------------------------------------
        # final_pericardium = final_dir / "refined_pericardium_filled.nii.gz"
        # apply_convex_hull(refined_peri, final_pericardium)

        # --- 9. Convert multiclass to MHA ---
        original_name = input_file.stem
        multiclass_nifti = final_dir / "refined_multiclass.nii.gz"
        multiclass_mha = final_dir / f"{original_name}_segmented_multiclass.mha"

        img = sitk.ReadImage(str(multiclass_nifti))
        sitk.WriteImage(img, str(multiclass_mha))
        logger.info(f"Converted to MHA: {multiclass_mha}")

        # ------------------------------------------------------------------
        # --- 10. Metrics involving pericardium (DISABLED) -----------------
        # ------------------------------------------------------------------
        analysis_results = {"status": "skipped", "reason": "pericardium disabled"}

        # --- 11. Cleanup ---
        for nii_file in final_dir.glob("*.nii.gz"):
            nii_file.unlink()

        shutil.rmtree(temp_dir, ignore_errors=True)

        # --- 12. Firestore update ---
        job_ref.update({
            "status": "finished",
            "finishedAt": datetime.utcnow(),
            "outputDir": str(final_dir),
            "output_files": {
                "multiclass_segmentation": str(multiclass_mha),
            },
            "analysis_results": analysis_results,
        })

        logger.info(f"Job {jobId} completed successfully (pericardium disabled)")

    except Exception as e:
        logger.error(f"Job {jobId} failed: {e}", exc_info=True)
        job_ref.update({
            "status": "failed",
            "error": str(e),
            "finishedAt": datetime.utcnow(),
        })

        
# --- Quantify EAT function  ---
def calculate_all_metrics(
    ct_nifti_path: Path,
    pericardium_nifti_path: Path,
    multiclass_nifti_path: Path
) -> Dict[str, Any]:
    """
    Calculates ALL metrics: fat volumes + multiclass structure volumes.
    Returns combined results dictionary.
    """
    try:
        results = {} 

        # --- 1. FAT ANALYSIS (using pericardium segmentation) ---
        # Load files
        ct_nii = nib.load(ct_nifti_path)
        ct_data = ct_nii.get_fdata()
        
        pericardium_nii = nib.load(pericardium_nifti_path)
        pericardium_data = pericardium_nii.get_fdata()
        
        # Calculate voxel volume
        voxel_size_mm = ct_nii.header.get_zooms()
        voxel_volume_mm3 = np.prod(voxel_size_mm)
        voxel_volume_cm3 = voxel_volume_mm3 / 1000.0
        
        # Create pericardium mask
        pericardium_mask = (pericardium_data > 0)
        
        # Define HU ranges
        hu_ranges = {
            'inflamed': (-70, -30),
            'non_inflamed': (-190, -71),
            'total_eat': (-190, -30)
        }
        
        # Calculate fat volumes
        fat_results = {}
        for fat_type, (hu_min, hu_max) in hu_ranges.items():
            fat_mask = (ct_data >= hu_min) & (ct_data <= hu_max) & pericardium_mask
            voxel_count = np.sum(fat_mask)
            volume_cm3 = voxel_count * voxel_volume_cm3
            fat_results[f'volume_{fat_type}_cm3'] = float(volume_cm3)
            fat_results[f'voxels_{fat_type}'] = int(voxel_count)
        
        # Inflamed percentage
        if fat_results['volume_total_eat_cm3'] > 0:
            inflamed_percentage = (fat_results['volume_inflamed_cm3'] / 
                                 fat_results['volume_total_eat_cm3']) * 100
            fat_results['inflamed_percentage'] = float(inflamed_percentage)
        else:
            fat_results['inflamed_percentage'] = 0.0
        
        results['fat_analysis'] = fat_results


        # --- 2. MULTICLASS STRUCTURE VOLUMES ---
        multiclass_nii = nib.load(multiclass_nifti_path)
        multiclass_data = multiclass_nii.get_fdata()
        
        # Define structure labels (from dataset.json)
        structure_labels = {
            1: 'subcutaneous_tissue',
            2: 'muscle',
            3: 'abdominal_cavity',
            4: 'thoracic_cavity',
            5: 'bones',
            6: 'parotid_glands',
            7: 'pericardium',
            8: 'breast_implant',
            9: 'mediastinum',  # Contains heart region
            10: 'brain',
            11: 'spinal_cord',
            12: 'thyroid_glands',
            13: 'submandibular_glands'
        }

        structure_volumes = {}
        for label_id, structure_name in structure_labels.items():
            mask = (multiclass_data == label_id)
            voxel_count = np.sum(mask)
            volume_cm3 = voxel_count * voxel_volume_cm3
            structure_volumes[structure_name] = {
                'volume_cm3': float(volume_cm3),
                'voxel_count': int(voxel_count),
                'label_id': int(label_id)
            }

        results['structure_volumes'] = structure_volumes


        # --- 3. COMPARE PERICARDIUM FROM BOTH SEGMENTATIONS ---
        pericardium_multiclass = (multiclass_data == 7)
        pericardium_refined = (pericardium_data > 0)
        
        # Dice score (segmentation quality)
        intersection = np.sum(pericardium_multiclass & pericardium_refined)
        union = np.sum(pericardium_multiclass) + np.sum(pericardium_refined)
        dice = (2 * intersection) / union if union > 0 else 0
        
        results['quality_metrics'] = {
            # 'pericardium_dice_score': float(dice),
            'multiclass_pericardium_volume': structure_volumes['pericardium']['volume_cm3'],
            'refined_pericardium_volume': fat_results['volume_total_eat_cm3'] + 
                                         (np.sum(pericardium_refined) * voxel_volume_cm3 - 
                                          fat_results['volume_total_eat_cm3'])
        }




        # Calculate the bounding box using the pericardium mask
        bounding_box_results = calculate_pericardium_bounding_box(pericardium_data, voxel_size_mm)
        results['pericardium_bounding_box'] = bounding_box_results
        
        # --- 5. LOG RESULTS ---
        logger.info(f"Total EAT: {fat_results['volume_total_eat_cm3']:.2f} cm³, "f"Dice score: {dice:.3f}")
        
        # Add bounding box info to log
        if 'dimensions_mm' in bounding_box_results:
            logger.info(f"Pericardium bounding box: {bounding_box_results['dimensions_mm']} mm")
            logger.info(f"Box volume: {bounding_box_results['volume_cm3']:.2f} cm³")
            logger.info(f"Coverage: {bounding_box_results['coverage_percentage']:.1f}%")
        
        return results
        
    except Exception as e:
        logger.error(f"Combined calculation failed: {e}")
        raise



# --- Flask route to trigger the job ---
from flask import Blueprint, request, jsonify

segmentation_bp = Blueprint('segmentation_bp', __name__)

@segmentation_bp.route("/start_segmentation/<image_id>", methods=["POST"])
def start_segmentation(image_id):
    db = firestore.client()

    # Create a new job
    job_doc = {
        "imageId": image_id,
        "status": "queued",
        "createdAt": datetime.utcnow()
    }
    job_ref = db.collection("cardiac_segmentation_jobs").add(job_doc)
    jobId = job_ref[1].id

    # Fetch image doc
    image_doc = db.collection("images").document(image_id).get().to_dict()

    # Run segmentation in background thread
    threading.Thread(
        target=run_segmentation_job,
        args=(jobId, image_doc, 888, 877),  # multiclass_model_id, pericardium_model_id
        daemon=True
    ).start()

    return jsonify({"jobId": jobId, "status": "queued"})

     
# --- 4. CALCULATE PERICARDIUM BOUNDING BOX ---
def calculate_pericardium_bounding_box(pericardium_mask_data, voxel_size_mm):
    """
    Calculate the 3D bounding box that tightly encloses the pericardium.
    
    The bounding box gives us the spatial extent of the heart region
    in 3D coordinates, useful for spatial analysis and visualization.
    
    Args:
        pericardium_mask_data: 3D numpy array of the pericardium mask
                                (1=pericardium, 0=background)
    
    Returns:
        Dictionary with bounding box coordinates and dimensions
    """
    # Find all coordinates where pericardium exists
    coords = np.where(pericardium_mask_data > 0)
    
    # If no pericardium found, return empty
    if len(coords[0]) == 0:
        return {
            'error': 'No pericardium detected',
            'min_coords': None,
            'max_coords': None,
            'dimensions': None,
            'center': None,
            'coverage': 0.0
        }
    
    # Extract coordinates for each axis
    x_coords, y_coords, z_coords = coords
    
    # Calculate box boundaries
    x_min, x_max = np.min(x_coords), np.max(x_coords)
    y_min, y_max = np.min(y_coords), np.max(y_coords)
    z_min, z_max = np.min(z_coords), np.max(z_coords)
    
    # Box dimensions (in voxels)
    width = x_max - x_min + 1
    height = y_max - y_min + 1
    depth = z_max - z_min + 1
    
    # Box center point
    center_x = (x_min + x_max) / 2.0
    center_y = (y_min + y_max) / 2.0
    center_z = (z_min + z_max) / 2.0
    
    # Calculate box volume in actual mm³ (not just voxels)
    # Convert from voxel dimensions to real-world dimensions
    width_mm = width * voxel_size_mm[0]
    height_mm = height * voxel_size_mm[1]
    depth_mm = depth * voxel_size_mm[2]
    box_volume_mm3 = width_mm * height_mm * depth_mm
    box_volume_cm3 = box_volume_mm3 / 1000.0
    
    # Count pericardium voxels inside our calculated box
    # This verifies the box correctly contains all pericardium
    pericardium_in_box = np.sum(
        (pericardium_mask_data > 0) & 
        (np.arange(pericardium_mask_data.shape[0])[:, None, None] >= x_min) &
        (np.arange(pericardium_mask_data.shape[0])[:, None, None] <= x_max) &
        (np.arange(pericardium_mask_data.shape[1])[None, :, None] >= y_min) &
        (np.arange(pericardium_mask_data.shape[1])[None, :, None] <= y_max) &
        (np.arange(pericardium_mask_data.shape[2])[None, None, :] >= z_min) &
        (np.arange(pericardium_mask_data.shape[2])[None, None, :] <= z_max)
    )
    
    total_pericardium = np.sum(pericardium_mask_data > 0)
    coverage_percentage = (pericardium_in_box / total_pericardium) * 100 if total_pericardium > 0 else 0
    
    return {
        'min_coords_voxels': [int(x_min), int(y_min), int(z_min)],
        'max_coords_voxels': [int(x_max), int(y_max), int(z_max)],
        'min_coords_mm': [
            float(x_min * voxel_size_mm[0]),
            float(y_min * voxel_size_mm[1]),
            float(z_min * voxel_size_mm[2])
        ],
        'max_coords_mm': [
            float(x_max * voxel_size_mm[0]),
            float(y_max * voxel_size_mm[1]),
            float(z_max * voxel_size_mm[2])
        ],
        'dimensions_voxels': [int(width), int(height), int(depth)],
        'dimensions_mm': [float(width_mm), float(height_mm), float(depth_mm)],
        'center_voxels': [float(center_x), float(center_y), float(center_z)],
        'center_mm': [
            float(center_x * voxel_size_mm[0]),
            float(center_y * voxel_size_mm[1]),
            float(center_z * voxel_size_mm[2])
        ],
        'volume_voxels': int(width * height * depth),
        'volume_cm3': float(box_volume_cm3),
        'coverage_percentage': float(coverage_percentage),
        'total_pericardium_voxels': int(total_pericardium)
    }