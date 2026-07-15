import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';

// DOM Elements
const grid = document.getElementById('harnesses-grid');
const modal = document.getElementById('auth-modal');
const modalTitle = document.getElementById('modal-title');
const closeModalBtn = document.getElementById('close-modal-btn');
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
      background: '#030712', // Matches slate-950
      foreground: '#cbd5e1', // Slate-300
      cursor: '#14b8a6',     // Teal-500
      black: '#1e293b',      // Slate-800
      red: '#ef4444',        // Red-500
      green: '#10b981',      // Emerald-500
      yellow: '#f59e0b',     // Amber-500
      blue: '#3b82f6',       // Blue-500
      magenta: '#a855f7',    // Purple-500
      cyan: '#06b6d4',       // Cyan-500
      white: '#f8fafc',      // Slate-50
    },
    fontFamily: 'JetBrains Mono, Menlo, Monaco, Consolas, monospace',
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
  // Note: served on port 8139 via our gateway
  const socketUrl = `${protocol}//${window.location.host}/openhost/api/pty/${command}`;
  
  socket = new WebSocket(socketUrl);
  socket.binaryType = 'arraybuffer';

  socket.onopen = () => {
    terminalLoader.style.opacity = '0';
    terminalLoader.style.pointerEvents = 'none';
    term.clear();
    term.write('\x1b[1;36m[System] Terminal established successfully with openhost gateway.\x1b[0m\r\n\r\n');
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
    term.write('\r\n\r\n\x1b[1;31m[System] Connection to terminal closed.\x1b[0m\r\n');
  };

  socket.onerror = () => {
    term.write('\r\n\r\n\x1b[1;31m[System] Connection error occurred.\x1b[0m\r\n');
    terminalLoader.style.opacity = '0';
    terminalLoader.style.pointerEvents = 'none';
  };
}

// Open modal and connect terminal
function openAuthTerminal(command, displayName) {
  modalTitle.textContent = `${command}_auth.sh`;
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

// SVGs for branding
const brandIcons = {
  claude: `<svg class="w-6 h-6 text-orange-400" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2L2 22h4.5l2.1-4.8h6.8l2.1 4.8H22L12 2zm1.2 11.2h-2.4l1.2-3.1 1.2 3.1z"/>
  </svg>`,
  agy: `<svg class="w-6 h-6 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
  </svg>`,
  codex: `<svg class="w-6 h-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
  </svg>`,
  gemini: `<svg class="w-6 h-6 text-blue-400" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2c-.4 4.5-3.5 8-8 8.4 4.5.4 8 3.5 8.4 8 .4-4.5 3.5-8 8-8.4-4.5-.4-8-3.5-8.4-8z"/>
    <path d="M19 3c-.2 2.2-1.8 4-4 4.2 2.2.2 4 1.8 4.2 4 .2-2.2 1.8-4 4-4.2-2.2-.2-4-1.8-4.2-4z" opacity="0.6"/>
  </svg>`,
  default: `<svg class="w-6 h-6 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
  </svg>`
};

function getBrandIcon(name) {
  const norm = name.toLowerCase();
  if (norm.includes('claude')) return brandIcons.claude;
  if (norm.includes('antigravity') || norm.includes('agy')) return brandIcons.agy;
  if (norm.includes('codex')) return brandIcons.codex;
  if (norm.includes('gemini')) return brandIcons.gemini;
  return brandIcons.default;
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
    grid.innerHTML = `
      <div class="glass-card p-6 rounded-2xl w-full col-span-full border-red-500/20 bg-red-950/10">
        <div class="flex items-center gap-3 text-red-400 font-bold mb-2">
          <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <h3>Failed to Load Harness Status</h3>
        </div>
        <p class="text-sm text-slate-400">
          Could not communicate with the backend API. Please make sure the Catalyst backend is up and running.
        </p>
      </div>
    `;
  }
}

// Render harnesses into UI
function renderHarnesses(harnesses) {
  grid.innerHTML = '';
  
  harnesses.forEach(h => {
    const brand = getAuthCommand(h.name) || 'default';
    const isAvailable = h.available;
    const authCmd = getAuthCommand(h.name);
    
    // Create card element
    const card = document.createElement('div');
    card.className = `glass-card p-6 rounded-2xl flex flex-col justify-between ${brand === 'agy' || brand === 'claude' ? 'glow-teal' : 'glow-purple'}`;
    
    // Status Badge HTML
    const statusBadge = isAvailable
      ? `<span class="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-semibold border border-emerald-500/20">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
          Active
         </span>`
      : `<span class="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800 text-slate-400 text-xs font-semibold border border-slate-700/50">
          <span class="w-1.5 h-1.5 rounded-full bg-slate-500"></span>
          Unavailable
         </span>`;

    // Models badge list
    let modelsHTML = '';
    if (h.models && h.models.length > 0) {
      modelsHTML = `
        <div class="mt-4">
          <p class="text-[11px] text-slate-500 font-bold uppercase tracking-wider">Supported Models</p>
          <div class="details-list">
            ${h.models.map(m => `<span class="tag-badge">${m}</span>`).join('')}
          </div>
        </div>
      `;
    }

    // Help message or warning
    const helpMessageHTML = h.help_message
      ? `<p class="text-xs text-slate-400 mt-2 bg-slate-950/30 border border-slate-800/40 p-2.5 rounded-lg leading-relaxed">${h.help_message}</p>`
      : `<p class="text-xs text-slate-500 mt-2 italic leading-relaxed">Harness is healthy and authorized for execution.</p>`;

    // Button HTML
    let actionButtonHTML = '';
    if (authCmd) {
      actionButtonHTML = `
        <button class="auth-btn mt-6" data-command="${authCmd}" data-display="${h.display_name}">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
          Authenticate Client
        </button>
      `;
    } else {
      actionButtonHTML = `
        <button class="auth-btn mt-6" disabled>
          No CLI Auth Required
        </button>
      `;
    }

    card.innerHTML = `
      <div>
        <div class="flex items-center justify-between gap-4 mb-4 border-b border-slate-800/40 pb-4">
          <div class="flex items-center gap-3">
            <div class="w-12 h-12 rounded-xl bg-slate-950 flex items-center justify-center border border-slate-800/60">
              ${getBrandIcon(h.name)}
            </div>
            <div>
              <h3 class="font-bold text-base text-white tracking-tight">${h.display_name}</h3>
              <p class="text-[10px] text-slate-500 font-mono mt-0.5">ID: ${h.name}</p>
            </div>
          </div>
          ${statusBadge}
        </div>
        ${helpMessageHTML}
        ${modelsHTML}
      </div>
      <div>
        ${actionButtonHTML}
      </div>
    `;
    
    grid.appendChild(card);
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
closeModalBtn.addEventListener('click', closeAuthTerminal);
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
