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
  if (message.startsWith("Alerta de segurança")) {
    return getComputedStyle(document.documentElement).getPropertyValue('--c-error');
  }
  if (message.startsWith("Norton e Firewall voltaram")) {
    return getComputedStyle(document.documentElement).getPropertyValue('--c-speaking');
  }
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

  const status = document.getElementById('status-text');
  status.innerText = message.toUpperCase();
  status.title = message;
}

function applyMicButton(micEnabled) {
  const button = document.getElementById('mic-toggle');
  const icon = document.getElementById('mic-icon');
  const label = document.getElementById('mic-label');
  button.classList.toggle('paused', !micEnabled);
  icon.innerText = micEnabled ? '🎤' : '🔇';
  label.innerText = micEnabled ? 'MICROFONE LIGADO' : 'MICROFONE PAUSADO';
  button.title = micEnabled ? 'Pausar o microfone' : 'Ativar o microfone';
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
    const r = await fetch('/mic/toggle', {
      method: 'POST',
      headers: { 'X-Nico-Request': '1' }
    });
    const data = await r.json();
    applyMicButton(data.mic_enabled);
  } catch (err) {
    console.error('Failed to toggle mic:', err);
  }
}

async function closeNico() {
  if (window.pywebview && window.pywebview.api) {
    await window.pywebview.api.close_nico();
  }
}

let lastHistoryLength = -1;
async function refreshHistory() {
  const r = await fetch('/history');
  const data = await r.json();
  if (data.history.length === lastHistoryLength) return;
  lastHistoryLength = data.history.length;

  const el = document.getElementById('transcript');
  el.replaceChildren(...data.history.map(h => {
    const entry = document.createElement('div');
    entry.className = 'entry';

    const you = document.createElement('div');
    you.className = 'you';
    you.textContent = `Você: ${h[0]}`;

    const nico = document.createElement('div');
    nico.className = 'nico';
    nico.textContent = `Nico: ${h[1]}`;

    entry.append(you, nico);
    return entry;
  }));
  el.scrollTop = el.scrollHeight;
}

async function sendCommand() {
  const input = document.getElementById('cmd');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  await fetch('/command', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Nico-Request': '1'
    },
    body: JSON.stringify({ text })
  });
  lastHistoryLength = -1;
  refreshHistory();
}

document.getElementById('cmd').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') sendCommand();
});
document.getElementById('send-button').addEventListener('click', sendCommand);
document.getElementById('mic-toggle').addEventListener('click', toggleMic);
document.getElementById('close-button').addEventListener('click', closeNico);

applyStatus("Nico está iniciando...");
setInterval(refreshStatus, 500);
setInterval(refreshHistory, 1500);
refreshStatus();
refreshHistory();
