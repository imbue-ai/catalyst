import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

// DOM Elements
const tbody = document.getElementById('harnesses-tbody');
const modal = document.getElementById('auth-modal');
const modalTitle = document.getElementById('modal-title');
const closeModalTextBtn = document.getElementById('close-modal-text-btn');
const resetTerminalBtn = document.getElementById('reset-terminal-btn');
const copyBtn = document.getElementById('copy-btn');
const pasteBtn = document.getElementById('paste-btn');
const terminalContainer = document.getElementById('terminal-container');
const terminalLoader = document.getElementById('terminal-loader');

let term = null;
let fitAddon = null;
let socket = null;
let currentCommand = null;

// Initialize the single xterm instance
function initTerminal() {
  if (term) return;

  term = new Terminal({
    cursorBlink: true,
    theme: {
      background: '#000000',
      foreground: '#ffffff',
      cursor: '#ffffff',
      black: '#000000',
      red: '#ef4444',
      green: '#16a34a',
      yellow: '#eab308',
      blue: '#2563eb',
      magenta: '#d946ef',
      cyan: '#0891b2',
      white: '#ffffff',
    },
    fontFamily: 'Courier New, Courier, monospace',
    fontSize: 13,
    lineHeight: 1.4,
  });

  fitAddon = new FitAddon();
  term.loadAddon(fitAddon);
  term.open(terminalContainer);
  fitAddon.fit();

  // Forward keyboard inputs to the running process
  term.onData((data) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(data);
    }
  });

  // Handle window resizing
  window.addEventListener('resize', () => {
    if (fitAddon) {
      fitAddon.fit();
      sendResize();
    }
  });
}

function sendResize() {
  if (socket && socket.readyState === WebSocket.OPEN && term) {
    const size = {
      resize: [term.cols, term.rows]
    };
    socket.send(JSON.stringify(size));
  }
}

// Connect to the backend WebSocket
function connectWebSocket(command) {
  // Close any existing connection
  if (socket) {
    try { socket.close(); } catch (e) {}
  }

  currentCommand = command;
  terminalLoader.style.opacity = '1';
  terminalLoader.style.pointerEvents = 'auto';

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socketUrl = `${protocol}//${window.location.host}/openhost/api/pty/${command}`;
  
  socket = new WebSocket(socketUrl);
  socket.binaryType = 'arraybuffer';

  socket.onopen = () => {
    terminalLoader.style.opacity = '0';
    terminalLoader.style.pointerEvents = 'none';
    term.clear();
    term.write('[System] Terminal established successfully with openhost gateway.\r\n\r\n');
    sendResize();
  };

  socket.onmessage = (event) => {
    if (typeof event.data === 'string') {
      term.write(event.data);
    } else {
      term.write(new Uint8Array(event.data));
    }
  };

  socket.onclose = () => {
    term.write('\r\n\r\n[System] Connection to terminal closed.\r\n');
  };

  socket.onerror = () => {
    term.write('\r\n\r\n[System] Connection error occurred.\r\n');
    terminalLoader.style.opacity = '0';
    terminalLoader.style.pointerEvents = 'none';
  };
}

// Open modal and connect terminal
function openAuthTerminal(command, displayName) {
  const commandTexts = {
    'agy': 'agy',
    'codex': 'codex login --device-auth',
    'gemini': 'gemini',
    'claude': 'claude auth login'
  };
  modalTitle.textContent = commandTexts[command] || command;
  modal.classList.add('open');
  
  // Make sure terminal is initialized and fitted
  initTerminal();
  setTimeout(() => {
    fitAddon.fit();
    connectWebSocket(command);
    term.focus();
  }, 100);
}

// Close modal and disconnect
function closeAuthTerminal() {
  modal.classList.remove('open');
  if (socket) {
    try { socket.close(); } catch (e) {}
    socket = null;
  }
}

function getAuthCommand(name) {
  const norm = name.toLowerCase();
  if (norm.includes('claude')) return 'claude';
  if (norm.includes('antigravity') || norm.includes('agy')) return 'agy';
  if (norm.includes('codex')) return 'codex';
  if (norm.includes('gemini')) return 'gemini';
  return null;
}

// Fetch harnesses status
async function loadHarnesses() {
  try {
    const res = await fetch('/api/harnesses');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const harnesses = await res.json();
    
    renderHarnesses(harnesses);
  } catch (err) {
    console.error('Error fetching harnesses:', err);
    tbody.innerHTML = `
      <tr class="loading-row">
        <td colspan="4" style="color: #dc2626; font-weight: 600;">
          Failed to load harness status. Could not communicate with Catalyst backend.
        </td>
      </tr>
    `;
  }
}

// Render harnesses into UI
function renderHarnesses(harnesses) {
  tbody.innerHTML = '';
  
  if (harnesses.length === 0) {
    tbody.innerHTML = `
      <tr class="loading-row">
        <td colspan="4">No agent harnesses found.</td>
      </tr>
    `;
    return;
  }

  harnesses.forEach(h => {
    const isAvailable = h.available;
    const authCmd = getAuthCommand(h.name);
    
    // Create row
    const row = document.createElement('tr');
    
    // Status text
    const statusText = isAvailable
      ? `<span class="status-text active">ok</span>`
      : `<span class="status-text inactive">configuration required</span>`;

    // Hint text (only shown if not ok)
    const hintText = !isAvailable ? (h.help_message || '') : '';

    // Action button
    let actionButtonHTML = '';
    if (authCmd) {
      actionButtonHTML = `
        <button class="simple-btn auth-btn" data-command="${authCmd}" data-display="${h.display_name}">
          Authenticate
        </button>
      `;
    } else {
      actionButtonHTML = `
        <button class="simple-btn" disabled>
          N/A
        </button>
      `;
    }

    row.innerHTML = `
      <td><strong>${h.display_name}</strong></td>
      <td>${statusText}</td>
      <td>${hintText}</td>
      <td>${actionButtonHTML}</td>
    `;
    
    tbody.appendChild(row);
  });

  // Bind click events to the Authenticate buttons
  document.querySelectorAll('.auth-btn[data-command]').forEach(btn => {
    btn.addEventListener('click', () => {
      const command = btn.getAttribute('data-command');
      const display = btn.getAttribute('data-display');
      openAuthTerminal(command, display);
    });
  });
}

// Event Listeners for closing the terminal
closeModalTextBtn.addEventListener('click', closeAuthTerminal);
resetTerminalBtn.addEventListener('click', () => {
  if (currentCommand) {
    connectWebSocket(currentCommand);
  }
});

// Copy selected terminal text to clipboard
copyBtn.addEventListener('click', async () => {
  if (term) {
    const selection = term.getSelection();
    if (selection) {
      try {
        await navigator.clipboard.writeText(selection);
        const originalText = copyBtn.textContent;
        copyBtn.textContent = 'Copied!';
        setTimeout(() => {
          copyBtn.textContent = originalText;
        }, 1000);
      } catch (err) {
        console.error('Failed to copy to clipboard:', err);
      }
    }
  }
});

// Paste clipboard text into the terminal session
pasteBtn.addEventListener('click', async () => {
  try {
    const text = await navigator.clipboard.readText();
    if (text && socket && socket.readyState === WebSocket.OPEN) {
      socket.send(text);
    }
  } catch (err) {
    console.error('Failed to read from clipboard:', err);
  }
});

// Modal can only be closed via the explicit 'Exit' button to avoid accidental closures during text selection.

// Environment Variables Section Logic
const defaultEnvSelect = document.getElementById('default-env-select');
const addCustomEnvBtn = document.getElementById('add-custom-env-btn');
const envVarsTbody = document.getElementById('env-vars-tbody');
const restartCatalystBtn = document.getElementById('restart-catalyst-btn');
const restartStatus = document.getElementById('restart-status');
const envWarningBanner = document.getElementById('env-warning-banner');

const DEFAULT_ENV_DEFAULTS = {
  'CATALYST_MAX_CONCURRENCY_PER_TASK': '3',
  'CATALYST_EXPERIMENT_TIMEOUT_SECS': '1800',
  'CATALYST_EXPERIMENT_RLIMIT_AS': '12884901888'
};

let envVarsList = []; // Array of { key: string, value: string }

async function loadEnvVars() {
  try {
    const res = await fetch('/openhost/api/env');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (data.openhost_app_data_dir_set === false) {
      if (envWarningBanner) envWarningBanner.classList.remove('hidden');
    } else {
      if (envWarningBanner) envWarningBanner.classList.add('hidden');
    }

    const envMap = data.env || {};
    envVarsList = Object.entries(envMap).map(([k, v]) => ({ key: k, value: String(v) }));
    renderEnvVars();
  } catch (err) {
    console.error('Error fetching environment variables:', err);
    if (envVarsTbody) {
      envVarsTbody.innerHTML = `
        <tr class="loading-row">
          <td colspan="3" style="color: #dc2626; font-weight: 600;">
            Failed to load environment variables.
          </td>
        </tr>
      `;
    }
  }
}

function renderEnvVars() {
  if (!envVarsTbody) return;
  envVarsTbody.innerHTML = '';

  if (envVarsList.length === 0) {
    envVarsTbody.innerHTML = `
      <tr class="loading-row">
        <td colspan="3">No environment variables configured yet. Select a default variable or add a custom variable above.</td>
      </tr>
    `;
    return;
  }

  envVarsList.forEach((item, index) => {
    const row = document.createElement('tr');

    const keyTd = document.createElement('td');
    const keyInput = document.createElement('input');
    keyInput.type = 'text';
    keyInput.className = 'env-key-input';
    keyInput.placeholder = 'e.g. MY_ENV_VAR';
    keyInput.value = item.key;
    keyInput.addEventListener('input', (e) => {
      envVarsList[index].key = e.target.value;
    });
    keyTd.appendChild(keyInput);

    const valTd = document.createElement('td');
    const valInput = document.createElement('input');
    valInput.type = 'text';
    valInput.className = 'env-val-input';
    valInput.placeholder = 'Value';
    valInput.value = item.value;
    valInput.addEventListener('input', (e) => {
      envVarsList[index].value = e.target.value;
    });
    valTd.appendChild(valInput);

    const actionTd = document.createElement('td');
    const removeBtn = document.createElement('button');
    removeBtn.className = 'simple-btn btn-danger';
    removeBtn.textContent = 'Remove';
    removeBtn.addEventListener('click', () => {
      envVarsList.splice(index, 1);
      renderEnvVars();
    });
    actionTd.appendChild(removeBtn);

    row.appendChild(keyTd);
    row.appendChild(valTd);
    row.appendChild(actionTd);

    envVarsTbody.appendChild(row);
  });
}

function getEnvPayload() {
  const envObj = {};
  envVarsList.forEach(item => {
    const k = item.key.trim();
    if (k) {
      envObj[k] = item.value;
    }
  });
  return envObj;
}

if (defaultEnvSelect) {
  defaultEnvSelect.addEventListener('change', (e) => {
    const selectedKey = e.target.value;
    if (!selectedKey) return;

    const existingIndex = envVarsList.findIndex(item => item.key.trim() === selectedKey);
    const defaultValue = DEFAULT_ENV_DEFAULTS[selectedKey] || '';

    if (existingIndex >= 0) {
      envVarsList[existingIndex].value = defaultValue;
    } else {
      envVarsList.push({ key: selectedKey, value: defaultValue });
    }

    defaultEnvSelect.value = '';
    renderEnvVars();
  });
}

if (addCustomEnvBtn) {
  addCustomEnvBtn.addEventListener('click', () => {
    envVarsList.push({ key: '', value: '' });
    renderEnvVars();
    const inputs = envVarsTbody.querySelectorAll('.env-key-input');
    if (inputs.length > 0) {
      inputs[inputs.length - 1].focus();
    }
  });
}

function setRestartStatus(message, type) {
  if (!restartStatus) return;
  restartStatus.textContent = message;
  restartStatus.className = `restart-status ${type}`;
  restartStatus.classList.remove('hidden');
}

if (restartCatalystBtn) {
  restartCatalystBtn.addEventListener('click', async () => {
    const envPayload = getEnvPayload();

    restartCatalystBtn.disabled = true;
    setRestartStatus('Saving environment variables and restarting Catalyst...', 'info');

    try {
      const saveRes = await fetch('/openhost/api/env', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ env: envPayload })
      });
      if (!saveRes.ok) throw new Error(`Failed to save env vars: HTTP ${saveRes.status}`);

      const restartRes = await fetch('/openhost/api/restart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ env: envPayload })
      });
      if (!restartRes.ok) throw new Error(`Failed to trigger restart: HTTP ${restartRes.status}`);

      setRestartStatus('Catalyst is restarting, waiting for server to come back online...', 'info');

      let attempts = 0;
      const maxAttempts = 20;
      let online = false;

      while (attempts < maxAttempts) {
        await new Promise(r => setTimeout(r, 1000));
        attempts++;
        try {
          const healthRes = await fetch('/openhost/health');
          if (healthRes.ok) {
            online = true;
            break;
          }
        } catch (e) {
          // Expected while server is restarting
        }
      }

      if (online) {
        setRestartStatus('Catalyst restarted successfully!', 'success');
        loadHarnesses();
      } else {
        setRestartStatus('Restart requested, but Catalyst health check timed out. Check server logs.', 'error');
      }
    } catch (err) {
      console.error('Error restarting Catalyst:', err);
      setRestartStatus(`Restart failed: ${err.message}`, 'error');
    } finally {
      restartCatalystBtn.disabled = false;
    }
  });
}

// Initial load
loadHarnesses();
loadEnvVars();

// Polling interval (refresh harnesses list every 5 seconds)
setInterval(loadHarnesses, 5000);

