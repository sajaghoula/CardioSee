const viewDistributionAnalysisBtn = document.getElementById("viewDistributionAnalysisBtn");
const distContainer = document.getElementById("distContainer");
const numericalDist = document.getElementById("numericalDist");
const categoricalDist = document.getElementById("categoricalDist");

async function getOutlierSystemVariables() {
    try {
        const response = await fetch('/get_system_variables');
        const variables = await response.json();
        
        const varObj = {};
        variables.forEach(v => {
            varObj[v.variable] = v.value;
        });
        
        // Parse coverage factor with validation
        let coverageFactor = parseFloat(varObj.outlier_coverage_factor) || 1.96;
        
        // Validate against common Z-scores
        const validZValues = [1.645, 1.96, 2.576, 3.291];
        if (!validZValues.includes(coverageFactor)) {
            console.warn(`Invalid coverage factor: ${coverageFactor}. Using default 1.96`);
            coverageFactor = 1.96;
        }

        
        return {
            coverageFactor: coverageFactor,
            
        };
    } catch (error) {
        console.error('Error:', error);
        return { coverageFactor: 1.96 }; // Default fallback
    }
}



// STEP 5: View Distribution Analysis
viewDistributionAnalysisBtn.addEventListener("click", async () => {

    const formData = new FormData();
    formData.append("file", selectedFile);
    const column = columnSelect.value;
    formData.append("column", column);

    if (!statsSheetSelector.classList.contains("hidden")) {
        formData.append("sheet_name", statsSheetSelect.value);
    }
    numeric_corrContainer.classList.add("hidden");
    corrContainer.classList.add("hidden");
    statsResult.classList.add("hidden");
    distContainer.classList.remove("hidden");


    const res = await fetch("/get_distributionAnalysis", { method: "POST", body: formData });
    const result = await res.json();

    console.log(result);

    if (window.distContainer && typeof window.distContainer.destroy === "function") {
        window.distContainer.destroy();
    }




    if (result.type === "numeric") {

        categoricalDist.classList.add("hidden");
        numericalDist.classList.remove("hidden");




        const numericDist = document.getElementById("numericalDist");

        // Clear content safely
        numericDist.innerHTML = '';
        const header = document.createElement("h3");
        header.textContent = "Numerical Distribution Analysis";
        numericDist.appendChild(header);

        // HISTOGRAM
        const histCanvas = document.createElement("canvas");
        histCanvas.id = "histChart";
        numericDist.appendChild(histCanvas);

        new Chart(histCanvas, {
            type: "bar",
            data: {
                labels: result.histogram.edges.slice(0, -1).map(e => e.toFixed(2)),
                datasets: [{
                    label: "Histogram",
                    data: result.histogram.counts,
                    backgroundColor: "rgba(75,192,192,0.5)"
                }]
            },
            options: {
                scales: {
                    x: { title: { display: true, text: column } },
                    y: { title: { display: true, text: "Count" } }
                }
            }
        });

        // DENSITY PLOT
        const densityCanvas = document.createElement("canvas");
        densityCanvas.id = "densityChart";
        numericDist.appendChild(densityCanvas);



        new Chart(densityCanvas, {
            data: {
                labels: result.density.x, // x-axis values
                datasets: [
                    {
                        type: "bar",
                        label: "Density (Bar)",
                        data: result.density.y,
                        backgroundColor: "rgba(54, 162, 235, 0.5)",
                        borderColor: "rgba(54, 162, 235, 1)",
                        borderWidth: 1
                    },
                    {
                        type: "line",
                        label: "Density (Line)",
                        data: result.density.y,
                        fill: false,
                        borderColor: "rgba(255, 99, 132, 1)",
                        tension: 0.2
                    }
                ]
            },
            options: {
                responsive: true,
                scales: {
                    x: {
                        title: { display: true, text: column }
                    },
                    y: {
                        title: { display: true, text: "Density" }
                    }
                }
            }
        });

        const config = await getOutlierSystemVariables();

        const yValues = result.seriesData; // your numeric column
        const mean = math.mean(yValues);
        const std = math.std(yValues);


        const coverageFactor = config.coverageFactor;
        const ellipseHeight = coverageFactor * std; 
        const ellipseWidth = 0.8; // X jitter range
        const centerX = 0.4; // middle of X-axis
        const centerY = mean;

        // Create canvas
        const dotCanvas = document.createElement("canvas");
        dotCanvas.id = "dotCanvas";
        numericDist.appendChild(dotCanvas);

        // Scatter chart with ellipse plugin
        new Chart(dotCanvas, {
            type: "scatter",
            data: {
                datasets: [{
                    label: "Values",
                    data: yValues.map(y => ({ x: Math.random() * ellipseWidth, y })), // jitter
                    pointBackgroundColor: yValues.map(v =>
                        (v < centerY - coverageFactor * std || v > centerY + coverageFactor * std) ? 'red' : 'blue'
                    ),
                    pointRadius: 4
                }]
            },
            options: {
                scales: {
                    x: {
                        min: 0,
                        max: ellipseWidth,
                        display: false
                    },
                    y: {
                        title: { display: true, text: column }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            },
            plugins: [{
                id: 'ellipseOverlay',
                afterDatasetsDraw: chart => {
                    const ctx = chart.ctx;
                    const xScale = chart.scales.x;
                    const yScale = chart.scales.y;

                    // Calculate pixels
                    const cx = xScale.getPixelForValue(centerX);
                    const cy = yScale.getPixelForValue(centerY);
                    const rx = xScale.getPixelForValue(centerX + ellipseWidth / 2) - xScale.getPixelForValue(centerX);
                    const ry = yScale.getPixelForValue(centerY - coverageFactor * std) - cy; // negative because y-axis is inverted

                    ctx.save();
                    ctx.beginPath();
                    ctx.ellipse(cx, cy, rx, Math.abs(ry), 0, 0, 2 * Math.PI);
                    ctx.fillStyle = 'rgba(0,123,255,0.1)';
                    ctx.fill();
                    ctx.strokeStyle = 'rgba(0,123,255,0.5)';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                    ctx.restore();
                }
            }]
        });



    }

    else if (result.type === "categorical") {
        numericalDist.classList.add("hidden");
        categoricalDist.classList.remove("hidden");







        // Clear previous charts
        document.getElementById("catBarChart").innerHTML = "";
        document.getElementById("chiSquareTable").innerHTML = "";

        //---------------------- BAR CHART (with destroy fix) ----------------------
        const categories = result.frequency_table.map(item => item.Category);
        const counts = result.frequency_table.map(item => item.Count);

        // Destroy old chart if exists

        if (window.catBarChartInstance && typeof window.catBarChartInstance.destroy === "function") {
            window.catBarChartInstance.destroy();
        }



        catBarChartInstance = new Chart(document.getElementById("catBarChart"), {
            type: 'bar',
            data: {
                labels: categories,
                datasets: [{
                    data: counts
                }]
            },
            options: {
                plugins: {
                    title: { display: true, text: "Frequency Bar Chart" },
                    legend: { display: false }
                }
            }
        });


        //---------------------- 3) CHI-SQUARE TABLE ----------------------
        const chi = result.chi_square;


        let html = `
    <h3 style="margin-top:25px;">Chi-Square Association with Other Categorical Columns</h3>

    <div class="chi-container">
        <table class="chi-table">
            <thead>
                <tr>
                    <th style ="text-align: center">Column</th>
                    <th style ="text-align: center">Chi²</th>
                    <th style ="text-align: center">P-value</th>
                    <th style ="text-align: center">df</th>
                    <th style ="text-align: center">Significance</th>
                </tr>
            </thead>
            <tbody>
`;

        // Sort by p-value ascending
        const sorted = Object.entries(chi).sort((a, b) => a[1].p_value - b[1].p_value);

        sorted.forEach(([col, stats]) => {
            const p = stats.p_value;
            const significant = p < 0.05;

            html += `
        <tr class="${significant ? "significant-row" : ""}">
            <td style ="text-align: center">${col}</td>
            <td style ="text-align: center">${stats.chi2.toFixed(3)}</td>
            <td style ="text-align: center">${p.toExponential(3)}</td>
            <td style ="text-align: center">${stats.degrees_of_freedom}</td>
            <td style ="text-align: center">
                <span class="badge ${significant ? "badge-green" : "badge-gray"}">
                    ${significant ? "Significant" : "Not Significant"}
                </span>
            </td>
        </tr>
    `;
        });

        html += `
            </tbody>
        </table>
    </div>
`;

//comment chi square in distribution analysis
        //document.getElementById("chiSquareTable").innerHTML = html;



    }


});
