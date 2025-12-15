
// STEP 3: View statistics
viewStatsBtn.addEventListener("click", async () => {
    const formData = new FormData();
    formData.append("file", selectedFile);
    const col = columnSelect.value;
    formData.append("column", col);

    if (!statsSheetSelector.classList.contains("hidden")) {
        formData.append("sheet_name", statsSheetSelect.value);
    }

    const res = await fetch("/column_stats", { method: "POST", body: formData });
    const result = await res.json();

    
    // Inject table HTML
    document.getElementById("statsTableContainer").innerHTML = result.html;


    distContainer.classList.add("hidden");
    corrContainer.classList.add("hidden");
    numeric_corrContainer.classList.add("hidden");
    statsResult.classList.remove("hidden");


    // Pie chart
    if (result.pie_data) {
        const pieContainer = document.getElementById("pieChartContainer");
        pieContainer.style.display = "block";

        const ctx = document.getElementById("pieChart").getContext("2d");

        if (window.pieChart && typeof window.pieChart.destroy === "function") {
            window.pieChart.destroy();
        }

        const dataValues = Object.values(result.pie_data);
        const total = dataValues.reduce((a, b) => a + b, 0);

        window.pieChart = new Chart(ctx, {
            type: "pie",
            data: {
                labels: Object.keys(result.pie_data),
                datasets: [{
                    data: dataValues,
                    backgroundColor: [
                        "#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0",
                        "#9966FF", "#FF9F40", "#C9CBCF", "#A8A8A8",
                        "#FF7F50", "#87CEFA", "#B0E0E6"
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: "bottom" },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                const value = context.raw;
                                const percent = ((value / total) * 100).toFixed(1);
                                return `${context.label}: ${value} (${percent}%)`;
                            }
                        }
                    },
                    datalabels: {
                        formatter: (value, ctx) => {
                            const percent = ((value / total) * 100).toFixed(1);
                            return percent + "%";
                        },
                        color: "#fff",
                        font: {
                            weight: "bold",
                            size: 12
                        }
                    }
                }
            },
            plugins: [ChartDataLabels]
        });
    } else {
        document.getElementById("pieChartContainer").style.display = "none";
    }



});
