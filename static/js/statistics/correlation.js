
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



    const entries = Object.keys(result.correlation_data_numeric_numeric).map(k => ({
        key: k,
        r: result.correlation_data_numeric_numeric[k],
        p: pvals[k]
    }));
    entries.sort((a, b) => {
        const sigA = a.p !== null && a.p < 0.05;
        const sigB = b.p !== null && b.p < 0.05;

        if (sigA !== sigB) return sigB - sigA;
        if (a.p !== null && b.p !== null) return a.p - b.p;

        return Math.abs(b.r) - Math.abs(a.r);
    });
    const keys = entries.map(e => e.key);
    const values = entries.map(e => e.r);


    window.numeric_corrContainer = new Chart(ctx, {
        type: "bar",
        data: {
            labels: keys,
            datasets: [{
                label: `Spearman correlation with ${col}`,
                data: values.map(v => v !== null ? v.toFixed(3) : 0),
                backgroundColor: keys.map((k, i) => {
                    const r = Math.abs(values[i]);
                    const p = pvals[k];

                    let alpha;

                    if (p !== null && p < 0.05) {
                        // dark stays dark → stronger = darker
                        alpha = 0.75 + 0.50 * r;   // 0.6 → 0.95
                    } else {
                        // light stays light → weaker = lighter
                        alpha = 0.10 + 0.1 * r;  // 0.15 → 0.4
                    }

                    return values[i] >= 0
                        ? `rgba(54,162,235,${alpha})`
                        : `rgba(255,99,132,${alpha})`;
                }),
                borderColor: values.map(v =>
                    v >= 0 ? "rgba(54,162,235,1)" : "rgba(255,99,132,1)"
                ),
                borderWidth: keys.map(k =>
    pvals[k] !== null && pvals[k] < 0.05 ? 2 : 1
),
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

    // Create canvas for the chart (increased size)
    const canvasId = "numeric_categorical_barchart";
    numeric_categorical_correlation.innerHTML = `<canvas id="${canvasId}" width="800" height="400"></canvas>`;
    const ctx = document.getElementById(canvasId).getContext("2d");

    // Destroy previous chart if exists
    if (window.numericCategoricalChart && typeof window.numericCategoricalChart.destroy === "function") {
        window.numericCategoricalChart.destroy();
    }

    // Prepare entries
    const entries = Object.keys(result.correlation_data_numeric_categorical).map(k => ({
        key: k,
        eta: result.correlation_data_numeric_categorical[k].eta_squared,
        p: result.correlation_data_numeric_categorical[k]["p-value"]
    }));

    // Sort by significance (smallest p first)
    entries.sort((a, b) => {
        if (a.p === null) return 1;
        if (b.p === null) return -1;
        return a.p - b.p;
    });

    const keys = entries.map(e => e.key);
    const valuesForChart = entries.map(e => e.eta !== null ? Number(e.eta.toFixed(3)) : 0);

    // Prepare p-values for scaling dark bars
    const sigPs = entries.map(e => e.p).filter(p => p !== null && p < 0.05);
    const minSigP = sigPs.length > 0 ? Math.min(...sigPs) : 0.001;
    const maxSigP = sigPs.length > 0 ? Math.max(...sigPs) : 0.05;

    // Dynamic background color
    const backgroundColors = entries.map(e => {
        let alpha;
        if (e.p !== null && e.p < 0.05) {
            // Significant → dark, scale based on p-value
            const t = (e.p - minSigP) / (maxSigP - minSigP || 1); // normalize 0 → 1
            alpha = 0.95 - 0.25 * t; // smaller p → darker
        } else {
            // Not significant → light
            alpha = 0.2;
        }
        return `rgba(54,162,235,${alpha})`;
    });

    // Determine max Y for chart to make small η² visible
    const maxY = Math.max(...valuesForChart) * 1.1 || 0.1;

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
                            const p = entries[idx].p;
                            return `η² = ${eta}, p = ${p !== null ? p.toExponential(2) : "NA"}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: maxY,
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

    // Prepare entries
    const entries = Object.keys(data).map(col => ({
        key: col,
        cramers: data[col].cramers_v ?? 0,
        p: data[col]["p-value"] ?? 1
    }));

    // Sort by significance (lowest p first)
    entries.sort((a, b) => {
        if (a.p === null) return 1;
        if (b.p === null) return -1;
        return a.p - b.p;
    });

    const cols = entries.map(e => e.key);
    const cramersValues = entries.map(e => e.cramers !== null ? parseFloat(e.cramers.toFixed(3)) : 0);
    const pvalues = entries.map(e => e.p);

    // Prepare p-values for scaling dark bars
    const sigPs = entries.map(e => e.p).filter(p => p !== null && p < 0.05);
    const minSigP = sigPs.length > 0 ? Math.min(...sigPs) : 0.001;
    const maxSigP = sigPs.length > 0 ? Math.max(...sigPs) : 0.05;

    // Dynamic background color
    const barColors = entries.map(e => {
        let alpha;
        if (e.p !== null && e.p < 0.05) {
            // Significant → dark, scale based on p-value
            const t = (e.p - minSigP) / (maxSigP - minSigP || 1);
            alpha = 0.95 - 0.25 * t; // smaller p → darker
        } else {
            // Not significant → light
            alpha = 0.2;
        }
        return `rgba(54,162,235,${alpha})`;
    });

    // Determine max Y dynamically for visibility
    const maxY = Math.max(...cramersValues) * 1.1 || 0.1;

    // Create chart
    container.innerHTML += `<h3>🔗 Correlation with Categorical Columns - Cramer's V & Chi-square - </h3>`;
    container.innerHTML += `<canvas id="categorical_categorical_chart" width="800" height="400"></canvas>`;

    const ctx = document.getElementById("categorical_categorical_chart").getContext("2d");

    if (window.categoricalCategoricalChart) {
        window.categoricalCategoricalChart.destroy();
    }

    window.categoricalCategoricalChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: cols,
            datasets: [{
                label: "Cramer's V (strength)",
                data: cramersValues,
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
                y: {
                    min: 0,
                    max: maxY,
                    title: { display: true, text: "Cramer's V" }
                }
            }
        }
    });
}




if (result.correlation_data_categorical_numeric && Object.keys(result.correlation_data_categorical_numeric).length > 0) {
    corrContainer.classList.remove("hidden");
    numeric_corrContainer.classList.add("hidden");

    // Prepare entries
    const entries = Object.keys(result.correlation_data_categorical_numeric).map(k => ({
        key: k,
        eta: result.correlation_data_categorical_numeric[k].eta_squared_cn,
        p: result.correlation_data_categorical_numeric[k]["p-value"]
    }));

    // Sort by significance (lowest p first)
    entries.sort((a, b) => {
        if (a.p === null) return 1;
        if (b.p === null) return -1;
        return a.p - b.p;
    });

    const keys = entries.map(e => e.key);
    const etaValues = entries.map(e => e.eta !== null ? Number(e.eta.toFixed(3)) : 0);

    // Prepare p-values for scaling dark bars
    const sigPs = entries.map(e => e.p).filter(p => p !== null && p < 0.05);
    const minSigP = sigPs.length > 0 ? Math.min(...sigPs) : 0.001;
    const maxSigP = sigPs.length > 0 ? Math.max(...sigPs) : 0.05;

    // Dynamic background color
    const backgroundColors = entries.map(e => {
        let alpha;
        if (e.p !== null && e.p < 0.05) {
            // Significant → dark, scale based on p-value
            const t = (e.p - minSigP) / (maxSigP - minSigP || 1); // normalize 0 → 1
            alpha = 0.95 - 0.25 * t; // smaller p → darker
        } else {
            // Not significant → light
            alpha = 0.2;
        }
        return `rgba(54,162,235,${alpha})`;
    });

    // Determine max Y dynamically
    const maxY = Math.max(...etaValues) * 1.1 || 0.1;

    // Clear container and create canvas
    correlationPValContainer.innerHTML = `<canvas id="categoricalNumericChart" width="800" height="400"></canvas>`;
    const ctx = document.getElementById("categoricalNumericChart").getContext("2d");

    // Destroy previous chart if exists
    if (window.categoricalNumericChart && typeof window.categoricalNumericChart.destroy === "function") {
        window.categoricalNumericChart.destroy();
    }

    // Create chart
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
                            const p = entries[idx].p;
                            return `η² = ${eta}, p = ${p !== null ? p.toExponential(2) : "NA"}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: maxY,
                    title: { display: true, text: "η²" }
                }
            }
        }
    });
}


});
