import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

// DOM Elements
const tbody = document.getElementById('harnesses-tbody');
const modal = document.getElementById('auth-modal');
const modalTitle = document.getElementById('modal-title');
const closeModalTextBtn = document.getElementById('close-modal-text-btn');
const resetTerminalBtn = document.getElementById('reset-terminal-btn');
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

// Close modal if clicked outside container
modal.addEventListener('click', (e) => {
  if (e.target === modal) {
    closeAuthTerminal();
  }
});

// Initial load
loadHarnesses();

// Polling interval (refresh harnesses list every 5 seconds)
setInterval(loadHarnesses, 5000);
