// src/main.js
const { app, BrowserWindow, screen } = require('electron');
const path = require('path');

function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  const mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    x: 0,
    y: 0,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: true
    },
    icon: path.join(__dirname, '../public/favicon.jpg')
  });

  mainWindow.setMenu(null);
  mainWindow.loadFile(path.join(__dirname, '../public/index.html'));
  mainWindow.webContents.openDevTools();
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});