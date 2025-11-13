// ui/main.js
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');

let mainWindow;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1600,
        height: 900,
        backgroundColor: '#0a0f14',
        frame: false,
        titleBarStyle: 'hidden',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js'),
            webviewTag: true
        }
    });

    mainWindow.loadFile(path.join(__dirname, 'index.html'));
    mainWindow.webContents.openDevTools({ mode: 'detach' });
}

app.whenReady().then(() => {
    ipcMain.on('spawn-overlay', (event, data) => {
        if (!mainWindow) return;

        const [x, y] = mainWindow.getPosition();
        const [w] = mainWindow.getSize();

        const overlay = new BrowserWindow({
            width: 340,
            height: 440,
            x: x + w - 350,
            y: y + 110,
            frame: false,
            transparent: true,
            alwaysOnTop: true,
            resizable: false,
            skipTaskbar: true,
            webPreferences: {
                nodeIntegration: false,
                contextIsolation: true
            }
        });

        overlay.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(`
            <!DOCTYPE html>
            <html>
            <body style="margin:0;background:rgba(15,22,35,0.98);color:#cdd3da;font-family:Segoe UI;padding:20px;box-sizing:border-box;">
                <h3 style="margin:0 0 16px;color:#fff;font-size:1.1em;border-bottom:1px solid #3c82f6;padding-bottom:10px;">
                    ${data.title || 'ARGUS Suggestion'}
                </h3>
                <ul style="margin:0;padding-left:24px;font-size:0.95em;line-height:1.6;">
                    ${data.suggestions?.map(s => `<li>${s}</li>`).join('') || ''}
                </ul>
            </body>
            </html>
        `));

        setTimeout(() => overlay.close(), 10000);
    });

    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});