
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


    console.log(result.correlation_data_numeric_categorical)

    if (result.correlation_data_numeric_numeric && Object.keys(result.correlation_data_numeric_numeric).length > 0) {
        const numeric_corrContainer = document.getElementById("numeric_corrContainer");
        const numeric_numeric_correlation = document.getElementById("numeric_numeric_correlation");
        const numeric_categorical_correlation = document.getElementById("numeric_categorical_correlation");


        numeric_corrContainer.classList.remove("hidden");
        numeric_numeric_correlation.classList.remove("hidden");
        numeric_numeric_correlation.innerHTML = "";


        // --- Build Spearman bar chart ---
        const numeric_numeric_barchart = "numeric_numeric_barchart";
        numeric_numeric_correlation.innerHTML += `<canvas id="${numeric_numeric_barchart}" width="600" height="300"></canvas>`;
        const numeric_numeric_ctxBar = document.getElementById(numeric_numeric_barchart).getContext("2d");

        if (window.numeric_corrContainer && typeof window.numeric_corrContainer.destroy === "function") {
            window.numeric_corrContainer.destroy();
        }

        const keys = Object.keys(result.correlation_data_numeric_numeric);
        const values = Object.values(result.correlation_data_numeric_numeric);



        window.numeric_corrContainer = new Chart(numeric_numeric_ctxBar, {
            type: "bar",
            data: {
                labels: keys,
                datasets: [{
                    label: `Spearman correlation with ${col}`,
                    data: values.map(v => v !== null ? v.toFixed(3) : 0),
                    backgroundColor: values.map(v => v >= 0 ? "rgba(54,162,235,0.7)" : "rgba(255,99,132,0.7)"),
                    borderColor: values.map(v => v >= 0 ? "rgba(54,162,235,1)" : "rgba(255,99,132,1)"),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    y: { min: -1, max: 1, title: { display: true, text: "Correlation" } }
                }
            }
        });



    }


    if (result.correlation_data_numeric_categorical && Object.keys(result.correlation_data_numeric_categorical).length > 0) {
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

        // Extract eta_squared for display
        const valuesForChart = values.map(v => {
            if (v.eta_squared !== null) return parseFloat(v.eta_squared.toFixed(3));
            if (v.F !== null) return parseFloat(v.F.toFixed(3));
            return 0;
        });

        window.numericCategoricalChart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: keys,
                datasets: [{
                    label: `Correlation ratio (η²) with ${col}`,
                    data: valuesForChart,
                    backgroundColor: "rgba(54,162,235,0.7)",
                    borderColor: "rgba(54,162,235,1)",
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, max: 1, title: { display: true, text: "η²" } }
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
        const pvalues = cols.map(col => data[col].p_value ?? 0);

        // --------------------------
        // Chart 1: Cramer's V
        // --------------------------
        container.innerHTML += `<h3>Correlation with Categorical Columns - Cramer's V (Strength of Association)</h3>`;
        container.innerHTML += `<canvas id="categorical_categorical_cramers_chart" width="600" height="300"></canvas>`;

        const ctx1 = document.getElementById("categorical_categorical_cramers_chart").getContext("2d");

        if (window.categoricalCategoricalCramersChart) {
            window.categoricalCategoricalCramersChart.destroy();
        }

        window.categoricalCategoricalCramersChart = new Chart(ctx1, {
            type: "bar",
            data: {
                labels: cols,
                datasets: [{
                    label: "Cramer's V",
                    data: cramersValues
                }]
            },
            options: {
                responsive: true,
                scales: { y: { min: 0, max: 1 } }
            }
        });


    }


    if (result.correlation_data_categorical_numeric && Object.keys(result.correlation_data_categorical_numeric).length > 0) {
        corrContainer.classList.remove("hidden");
        numeric_corrContainer.classList.add("hidden");

        const keys = Object.keys(result.correlation_data_categorical_numeric);
        const values = Object.values(result.correlation_data_categorical_numeric);

        // Check if values are objects (ANOVA: {F, p-value}) or simple numbers (Spearman)
        const isANOVA =
            typeof values[0] === "object" &&
            values[0] !== null &&
            values[0].hasOwnProperty("F") &&
            values[0].hasOwnProperty("p-value");

        if (isANOVA) {


            // --- Prepare data for ANOVA charts ---
            const chartCols = [];
            const Fvalues = [];
            const pvalues = [];

            for (let i = 0; i < keys.length; i++) {
                const val = values[i];
                const Fval = val.F !== null ? val.F : 0;               // Replace N/A with 0
                const pval = val["p-value"] !== null ? val["p-value"] : 0; // Replace N/A with 0

                chartCols.push(keys[i]);
                Fvalues.push(Fval);
                pvalues.push(pval);
            }


            // Clear container (we removed the table)
            correlationPValContainer.innerHTML = "";
            correlationFValContainer.innerHTML = "";

            /* -------------------------------
               F-VALUE BAR CHART
            -------------------------------- */
            const fChartId = "anovaFChart";
            correlationFValContainer.innerHTML += `<canvas id="${fChartId}" width="600" height="300" style="margin-top:20px;"></canvas>`;



            const pChartId = "anovaPChart";
            correlationPValContainer.innerHTML += `<canvas id="${pChartId}" width="600" height="300" style="margin-top:20px;"></canvas>`;



            const ctxF = document.getElementById(fChartId).getContext("2d");

            if (window.anovaFChart && typeof window.anovaFChart.destroy === "function") {
                window.anovaFChart.destroy();
            }



            // Extract eta_squared for display
            const valuesForChart = values.map(v => {
                if (v.eta_squared_cn !== null) return parseFloat(v.eta_squared_cn.toFixed(3));
                if (v.F !== null) return parseFloat(v.F.toFixed(3));
                return 0;
            });
            console.log('saja', valuesForChart)


            window.numericCategoricalChart = new Chart(ctxF, {
                type: "bar",
                data: {
                    labels: chartCols,
                    datasets: [{
                        label: `Correlation ratio (η²) with ${col}`,
                        data: valuesForChart,
                        backgroundColor: "rgba(75,192,75,0.7)",
                        borderColor: "rgba(75,192,75,1)",
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { beginAtZero: true, max: 1, title: { display: true, text: "η²" } }
                    }
                }
            });




            /* -------------------------------
               P-VALUE BAR CHART
            -------------------------------- */


            const ctxP = document.getElementById(pChartId).getContext("2d");

            if (window.anovaPChart && typeof window.anovaPChart.destroy === "function") {
                window.anovaPChart.destroy();
            }

            const barColors = pvalues.map(v => v < 0.05 ? "rgba(255, 0, 0, 0.9)" : "rgba(255, 182, 193, 0.9)");


            window.anovaPChart = new Chart(ctxP, {
                type: "bar",
                data: {
                    labels: chartCols,
                    datasets: [{
                        label: "p-value",
                        data: pvalues,
                        backgroundColor: barColors,
                        borderColor: barColors,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { display: false },
                        annotation: {
                            annotations: {
                                line1: {
                                    type: 'line',
                                    yMin: 0.05,
                                    yMax: 0.05,
                                    borderColor: 'red',
                                    borderWidth: 2,
                                    label: { content: 'Significance 0.05', enabled: true, position: 'start' }
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: "p-value" }
                        },
                        x: {
                            ticks: {
                                callback: function (value, index) {
                                    // Make label bold if corresponding p-value < 0.05
                                    const p = pvalues[index];
                                    if (p < 0.05) {
                                        return '\u0000' + this.getLabelForValue(value); // placeholder, real bold below
                                    } else {
                                        return this.getLabelForValue(value);
                                    }
                                },
                                font: function (context) {
                                    const index = context.index;
                                    const p = pvalues[index];
                                    return {
                                        weight: p < 0.05 ? 'bold' : 'normal'
                                    }
                                }
                            }
                        }
                    }
                }
            });



        }


    }
});
