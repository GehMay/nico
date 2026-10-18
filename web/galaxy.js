const STAR_COLORS = ["#4fd6ff", "#9d6bff", "#3be389", "#ffd166", "#ff6bcb"];

function colorForIndex(i) {
  return STAR_COLORS[i % STAR_COLORS.length];
}

let network = null;
let allNodesData = null;
let allEdgesData = null;
let selectedMemoryId = null;

async function loadGraph() {
  const r = await fetch('/api/memory/graph');
  const data = await r.json();

  document.getElementById('count').innerText =
    data.nodes.length + ' memórias · ' + data.edges.length + ' conexões';

  const degree = {};
  data.edges.forEach(e => {
    degree[e.from] = (degree[e.from] || 0) + 1;
    degree[e.to] = (degree[e.to] || 0) + 1;
  });

  const nodes = data.nodes.map((n, i) => ({
    id: n.id,
    label: n.label,
    question: n.question,
    answer: n.answer,
    shape: 'dot',
    size: 10 + Math.min(14, (degree[n.id] || 0) * 3),
    color: {
      background: colorForIndex(i),
      border: colorForIndex(i),
      highlight: { background: '#ffffff', border: colorForIndex(i) },
    },
    font: { color: '#cfe0ff', size: 12, face: 'Share Tech Mono' },
    shadow: { enabled: true, color: colorForIndex(i), size: 18, x: 0, y: 0 },
  }));

  const edges = data.edges.map(e => ({
    from: e.from,
    to: e.to,
    width: 0.5 + e.value * 3,
    color: { color: '#8fb3ff33', highlight: '#8fb3ffaa' },
    smooth: { type: 'continuous' },
  }));

  allNodesData = new vis.DataSet(nodes);
  allEdgesData = new vis.DataSet(edges);

  const container = document.getElementById('galaxy');
  const options = {
    physics: {
      solver: 'forceAtlas2Based',
      forceAtlas2Based: { gravitationalConstant: -60, springLength: 120, springConstant: 0.03 },
      stabilization: { iterations: 150 },
    },
    interaction: { hover: true, tooltipDelay: 120 },
    nodes: { borderWidth: 1 },
    edges: { smooth: false },
  };

  if (network) {
    network.destroy();
  }
  network = new vis.Network(container, { nodes: allNodesData, edges: allEdgesData }, options);

  network.on('click', (params) => {
    if (params.nodes.length === 0) {
      closeDetail();
      return;
    }
    const node = allNodesData.get(params.nodes[0]);
    showDetail(node.id, node.question, node.answer);
  });
}

function showDetail(id, question, answer) {
  selectedMemoryId = id;
  document.getElementById('detail-q').innerText = 'Você: ' + question;
  document.getElementById('detail-a').innerText = 'Nico: ' + answer;
  document.getElementById('detail').style.display = 'block';
}

function closeDetail() {
  selectedMemoryId = null;
  document.getElementById('detail').style.display = 'none';
}

document.getElementById('detail-close').addEventListener('click', closeDetail);

async function deleteMemory(id) {
  const r = await fetch('/api/memory/' + id, {
    method: 'DELETE',
    headers: { 'X-Nico-Request': '1' },
  });
  if (!r.ok) {
    alert('Não consegui apagar essa memória. Tente de novo.');
    return;
  }
  if (allNodesData) {
    allNodesData.remove(id);
  }
  if (allEdgesData) {
    allEdgesData.get().forEach(edge => {
      if (edge.from === id || edge.to === id) {
        allEdgesData.remove(edge.id);
      }
    });
  }
  const remaining = allNodesData ? allNodesData.length : 0;
  const connections = allEdgesData ? allEdgesData.length : 0;
  document.getElementById('count').innerText = remaining + ' memórias · ' + connections + ' conexões';
  closeDetail();
}

document.getElementById('detail-delete').addEventListener('click', () => {
  if (selectedMemoryId === null) return;
  if (!confirm('Apagar esta memória? Essa ação não pode ser desfeita.')) return;
  deleteMemory(selectedMemoryId);
});

document.getElementById('clear-all').addEventListener('click', async () => {
  if (!confirm('Apagar TODAS as memórias de conversa? Fatos e lembretes não são afetados. Essa ação não pode ser desfeita.')) return;
  const r = await fetch('/api/memory', {
    method: 'DELETE',
    headers: { 'X-Nico-Request': '1' },
  });
  if (!r.ok) {
    alert('Não consegui apagar a memória. Tente de novo.');
    return;
  }
  closeDetail();
  loadGraph();
});

function applySearch(term) {
  if (!allNodesData) return;
  const query = term.trim().toLowerCase();

  allNodesData.forEach(node => {
    const match = !query ||
      node.question.toLowerCase().includes(query) ||
      node.answer.toLowerCase().includes(query);
    allNodesData.update({
      id: node.id,
      opacity: match ? 1 : 0.12,
    });
  });
}

document.getElementById('search').addEventListener('input', (e) => applySearch(e.target.value));

loadGraph();
