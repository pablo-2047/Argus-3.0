// ===================================================================
// ARGUS J.A.R.V.I.S. UI - Main Renderer
// Complete panel system, drag/drop, chat management
// ===================================================================

// === GLOBAL STATE ===
const ARGUS = {
    panels: new Map(),
    dragState: null,
    resizeState: null,
    chatHistory: [],
    isListening: false,
    currentTheme: null,
    ws: null
};

// === INITIALIZATION ===
document.addEventListener('DOMContentLoaded', () => {
    console.log('[ARGUS] Initializing UI...');
    
    initializeParticles();
    initializePanels();
    initializeChat();
    initializeStatusBar();
    initializeRadialMenu();
    initializeKeyboardShortcuts();
    
    console.log('[ARGUS] UI Ready');
});

// === PARTICLE SYSTEM ===
function initializeParticles() {
    const canvas = document.getElementById('particle-canvas');
    const ctx = canvas.getContext('2d');
    
    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    
    resize();
    window.addEventListener('resize', resize);
    
    const particles = [];
    const particleCount = 300;
    
    class Particle {
        constructor() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            this.size = Math.random() * 2 + 0.5;
            this.speedX = Math.random() * 0.5 - 0.25;
            this.speedY = Math.random() * 0.5 - 0.25;
            this.opacity = Math.random() * 0.5 + 0.2;
        }
        
        update() {
            this.x += this.speedX;
            this.y += this.speedY;
            
            if (this.x > canvas.width) this.x = 0;
            if (this.x < 0) this.x = canvas.width;
            if (this.y > canvas.height) this.y = 0;
            if (this.y < 0) this.y = canvas.height;
        }
        
        draw() {
            ctx.fillStyle = `rgba(212, 175, 55, ${this.opacity})`;
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fill();
        }
    }
    
    for (let i = 0; i < particleCount; i++) {
        particles.push(new Particle());
    }
    
    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        particles.forEach(particle => {
            particle.update();
            particle.draw();
        });
        
        // Connect nearby particles
        // Connect nearby particles (ENHANCED)
        particles.forEach((a, i) => {
            particles.slice(i + 1).forEach(b => {
                const dx = a.x - b.x;
                const dy = a.y - b.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance < 150) {  // Increased range
                    const opacity = 0.3 - distance / 500;
                    
                    // Gradient line (looks cooler)
                    const gradient = ctx.createLinearGradient(a.x, a.y, b.x, b.y);
                    gradient.addColorStop(0, `rgba(212, 175, 55, ${opacity})`);
                    gradient.addColorStop(0.5, `rgba(244, 208, 63, ${opacity * 1.5})`);
                    gradient.addColorStop(1, `rgba(212, 175, 55, ${opacity})`);
                    
                    ctx.strokeStyle = gradient;
                    ctx.lineWidth = 1.5;  // Thicker lines
                    ctx.beginPath();
                    ctx.moveTo(a.x, a.y);
                    ctx.lineTo(b.x, b.y);
                    ctx.stroke();
                }
            });
        });
        particles.forEach(particle => {
            ctx.shadowBlur = 15;
            ctx.shadowColor = `rgba(212, 175, 55, ${particle.opacity})`;
            particle.draw();
            ctx.shadowBlur = 0;
        });
        
        requestAnimationFrame(animate);
    }
    
    animate();
}

// === PANEL MANAGEMENT ===
function initializePanels() {
    const panels = document.querySelectorAll('.panel.draggable');
    
    panels.forEach(panel => {
        const id = panel.id;
        
        // Parse default position
        const defaultPos = panel.dataset.defaultPos;
        const defaultSize = panel.dataset.defaultSize;
        
        setDefaultPosition(panel, defaultPos, defaultSize);
        
        // Register panel
        ARGUS.panels.set(id, {
            element: panel,
            isMinimized: false,
            isMaximized: false,
            savedState: null
        });
        
        // Attach drag handlers
        const header = panel.querySelector('.panel-header');
        header.addEventListener('mousedown', (e) => startDrag(e, panel));
        
        // Attach resize handlers
        if (panel.classList.contains('resizable')) {
            const resizeHandle = panel.querySelector('.resize-handle');
            if (resizeHandle) {
                resizeHandle.addEventListener('mousedown', (e) => startResize(e, panel));
            }
        }
        
        // Attach control buttons
        const controls = panel.querySelectorAll('.panel-btn');
        controls.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                handlePanelAction(panel, btn.dataset.action);
            });
        });
        
        // Bring to front on click
        panel.addEventListener('mousedown', () => bringToFront(panel));
    });
}

function setDefaultPosition(panel, posStr, sizeStr) {
    const [width, height] = sizeStr.split(',').map(Number);
    panel.style.width = `${width}px`;
    panel.style.height = `${height}px`;
    
    if (posStr.includes('center')) {
        const x = (window.innerWidth - width) / 2;
        const y = posStr.includes('bottom') 
            ? window.innerHeight - height - 80 
            : (window.innerHeight - height) / 2;
        panel.style.left = `${x}px`;
        panel.style.top = `${y}px`;
    } else if (posStr.includes('right')) {
        const offset = parseInt(posStr.split('-')[1]);
        panel.style.right = `${offset}px`;
        const top = parseInt(posStr.split(',')[1]);
        panel.style.top = `${top}px`;
    } else if (posStr.includes('bottom')) {
        const [x, bottom] = posStr.split(',');
        panel.style.left = `${x}px`;
        panel.style.bottom = `${bottom.split('-')[1]}px`;
    } else {
        const [x, y] = posStr.split(',').map(Number);
        panel.style.left = `${x}px`;
        panel.style.top = `${y}px`;
    }
}

// === DRAG & DROP ===
function startDrag(e, panel) {
    if (e.target.closest('.panel-controls')) return;
    if (ARGUS.panels.get(panel.id).isMaximized) return;
    
    ARGUS.dragState = {
        panel,
        startX: e.clientX,
        startY: e.clientY,
        panelX: panel.offsetLeft,
        panelY: panel.offsetTop
    };
    
    panel.style.cursor = 'grabbing';
    document.addEventListener('mousemove', onDragMove);
    document.addEventListener('mouseup', onDragEnd);
}

function onDragMove(e) {
    if (!ARGUS.dragState) return;
    
    const dx = e.clientX - ARGUS.dragState.startX;
    const dy = e.clientY - ARGUS.dragState.startY;
    
    let newX = ARGUS.dragState.panelX + dx;
    let newY = ARGUS.dragState.panelY + dy;
    
    // Magnetic snapping to edges (20px threshold)
    const snapThreshold = 20;
    if (newX < snapThreshold) newX = 10;
    if (newY < snapThreshold + 60) newY = 70; // Account for status bar
    if (newX + ARGUS.dragState.panel.offsetWidth > window.innerWidth - snapThreshold) {
        newX = window.innerWidth - ARGUS.dragState.panel.offsetWidth - 10;
    }
    if (newY + ARGUS.dragState.panel.offsetHeight > window.innerHeight - snapThreshold) {
        newY = window.innerHeight - ARGUS.dragState.panel.offsetHeight - 10;
    }
    
    ARGUS.dragState.panel.style.left = `${newX}px`;
    ARGUS.dragState.panel.style.top = `${newY}px`;
    ARGUS.dragState.panel.style.right = 'auto';
    ARGUS.dragState.panel.style.bottom = 'auto';
}

function onDragEnd() {
    if (ARGUS.dragState) {
        ARGUS.dragState.panel.style.cursor = '';
        ARGUS.dragState = null;
    }
    document.removeEventListener('mousemove', onDragMove);
    document.removeEventListener('mouseup', onDragEnd);
}

// === RESIZE ===
function startResize(e, panel) {
    e.stopPropagation();
    
    ARGUS.resizeState = {
        panel,
        startX: e.clientX,
        startY: e.clientY,
        startWidth: panel.offsetWidth,
        startHeight: panel.offsetHeight
    };
    
    document.addEventListener('mousemove', onResizeMove);
    document.addEventListener('mouseup', onResizeEnd);
}

function onResizeMove(e) {
    if (!ARGUS.resizeState) return;
    
    const dx = e.clientX - ARGUS.resizeState.startX;
    const dy = e.clientY - ARGUS.resizeState.startY;
    
    const newWidth = Math.max(250, ARGUS.resizeState.startWidth + dx);
    const newHeight = Math.max(200, ARGUS.resizeState.startHeight + dy);
    
    ARGUS.resizeState.panel.style.width = `${newWidth}px`;
    ARGUS.resizeState.panel.style.height = `${newHeight}px`;
}

function onResizeEnd() {
    ARGUS.resizeState = null;
    document.removeEventListener('mousemove', onResizeMove);
    document.removeEventListener('mouseup', onResizeEnd);
}

// === PANEL ACTIONS ===
function handlePanelAction(panel, action) {
    const panelState = ARGUS.panels.get(panel.id);
    
    switch (action) {
        case 'minimize':
            minimizePanel(panel);
            break;
        case 'maximize':
            toggleMaximize(panel);
            break;
        case 'close':
            closePanel(panel);
            break;
        case 'export':
            exportChat();
            break;
        case 'clear':
            clearChat();
            break;
        case 'test':
            testForgedCode();
            break;
        case 'deploy':
            deployForgedCode();
            break;
    }
}

function minimizePanel(panel) {
    const panelState = ARGUS.panels.get(panel.id);
    panelState.isMinimized = true;
    panel.classList.add('minimized');
    
    // Add to taskbar
    addToTaskbar(panel);
}

function toggleMaximize(panel) {
    const panelState = ARGUS.panels.get(panel.id);
    
    if (panelState.isMaximized) {
        // Restore
        panel.classList.remove('maximized');
        if (panelState.savedState) {
            panel.style.cssText = panelState.savedState;
        }
        panelState.isMaximized = false;
    } else {
        // Maximize
        panelState.savedState = panel.style.cssText;
        panel.classList.add('maximized');
        panelState.isMaximized = true;
    }
}

function closePanel(panel) {
    panel.style.animation = 'slideOut 0.3s ease-out forwards';
    setTimeout(() => {
        panel.style.display = 'none';
        panel.style.animation = '';
    }, 300);
}

function bringToFront(panel) {
    const panels = document.querySelectorAll('.panel');
    panels.forEach((p, i) => {
        p.style.zIndex = 10 + i;
    });
    panel.style.zIndex = 10 + panels.length;
}

// === TASKBAR ===
function addToTaskbar(panel) {
    const taskbar = document.getElementById('taskbar');
    taskbar.style.display = 'flex';
    
    const item = document.createElement('div');
    item.className = 'taskbar-item';
    item.innerHTML = panel.querySelector('.panel-icon').innerHTML;
    item.dataset.panelId = panel.id;
    
    item.addEventListener('click', () => {
        restorePanel(panel);
        taskbar.removeChild(item);
        if (taskbar.children.length === 0) {
            taskbar.style.display = 'none';
        }
    });
    
    taskbar.appendChild(item);
}

function restorePanel(panel) {
    const panelState = ARGUS.panels.get(panel.id);
    panelState.isMinimized = false;
    panel.classList.remove('minimized');
    bringToFront(panel);
}

// === VOICE INPUT (FIX 1) ===
let mediaRecorder = null;
let audioChunks = [];

async function startVoiceInput() {
    try {
        // Request microphone access
        const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                sampleRate: 16000  // Match whisper.cpp
            } 
        });
        
        // Create recorder
        mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus'
        });
        
        audioChunks = [];
        
        // Collect audio data
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };
        
        // When recording stops, send to backend
        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            audioChunks = [];
            
            // Convert to base64 for WebSocket transmission
            const reader = new FileReader();
            reader.onloadend = () => {
                const base64Audio = reader.result.split(',')[1];
                
                if (window.argusBackend && window.argusBackend.readyState === WebSocket.OPEN) {
                    window.argusBackend.send(JSON.stringify({
                        type: 'voice_input',
                        data: { 
                            audio: base64Audio,
                            format: 'webm'
                        }
                    }));
                    
                    setStatus('thinking', 'PROCESSING');
                } else {
                    showToast('Backend not connected', 'error');
                    setStatus('normal', 'STANDBY');
                }
            };
            reader.readAsDataURL(audioBlob);
            
            // Stop all tracks
            stream.getTracks().forEach(track => track.stop());
        };
        
        // Start recording
        mediaRecorder.start();
        
        // Update UI
        ARGUS.isListening = true;
        document.getElementById('voice-btn').classList.add('recording');
        document.getElementById('voice-waveform').style.display = 'flex';
        setStatus('recording', 'LISTENING');
        
        console.log('[Voice] Recording started');
        
    } catch (error) {
        console.error('[Voice] Microphone access denied:', error);
        showToast('Microphone access denied. Check browser permissions.', 'error');
        setStatus('normal', 'STANDBY');
    }
}

function stopVoiceInput() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        console.log('[Voice] Recording stopped');
    }
    
    // Update UI
    ARGUS.isListening = false;
    document.getElementById('voice-btn').classList.remove('recording');
    document.getElementById('voice-waveform').style.display = 'none';
}

// === CHAT SYSTEM ===
function initializeChat() {
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const voiceBtn = document.getElementById('voice-btn');
    const chatHistory = document.getElementById('chat-history');
    
    // Send on Enter
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && input.value.trim()) {
            sendMessage(input.value.trim());
            input.value = '';
        }
    });
    
    // Send button
    sendBtn.addEventListener('click', () => {
        if (input.value.trim()) {
            sendMessage(input.value.trim());
            input.value = '';
        }
    });
    
    // Voice button (hold to speak)
    voiceBtn.addEventListener('mousedown', startVoiceInput);
    voiceBtn.addEventListener('mouseup', stopVoiceInput);
    voiceBtn.addEventListener('mouseleave', stopVoiceInput);
    
    // Auto-scroll detection (FIX 3)
    chatHistory.addEventListener('scroll', () => {
        const threshold = 5; // pixels
        const isAtBottom = Math.abs(
            chatHistory.scrollHeight - chatHistory.scrollTop - chatHistory.clientHeight
        ) < threshold;
        
        const scrollBtn = document.getElementById('scroll-to-bottom');
        scrollBtn.style.display = isAtBottom ? 'none' : 'block';
    });
    
    // Scroll to bottom button
    document.getElementById('scroll-to-bottom').addEventListener('click', () => {
        chatHistory.scrollTop = chatHistory.scrollHeight;
    });
}

// (FIX 2)
function sendMessage(text) {
    addChatMessage('user', text);
    
    const message = JSON.stringify({
        type: 'text_command',
        data: { text }
    });
    
    if (window.argusBackend && window.argusBackend.readyState === WebSocket.OPEN) {
        window.argusBackend.send(message);
    } else {
        // Queue the message
        if (window.messageQueue) {
             window.messageQueue.push(message);
        }
        showToast('Connecting to backend...', 'info');
    }
    
    showTypingIndicator();
}

function addChatMessage(type, text, timestamp = null) {
    const chatHistory = document.getElementById('chat-history');
    const message = document.createElement('div');
    message.className = `chat-message ${type}-message`;
    
    const icon = {
        user: '👤',
        argus: '🤖',
        system: '⚙️',
        tool: '🔧'
    }[type] || '💬';
    
    const time = timestamp || new Date().toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    
    message.innerHTML = `
        <div class="message-icon">${icon}</div>
        <div class="message-content">
            <div class="message-text">${formatMessageText(text)}</div>
            <div class="message-time">${time}</div>
        </div>
    `;
    
    chatHistory.appendChild(message);
    
    // Auto-scroll if at bottom
    if (chatHistory.scrollHeight - chatHistory.scrollTop < chatHistory.clientHeight + 100) {
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
    
    // Save to history
    ARGUS.chatHistory.push({ type, text, time });
}

function formatMessageText(text) {
    // Format code blocks
    text = text.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
        return `<pre><code class="language-${lang || 'text'}">${escapeHtml(code)}</code></pre>`;
    });
    
    // Format inline code
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Format links
    text = text.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank">$1</a>');
    
    return text;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    indicator.style.display = 'flex';
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    indicator.style.display = 'none';
}

function exportChat() {
    const dataStr = JSON.stringify(ARGUS.chatHistory, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `argus-chat-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    
    showToast('Chat exported successfully', 'success');
}

function clearChat() {
    if (confirm('Clear all chat history?')) {
        const chatHistory = document.getElementById('chat-history');
        chatHistory.innerHTML = `
            <div class="chat-message system-message">
                <div class="message-icon">⚙️</div>
                <div class="message-content">
                    <div class="message-text">Chat cleared</div>
                    <div class="message-time">${new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}</div>
                </div>
            </div>
        `;
        ARGUS.chatHistory = [];
    }
}

// === STATUS BAR ===
function initializeStatusBar() {
    // Update time every second
    setInterval(() => {
        const now = new Date();
        document.getElementById('time-display').textContent = 
            now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    }, 1000);
}

function setStatus(state, text) {
    const dot = document.getElementById('rec-dot');
    const statusText = document.getElementById('status-text');
    
    dot.className = `rec-dot ${state}`;
    statusText.textContent = text;
}

function updateVitals(data) {
    // Mini vitals in status bar
    if (data.cpu_usage !== undefined) {
        document.getElementById('cpu-mini').querySelector('.vital-value').textContent = 
            `${Math.round(data.cpu_usage)}%`;
    }
    if (data.ram_usage !== undefined) {
        document.getElementById('ram-mini').querySelector('.vital-value').textContent = 
            `${Math.round(data.ram_usage)}%`;
    }
    if (data.cpu_temp !== undefined) {
        document.getElementById('temp-mini').querySelector('.vital-value').textContent = 
            `${Math.round(data.cpu_temp)}°`;
    }
    if (data.battery_percent !== undefined) {
        document.getElementById('battery-mini').querySelector('.vital-value').textContent = 
            `${Math.round(data.battery_percent)}%`;
    }
    
    // Full vitals panel
    updateCircularGauge('cpu-circle', 'cpu-text', data.cpu_usage);
    updateCircularGauge('ram-circle', 'ram-text', data.ram_usage);
    updateCircularGauge('gpu-circle', 'gpu-text', data.gpu_usage || 0);
    
    if (data.cpu_temp !== undefined) {
        document.getElementById('temp-data').textContent = `${Math.round(data.cpu_temp)}°C`;
    }
}

function updateCircularGauge(circleId, textId, value) {
    const circle = document.getElementById(circleId);
    const text = document.getElementById(textId);
    
    if (!circle || !text) return;
    
    const circumference = 283;
    const offset = circumference - (value / 100) * circumference;
    circle.style.strokeDashoffset = offset;
    text.textContent = `${Math.round(value)}%`;
    
    // Color coding
    if (value > 80) {
        circle.style.stroke = '#e74c3c';
    } else if (value > 60) {
        circle.style.stroke = '#f39c12';
    } else {
        circle.style.stroke = '#D4AF37';
    }
}

// Continued in Part 2...
// renderer.js - Part 2/2
// Continued from Part 1...

// === RADIAL MENU ===
function initializeRadialMenu() {
    const radialMenu = document.getElementById('radial-menu');
    let menuTimeout;
    
    // Show on right-click
    document.addEventListener('contextmenu', (e) => {
        // Don't show on panels
        if (e.target.closest('.panel')) return;
        
        e.preventDefault();
        showRadialMenu(e.clientX, e.clientY);
    });
    
    // Hide on click outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#radial-menu')) {
            hideRadialMenu();
        }
    });
    
    // Handle menu actions
    const options = radialMenu.querySelectorAll('.radial-option');
    options.forEach(option => {
        option.addEventListener('click', () => {
            const action = option.dataset.action;
            handleRadialAction(action);
            hideRadialMenu();
        });
    });
}

function showRadialMenu(x, y) {
    const menu = document.getElementById('radial-menu');
    menu.style.left = `${x - 150}px`;
    menu.style.top = `${y - 150}px`;
    menu.style.display = 'block';
    menu.classList.add('active');
    
    // Animate options
    const options = menu.querySelectorAll('.radial-option');
    options.forEach((option, i) => {
        option.style.animation = `fadeIn 0.3s ease-out ${i * 0.05}s backwards`;
    });
}

function hideRadialMenu() {
    const menu = document.getElementById('radial-menu');
    menu.classList.remove('active');
    setTimeout(() => {
        menu.style.display = 'none';
    }, 200);
}

function handleRadialAction(action) {
    switch (action) {
        case 'search':
            const query = prompt('Enter search query:');
            if (query) sendMessage(`search ${query}`);
            break;
        case 'diagnostics':
            sendMessage('run diagnostics');
            break;
        case 'forge':
            showPanel('forge-panel');
            break;
        case '3d':
            showPanel('workspace-panel');
            // Initialize 3D viewer
            if (window.initialize3DViewer) {
                window.initialize3DViewer();
            }
            break;
        case 'webview':
            const url = prompt('Enter URL or app name (e.g., whatsapp, gmail):');
            if (url) sendMessage(`open ${url}`);
            break;
        case 'dossier':
            const target = prompt('Enter target (email, username, or domain):');
            if (target) sendMessage(`build dossier ${target}`);
            break;
    }
}

function showPanel(panelId) {
    const panel = document.getElementById(panelId);
    if (panel) {
        panel.style.display = 'flex';
        bringToFront(panel);
    }
}

// === KEYBOARD SHORTCUTS ===
function initializeKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + K: Focus chat
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            document.getElementById('chat-input').focus();
        }
        
        // Ctrl/Cmd + D: Toggle diagnostics panel
        if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
            e.preventDefault();
            const panel = document.getElementById('vitals-panel');
            if (panel.style.display === 'none') {
                showPanel('vitals-panel');
            } else {
                closePanel(panel);
            }
        }
        
        // Ctrl/Cmd + E: Export chat
        if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
            e.preventDefault();
            exportChat();
        }
        
        // Escape: Close radial menu
        if (e.key === 'Escape') {
            hideRadialMenu();
        }
    });
}

// === BACKEND MESSAGE HANDLER ===
window.handleBackendMessage = function(data) {
    console.log('[Backend]', data);
    
    switch (data.type) {
        case 'speech':
            // Argus is speaking
            addChatMessage('argus', data.data.text);
            hideTypingIndicator();
            setStatus('speaking', 'SPEAKING');
            break;
            
        case 'user_speech':
            // User's voice was transcribed
            addChatMessage('user', data.data.text);
            break;
            
        case 'status':
            // Status update
            handleStatusUpdate(data.data);
            break;
            
        case 'context_update':
            // Activity context changed
            updateContextPanel(data.data);
            break;
            
        case 'theme_update':
            // Theme should change
            applyTheme(data.data);
            break;
            
        case 'hardware_status':
            // System vitals
            updateVitals(data.data);
            break;
            
        case 'system_diagnostics':
            // Full diagnostics report
            showDiagnosticsReport(data.data);
            break;
            
        case 'proactive_suggestion':
            // Proactive assistant suggestion
            addSuggestion(data.data);
            break;
            
        case 'forge_success':
            // Tool was forged
            showToast(`Tool '${data.data.name}' forged successfully!`, 'success');
            break;
            
        case 'dossier_complete':
            // Dossier compilation done
            showDossierReport(data.data);
            break;
            
        case 'webview_spawn':
            // Open webview
            createWebview(data.data);
            break;
            
        case 'overlay_spawn':
            // Show overlay (not implemented in this version)
            break;
            
        case 'history':
            // Chat history loaded
            loadChatHistory(data.data);
            break;
    }
};

function handleStatusUpdate(data) {
    const stateMap = {
        'passively_listening': { state: 'normal', text: 'STANDBY' },
        'actively_listening': { state: 'recording', text: 'LISTENING' },
        'thinking': { state: 'thinking', text: 'THINKING' },
        'searching': { state: 'thinking', text: 'SEARCHING' },
        'forging': { state: 'thinking', text: 'FORGING TOOL' },
        'reading_file': { state: 'thinking', text: 'READING FILE' },
        'reading_screen': { state: 'thinking', text: 'READING SCREEN' },
        'compiling_dossier': { state: 'thinking', text: 'COMPILING DOSSIER' },
        'sandboxing': { state: 'thinking', text: 'TESTING CODE' }
    };
    
    const status = stateMap[data.state] || { state: 'normal', text: 'READY' };
    setStatus(status.state, status.text);
}

function updateContextPanel(data) {
    document.getElementById('current-activity').textContent = data.activity.toUpperCase();
    document.getElementById('current-app').textContent = data.context.app_name || '—';
    document.getElementById('current-file').textContent = data.context.current_file || '—';
    
    const minutes = Math.floor(data.focus_duration_seconds / 60);
    document.getElementById('focus-time').textContent = `${minutes} min`;
}

function applyTheme(theme) {
    ARGUS.currentTheme = theme;
    
    // Animate theme transition
    document.documentElement.style.setProperty('--gold-primary', theme.primary);
    document.documentElement.style.setProperty('--glass-border', `${theme.primary}40`);
    
    // Adjust particle count if needed
    // (Would require modifying the particle system)
    
    // Dim UI if needed
    if (theme.should_dim) {
        document.querySelectorAll('.panel').forEach(panel => {
            if (panel.id !== 'chat-console') {
                panel.style.opacity = '0.3';
            }
        });
    } else {
        document.querySelectorAll('.panel').forEach(panel => {
            panel.style.opacity = '1';
        });
    }
    // In the applyTheme() function, add this at the end:

if (theme.mode === 'gaming') {
    // Reduce effects during gaming
    console.log('[ARGUS] Gaming mode - reducing UI load');
    
    // Reduce particles
    while (particles.length > 50) {
        particles.pop();
    }
    
    // Pause 3D rendering if not in use
    if (!viewportActive) {
        viewportActive = false;
    }
    
    // Dim all panels except chat
    document.querySelectorAll('.panel').forEach(panel => {
        if (panel.id !== 'chat-console') {
            panel.style.opacity = '0.1';
            panel.style.pointerEvents = 'none';
        }
    });
    } else {
        // Restore full effects
        while (particles.length < 250) {
            particles.push(new Particle());
        }
        
        document.querySelectorAll('.panel').forEach(panel => {
            panel.style.opacity = '1';
            panel.style.pointerEvents = 'auto';
        });
    }
    }

function addSuggestion(data) {
    const container = document.getElementById('suggestions-container');
    const suggestion = document.createElement('div');
    suggestion.className = 'suggestion-item';
    suggestion.innerHTML = `
        <div>${data.text}</div>
        ${data.action ? `<button onclick="handleSuggestionAction('${data.action}')" style="margin-top: 8px; padding: 5px 10px; background: rgba(212, 175, 55, 0.2); border: 1px solid var(--gold-primary); border-radius: 4px; color: var(--gold-primary); cursor: pointer;">Execute</button>` : ''}
    `;
    container.appendChild(suggestion);
    
    // Keep only last 3 suggestions
    while (container.children.length > 3) {
        container.removeChild(container.firstChild);
    }
}

window.handleSuggestionAction = function(action) {
    // Handle suggestion actions
    sendMessage(action);
};

function addMemory(text) {
    const feed = document.getElementById('memory-feed');
    const memory = document.createElement('div');
    memory.className = 'memory-item';
    memory.textContent = text;
    feed.insertBefore(memory, feed.firstChild);
    
    // Keep only last 5 memories
    while (feed.children.length > 5) {
        feed.removeChild(feed.lastChild);
    }
}

function showDiagnosticsReport(data) {
    const message = `
        <strong>System Diagnostics</strong><br>
        Health: ${data.overall_health.toUpperCase()}<br>
        ${data.issues.length > 0 ? '<br><strong>Issues:</strong><br>' + data.issues.map(i => `• ${i}`).join('<br>') : ''}
        ${data.recommendations.length > 0 ? '<br><br><strong>Recommendations:</strong><br>' + data.recommendations.map(r => `• ${r}`).join('<br>') : ''}
    `;
    addChatMessage('system', message);
}

function showDossierReport(data) {
    showPanel('workspace-panel');
    const workspace = document.getElementById('workspace-content');
    
    workspace.innerHTML = `
        <div style="padding: 20px; width: 100%; height: 100%; overflow-y: auto;">
            <h2 style="color: var(--gold-primary); font-family: 'Orbitron', sans-serif; margin-bottom: 20px;">
                DOSSIER: ${data.query}
            </h2>
            <div id="dossier-results"></div>
        </div>
    `;
    
    const resultsContainer = document.getElementById('dossier-results');
    
    for (const [toolName, toolData] of Object.entries(data.intel)) {
        const section = document.createElement('div');
        section.style.cssText = 'background: rgba(0,0,0,0.3); border-left: 3px solid var(--gold-primary); padding: 15px; margin-bottom: 15px; border-radius: 6px;';
        section.innerHTML = `
            <h3 style="color: var(--gold-primary); margin-bottom: 10px;">${toolName}</h3>
            <pre style="white-space: pre-wrap; font-size: 12px;">${JSON.stringify(toolData, null, 2)}</pre>
        `;
        resultsContainer.appendChild(section);
    }
    
    addChatMessage('system', `Dossier for "${data.query}" compiled with ${Object.keys(data.intel).length} intelligence packets.`);
}

function createWebview(data) {
    showPanel('workspace-panel');
    document.getElementById('workspace-title').innerHTML = `<span class="panel-icon">🌐</span>${data.title}`;
    
    const workspace = document.getElementById('workspace-content');
    workspace.innerHTML = `
        <webview 
            src="${data.url}" 
            style="width: 100%; height: 100%;"
            partition="persist:webview"
        ></webview>
    `;
    
    addChatMessage('system', `Opened ${data.title}`);
}

function loadChatHistory(data) {
    const chatHistory = document.getElementById('chat-history');
    
    // Clear existing (except init message)
    chatHistory.innerHTML = '';
    
    // Interleave user and argus messages by timestamp
    const allMessages = [];
    
    data.user.forEach(text => {
        allMessages.push({ type: 'user', text, time: null });
    });
    
    data.argus.forEach(text => {
        allMessages.push({ type: 'argus', text, time: null });
    });
    
    // Add all messages
    allMessages.forEach(msg => {
        addChatMessage(msg.type, msg.text, msg.time);
    });
}

// === TOAST NOTIFICATIONS ===
function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: '✓',
        warning: '⚠',
        error: '✕',
        info: 'ℹ'
    };
    
    toast.innerHTML = `
        <span style="font-size: 18px;">${icons[type]}</span>
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'toastSlideOut 0.3s ease-out forwards';
        setTimeout(() => container.removeChild(toast), 300);
    }, duration);
}

// === FORGE PANEL ===
function testForgedCode() {
    const code = document.getElementById('code-editor').value;
    if (!code.trim()) {
        showToast('No code to test', 'warning');
        return;
    }
    
    // Send to backend for sandbox testing
    sendMessage(`forge test ${code}`);
}

function deployForgedCode() {
    const code = document.getElementById('code-editor').value;
    if (!code.trim()) {
        showToast('No code to deploy', 'warning');
        return;
    }
    
    const toolName = prompt('Enter tool name:');
    if (toolName) {
        sendMessage(`forge deploy ${toolName} ${code}`);
    }
}

// === UTILITY FUNCTIONS ===
function rippleEffect(x, y) {
    const ripple = document.createElement('div');
    ripple.className = 'ripple';
    ripple.style.left = `${x}px`;
    ripple.style.top = `${y}px`;
    document.body.appendChild(ripple);
    
    setTimeout(() => ripple.remove(), 2000);
}

// Add ripple on voice activation
document.addEventListener('click', (e) => {
    if (e.target.id === 'voice-btn' || e.target.closest('#voice-btn')) {
        rippleEffect(e.clientX, e.clientY);
    }
});

// === PERFORMANCE MONITORING ===
setInterval(() => {
    const fps = Math.round(1000 / (performance.now() - (window.lastFrameTime || performance.now())));
    window.lastFrameTime = performance.now();
    
    // Log FPS if it drops below 30
    if (fps < 30) {
        console.warn('[Performance] Low FPS:', fps);
    }
}, 1000);

// === ERROR HANDLING ===
window.addEventListener('error', (e) => {
    console.error('[ARGUS Error]', e);
    showToast('An error occurred. Check console.', 'error');
});
// RTX 4050 has NVENC encoder - optimize for screen recording
function optimizeForRecording() {
    // Reduce particle updates when recording
    if (navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia) {
        // User might be recording
        console.log('[ARGUS] Screen recording detected - optimizing');
        
        // Lock animations to 60 FPS (smoother recordings)
        let lastFrame = performance.now();
        const targetFPS = 60;
        const frameTime = 1000 / targetFPS;
        
        function recordingOptimizedAnimate() {
            const now = performance.now();
            const delta = now - lastFrame;
            
            if (delta >= frameTime) {
                // Your animation code here
                lastFrame = now - (delta % frameTime);
            }
            
            requestAnimationFrame(recordingOptimizedAnimate);
        }
        
        // Optional: Start this instead of regular animate
        // recordingOptimizedAnimate();
    }
}

// Call on load
optimizeForRecording();
// === EXPORT FOR OTHER MODULES ===
window.ARGUS = ARGUS;
window.addChatMessage = addChatMessage;
window.showToast = showToast;
window.updateVitals = updateVitals;
window.showPanel = showPanel;

console.log('[ARGUS] renderer.js loaded successfully');