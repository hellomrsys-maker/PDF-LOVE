/**
 * PDFLove Desktop — a real installed application.
 *
 * This is deliberately NOT a browser shortcut to a website. The entire app
 * is copied into the package at build time and loaded from disk with a
 * file:// URL, so:
 *
 *   * there is no origin, no service worker and no HTTP cache involved;
 *   * it cannot show "This site can't be reached", because it never
 *     resolves a host;
 *   * it works on a machine that has never had an internet connection.
 *
 * Outbound network access is blocked at the session level, so even a bug
 * or a third-party script cannot phone home. The single exception is the
 * update check, which the user triggers from the Help menu.
 */
const { app, BrowserWindow, Menu, shell, dialog, session } = require('electron');
const path = require('path');
const fs = require('fs');
const https = require('https');

const APP_DIR = path.join(__dirname, 'app');       // the bundled frontend
const ENTRY = path.join(APP_DIR, 'index.html');
const UPDATE_URL = 'https://pdflove.co.in/desktop-version.json';

// Set once the user asks to check for updates; every other request is denied.
let updateCheckInFlight = false;

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 940,
    minWidth: 380,
    minHeight: 520,
    backgroundColor: '#F6F3EC',
    title: 'PDFLove',
    icon: path.join(__dirname, 'build', 'icon.png'),
    webPreferences: {
      // The bundled app is trusted, local, first-party code, but it never
      // needs Node — so don't give it any.
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      spellcheck: false,
    },
  });

  win.loadFile(ENTRY);

  // External links open in the real browser, never inside the app window.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
  win.webContents.on('will-navigate', (e, url) => {
    if (!url.startsWith('file://')) {
      e.preventDefault();
      shell.openExternal(url);
    }
  });

  return win;
}

/**
 * Hard network block. Everything the app needs is on disk; nothing should
 * leave the machine. file:// and devtools are allowed through so the app
 * itself can load.
 */
function lockDownNetwork() {
  session.defaultSession.webRequest.onBeforeRequest((details, callback) => {
    const u = details.url;
    if (u.startsWith('file://') || u.startsWith('devtools://') || u.startsWith('blob:') || u.startsWith('data:')) {
      return callback({ cancel: false });
    }
    // The update check is made by the main process with https, not by the
    // renderer, so nothing in the page is ever allowed out.
    return callback({ cancel: true });
  });
}

function checkForUpdates(win) {
  if (updateCheckInFlight) return;
  updateCheckInFlight = true;

  const req = https.get(UPDATE_URL, { timeout: 10000 }, (res) => {
    let body = '';
    res.on('data', (c) => { body += c; });
    res.on('end', () => {
      updateCheckInFlight = false;
      let latest;
      try { latest = JSON.parse(body).version; } catch (e) { latest = null; }
      if (!latest) {
        return dialog.showMessageBox(win, {
          type: 'warning', title: 'Check for updates',
          message: 'Could not read the update information.',
          detail: 'PDFLove keeps working exactly as it is.',
        });
      }
      const current = app.getVersion();
      if (latest === current) {
        return dialog.showMessageBox(win, {
          type: 'info', title: 'Check for updates',
          message: `You are on the latest version (${current}).`,
        });
      }
      dialog.showMessageBox(win, {
        type: 'info', title: 'Update available',
        message: `Version ${latest} is available. You have ${current}.`,
        detail: 'Downloading it is optional — this copy will keep working offline either way.',
        buttons: ['Open download page', 'Later'], defaultId: 0, cancelId: 1,
      }).then(({ response }) => {
        if (response === 0) shell.openExternal('https://pdflove.co.in/');
      });
    });
  });
  req.on('timeout', () => { req.destroy(); });
  req.on('error', () => {
    updateCheckInFlight = false;
    dialog.showMessageBox(win, {
      type: 'info', title: 'Check for updates',
      message: 'No internet connection.',
      detail: 'That is fine — PDFLove is fully offline and every tool keeps working.',
    });
  });
}

function buildMenu(win) {
  const isMac = process.platform === 'darwin';
  const template = [
    ...(isMac ? [{ role: 'appMenu' }] : []),
    {
      label: 'File',
      submenu: [
        { label: 'Home', accelerator: 'CmdOrCtrl+H', click: () => win.loadFile(ENTRY) },
        { type: 'separator' },
        isMac ? { role: 'close' } : { role: 'quit' },
      ],
    },
    { role: 'editMenu' },
    {
      label: 'View',
      submenu: [
        { role: 'reload' }, { role: 'forceReload' }, { type: 'separator' },
        { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' },
        { type: 'separator' }, { role: 'togglefullscreen' },
        { type: 'separator' }, { role: 'toggleDevTools' },
      ],
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'About PDFLove',
          click: () => dialog.showMessageBox(win, {
            type: 'info', title: 'About PDFLove',
            message: `PDFLove ${app.getVersion()}`,
            detail:
              'Every tool runs on this device, using its own CPU and memory.\n\n' +
              'This application is fully self-contained: the whole toolkit is ' +
              'installed on your disk. It never contacts a server, and it works ' +
              'with no internet connection at all.\n\n' +
              'The only time it uses the network is when you choose ' +
              '"Check for updates" from this menu.',
          }),
        },
        { label: 'Check for updates…', click: () => checkForUpdates(win) },
        { type: 'separator' },
        { label: 'Terms & conditions', click: () => win.loadFile(path.join(APP_DIR, 'terms.html')) },
        { label: 'Privacy policy', click: () => win.loadFile(path.join(APP_DIR, 'privacy.html')) },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// One instance only — a second launch focuses the existing window.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.whenReady().then(() => {
    if (!fs.existsSync(ENTRY)) {
      dialog.showErrorBox('PDFLove',
        'The bundled application files are missing.\n\nExpected: ' + ENTRY);
      app.quit();
      return;
    }
    lockDownNetwork();
    const win = createWindow();
    buildMenu(win);

    app.on('second-instance', () => {
      if (win.isMinimized()) win.restore();
      win.focus();
    });
    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
  });
}
