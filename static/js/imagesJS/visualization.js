
const displayImageBtn = document.getElementById("displayImage");
const viewingBoxes = document.getElementById("viewingBoxes");



let uploadedFile = null;
let depth = 0, height = 0, width = 0;
let current = { axial: 0, sagittal: 0, coronal: 0 };


document.getElementById("fileInput").addEventListener("change", function () {
    const file = this.files[0];
    if (!file) return;

    
    // Save it globally
    uploadedFile = file;

    document.getElementById("filePreview").classList.remove("hidden");
    document.getElementById("columnSelector").classList.remove("hidden");

    document.getElementById("uploadedMessage").innerHTML =
        `You uploaded: <span style="color:#bb0d2d; font-weight:700;">${file.name}</span>`;
});


displayImageBtn.addEventListener("click", async () => {

    viewingBoxes.classList.remove("hidden");

    if (!uploadedFile) return alert("Select a file first!");

    const formData = new FormData();
    formData.append("file", uploadedFile);

    const res = await fetch("/upload_image", { method: "POST", body: formData });
    const info = await res.json();

    depth = Number(info.depth) || 1;
    height = Number(info.height) || 1;
    width = Number(info.width) || 1;

    current.axial = Math.floor((depth || 1) / 2);
    current.sagittal = Math.floor((width || 1) / 2);
    current.coronal = Math.floor((height || 1) / 2);

    // Load initial slices
    updateSlice('axial');
    updateSlice('sagittal');
    updateSlice('coronal');




    // --- NEW: handle 3D volume ---
    const volume3D = info.volume_3d;

    // separate factors for scaling
    const factorX = info.downsample_factorx; // X axis
    const factorY = info.downsample_factory; // Y axis
    const factorZ = 1;                       // depth kept intact

    console.log(factorX, factorY, factorZ) //320 320 1

    render3D(volume3D, { x: factorX, y: factorY, z: factorZ });

});


// Function to fetch and update a slice
async function updateSlice(view) {
    const index = Number(current[view]) || 0;  // Prevent NaN

    const res = await fetch(`/get_slice?view=${view}&index=${index}`);
    const data = await res.json();

    document.getElementById(view + "Canvas").src = "data:image/png;base64," + data.image;
    document.getElementById(view + "Index").innerText = index;
}


// Function to change slice with arrows
function changeSlice(view, delta) {
    if (view === "axial")
        current.axial = Math.min(Math.max((Number(current.axial) || 0) + delta, 0), depth - 1);

    if (view === "sagittal")
        current.sagittal = Math.min(Math.max((Number(current.sagittal) || 0) + delta, 0), width - 1);

    if (view === "coronal")
        current.coronal = Math.min(Math.max((Number(current.coronal) || 0) + delta, 0), height - 1);

    updateSlice(view);
}





function render3D(volume, scale) {
    const x = [];
    const y = [];
    const z = [];
    const values = [];

    const depth = volume.length;
    const height = volume[0].length;
    const width = volume[0][0].length;

    const threshold = 0; // adjust to hide background

    for (let k = 0; k < depth; k++) {
        for (let i = 0; i < height; i++) {
            for (let j = 0; j < width; j++) {
                const val = volume[k][i][j];
                if (val > threshold) {
                    x.push(j * scale.x);
                    y.push(i * scale.y);
                    z.push(k * scale.z);
                    values.push(val);
                }
            }
        }
    }

    const trace = {
        x: x,
        y: y,
        z: z,
        mode: 'markers',
        marker: {
            size: 1,
            color: values,
            colorscale: 'Gray',
            opacity: 0.3
        },
        type: 'scatter3d'
    };

    const layout = {
        scene: {
            xaxis: { title: 'X' },
            yaxis: { title: 'Y' },
            zaxis: { title: 'Z' }
        },
        margin: { l: 0, r: 0, b: 0, t: 0 }
    };

    Plotly.newPlot('volume3D', [trace], layout);
}
