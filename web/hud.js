const STATUS_COLORS = {
  "Nico está iniciando...": getComputedStyle(document.documentElement).getPropertyValue('--c-idle'),
  "Ouvindo": getComputedStyle(document.documentElement).getPropertyValue('--c-listening'),
  "Pensando": getComputedStyle(document.documentElement).getPropertyValue('--c-thinking'),
  "Falando": getComputedStyle(document.documentElement).getPropertyValue('--c-speaking'),
  "Pesquisando": getComputedStyle(document.documentElement).getPropertyValue('--c-research'),
  "Lendo documentos": getComputedStyle(document.documentElement).getPropertyValue('--c-documents'),
  "Aguardando aprovação": getComputedStyle(document.documentElement).getPropertyValue('--c-approval'),
  "Executando ação": getComputedStyle(document.documentElement).getPropertyValue('--c-action'),
  "Pausado": getComputedStyle(document.documentElement).getPropertyValue('--c-error'),
};

function colorForStatus(message) {
  if (message.startsWith("Erro")) {
    return getComputedStyle(document.documentElement).getPropertyValue('--c-error');
  }
  return STATUS_COLORS[message] || getComputedStyle(document.documentElement).getPropertyValue('--c-idle');
}

function applyStatus(message) {
  const color = colorForStatus(message).trim();
  const core = document.getElementById('core');
  core.style.background = `radial-gradient(circle at 35% 30%, #ffffff33, ${color} 70%)`;
  core.style.boxShadow = `0 0 30px 6px ${color}, 0 0 70px 20px transparent`;

  document.querySelectorAll('.ring').forEach(ring => {
    ring.style.borderTopColor = color;
    ring.style.borderRightColor = color + '55';
  });

  document.getElementById('status-text').innerText = message.toUpperCase();
}

function applyMicButton(micEnabled) {
  const button = document.getElementById('mic-toggle');
  const icon = document.getElementById('mic-icon');
  const label = document.getElementById('mic-label');
  button.classList.toggle('paused', !micEnabled);
  icon.innerText = micEnabled ? '🎤' : '🔇';
  label.innerText = micEnabled ? 'MICROFONE LIGADO' : 'MICROFONE PAUSADO';
}

let lastStatus = null;
async function refreshStatus() {
  try {
    const r = await fetch('/status');
    const data = await r.json();
    if (data.status !== lastStatus) {
      lastStatus = data.status;
      applyStatus(data.status);
    }
    applyMicButton(data.mic_enabled);
  } catch (err) {
    applyStatus("Erro - conexão perdida");
  }
}

async function toggleMic() {
  try {
    const r = await fetch('/mic/toggle', { method: 'POST' });
    const data = await r.json();
    applyMicButton(data.mic_enabled);
  } catch (err) {
    console.error('Failed to toggle mic:', err);
  }
}

let lastHistoryLength = -1;
async function refreshHistory() {
  const r = await fetch('/history');
  const data = await r.json();
  if (data.history.length === lastHistoryLength) return;
  lastHistoryLength = data.history.length;

  const el = document.getElementById('transcript');
  el.innerHTML = data.history.map(h =>
    `<div class="entry"><div class="you">Você: ${h[0]}</div><div class="nico">Nico: ${h[1]}</div></div>`
  ).join('');
  el.scrollTop = el.scrollHeight;
}

async function sendCommand() {
  const input = document.getElementById('cmd');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  await fetch('/command', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text })
  });
  lastHistoryLength = -1;
  refreshHistory();
}

document.getElementById('cmd').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') sendCommand();
});

applyStatus("Nico está iniciando...");
setInterval(refreshStatus, 500);
setInterval(refreshHistory, 1500);
refreshStatus();
refreshHistory();
