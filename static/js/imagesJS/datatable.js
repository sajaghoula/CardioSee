// Render table
let currentPage = 1;
const rowsPerPage = 10;
let filteredRows = []; // store rows after search

// Sorting
let sortState = {}; // remembers asc/desc
let currentImageId = null;


const current = {
    axial: 0,
    coronal: 0,
    sagittal: 0
};




async function loadLibraryTable() {
    const res = await fetch("/library_data");
    const data = await res.json();


    window.tableRows = data.map(item => ({
        id: item.id,
        name: item.name || "-",
        filetype: item.filetype || "-",
        createdBy: item.createdBy || "-",
        createdAt: item.createdAt || "-", 
        quality: item.quality  || "-", 
        geometry: item.geometry  || "-", 
        stats: item.stats  || "-",
        median: item.median ?? "-",
        dark: item.dark ?? "-",
        dominant_tissue: item.dominant_tissue || "-",
        physical_size: item.physical_size ?? "-",
        volume_cm3: item.volume_cm3 ?? "-",
        cardio: item.cardio ?? "-",
        segmentation: item.segmentation || "-",
        total_eat_volume: item.total_eat_volume || "not ready",
    }));


    filteredRows = window.tableRows; // initially no filter
    currentPage = 1;
    renderTable();
}

function renderTable(rows) {
    const tableBody = document.querySelector("#libraryTableBody");
    tableBody.innerHTML = "";

    const start = (currentPage - 1) * rowsPerPage;
    const end = start + rowsPerPage;
    const paginatedRows = filteredRows.slice(start, end);

    paginatedRows.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
        <td>${row.name}</td>
        <td>${row.filetype}</td>
        <td>${row.total_eat_volume}</td>
        
        <td>${row.median}</td>
        <td>${row.volume_cm3}</td>
        <td>${row.dark}</td>

        <td>
            ${renderSegmentationCell(row)}
        </td>

        <td>
            <button class="btn-small" onclick="viewInfo('${row.id}')">
            <i class="fa-solid fa-info"></i>
            </button>

            <button class="btn-small" onclick="viewImage('${row.id}')">
            <i class="fas fa-eye"></i>
            </button>

            <button class="btn-small" onclick="view3D('${row.id}')">
            3D
            </button>

            <button class="btn-small btn-danger" onclick="deleteImage('${row.id}')">
            <i class="fas fa-trash-alt"></i>
            </button>
        </td>
        `;

        tableBody.appendChild(tr);
    });

    renderPaginationControls();
}


function renderPaginationControls() {
    const totalPages = Math.ceil(filteredRows.length / rowsPerPage);
    const paginationDiv = document.getElementById("pagination");
    paginationDiv.innerHTML = "";

    // Left arrow
    const prevBtn = document.createElement("button");
    prevBtn.textContent = "<<";
    prevBtn.classList.add("page-btn");
    prevBtn.disabled = currentPage === 1; // disable on first page
    prevBtn.addEventListener("click", () => {
        if (currentPage > 1) {
            currentPage--;
            renderTable();
        }
    });
    paginationDiv.appendChild(prevBtn);

    // Page numbers
    for (let i = 1; i <= totalPages; i++) {
        const btn = document.createElement("button");
        btn.textContent = i;
        btn.classList.add("page-btn");
        if (i === currentPage) btn.classList.add("active");

        btn.addEventListener("click", () => {
            currentPage = i;
            renderTable();
        });

        paginationDiv.appendChild(btn);
    }

    // Right arrow
    const nextBtn = document.createElement("button");
    nextBtn.textContent = ">>";
    nextBtn.classList.add("page-btn");
    nextBtn.disabled = currentPage === totalPages; // disable on last page
    nextBtn.addEventListener("click", () => {
        if (currentPage < totalPages) {
            currentPage++;
            renderTable();
        }
    });
    paginationDiv.appendChild(nextBtn);
}



// Search input
searchInput.addEventListener("input", () => {
    const term = searchInput.value.toLowerCase();

    filteredRows = window.tableRows.filter(row => 
        row.name.toLowerCase().includes(term) ||
        row.filetype.toLowerCase().includes(term) ||
        row.createdBy.toLowerCase().includes(term) 
        //row.dominant_tissue.toLowerCase().includes(term)
        
    );

    currentPage = 1; // reset to first page after search
    renderTable();
});


// Sorting
document.querySelectorAll("th[data-sort]").forEach(header => {
    header.addEventListener("click", () => {
        const key = header.dataset.sort;

        // toggle ASC/DESC
        sortState[key] = sortState[key] === "asc" ? "desc" : "asc";
        const direction = sortState[key];

        filteredRows.sort((a, b) => {
            let x = a[key];
            let y = b[key];

            // Handle missing values
            if (x === "-" || x === null || x === undefined) return 1;
            if (y === "-" || y === null || y === undefined) return -1;

            // Date sorting
            if (key === "createdAt") {
                x = new Date(x);
                y = new Date(y);
                return direction === "asc" ? x - y : y - x;
            }

            // Numeric sorting
            if (!isNaN(x) && !isNaN(y)) {
                return direction === "asc"
                    ? Number(x) - Number(y)
                    : Number(y) - Number(x);
            }

            // String sorting (fallback)
            return direction === "asc"
                ? x.toString().localeCompare(y.toString())
                : y.toString().localeCompare(x.toString());
        });


        currentPage = 1; // reset to first page after sort
        renderTable();
    });
});



function viewInfo(imageId) {
    const row = window.tableRows.find(r => r.id === imageId);
    if (!row) return;



    
    // ---- Quality ----
    if (row.quality) {
        document.getElementById("qualityContent").innerHTML = `
            <br>
<table class="info-table">
    <tr><th>Variable</th><th>Value</th></tr>
    <tr><td>CNR</td><td>${parseFloat(row.quality.CNR).toFixed(2)}</td></tr>
    <tr><td>SNR</td><td>${parseFloat(row.quality.SNR).toFixed(2)}</td></tr>
    <tr><td>entropy</td><td>${parseFloat(row.quality.entropy).toFixed(2)}</td></tr>
    <tr><td>kurtosis</td><td>${parseFloat(row.quality.kurtosis).toFixed(2)}</td></tr>
    <tr><td>skewness</td><td>${parseFloat(row.quality.skewness).toFixed(2)}</td></tr>
</table>


        `;
    }

// ---- Geometry ----
const geometryDiv = document.getElementById("geometryContent");
const summaryDiv = document.getElementById("segmentationContent");

if (row.segmentation && row.segmentation.analysis_results && row.segmentation.analysis_results.pericardium_bounding_box) {
    const pericardiumBB = row.segmentation.analysis_results.pericardium_bounding_box;

    geometryDiv.innerHTML = `
        <h4>Pericardium Bounding Box (mm)</h4>
        <table class="info-table">
            <tr><th>Axis</th><th>Min</th><th>Max</th><th>Center</th><th>Size</th></tr>
            <tr>
                <td>X</td>
                <td>${parseFloat(pericardiumBB.min_coords_mm[0]).toFixed(2)}</td>
                <td>${parseFloat(pericardiumBB.max_coords_mm[0]).toFixed(2)}</td>
                <td>${parseFloat(pericardiumBB.center_mm[0]).toFixed(2)}</td>
                <td>${parseFloat(pericardiumBB.dimensions_mm[0]).toFixed(2)}</td>
            </tr>
            <tr>
                <td>Y</td>
                <td>${parseFloat(pericardiumBB.min_coords_mm[1]).toFixed(2)}</td>
                <td>${parseFloat(pericardiumBB.max_coords_mm[1]).toFixed(2)}</td>
                <td>${parseFloat(pericardiumBB.center_mm[1]).toFixed(2)}</td>
                <td>${parseFloat(pericardiumBB.dimensions_mm[1]).toFixed(2)}</td>
            </tr>
            <tr>
                <td>Z</td>
                <td>${parseFloat(pericardiumBB.min_coords_mm[2]).toFixed(2)}</td>
                <td>${parseFloat(pericardiumBB.max_coords_mm[2]).toFixed(2)}</td>
                <td>${parseFloat(pericardiumBB.center_mm[2]).toFixed(2)}</td>
                <td>${parseFloat(pericardiumBB.dimensions_mm[2]).toFixed(2)}</td>
            </tr>
        </table>
        
        <div class="info-box">
            <strong>Volume:</strong> ${parseFloat(pericardiumBB.volume_cm3).toFixed(2)} cm³<br>
        </div>
    `;
} else {
    geometryDiv.innerHTML = `
        <div class="alert alert-warning">
            <i class="fas fa-exclamation-triangle"></i>
            Pericardium segmentation not available or analysis incomplete.
        </div>
    `;
}



// ---- Segmentation Summary Section ----

if (row.segmentation) {
    const analysis = row.segmentation.analysis_results;
    const status = row.segmentation.status;
    
    let summaryHTML = `
        <h4>Segmentation Analysis Summary</h4>
        <div class="status-badge ${status === 'finished' ? 'status-success' : 'status-warning'}">
            Status: ${status}
        </div>
    `;
    
    // Add analysis results if available
    if (analysis) {
        // Fat Analysis (if exists)
        if (analysis.fat_analysis) {
            const fat = analysis.fat_analysis;
            summaryHTML += `
                <div class="info-card">
                    <h5><i class="fas fa-heartbeat"></i> Fat Analysis (EAT)</h5>
                    <table class="info-table">
                        <tr><td>Total EAT Volume</td><td>${parseFloat(fat.volume_total_eat_cm3).toFixed(2)} cm³</td></tr>
                        <tr><td>Inflamed EAT</td><td>${parseFloat(fat.volume_inflamed_cm3).toFixed(2)} cm³ (${parseFloat(fat.inflamed_percentage).toFixed(1)}%)</td></tr>
                        <tr><td>Non-Inflamed EAT</td><td>${parseFloat(fat.volume_non_inflamed_cm3).toFixed(2)} cm³</td></tr>
                    </table>
                </div>
            `;
        }
        

        
    } else {
        summaryHTML += `
            <div class="alert alert-info">
                <i class="fas fa-info-circle"></i>
                Analysis results are pending or not yet generated.
            </div>
        `;
    }
    
    summaryDiv.innerHTML = summaryHTML;
} else {
    summaryDiv.innerHTML = `
        <div class="alert alert-info">
            <i class="fas fa-info-circle"></i>
            No segmentation data available for this record.
        </div>
    `;
}




    // ---- Stats ----
    if (row.stats) {
        document.getElementById("statsContent").innerHTML = `

            <br>
            <table class="info-table">
    <tr><th>Variable</th><th>Value</th></tr>
    <tr><td>Mean</td><td>${parseFloat(row.stats.mean).toFixed(2)}</td></tr>
    <tr><td>Median</td><td>${parseFloat(row.stats.median).toFixed(2)}</td></tr>
    <tr><td>Min</td><td>${parseFloat(row.stats.min).toFixed(2)}</td></tr>
    <tr><td>Max</td><td>${parseFloat(row.stats.max).toFixed(2)}</td></tr>
    <tr><td>STD</td><td>${parseFloat(row.stats.std).toFixed(2)}</td></tr>
    <tr><td>Variance</td><td>${parseFloat(row.stats.var).toFixed(2)}</td></tr>
    <tr><td>Shape</td><td>${row.stats.shape}</td></tr>   
            </table>

        `;
    }

    // Show modal
    document.getElementById("infoModal").style.display = "flex";

    // Reset tabs
    document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
    document.querySelectorAll(".tab").forEach(tab => tab.classList.remove("active"));

    document.querySelector(".tab-btn").classList.add("active");
    document.querySelector(".tab").classList.add("active");
}

/* Tab switching */
document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", function () {
        const tabId = btn.getAttribute("data-tab");

        // Activate button
        document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");

        // Activate tab
        document.querySelectorAll(".tab").forEach(tab => tab.classList.remove("active"));
        document.getElementById(tabId).classList.add("active");
    });
});

function closeModal() {
    document.getElementById("infoModal").style.display = "none";
    document.getElementById("visualModal").style.display = "none";
    document.getElementById("visualModal3D").style.display = "none";
    document.getElementById("renderCanvas3D").innerHTML = "";
}




window.onclick = function (event) {
    const modal = document.getElementById("infoModal");
    if (event.target === modal) {
        modal.style.display = "none";
    }
};






async function viewImage(imageId) {
    currentImageId = imageId;   // store it

    const row = window.tableRows.find(r => r.id === imageId);
    if (!row) return alert("Image not found");

    const filename = row.name;   

    document.getElementById("currentFile").value = filename;

    // Show the modal
    const modal = document.getElementById("visualModal");
    modal.style.display = "flex";

    // Load initial slices
    await loadSlices(filename);

}



async function loadSlices(filename) {
    const views = ["axial", "sagittal", "coronal"];
    
    // fetch image info from backend to get volume dimensions
    const res = await fetch(`/load_image_by_name?file=${filename}`);
    const info = await res.json();
    
    // set middle slices for first load
    current.axial = Math.floor(info.depth / 2);
    current.sagittal = Math.floor(info.width / 2);
    current.coronal = Math.floor(info.height / 2);

    for (let view of views) {
        await updateSlice(view, filename, 1);
    }
}

async function updateSlice(view, filename, firstTime) {
    const index = current[view] || 0;

    // Note: backticks used here
    //const res = await fetch(`/get_slice_2?view=${view}&index=${index}&file=${filename}&firstTime=${firstTime}`);
    const res = await fetch( `/get_slice_mapping?view=${view}&index=${index}&file=${filename}&image_id=${currentImageId}`);
    
    if (!res.ok) {
        console.error("Slice request failed:", res.status, await res.text());
        return;
    }

    const data = await res.json();
    document.getElementById(view + "Canvas").src = "data:image/png;base64," + data.image;
    document.getElementById(view + "Index").innerText = index;
}


// Function to change slice
function changeSlice(view, delta) {
    current[view] += delta;
    if (current[view] < 0) current[view] = 0;

    const filename = document.getElementById("currentFile").value;
    updateSlice(view, filename);
}











async function view3D(imageId) {
    try {
        const row = window.tableRows.find(r => r.id === imageId);
        if (!row) {
            alert("Image not found");
            return;
        }

        const filename = row.name;

        // Show modal
        const modal = document.getElementById("visualModal3D");
        modal.style.display = "flex";

        // Show loading indicator
        const loading = document.createElement('div');
        loading.id = 'loading3D';
        loading.style.cssText = `
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: white;
            font-size: 20px;
            z-index: 1000;
        `;
        loading.textContent = 'Loading 3D volume...';
        modal.appendChild(loading);

        const res = await fetch(`/load_volume_3d?file=${encodeURIComponent(filename)}`);
        
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }

        const json = await res.json();

        if (!json.data || !json.shape) {
            console.error("Volume load failed:", json);
            alert("Error loading 3D volume: Invalid response format");
            return;
        }

        // Decode base64 into ArrayBuffer
        const binaryStr = atob(json.data);
        const len = binaryStr.length;
        const buffer = new ArrayBuffer(len);
        const view = new Uint8Array(buffer);
        for (let i = 0; i < len; i++) {
            view[i] = binaryStr.charCodeAt(i);
        }

        const floatArray = new Float32Array(buffer);

        console.log('Volume data loaded:', {
            size: floatArray.length,
            shape: json.shape,
            expectedSize: json.shape[0] * json.shape[1] * json.shape[2]
        });

        // Verify data matches shape
        const expectedSize = json.shape[0] * json.shape[1] * json.shape[2];
        if (floatArray.length !== expectedSize) {
            console.warn(`Data size mismatch: expected ${expectedSize}, got ${floatArray.length}`);
        }

        // Remove loading indicator
        modal.removeChild(loading);

        // Ensure canvas exists
        let canvas = document.getElementById('renderCanvas3D');
        if (!canvas) {
            canvas = document.createElement('canvas');
            canvas.id = 'renderCanvas3D';
            canvas.style.width = '100%';
            canvas.style.height = '100%';
            modal.querySelector('.modal-content').appendChild(canvas);
        }

        // Clear any previous Three.js scene
        if (window.currentScene3D) {
            window.currentScene3D.dispose();
        }

        // Render 3D volume
        await render3D({ data: floatArray, shape: json.shape });
        
        // Store reference for cleanup
        window.currentScene3D = { dispose: () => {
            // Add cleanup logic here if needed
        }};

    } catch (error) {
        console.error('Error in view3D:', error);
        alert(`Error loading 3D volume: ${error.message}`);
        
        // Remove loading indicator
        const loading = document.getElementById('loading3D');
        if (loading && loading.parentNode) {
            loading.parentNode.removeChild(loading);
        }
    }
}


async function render3D(volumeData) {
    const { data, shape } = volumeData;
    
    // Create Three.js scene
    const canvas = document.getElementById('renderCanvas3D');
    if (!canvas) {
        console.error('Canvas element not found');
        return;
    }
    
    // Get modal content container for sizing
    const container = canvas.parentElement || document.getElementById('visualModal3D');
    const width = container.clientWidth;
    const height = container.clientHeight;
    
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ 
        canvas, 
        alpha: true,
        antialias: true 
    });
    
    renderer.setSize(width, height);
    renderer.setClearColor(0x000000, 0);
    
    // Calculate min/max values for normalization
    let min = Infinity;
    let max = -Infinity;
    const sampleSize = Math.min(10000, data.length);
    const step = Math.floor(data.length / sampleSize);
    
    for (let i = 0; i < data.length; i += step) {
        const val = data[i];
        if (val < min) min = val;
        if (val > max) max = val;
    }
    
    console.log('Data range:', min, 'to', max);
    
    // METHOD 1: Slice-based rendering (simpler, works with all Three.js versions)
    // Create a stack of 2D textures
    const slices = [];
    const sliceCount = Math.min(50, shape[0]); // Limit to 50 slices for performance
    
    for (let z = 0; z < sliceCount; z++) {
        const sliceIndex = Math.floor(z * (shape[0] - 1) / (sliceCount - 1));
        const sliceData = new Uint8Array(shape[1] * shape[2] * 4);
        
        for (let y = 0; y < shape[1]; y++) {
            for (let x = 0; x < shape[2]; x++) {
                const dataIndex = (sliceIndex * shape[1] * shape[2]) + (y * shape[2]) + x;
                const normalizedValue = (data[dataIndex] - min) / (max - min);
                
                // Store as grayscale with alpha
                const pixelIndex = (y * shape[2] + x) * 4;
                const intensity = Math.floor(normalizedValue * 255);
                sliceData[pixelIndex] = intensity;     // R
                sliceData[pixelIndex + 1] = intensity; // G
                sliceData[pixelIndex + 2] = intensity; // B
                sliceData[pixelIndex + 3] = intensity > 50 ? 200 : 0; // Alpha
            }
        }
        
        const texture = new THREE.DataTexture(
            sliceData,
            shape[2],
            shape[1],
            THREE.RGBAFormat,
            THREE.UnsignedByteType
        );
        texture.needsUpdate = true;
        slices.push(texture);
    }
    
    // Create slice planes
    const planeGeometry = new THREE.PlaneGeometry(1, 1);
    
    for (let i = 0; i < slices.length; i++) {
        const zPos = (i / (slices.length - 1)) * 2 - 1; // Position from -1 to 1
        const material = new THREE.MeshBasicMaterial({
            map: slices[i],
            transparent: true,
            side: THREE.DoubleSide,
            depthWrite: false
        });
        
        const plane = new THREE.Mesh(planeGeometry, material);
        plane.position.z = zPos;
        plane.scale.set(1, shape[1] / shape[2], 1); // Adjust aspect ratio
        scene.add(plane);
    }
    

    // Add lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);
    
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(1, 1, 1);
    scene.add(directionalLight);
    
    // Position camera
    camera.position.set(1, 1, 1.5);
    camera.lookAt(0, 0, 0);
    
    // Add controls
    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    
    // Add simple GUI for slice visibility
    if (typeof dat !== 'undefined') {
        const gui = new dat.GUI();
        const params = {
            opacity: 0.8,
            showSlices: true,
            sliceSpacing: 0.02
        };
        
        gui.add(params, 'opacity', 0, 1).onChange(value => {
            scene.traverse(child => {
                if (child.material) {
                    child.material.opacity = value;
                }
            });
        });
        
        gui.add(params, 'showSlices').onChange(value => {
            scene.traverse(child => {
                if (child.material && child.material.map) {
                    child.visible = value;
                }
            });
        });
    }
    
    // Animation loop
    function animate() {
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    }
    animate();
    
    // Handle window resize
    function handleResize() {
        const container = canvas.parentElement || document.getElementById('visualModal3D');
        const width = container.clientWidth;
        const height = container.clientHeight;
        
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height);
    }
    
    window.addEventListener('resize', handleResize);
    
    // Store scene reference for cleanup
    window.currentScene3D = {
        scene: scene,
        renderer: renderer,
        controls: controls,
        dispose: () => {
            renderer.dispose();
            scene.traverse(child => {
                if (child.material) {
                    child.material.dispose();
                    if (child.material.map) child.material.map.dispose();
                }
                if (child.geometry) child.geometry.dispose();
            });
            window.removeEventListener('resize', handleResize);
            if (controls) controls.dispose();
        }
    };
}





async function deleteImage(imageId) {
    if (!confirm("Are you sure you want to delete this image?")) return;

    uploadInfoSection.classList.remove("hidden");

    try {
        // Call your backend route to update Firestore
        const res = await fetch(`/delete_image`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: imageId })
        });

        const data = await res.json();
        if (res.ok) {

            infoContainer.style.color = "green";
            infoContainer.style.fontWeight = "bold";
            infoContainer.innerHTML = "✅ Image Deleted Successfully!";

            await loadLibraryTable();
        } else {
            console.error(data);
            alert("Failed to delete image: " + data.error);
        }
    } catch (err) {
        console.error(err);
        alert("An error occurred while deleting the image.");
    }

        setTimeout(() => {
        infoContainer.innerHTML = "";
    }, 3000);

}

//     🧊 3D

function renderSegmentationCell(row) {

  if (!row.segmentation) {
    return `
      <button class="btn-small btn-primary"
              onclick="startSegmentation('${row.id}')">
        🫀 Run
      </button>
    `;
  }

  const status = row.segmentation.status;

  if (status === "pending" || status === "running") {
    return `<span class="badge badge-running">⏳ Running</span>`;

  }else if (status === "finished") {
    return `
      <button class="btn-small"> ✅ Done </button>
    `;
  }else if (status === "failed") {
    return `
      <button class="btn-small"
              onclick="startSegmentation('${row.id}')">
        🔁 Retry
      </button>
    `;
  }else {
        return `
      <button class="btn-small btn-primary"
              onclick="startSegmentation('${row.id}')">
        🫀 Run
      </button>
    `;
    }

}






async function startSegmentation(imageId) {
  if (!confirm("Start cardiac segmentation for this image?")) return;

  //try {

    console.log('saja')

    await fetch(`/start_segmentation/${imageId}`, { 
      method: "POST",
      headers: {
      }
    });

    alert("Segmentation job started.");
    await loadLibraryTable(); // refresh table

  //} catch (err) {
  //  console.error(err);
  //  alert("Failed to start segmentation.");
  //}
}


