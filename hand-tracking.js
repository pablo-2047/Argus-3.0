let handLandmarker = null;
let handTrackingActive = false;
let videoStream = null;
let lastHandGesture = null;
let lastFpsUpdate = 0;
let frameCount = 0;

async function toggleHandTracking() {
    if (handTrackingActive) {
        stopHandTracking();
    } else {
        await startHandTracking();
    }
}

async function startHandTracking() {
    try {
        // Show loading
        showToast('Initializing hand tracking...', 'info');
        
        // Initialize MediaPipe
        const vision = await FilesetResolver.forVisionTasks(
            "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.0/wasm"
        );
        
        handLandmarker = await HandLandmarker.createFromOptions(vision, {
            baseOptions: {
                modelAssetPath: "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
                delegate: "GPU"
            },
            runningMode: "VIDEO",
            numHands: 2
        });
        
        // Start video
        const video = document.getElementById('hand-video');
        videoStream = await navigator.mediaDevices.getUserMedia({
            video: { 
                width: 1280,   // 2x resolution
                height: 720,
                frameRate: 60  // Smoother tracking
            }
        });
        video.srcObject = videoStream;
        await video.play();
        
        // Setup canvas
        const canvas = document.getElementById('hand-canvas');
        const container = document.getElementById('three-viewport');
        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight;
        canvas.style.display = 'block';
        
        handTrackingActive = true;
        document.getElementById('hand-btn-text').textContent = '👋 Disable Hands';
        document.getElementById('hand-overlay').style.display = 'block';
        
        showToast('Hand tracking active!', 'success');
        
        // Start detection loop
        detectHands();
        
    } catch (error) {
        console.error('Hand tracking error:', error);
        showToast('Failed to start hand tracking', 'error');
    }
}

function stopHandTracking() {
    handTrackingActive = false;
    
    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        videoStream = null;
    }
    
    document.getElementById('hand-canvas').style.display = 'none';
    document.getElementById('hand-btn-text').textContent = '👋 Enable Hands';
    document.getElementById('hand-overlay').style.display = 'none';
    
    showToast('Hand tracking stopped', 'info');
}

async function detectHands() {
    if (!handTrackingActive) return;
    
    const video = document.getElementById('hand-video');
    const canvas = document.getElementById('hand-canvas');
    const ctx = canvas.getContext('2d');
    frameCount++;
    const now = performance.now();
    if (now - lastFpsUpdate > 1000) {
        document.getElementById('hand-tracking-fps').textContent = `${frameCount} FPS`;
        frameCount = 0;
        lastFpsUpdate = now;
    }
    
    // Update hand count
    const handCount = results.landmarks ? results.landmarks.length : 0;
    document.getElementById('hand-tracking-hands').textContent = `${handCount} hand${handCount !== 1 ? 's' : ''}`;
    
    // Detect hands
    const results = await handLandmarker.detectForVideo(video, performance.now());
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw landmarks
    if (results.landmarks && results.landmarks.length > 0) {
        results.landmarks.forEach((landmarks) => {
            drawHandLandmarks(ctx, landmarks, canvas.width, canvas.height);
        });
        
        // Detect gestures
        const gesture = detectGesture(results.landmarks[0]);
        if (gesture !== lastHandGesture) {
            handleGesture(gesture);
            lastHandGesture = gesture;
        }
    }
    
    // Continue loop
    requestAnimationFrame(detectHands);
}

function drawHandLandmarks(ctx, landmarks, width, height) {
    // Draw connections
    const connections = [
        [0, 1], [1, 2], [2, 3], [3, 4],  // Thumb
        [0, 5], [5, 6], [6, 7], [7, 8],  // Index
        [0, 9], [9, 10], [10, 11], [11, 12],  // Middle
        [0, 13], [13, 14], [14, 15], [15, 16],  // Ring
        [0, 17], [17, 18], [18, 19], [19, 20],  // Pinky
        [5, 9], [9, 13], [13, 17]  // Palm
    ];
    
    ctx.strokeStyle = '#D4AF37';
    ctx.lineWidth = 2;
    
    connections.forEach(([start, end]) => {
        const startPoint = landmarks[start];
        const endPoint = landmarks[end];
        
        ctx.beginPath();
        ctx.moveTo(startPoint.x * width, startPoint.y * height);
        ctx.lineTo(endPoint.x * width, endPoint.y * height);
        ctx.stroke();
    });
    
    // Draw points
    ctx.fillStyle = '#F4D03F';
    landmarks.forEach((landmark) => {
        ctx.beginPath();
        ctx.arc(landmark.x * width, landmark.y * height, 5, 0, 2 * Math.PI);
        ctx.fill();
    });
}

function detectGesture(landmarks) {
    if (!landmarks || landmarks.length < 21) return 'none';
    
    // Get all key points
    const thumb = { tip: landmarks[4], base: landmarks[2] };
    const index = { tip: landmarks[8], base: landmarks[6], mcp: landmarks[5] };
    const middle = { tip: landmarks[12], base: landmarks[10], mcp: landmarks[9] };
    const ring = { tip: landmarks[16], base: landmarks[14] };
    const pinky = { tip: landmarks[20], base: landmarks[18] };
    const wrist = landmarks[0];
    const palm = landmarks[9];
    
    // Helper: Distance between two points
    const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
    
    // Helper: Is finger extended?
    const isExtended = (tip, base) => tip.y < base.y;
    
    // === GESTURE 1: PINCH (Thumb + Index) ===
    const pinchDist = dist(thumb.tip, index.tip);
    if (pinchDist < 0.05) {
        return 'pinch';  // Rotate 3D model
    }
    
    // === GESTURE 2: SPREAD (All fingers extended) ===
    const indexExtended = isExtended(index.tip, index.base);
    const middleExtended = isExtended(middle.tip, middle.base);
    const ringExtended = isExtended(ring.tip, ring.base);
    const pinkyExtended = isExtended(pinky.tip, pinky.base);
    
    if (indexExtended && middleExtended && ringExtended && pinkyExtended) {
        const spreadDist = dist(index.tip, pinky.tip);
        if (spreadDist > 0.2) {
            return 'spread';  // Zoom out
        }
    }
    
    // === GESTURE 3: POINT (Only index extended) ===
    if (indexExtended && !middleExtended && !ringExtended && !pinkyExtended) {
        return 'point';  // Select/Click
    }
    
    // === GESTURE 4: PEACE (Index + Middle extended) ===
    if (indexExtended && middleExtended && !ringExtended && !pinkyExtended) {
        return 'peace';  // Take Screenshot
    }
    
    // === GESTURE 5: FIST (All fingers closed) ===
    if (!indexExtended && !middleExtended && !ringExtended && !pinkyExtended) {
        return 'fist';  // Stop/Cancel action
    }
    
    // === GESTURE 6: THUMBS UP ===
    const thumbExtended = thumb.tip.y < thumb.base.y;
    if (thumbExtended && !indexExtended && !middleExtended) {
        return 'thumbs_up';  // Confirm/Like/Accept
    }
    
    // === GESTURE 7: THUMBS DOWN ===
    if (!thumbExtended && thumb.tip.y > thumb.base.y + 0.1) {
        return 'thumbs_down';  // Reject/Dislike
    }
    
    // === GESTURE 8: OK SIGN (Thumb + Index circle) ===
    const okDist = dist(thumb.tip, index.tip);
    if (okDist < 0.04 && middleExtended && ringExtended) {
        return 'ok_sign';  // Everything is OK
    }
    
    // === GESTURE 9: SWIPE RIGHT (Hand moving right fast) ===
    if (!window.lastPalmX) window.lastPalmX = palm.x;
    const palmDelta = palm.x - window.lastPalmX;
    window.lastPalmX = palm.x;
    
    if (palmDelta > 0.05) {
        return 'swipe_right';  // Next panel/page
    }
    if (palmDelta < -0.05) {
        return 'swipe_left';  // Previous panel/page
    }
    
    // === GESTURE 10: WAVE (Hand moving up/down rapidly) ===
    if (!window.lastPalmY) window.lastPalmY = palm.y;
    const palmYDelta = Math.abs(palm.y - window.lastPalmY);
    window.lastPalmY = palm.y;
    
    if (palmYDelta > 0.08) {
        return 'wave';  // Get Argus attention
    }
    
    // === GESTURE 11: PUSH (Palm facing camera, moving forward) ===
    const palmZ = palm.z;
    if (!window.lastPalmZ) window.lastPalmZ = palmZ;
    const zDelta = palmZ - window.lastPalmZ;
    window.lastPalmZ = palmZ;
    
    if (zDelta < -0.05 && !indexExtended) {
        return 'push';  // Push away/Close panel
    }
    
    // === GESTURE 12: PULL (Palm facing camera, moving backward) ===
    if (zDelta > 0.05 && !indexExtended) {
        return 'pull';  // Pull closer/Open panel
    }
    
    return 'none';
}

let lastGestureTime = 0;
const gestureCooldown = 500; // ms between gestures

function handleGesture(gesture) {
    const now = Date.now();
    if (now - lastGestureTime < gestureCooldown) return;
    lastGestureTime = now;
    
    // Visual feedback
    showGestureFeedback(gesture);
    
    switch (gesture) {
        case 'pinch':
            // Rotate 3D model
            if (currentModel) {
                currentModel.rotation.y += 0.1;
            }
            break;
            
        case 'spread':
            // Zoom out
            camera.position.z *= 1.1;
            camera.position.z = Math.min(camera.position.z, 20);
            break;
            
        case 'point':
            // Raycast selection (advanced)
            performRaycastSelection();
            break;
            
        case 'peace':
            // Take screenshot
            takeScreenshot();
            showToast('Screenshot captured!', 'success');
            break;
            
        case 'fist':
            // Stop/Cancel
            if (ARGUS.isListening) {
                stopVoiceInput();
            }
            showToast('Action cancelled', 'info');
            break;
            
        case 'thumbs_up':
            // Confirm last action
            sendMessage('yes');
            showToast('Confirmed!', 'success');
            break;
            
        case 'thumbs_down':
            // Reject last action
            sendMessage('no');
            showToast('Rejected', 'warning');
            break;
            
        case 'ok_sign':
            // Everything is OK
            sendMessage('looks good');
            break;
            
        case 'swipe_right':
            // Next panel
            cyclePanels('next');
            break;
            
        case 'swipe_left':
            // Previous panel
            cyclePanels('prev');
            break;
            
        case 'wave':
            // Activate Argus (like saying wake word)
            setStatus('recording', 'LISTENING');
            showToast('Listening...', 'info');
            startVoiceInput();
            break;
            
        case 'push':
            // Close/minimize active panel
            const activePanel = document.querySelector('.panel:not(.minimized)');
            if (activePanel) {
                minimizePanel(activePanel);
            }
            break;
            
        case 'pull':
            // Open context menu / radial menu
            const centerX = window.innerWidth / 2;
            const centerY = window.innerHeight / 2;
            showRadialMenu(centerX, centerY);
            break;
    }
}

// === HELPER FUNCTIONS ===//

function showGestureFeedback(gesture) {
    // Show gesture name briefly
    const feedback = document.getElementById('gesture-feedback');
    if (!feedback) {
        const div = document.createElement('div');
        div.id = 'gesture-feedback';
        div.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(212, 175, 55, 0.9);
            color: #0a0f14;
            padding: 20px 40px;
            border-radius: 10px;
            font-family: 'Orbitron', sans-serif;
            font-size: 24px;
            font-weight: 700;
            z-index: 10000;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s;
        `;
        document.body.appendChild(div);
    }
    
    const feedbackDiv = document.getElementById('gesture-feedback');
    
    const gestureIcons = {
        'pinch': '🤏 ROTATE',
        'spread': '✋ ZOOM',
        'point': '👆 SELECT',
        'peace': '✌️ SCREENSHOT',
        'fist': '✊ CANCEL',
        'thumbs_up': '👍 CONFIRM',
        'thumbs_down': '👎 REJECT',
        'ok_sign': '👌 OK',
        'swipe_right': '👉 NEXT',
        'swipe_left': '👈 PREVIOUS',
        'wave': '👋 HELLO',
        'push': '🤚 CLOSE',
        'pull': '🖐️ OPEN'
    };
    
    feedbackDiv.textContent = gestureIcons[gesture] || gesture.toUpperCase();
    feedbackDiv.style.opacity = '1';
    
    setTimeout(() => {
        feedbackDiv.style.opacity = '0';
    }, 800);
}

function performRaycastSelection() {
    // Raycast from screen center to 3D scene
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2(0, 0); // Center of screen
    
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(scene.children, true);
    
    if (intersects.length > 0) {
        const object = intersects[0].object;
        // Highlight selected object
        if (object.material) {
            const originalColor = object.material.color.getHex();
            object.material.color.setHex(0xFFFF00); // Yellow
            
            setTimeout(() => {
                object.material.color.setHex(originalColor);
            }, 500);
        }
        
        showToast(`Selected: ${object.name || 'Object'}`, 'info');
    }
}

function takeScreenshot() {
    // Capture the 3D canvas
    const canvas = document.getElementById('three-canvas');
    const dataURL = canvas.toDataURL('image/png');
    
    // Download
    const link = document.createElement('a');
    link.download = `argus-screenshot-${Date.now()}.png`;
    link.href = dataURL;
    link.click();
}

function cyclePanels(direction) {
    const panels = Array.from(document.querySelectorAll('.panel:not(.minimized)'));
    if (panels.length === 0) return;
    
    // Find current top panel
    let topPanel = panels.reduce((max, panel) => 
        parseInt(panel.style.zIndex) > parseInt(max.style.zIndex) ? panel : max
    );
    
    const currentIndex = panels.indexOf(topPanel);
    const nextIndex = direction === 'next' 
        ? (currentIndex + 1) % panels.length
        : (currentIndex - 1 + panels.length) % panels.length;
    
    bringToFront(panels[nextIndex]);
}

// ===================================================================
// FILE DROP HANDLER
// ===================================================================

document.addEventListener('DOMContentLoaded', () => {
    const workspace = document.getElementById('workspace-content');
    
    workspace.addEventListener('dragover', (e) => {
        e.preventDefault();
        workspace.style.border = '2px dashed var(--gold-primary)';
    });
    
    workspace.addEventListener('dragleave', () => {
        workspace.style.border = '';
    });
    
    workspace.addEventListener('drop', (e) => {
        e.preventDefault();
        workspace.style.border = '';
        
        const file = e.dataTransfer.files[0];
        if (file) {
            const ext = file.name.split('.').pop().toLowerCase();
            
            if (['gltf', 'glb', 'step', 'stp'].includes(ext)) {
                if (!viewportActive) {
                    initialize3DViewer();
                }
                
                if (ext === 'gltf' || ext === 'glb') {
                    load3DModelFromFile(file);
                } else {
                    // STEP files need backend conversion
                    showToast('STEP file conversion not yet implemented', 'warning');
                    // TODO: Send to backend for conversion to GLTF
                }
            } else {
                showToast('Unsupported file type', 'error');
            }
        }
    });
});

console.log('[ARGUS] 3D Viewer + Hand Tracking loaded successfully');