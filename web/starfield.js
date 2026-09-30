// Campo de estrelas animado (tsParticles) atrás do grafo de memória.
// Fica só de fundo: sem links entre partículas e sem interação de mouse,
// pra não competir visualmente com os nós/arestas do vis-network.
tsParticles.load("starfield", {
  fullScreen: { enable: false },
  background: { color: "transparent" },
  fpsLimit: 60,
  particles: {
    number: { value: 140, density: { enable: true, area: 900 } },
    color: { value: ["#ffffff", "#9fd8ff", "#c9b3ff"] },
    opacity: {
      value: { min: 0.15, max: 0.9 },
      animation: { enable: true, speed: 0.6, sync: false },
    },
    size: { value: { min: 0.4, max: 1.8 } },
    move: {
      enable: true,
      speed: 0.12,
      direction: "none",
      random: true,
      straight: false,
      outModes: { default: "out" },
    },
    links: { enable: false },
    twinkle: {
      particles: { enable: true, frequency: 0.03, opacity: 1 },
    },
  },
  interactivity: {
    events: { onHover: { enable: false }, onClick: { enable: false } },
  },
  detectRetina: true,
});
