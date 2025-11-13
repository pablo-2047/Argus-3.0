let scene, camera, renderer, currentModel, controls;
let viewportActive = false;

window.initialize3DViewer = function() {
    const workspace = document.getElementById('workspace-content');
    
    workspace.innerHTML = `
        <div id="three-viewport" style="width: 100%; height: 100%; position: relative;">
            <canvas id="three-canvas"></canvas>
            <div id="three-controls" style="position: absolute; bottom: 20px; left: 20px; display: flex; gap: 10px;">
                <button class="action-btn" onclick="toggle3DGrid()">
                    <span>📐 Grid</span>
                </button>
                <button class="action-btn" onclick="toggle3DWireframe()">
                    <span>🔲 Wireframe</span>
                </button>
                <button class="action-btn" onclick="reset3DView()">
                    <span>🔄 Reset</span>
                </button>
                <button class="action-btn" onclick="toggleHandTracking()">
                    <span id="hand-btn-text">👋 Enable Hands</span>
                </button>
            </div>
            <div id="hand-overlay" style="display: none; position: absolute; top: 20px; right: 20px; background: rgba(0,0,0,0.8); padding: 15px; border-radius: 8px; border: 1px solid var(--gold-primary);">
                <div style="color: var(--gold-primary); font-family: 'Orbitron', sans-serif; font-size: 11px; letter-spacing: 2px; margin-bottom: 10px;">HAND TRACKING</div>
                <div style="font-size: 12px; color: var(--text-secondary);">
                    <div>🤏 Pinch: Rotate</div>
                    <div>✋ Spread: Zoom</div>
                    <div>👆 Point: Pan</div>
                </div>
            </div>
            <video id="hand-video" style="display: none;"></video>
            <canvas id="hand-canvas" style="position: absolute; top: 0; left: 0; pointer-events: none; display: none;"></canvas>
        </div>
    `;
    
    setup3DScene();
    viewportActive = true;
    
    // Load a demo model (cube)
    createDemoModel();
};

function setup3DScene() {
    const canvas = document.getElementById('three-canvas');
    const container = document.getElementById('three-viewport');
    
    // Scene
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0f14);
    
    // Camera
    camera = new THREE.PerspectiveCamera(
        75,
        container.clientWidth / container.clientHeight,
        0.1,
        1000
    );
    camera.position.set(5, 5, 5);
    camera.lookAt(0, 0, 0);
    
    // Renderer
    renderer = new THREE.WebGLRenderer({ 
        canvas: canvas,
        antialias: true,
        alpha: true
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    // Enable shadows (looks AMAZING)
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;  // Soft shadows

    // Enable tone mapping (better colors)
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;

    // Enable anti-aliasing at max
    renderer.setPixelRatio(Math.min(window.devicePixelRatio * 1.5, 2));
    
    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);
    
    const directionalLight = new THREE.DirectionalLight(0xD4AF37, 1.2);
    directionalLight.position.set(5, 10, 5);
    directionalLight.castShadow = true;  // Enable shadows

    // Shadow quality settings
    directionalLight.shadow.mapSize.width = 2048;   // High quality
    directionalLight.shadow.mapSize.height = 2048;
    directionalLight.shadow.camera.near = 0.5;
    directionalLight.shadow.camera.far = 50;

    scene.add(directionalLight);

    // Add a second light for dramatic effect
    const rimLight = new THREE.DirectionalLight(0x5dade2, 0.5);
    rimLight.position.set(-5, 3, -5);
    scene.add(rimLight);
    
    // Grid
    const gridHelper = new THREE.GridHelper(10, 10, 0xD4AF37, 0x444444);
    scene.add(gridHelper);
    window.gridHelper = gridHelper;
    
    // Axes
    const axesHelper = new THREE.AxesHelper(5);
    scene.add(axesHelper);
    
    // Mouse controls (fallback)
    setupMouseControls();
    
    // Animation loop
    animate3D();
    
    // Handle resize
    window.addEventListener('resize', () => {
        if (viewportActive) {
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        }
    });
}

function setupMouseControls() {
    const canvas = document.getElementById('three-canvas');
    let isDragging = false;
    let previousMousePosition = { x: 0, y: 0 };
    
    canvas.addEventListener('mousedown', (e) => {
        isDragging = true;
        previousMousePosition = { x: e.clientX, y: e.clientY };
    });
    
    canvas.addEventListener('mousemove', (e) => {
        if (!isDragging || !currentModel) return;
        
        const deltaX = e.clientX - previousMousePosition.x;
        const deltaY = e.clientY - previousMousePosition.y;
        
        currentModel.rotation.y += deltaX * 0.01;
        currentModel.rotation.x += deltaY * 0.01;
        
        previousMousePosition = { x: e.clientX, y: e.clientY };
    });
    
    canvas.addEventListener('mouseup', () => {
        isDragging = false;
    });
    
    // Zoom with scroll
    canvas.addEventListener('wheel', (e) => {
        e.preventDefault();
        camera.position.z += e.deltaY * 0.01;
        camera.position.z = Math.max(2, Math.min(20, camera.position.z));
    });
}

function animate3D() {
    if (!viewportActive) return;
    requestAnimationFrame(animate3D);
    renderer.render(scene, camera);
}

function createDemoModel() {
    // Create a demo cube
    const geometry = new THREE.BoxGeometry(2, 2, 2);
    const material = new THREE.MeshStandardMaterial({
        color: 0xD4AF37,
        metalness: 0.7,
        roughness: 0.3
    });
    const cube = new THREE.Mesh(geometry, material);
    cube.castShadow = true;
    cube.receiveShadow = true;

    // Add a ground plane to receive shadows
    const planeGeometry = new THREE.PlaneGeometry(20, 20);
    const planeMaterial = new THREE.MeshStandardMaterial({ 
        color: 0x1a1a1a,
        metalness: 0.1,
        roughness: 0.8
    });
    const plane = new THREE.Mesh(planeGeometry, planeMaterial);
    plane.rotation.x = -Math.PI / 2;
    plane.position.y = -2;
    plane.receiveShadow = true;
    scene.add(plane);
    
    // Add edges
    const edges = new THREE.EdgesGeometry(geometry);
    const line = new THREE.LineSegments(
        edges,
        new THREE.LineBasicMaterial({ color: 0xffffff, linewidth: 2 })
    );
    cube.add(line);
    
    scene.add(cube);
    currentModel = cube;
    
    addChatMessage('system', 'Demo 3D model loaded. Use mouse or enable hand tracking.');
}

window.load3DModelFromFile = function(file) {
    // Load GLTF/STEP file
    const loader = new THREE.GLTFLoader();
    
    const reader = new FileReader();
    reader.onload = function(e) {
        loader.parse(e.target.result, '', (gltf) => {
            // Remove old model
            if (currentModel) {
                scene.remove(currentModel);
            }
            
            currentModel = gltf.scene;
            scene.add(currentModel);
            
            // Center and scale model
            const box = new THREE.Box3().setFromObject(currentModel);
            const center = box.getCenter(new THREE.Vector3());
            currentModel.position.sub(center);
            
            const size = box.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);
            const scale = 4 / maxDim;
            currentModel.scale.multiplyScalar(scale);
            
            addChatMessage('system', '3D model loaded successfully');
        }, (error) => {
            console.error('Error loading model:', error);
            showToast('Failed to load 3D model', 'error');
        });
    };
    reader.readAsArrayBuffer(file);
};

function toggle3DGrid() {
    if (window.gridHelper) {
        window.gridHelper.visible = !window.gridHelper.visible;
    }
}

function toggle3DWireframe() {
    if (currentModel) {
        currentModel.traverse((child) => {
            if (child.isMesh) {
                child.material.wireframe = !child.material.wireframe;
            }
        });
    }
}

function reset3DView() {
    camera.position.set(5, 5, 5);
    camera.lookAt(0, 0, 0);
    if (currentModel) {
        currentModel.rotation.set(0, 0, 0);
    }
}