
// STEP 4: View correlation
viewCorrelationBtn.addEventListener("click", async () => {
    // Hide previous stats
    statsResult.classList.add("hidden");
    distContainer.classList.add("hidden");
    document.getElementById("statsTableContainer").innerHTML = "";
    document.getElementById("pieChartContainer").style.display = "none";

    const formData = new FormData();
    formData.append("file", selectedFile);
    const col = columnSelect.value;
    formData.append("column", col);

    if (!statsSheetSelector.classList.contains("hidden")) {
        formData.append("sheet_name", statsSheetSelect.value);
    }

    const res = await fetch("/get_correlation", { method: "POST", body: formData });
    const result = await res.json();

    const corrContainer = document.getElementById("corrContainer");
    const correlationPValContainer = document.getElementById("correlationPValContainer");
    const correlationFValContainer = document.getElementById("correlationFValContainer");


    correlationPValContainer.innerHTML = ""; // clear previous content
    correlationFValContainer.innerHTML = ""; // clear previous content



if (result.correlation_data_numeric_numeric && Object.keys(result.correlation_data_numeric_numeric).length > 0) {

    corrContainer.classList.add("hidden");
    const pvals = result.pvalues_numeric_numeric;

    const numeric_corrContainer = document.getElementById("numeric_corrContainer");
    const numeric_numeric_correlation = document.getElementById("numeric_numeric_correlation");

    numeric_corrContainer.classList.remove("hidden");
    numeric_numeric_correlation.classList.remove("hidden");
    numeric_numeric_correlation.innerHTML = "";

    const chartId = "numeric_numeric_barchart";
    numeric_numeric_correlation.innerHTML += `<canvas id="${chartId}" width="600" height="300"></canvas>`;
    const ctx = document.getElementById(chartId).getContext("2d");

    if (window.numeric_corrContainer && typeof window.numeric_corrContainer.destroy === "function") {
        window.numeric_corrContainer.destroy();
    }

    const keys = Object.keys(result.correlation_data_numeric_numeric);
    const values = Object.values(result.correlation_data_numeric_numeric);

    window.numeric_corrContainer = new Chart(ctx, {
        type: "bar",
        data: {
            labels: keys,
            datasets: [{
                label: `Spearman correlation with ${col}`,
                data: values.map(v => v !== null ? v.toFixed(3) : 0),
                backgroundColor: keys.map((k, i) => {
                    const p = pvals[k];
                    const alpha = (p !== null && p < 0.05) ? 0.9 : 0.3;
                    return values[i] >= 0
                        ? `rgba(54,162,235,${alpha})`
                        : `rgba(255,99,132,${alpha})`;
                }),
                borderColor: values.map(v =>
                    v >= 0 ? "rgba(54,162,235,1)" : "rgba(255,99,132,1)"
                ),
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            const key = ctx.label;
                            const r = ctx.raw;
                            const p = pvals[key];
                            return `r = ${r}, p = ${p !== null ? p.toExponential(2) : "NA"}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    min: -1,
                    max: 1,
                    title: { display: true, text: "Spearman r" }
                }
            }
        }
    });
}



if (result.correlation_data_numeric_categorical && Object.keys(result.correlation_data_numeric_categorical).length > 0) {
    corrContainer.classList.add("hidden");
    const numeric_corrContainer = document.getElementById("numeric_corrContainer");
    const numeric_categorical_correlation = document.getElementById("numeric_categorical_correlation");

    numeric_corrContainer.classList.remove("hidden");
    numeric_categorical_correlation.classList.remove("hidden");
    numeric_categorical_correlation.innerHTML = "";

    // Create canvas for the chart
    const canvasId = "numeric_categorical_barchart";
    numeric_categorical_correlation.innerHTML = `<canvas id="${canvasId}" width="600" height="300"></canvas>`;
    const ctx = document.getElementById(canvasId).getContext("2d");

    // Destroy previous chart if exists
    if (window.numericCategoricalChart && typeof window.numericCategoricalChart.destroy === "function") {
        window.numericCategoricalChart.destroy();
    }

    const keys = Object.keys(result.correlation_data_numeric_categorical);
    const values = Object.values(result.correlation_data_numeric_categorical);

    // Extract eta_squared and p-value
    const valuesForChart = values.map(v =>
        v.eta_squared !== null ? Number(v.eta_squared.toFixed(3)) : 0
    );

    const backgroundColors = values.map(v => {
        const alpha = (v["p-value"] !== null && v["p-value"] < 0.05) ? 0.9 : 0.3; // solid if significant
        return `rgba(54,162,235,${alpha})`;
    });

    window.numericCategoricalChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: keys,
            datasets: [{
                label: `Correlation ratio (η²) with ${col}`,
                data: valuesForChart,
                backgroundColor: backgroundColors,
                borderColor: "rgba(54,162,235,1)",
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            const idx = ctx.dataIndex;
                            const eta = valuesForChart[idx];
                            const p = values[idx]["p-value"];
                            return `η² = ${eta}, p = ${p !== null ? p.toExponential(2) : "NA"}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 1,
                    title: { display: true, text: "η²" }
                }
            }
        }
    });
}




if (result.correlation_data_categorical_categorical &&
    Object.keys(result.correlation_data_categorical_categorical).length > 0) {

    corrContainer.classList.remove("hidden");
    numeric_corrContainer.classList.add("hidden");

    const container = document.getElementById("categorical_categorical_correlation");
    container.classList.remove("hidden");
    container.innerHTML = ""; // clean once

    const data = result.correlation_data_categorical_categorical;

    const cols = Object.keys(data);
    const cramersValues = cols.map(col => data[col].cramers_v ?? 0);
    const pvalues = cols.map(col => data[col]["p-value"] ?? 1); // default 1 if missing

    // --------------------------
    // Combined Chart: Cramer's V + p-value
    // --------------------------
    container.innerHTML += `<h3>🔗 Correlation with Categorical Columns -Carmers & Chai2- </h3>`;
    container.innerHTML += `<canvas id="categorical_categorical_chart" width="600" height="300"></canvas>`;

    const ctx = document.getElementById("categorical_categorical_chart").getContext("2d");

    if (window.categoricalCategoricalChart) {
        window.categoricalCategoricalChart.destroy();
    }

    // Use blue for bars, darker for smaller p-values
    const barColors = pvalues.map(p => `rgba(54,162,235,${p < 0.05 ? 0.9 : 0.5})`);

    window.categoricalCategoricalChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: cols,
            datasets: [{
                label: "Cramer's V (strength)",
                data: cramersValues.map(v => v !== null ? parseFloat(v.toFixed(3)) : 0),
                backgroundColor: barColors,
                borderColor: barColors,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const index = context.dataIndex;
                            const v = cramersValues[index] !== null ? cramersValues[index].toFixed(3) : "N/A";
                            const p = pvalues[index] !== null ? pvalues[index].toExponential(2) : "N/A";
                            return `Cramer's V: ${v}, p-value: ${p}`;
                        }
                    }
                }
            },
            scales: {
                y: { min: 0, max: 1, title: { display: true, text: "Cramer's V" } }
            }
        }
    });
}



if (result.correlation_data_categorical_numeric && Object.keys(result.correlation_data_categorical_numeric).length > 0) {
    corrContainer.classList.remove("hidden");
    numeric_corrContainer.classList.add("hidden");

    const keys = Object.keys(result.correlation_data_categorical_numeric);
    const values = Object.values(result.correlation_data_categorical_numeric);

    // Prepare data
    const etaValues = values.map(v => v.eta_squared_cn !== null ? Number(v.eta_squared_cn.toFixed(3)) : 0);
    const backgroundColors = values.map(v => {
        const alpha = (v["p-value"] !== null && v["p-value"] < 0.05) ? 0.9 : 0.3; // solid if significant
        return `rgba(54,162,235,${alpha})`;
    });

    // Clear container
    correlationPValContainer.innerHTML = `<canvas id="categoricalNumericChart" width="800" height="400"></canvas>`;
    const ctx = document.getElementById("categoricalNumericChart").getContext("2d");

    // Destroy previous chart if exists
    if (window.categoricalNumericChart && typeof window.categoricalNumericChart.destroy === "function") {
        window.categoricalNumericChart.destroy();
    }

    window.categoricalNumericChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: keys,
            datasets: [{
                label: `Correlation ratio (η²) with ${col}`,
                data: etaValues,
                backgroundColor: backgroundColors,
                borderColor: "rgba(54,162,235,1)",
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            const idx = ctx.dataIndex;
                            const eta = etaValues[idx];
                            const p = values[idx]["p-value"];
                            return `η² = ${eta}, p = ${p !== null ? p.toExponential(2) : "NA"}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 1,
                    title: { display: true, text: "η²" }
                }
            }
        }
    });
}

});
