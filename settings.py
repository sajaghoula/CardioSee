from flask import Flask, request, jsonify, send_file, Blueprint
from firebase_admin import firestore, auth
from datetime import datetime
import SimpleITK as sitk
from flask import Flask, request, jsonify, send_file
import numpy as np
import os
from io import BytesIO




settings_bp = Blueprint('settings_bp', __name__)

@settings_bp.route("/get_system_variables", methods=["GET"])
def get_system_variables():
    db = firestore.client()
    docs = db.collection('SystemVariables').stream()
    
    variables = []
    for doc in docs:
        data = doc.to_dict()
        data['id'] = doc.id  # Add the document ID
        variables.append(data)
    
    return jsonify(variables)


@settings_bp.route("/update_system_variable", methods=["POST"])
def update_system_variable():
    try:
        data = request.json
        variable_name = data.get('variable')
        new_value = data.get('value')
        
        if not variable_name or not new_value:
            return jsonify({"error": "Variable name and value are required"}), 400
        
        db = firestore.client()
        
        # Query to find the document by variable name
        docs = db.collection('SystemVariables').where('variable', '==', variable_name).stream()
        
        updated = False
        for doc in docs:
            doc_ref = db.collection('SystemVariables').document(doc.id)
            doc_ref.update({
                'value': new_value,
                'updatedAt': datetime.now()
            })
            updated = True
            break  # Assuming variable names are unique
        
        if updated:
            return jsonify({"message": f"Variable '{variable_name}' updated successfully"})
        else:
            return jsonify({"error": f"Variable '{variable_name}' not found"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500