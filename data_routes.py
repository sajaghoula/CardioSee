from flask import Blueprint, request, jsonify
import pandas as pd
import math
from scipy.stats import f_oneway, spearmanr
import numpy as np
import scipy.stats as stats
import matplotlib.pyplot as plt
from scipy.stats import gaussian_kde, chi2_contingency





data_bp = Blueprint('data_bp', __name__)


@data_bp.route('/get_sheets', methods=['POST'])
def get_sheets():
    """Return available sheet names from an uploaded Excel file."""
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    try:
        if not file.filename.endswith(('.xlsx', '.xls')):
            return jsonify({"error": "Only Excel files have sheets"}), 400

        # Read only metadata (no full load)
        excel_file = pd.ExcelFile(file)
        sheets = excel_file.sheet_names

        return jsonify({"sheets": sheets})
    except Exception as e:
        return jsonify({"error": f"Error reading sheets: {str(e)}"}), 500



@data_bp.route('/upload_data', methods=['POST'])
def upload_data():
    """Read selected sheet or full CSV and return data preview."""
    file = request.files.get('file')
    sheet_name = request.form.get('sheet_name')  # <-- added
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    try:
        # Read file according to type
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif file.filename.endswith(('.xlsx', '.xls')):
            # If sheet_name is provided → use it
            df = pd.read_excel(file, sheet_name=sheet_name if sheet_name else 0)
        else:
            return jsonify({"error": "Unsupported file format"}), 400

        num_rows = len(df)

        # Clean values for JSON
        def clean_value(val):
            if isinstance(val, float):
                if math.isnan(val) or math.isinf(val):
                    return None
                return val
            elif pd.isna(val):
                return None
            elif isinstance(val, pd.Timestamp):
                if pd.isnull(val):
                    return None
                return val.isoformat()
            return val

        preview = [
            {col: clean_value(row[col]) for col in df.columns}
            for _, row in df.iterrows()
        ]

        columns = df.columns.tolist()

        return jsonify({
            "columns": columns,
            "preview": preview,
            "num_rows": num_rows
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    


@data_bp.route('/get_columns', methods=['POST'])
def get_columns():
    file = request.files['file']
    sheet = request.form.get("sheet_name")

    if sheet:
        df = pd.read_excel(file, sheet_name=sheet)
    else:
        df = pd.read_excel(file)

    return jsonify({"columns": df.columns.tolist()})



@data_bp.route('/column_stats', methods=['POST'])
def column_stats():
    file = request.files['file']
    sheet = request.form.get("sheet_name")
    column = request.form.get("column")

    df = pd.read_excel(file, sheet_name=sheet) if sheet else pd.read_excel(file)
    series = df[column]

    # Detect numeric
    is_numeric = check_numeric(series) 
    cleaned_series = clean_column(is_numeric, series)


    
    if is_numeric:
        numeric = pd.to_numeric(cleaned_series, errors="coerce")
        numeric_mode = numeric.mode()
        stats = {
            "Count": len(series),
            "Mean": numeric.mean(),
            "Median": numeric.median(),
            "Mode": numeric_mode.tolist() if len(numeric_mode) > 1 else numeric_mode[0],
            "Std Dev": numeric.std(),
            "Variance": numeric.var(),
            "Min": numeric.min(),
            "Max": numeric.max(),
            "Missing": series.isna().sum(),
            "Interquartile Range (IQR)": numeric.quantile(0.75) - numeric.quantile(0.25),

            
        }
        col_type = "Numeric"
        pie_data = None

    else:

        counts = cleaned_series.value_counts()

        # Top N + Others for pie chart
        TOP_N = 15
        if len(counts) > TOP_N:
            top_counts = counts[:TOP_N]
            others_count = counts[TOP_N:].sum()
            top_counts["Others"] = others_count
            counts_for_chart = top_counts
        else:
            counts_for_chart = counts

        stats = {
            "Count": len(series),
            "Unique categories": cleaned_series.nunique(),
            "Most frequent": cleaned_series.mode()[0] if not cleaned_series.mode().empty else "None",
            "Missing": series.isna().sum(),
            #"Counts": counts.to_dict()  # full table still optional, can also normalize here if needed
        }

        col_type = "Categorical"
        pie_data = counts_for_chart.to_dict()


    # Build HTML table
    html = f"""
    <h4>Column: {column}</h4>
    <p>Type: <strong>{col_type}</strong></p>
    <table border="1" cellpadding="6" style="border-collapse: collapse; width: 80%;">
        <thead>
            <tr>
                <th>Statistic</th>
                <th>Value</th>
            </tr>
        </thead>
        <tbody>
    """

    for key, value in stats.items():
        if key == "Counts" and not is_numeric:
            html += f"<tr><td>{key}</td><td><table border='1' cellpadding='4' style='border-collapse: collapse; width: 100%;'>"
            for cat, freq in counts.items():
                html += f"<tr><td>{cat}</td><td>{freq}</td></tr>"
            html += "</table></td></tr>"
        else:
            html += f"<tr><td>{key}</td><td>{value}</td></tr>"

    html += "</tbody></table>"

    return jsonify({"html": html, "pie_data": pie_data})





@data_bp.route('/get_correlation', methods=['POST'])
def get_correlation():
    file = request.files['file']
    sheet = request.form.get("sheet_name")
    column = request.form.get("column")
    

    df = pd.read_excel(file, sheet_name=sheet) if sheet else pd.read_excel(file)
    series = df[column]
    
    # Detect numeric
    is_numeric = check_numeric(series) 

    correlation_data_numeric_numeric = None
    pvalues = {}
    correlation_data_numeric_categorical = None

    correlation_data_categorical_numeric = None
    correlation_data_categorical_categorical = None
   


    if is_numeric:
        # Use Spearman for numeric
        numeric_df = get_numerical(df)

        if column in numeric_df:
            correlation_data_numeric_numeric = numeric_df.corr(method="spearman")[column].drop(labels=[column]).to_dict()


        

        for col in numeric_df.columns:
            if col == column:
                continue
            
            corr, pval = spearmanr(numeric_df[column], numeric_df[col])
            pvalues[col] = pval



        # HERE - Find the Correlation between the numeric column and the Categorical column
        # 2) Numeric ↔ Categorical → Correlation Ratio η²
        categorical_df = get_categorical(df)
        
        correlation_data_numeric_categorical = {}

        for cat_col in categorical_df.columns:
            # Align numeric and categorical values, drop NaNs
            valid_idx = df[cat_col].notna() & df[column].notna()
            x = df[column][valid_idx]
            cats = df[cat_col][valid_idx]

            # Create groups for each category with at least 2 values
            unique_cats = cats.unique()
            groups = [x[cats == c] for c in unique_cats if len(x[cats == c]) > 1]

            # Skip if less than 2 valid groups
            if len(groups) < 2:
                continue

            try:
                # ANOVA F and p-value
                F, p = f_oneway(*groups)

                # Eta squared (effect size)
                grand_mean = x.mean()
                ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in groups)
                ss_total = sum((x - grand_mean) ** 2)
                eta_sq = ss_between / ss_total if ss_total != 0 else 0

                # Clip eta_sq to [0,1] to avoid rounding issues
                eta_sq = min(max(eta_sq, 0), 1)

            except Exception as e:
                F = p = eta_sq = None

            # Store results
            correlation_data_numeric_categorical[cat_col] = {
                "eta_squared": None if pd.isna(eta_sq) else float(eta_sq),
                "F": None if pd.isna(F) else float(F),
                "p-value": None if pd.isna(p) else float(p)
            }




    else:

        # Categorical column → ANOVA with other numeric columns
        numeric_df = get_numerical(df)

        

        correlation_data_categorical_numeric = {}
        correlation_data_categorical_categorical = {}

        

        for col in numeric_df.columns:
            # Align numeric and categorical values, remove NaNs
            valid_idx = series.notna() & numeric_df[col].notna()
            x = numeric_df[col][valid_idx]
            cats = series[valid_idx]

            # Create groups for each category, skip groups with < 2 values
            unique_cats = cats.unique()
            groups = [x[cats == c] for c in unique_cats if len(x[cats == c]) > 1]

            # Skip if less than 2 valid groups
            if len(groups) < 2:
                continue

            try:
                # ANOVA F and p-value
                F, p = f_oneway(*groups)

                # Eta squared (effect size)
                grand_mean = x.mean()
                ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in groups)
                ss_total = sum((x - grand_mean) ** 2)
                eta_sq = ss_between / ss_total if ss_total != 0 else 0

            except Exception as e:
                F = p = eta_sq = None

            # Store results
            print("-----------------------------------------", eta_sq)
            correlation_data_categorical_numeric[col] = {
                "F": None if pd.isna(F) else float(F),
                "p-value": None if pd.isna(p) else float(p),
                "eta_squared_cn": None if pd.isna(eta_sq) else float(eta_sq)
            }

        

        cat_df = get_categorical(df).drop(columns=[column]) 

        print("-----------------------------------------", correlation_data_categorical_numeric)
        


        
        for col in cat_df.columns:
            contingency = pd.crosstab(series, df[col].astype(str))  # cross-tabulate counts

            try:
                chi2, p, dof, expected = stats.chi2_contingency(contingency)
                n = contingency.sum().sum()
                phi2 = chi2 / n
                r, c = contingency.shape
                cramers_v = np.sqrt(phi2 / min(r-1, c-1)) if min(r-1, c-1) > 0 else None
                
            except:
                cramers_v = None

            correlation_data_categorical_categorical[col] = {
                "cramers_v": None if pd.isna(cramers_v) else float(cramers_v)
            }





    # Ensure numeric NaNs are converted to None
    correlation_data_categorical_numeric = NAN_converter(is_numeric, correlation_data_categorical_numeric)
    correlation_data_categorical_categorical = NAN_converter(is_numeric, correlation_data_categorical_categorical)
    correlation_data_numeric_numeric = NAN_converter(is_numeric, correlation_data_numeric_numeric)
    #correlation_data_numeric_categorical = NAN_converter(is_numeric, correlation_data_numeric_categorical)




    
    return jsonify({"correlation_data_categorical_numeric": correlation_data_categorical_numeric, 
                    "correlation_data_categorical_categorical": correlation_data_categorical_categorical,
                    "correlation_data_numeric_numeric": correlation_data_numeric_numeric, 
                    "correlation_data_numeric_categorical" : correlation_data_numeric_categorical })




@data_bp.route("/get_distributionAnalysis", methods=["POST"])
def get_distributionAnalysis():
    file = request.files['file']
    sheet = request.form.get("sheet_name")
    column = request.form.get("column")

    df = pd.read_excel(file, sheet_name=sheet) if sheet else pd.read_excel(file)
    series = df[column]
    

    is_numeric = check_numeric(series)
    cleaned_series = clean_column(is_numeric, series)

    
    if is_numeric:
        
        # Histogram
        hist_counts, hist_edges = np.histogram(cleaned_series, bins="auto")

        # Violin plot / density plot
        kde = gaussian_kde(cleaned_series)
        xs = np.linspace(cleaned_series.min(), cleaned_series.max(), 200)
        xs_rounded = np.round(xs, 2)
        ys = kde(xs_rounded)

        return jsonify({
            "type": "numeric",
            "seriesData" : cleaned_series.tolist(),
            "histogram": {
                "counts": hist_counts.tolist(),
                "edges": hist_edges.tolist()
            },
           
            "violin": {
                "x": xs_rounded.tolist(),
                "y": ys.tolist()
            },
            "density": {
                "x": xs_rounded.tolist(),
                "y": ys.tolist()
            }
        })
    
    else:
        print("categorical column")

        # ------------- (1) FREQUENCY + PERCENTAGE TABLE -------------
        counts = cleaned_series.value_counts(dropna=False)
        percentages = counts / counts.sum() * 100

        freq_table = pd.DataFrame({
            "Category": counts.index,
            "Count": counts.values,
            "Percentage": percentages.values.round(2)
        })


        # Convert to a list/dict (if returning JSON)
        freq_output = freq_table.to_dict(orient="records")

        categorical_df = get_categorical(df)

        # ------------- (2) CHI-SQUARE TEST WITH ALL OTHER CATEGORICAL COLUMNS -------------
        chi_square_results = {}


        for other_col in categorical_df:
            # Skip the same column
            if other_col == column:
                continue

            other_series = clean_column(False, df[other_col])

            # Build contingency table
            ct = pd.crosstab(cleaned_series, other_series)

            # Need at least 2x2 table
            if ct.shape[0] < 2 or ct.shape[1] < 2:
                continue

            chi2, p, dof, expected = chi2_contingency(ct)

            chi_square_results[other_col] = {
                "chi2": float(chi2),
                "p_value": float(p),
                "degrees_of_freedom": int(dof)
            }


        
        # ---------------- RETURN ----------------
        result = {
            "type": "categorical",
            "frequency_table": freq_output,
            "chi_square": chi_square_results
        }

        print('----------------------', result)

        return jsonify(result)





def NAN_converter(is_numeric, data):
    if data and is_numeric:
        for k, v in data.items():
            if pd.isna(v):
                data[k] = None
            else:
                data[k] = float(v)
    return data



def get_categorical(df, max_unique_ratio=0.05, max_unique_values=10):
    """
    Returns a DataFrame containing all categorical columns (including numeric-looking categorical)
    
    Parameters:
    - df : pandas DataFrame
    - max_unique_ratio : float
        Maximum ratio of unique values to total rows to consider numeric column categorical
    - max_unique_values : int
        Maximum number of unique values for a numeric column to be considered categorical
    
    Returns:
    - pandas DataFrame with categorical columns only
    """
    categorical_cols = []

    for col in df.columns:
        series = df[col]

        # Text/object → categorical
        if pd.api.types.is_object_dtype(series):
            categorical_cols.append(col)
            continue

        # Numeric-looking categorical
        if pd.api.types.is_numeric_dtype(series):
            unique_ratio = series.nunique() / len(series)
            if series.nunique() <= max_unique_values or unique_ratio <= max_unique_ratio:
                categorical_cols.append(col)

    return df[categorical_cols]  # return as DataFrame, preserving dtypes



def get_numerical(df, max_unique_ratio=0.05, max_unique_values=10):
    """
    Returns a DataFrame containing all numeric columns excluding numeric-looking categorical
    
    Parameters:
    - df : pandas DataFrame
    - max_unique_ratio : float
        Maximum ratio of unique values to total rows to consider numeric column categorical
    - max_unique_values : int
        Maximum number of unique values for a numeric column to be considered categorical
    
    Returns:
    - pandas DataFrame with numeric columns only (excluding numeric categorical)
    """
    numerical_cols = []

    for col in df.columns:
        series = df[col]

        # Only numeric columns
        if pd.api.types.is_numeric_dtype(series):
            unique_ratio = series.nunique() / len(series)

            # Skip numeric-looking categorical columns
            if not (series.nunique() <= max_unique_values or unique_ratio <= max_unique_ratio):
                numerical_cols.append(col)

    return df[numerical_cols]  # return as DataFrame, preserving dtypes



def check_numeric(series):
    """
    Returns 
    - True: if the column is numerical
    - False: if the column is categorical or numeric-looking categorical 
    """
    
    is_numeric = pd.api.types.is_numeric_dtype(series)

    if is_numeric and len(series) > 0:
        unique_ratio = series.nunique() / len(series)
        if series.nunique() <= 10 or unique_ratio < 0.05:
            is_numeric = False
    else:
        is_numeric = False

    return is_numeric


def clean_column(is_numeric, series):

    if is_numeric:
        cleaned_series = pd.to_numeric(series, errors="coerce").dropna()
    else:
        cleaned_series = series.astype(str).str.strip().str.lower()
        cleaned_series = cleaned_series.replace(["nan", ""], np.nan).dropna()

    return cleaned_series

