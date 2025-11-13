// ui/preload.js
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    spawnOverlay: (data) => ipcRenderer.send('spawn-overlay', data)
});