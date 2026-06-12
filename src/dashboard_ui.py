"""
dashboard_ui.py — Self-contained HTML/CSS/JS for the proxy dashboard.

The entire UI is embedded as a Python string constant so the dashboard
is fully self-contained with zero external files. Uses Chart.js from
CDN for live graphs and Server-Sent Events (SSE) for real-time updates.

Design: Dark glassmorphism aesthetic with animated gradients, live
counters, real-time charts, log feed, and cache/rate-limiter stats.
"""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Proxy Dashboard — Live Monitoring</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg-primary: #0a0e1a;
    --bg-card: rgba(15, 20, 40, 0.75);
    --bg-card-hover: rgba(20, 28, 55, 0.85);
    --border: rgba(99, 115, 175, 0.15);
    --border-glow: rgba(99, 145, 255, 0.3);
    --text-primary: #e8ecf4;
    --text-secondary: #8892b0;
    --text-muted: #5a6380;
    --accent-blue: #60a5fa;
    --accent-green: #34d399;
    --accent-red: #f87171;
    --accent-yellow: #fbbf24;
    --accent-purple: #a78bfa;
    --accent-cyan: #22d3ee;
    --glass-bg: rgba(255, 255, 255, 0.03);
    --glass-border: rgba(255, 255, 255, 0.06);
  }

  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    overflow-x: hidden;
  }

  body::before {
    content: '';
    position: fixed;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(ellipse at 20% 50%, rgba(59, 130, 246, 0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 20%, rgba(139, 92, 246, 0.06) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 80%, rgba(16, 185, 129, 0.04) 0%, transparent 50%);
    animation: drift 20s ease-in-out infinite;
    z-index: -1;
  }

  @keyframes drift {
    0%, 100% { transform: translate(0, 0) rotate(0deg); }
    25% { transform: translate(2%, -1%) rotate(1deg); }
    50% { transform: translate(-1%, 2%) rotate(-1deg); }
    75% { transform: translate(1%, -2%) rotate(0.5deg); }
  }

  .dashboard {
    max-width: 1400px;
    margin: 0 auto;
    padding: 24px;
  }

  /* ── Header ──────────────────────────────────────────── */
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 28px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--border);
  }

  .header h1 {
    font-size: 1.6rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.5px;
  }

  .header .status {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.82rem;
    color: var(--text-secondary);
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent-green);
    box-shadow: 0 0 8px rgba(52, 211, 153, 0.5);
    animation: pulse 2s ease-in-out infinite;
  }

  .status-dot.disconnected {
    background: var(--accent-red);
    box-shadow: 0 0 8px rgba(248, 113, 113, 0.5);
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  /* ── Counter Cards Row ───────────────────────────────── */
  .counters {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 14px;
    margin-bottom: 24px;
  }

  .counter-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px;
    transition: all 0.3s ease;
    backdrop-filter: blur(12px);
    position: relative;
    overflow: hidden;
  }

  .counter-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    border-radius: 14px 14px 0 0;
  }

  .counter-card:hover {
    background: var(--bg-card-hover);
    border-color: var(--border-glow);
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
  }

  .counter-card .label {
    font-size: 0.75rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-muted);
    margin-bottom: 8px;
  }

  .counter-card .value {
    font-size: 2rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    transition: all 0.3s ease;
  }

  .counter-card.total::before { background: linear-gradient(90deg, var(--accent-blue), var(--accent-cyan)); }
  .counter-card.total .value { color: var(--accent-blue); }

  .counter-card.allowed::before { background: linear-gradient(90deg, var(--accent-green), #6ee7b7); }
  .counter-card.allowed .value { color: var(--accent-green); }

  .counter-card.blocked::before { background: linear-gradient(90deg, var(--accent-red), #fca5a5); }
  .counter-card.blocked .value { color: var(--accent-red); }

  .counter-card.cached::before { background: linear-gradient(90deg, var(--accent-cyan), #67e8f9); }
  .counter-card.cached .value { color: var(--accent-cyan); }

  .counter-card.rate-limited::before { background: linear-gradient(90deg, var(--accent-yellow), #fde68a); }
  .counter-card.rate-limited .value { color: var(--accent-yellow); }

  .counter-card.errors::before { background: linear-gradient(90deg, var(--accent-purple), #c4b5fd); }
  .counter-card.errors .value { color: var(--accent-purple); }

  /* ── Grid Layout ─────────────────────────────────────── */
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px;
    margin-bottom: 18px;
  }

  .grid.full { grid-template-columns: 1fr; }

  .panel {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 22px;
    backdrop-filter: blur(12px);
    transition: border-color 0.3s ease;
  }

  .panel:hover { border-color: var(--border-glow); }

  .panel h2 {
    font-size: 0.85rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--text-secondary);
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .panel h2 .icon { font-size: 1rem; }

  /* ── Chart ───────────────────────────────────────────── */
  .chart-container {
    position: relative;
    height: 220px;
  }

  /* ── Log Feed ────────────────────────────────────────── */
  .log-feed {
    max-height: 380px;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--border) transparent;
  }

  .log-feed::-webkit-scrollbar { width: 5px; }
  .log-feed::-webkit-scrollbar-track { background: transparent; }
  .log-feed::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  .log-entry {
    display: grid;
    grid-template-columns: auto auto 1fr auto auto;
    gap: 10px;
    align-items: center;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 0.78rem;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    transition: background 0.2s ease;
    border-bottom: 1px solid rgba(255,255,255,0.02);
  }

  .log-entry:hover { background: rgba(255, 255, 255, 0.03); }

  .log-entry .time { color: var(--text-muted); font-size: 0.72rem; white-space: nowrap; }
  .log-entry .method { font-weight: 600; color: var(--accent-blue); }
  .log-entry .host { color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .log-entry .latency { color: var(--text-muted); font-size: 0.72rem; white-space: nowrap; }

  .log-entry .action {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    white-space: nowrap;
  }

  .action-FORWARD, .action-CONNECT, .action-FORWARDED { background: rgba(52, 211, 153, 0.15); color: var(--accent-green); }
  .action-BLOCKED { background: rgba(248, 113, 113, 0.15); color: var(--accent-red); }
  .action-CACHE_HIT { background: rgba(34, 211, 238, 0.15); color: var(--accent-cyan); }
  .action-CACHE_MISS, .action-CACHE_STORE { background: rgba(34, 211, 238, 0.08); color: rgba(34, 211, 238, 0.6); }
  .action-RATE_LIMITED { background: rgba(251, 191, 36, 0.15); color: var(--accent-yellow); }
  .action-AUTH_FAILED { background: rgba(167, 139, 250, 0.15); color: var(--accent-purple); }
  .action-ERROR { background: rgba(248, 113, 113, 0.2); color: var(--accent-red); }

  /* ── Stats Tables ────────────────────────────────────── */
  .stats-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .stat-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 14px;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 8px;
  }

  .stat-item .stat-label { font-size: 0.78rem; color: var(--text-secondary); }
  .stat-item .stat-value { font-size: 0.9rem; font-weight: 600; font-variant-numeric: tabular-nums; }

  /* ── Top Hosts Table ─────────────────────────────────── */
  .hosts-table { width: 100%; border-collapse: collapse; }

  .hosts-table th {
    text-align: left;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--text-muted);
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
  }

  .hosts-table td {
    padding: 8px 12px;
    font-size: 0.82rem;
    border-bottom: 1px solid rgba(255,255,255,0.02);
  }

  .hosts-table tr:hover td { background: rgba(255, 255, 255, 0.02); }

  .hosts-table .rank {
    color: var(--text-muted);
    font-weight: 600;
    width: 30px;
  }

  .host-bar {
    height: 4px;
    background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple));
    border-radius: 2px;
    margin-top: 4px;
    transition: width 0.5s ease;
  }

  /* ── Pool Utilization ────────────────────────────────── */
  .pool-bar-container {
    background: var(--glass-bg);
    border-radius: 8px;
    padding: 16px;
    border: 1px solid var(--glass-border);
  }

  .pool-bar-track {
    height: 12px;
    background: rgba(255,255,255,0.05);
    border-radius: 6px;
    overflow: hidden;
    margin: 10px 0 6px;
  }

  .pool-bar-fill {
    height: 100%;
    border-radius: 6px;
    background: linear-gradient(90deg, var(--accent-green), var(--accent-blue));
    transition: width 0.5s ease, background 0.5s ease;
  }

  .pool-bar-fill.warn { background: linear-gradient(90deg, var(--accent-yellow), var(--accent-red)); }

  .pool-bar-labels {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  /* ── Responsive ──────────────────────────────────────── */
  @media (max-width: 900px) {
    .grid { grid-template-columns: 1fr; }
    .counters { grid-template-columns: repeat(3, 1fr); }
    .stats-grid { grid-template-columns: 1fr; }
  }

  @media (max-width: 600px) {
    .counters { grid-template-columns: repeat(2, 1fr); }
    .dashboard { padding: 14px; }
  }

  .fade-in { animation: fadeIn 0.4s ease-out; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
</style>
</head>
<body>
<div class="dashboard">
  <!-- Header -->
  <div class="header">
    <h1>⚡ Proxy Dashboard</h1>
    <div class="status">
      <span class="status-dot" id="statusDot"></span>
      <span id="statusText">Connecting...</span>
      <span style="margin-left:12px;color:var(--text-muted)" id="uptime"></span>
    </div>
  </div>

  <!-- Counter Cards -->
  <div class="counters">
    <div class="counter-card total" id="card-total">
      <div class="label">Total Requests</div>
      <div class="value" id="cnt-total">0</div>
    </div>
    <div class="counter-card allowed">
      <div class="label">Allowed</div>
      <div class="value" id="cnt-allowed">0</div>
    </div>
    <div class="counter-card blocked">
      <div class="label">Blocked</div>
      <div class="value" id="cnt-blocked">0</div>
    </div>
    <div class="counter-card cached">
      <div class="label">Cache Hits</div>
      <div class="value" id="cnt-cached">0</div>
    </div>
    <div class="counter-card rate-limited">
      <div class="label">Rate Limited</div>
      <div class="value" id="cnt-rate_limited">0</div>
    </div>
    <div class="counter-card errors">
      <div class="label">Errors</div>
      <div class="value" id="cnt-errors">0</div>
    </div>
  </div>

  <!-- Row 1: Chart + Cache Stats -->
  <div class="grid">
    <div class="panel">
      <h2><span class="icon">📈</span> Requests / Second</h2>
      <div class="chart-container">
        <canvas id="rpsChart"></canvas>
      </div>
    </div>
    <div class="panel">
      <h2><span class="icon">🗄️</span> Cache Statistics</h2>
      <div class="stats-grid">
        <div class="stat-item">
          <span class="stat-label">Entries</span>
          <span class="stat-value" id="cache-entries" style="color:var(--accent-cyan)">0</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Hit Rate</span>
          <span class="stat-value" id="cache-hit-rate" style="color:var(--accent-green)">0%</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Total Hits</span>
          <span class="stat-value" id="cache-hits" style="color:var(--accent-blue)">0</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Total Misses</span>
          <span class="stat-value" id="cache-misses" style="color:var(--text-secondary)">0</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Evictions</span>
          <span class="stat-value" id="cache-evictions" style="color:var(--accent-yellow)">0</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Size</span>
          <span class="stat-value" id="cache-size" style="color:var(--accent-purple)">0 B</span>
        </div>
      </div>
      <div class="pool-bar-container" style="margin-top:16px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:0.78rem;color:var(--text-secondary)">Rate Limiter</span>
          <span style="font-size:0.75rem;color:var(--text-muted)" id="rl-info">—</span>
        </div>
        <div class="pool-bar-track">
          <div class="pool-bar-fill" id="rl-bar" style="width:0%"></div>
        </div>
        <div class="pool-bar-labels">
          <span>0 active IPs</span>
          <span id="rl-buckets">0</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Row 2: Log Feed + Top Hosts -->
  <div class="grid">
    <div class="panel">
      <h2><span class="icon">📜</span> Live Request Log</h2>
      <div class="log-feed" id="logFeed">
        <div style="text-align:center;color:var(--text-muted);padding:40px 0;font-size:0.85rem">
          Waiting for requests...
        </div>
      </div>
    </div>
    <div class="panel">
      <h2><span class="icon">🌐</span> Top Hosts</h2>
      <table class="hosts-table">
        <thead><tr><th>#</th><th>Host</th><th style="text-align:right">Requests</th></tr></thead>
        <tbody id="topHosts">
          <tr><td colspan="3" style="text-align:center;color:var(--text-muted);padding:30px 0;font-size:0.85rem">No data yet</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<script>
// ── State ─────────────────────────────────────────────────
let prevTotal = 0;
const rpsHistory = new Array(60).fill(0);
const startTime = Date.now();

// ── Chart Setup ───────────────────────────────────────────
const ctx = document.getElementById('rpsChart').getContext('2d');
const rpsChart = new Chart(ctx, {
  type: 'line',
  data: {
    labels: Array.from({length: 60}, (_, i) => `${60-i}s`),
    datasets: [{
      label: 'Req/s',
      data: [...rpsHistory],
      borderColor: 'rgba(96, 165, 250, 0.9)',
      backgroundColor: 'rgba(96, 165, 250, 0.08)',
      fill: true,
      tension: 0.35,
      pointRadius: 0,
      pointHoverRadius: 4,
      borderWidth: 2,
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(15, 20, 40, 0.9)',
        borderColor: 'rgba(99, 145, 255, 0.3)',
        borderWidth: 1,
        titleFont: { family: 'Inter' },
        bodyFont: { family: 'Inter' },
      }
    },
    scales: {
      x: {
        display: true,
        ticks: { color: '#5a6380', font: { size: 10 }, maxTicksLimit: 10 },
        grid: { color: 'rgba(255,255,255,0.03)' },
      },
      y: {
        display: true,
        beginAtZero: true,
        ticks: { color: '#5a6380', font: { size: 10 }, stepSize: 1 },
        grid: { color: 'rgba(255,255,255,0.03)' },
      }
    }
  }
});

// ── Helpers ───────────────────────────────────────────────
function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function formatUptime(ms) {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const h = Math.floor(m / 60);
  if (h > 0) return `${h}h ${m%60}m`;
  if (m > 0) return `${m}m ${s%60}s`;
  return `${s}s`;
}

function animateValue(el, newVal) {
  const old = el.textContent;
  if (old !== String(newVal)) {
    el.textContent = newVal;
    el.style.transform = 'scale(1.15)';
    setTimeout(() => el.style.transform = 'scale(1)', 200);
  }
}

// ── SSE Connection ───────────────────────────────────────
let es;
function connectSSE() {
  es = new EventSource('/events');
  const dot = document.getElementById('statusDot');
  const txt = document.getElementById('statusText');

  es.onopen = () => {
    dot.className = 'status-dot';
    txt.textContent = 'Live';
  };

  es.onerror = () => {
    dot.className = 'status-dot disconnected';
    txt.textContent = 'Reconnecting...';
  };

  es.addEventListener('metrics', (e) => {
    const d = JSON.parse(e.data);
    const m = d.metrics || {};
    const c = d.cache || {};
    const rl = d.rate_limiter || {};
    const hosts = d.top_hosts || [];

    // Update counters
    ['total','allowed','blocked','cached','rate_limited','errors'].forEach(k => {
      const el = document.getElementById('cnt-' + k);
      if (el && m[k] !== undefined) animateValue(el, m[k]);
    });

    // RPS calculation
    const newTotal = m.total || 0;
    const rps = newTotal - prevTotal;
    prevTotal = newTotal;
    rpsHistory.push(rps);
    rpsHistory.shift();
    rpsChart.data.datasets[0].data = [...rpsHistory];
    rpsChart.update('none');

    // Cache stats
    if (c.current_entries !== undefined) document.getElementById('cache-entries').textContent = c.current_entries;
    if (c.hit_rate !== undefined) document.getElementById('cache-hit-rate').textContent = c.hit_rate + '%';
    if (c.hits !== undefined) document.getElementById('cache-hits').textContent = c.hits;
    if (c.misses !== undefined) document.getElementById('cache-misses').textContent = c.misses;
    if (c.evictions !== undefined) document.getElementById('cache-evictions').textContent = c.evictions;
    if (c.current_bytes !== undefined) document.getElementById('cache-size').textContent = formatBytes(c.current_bytes);

    // Rate limiter
    if (rl.active_buckets !== undefined) {
      document.getElementById('rl-buckets').textContent = rl.active_buckets + ' tracked';
      document.getElementById('rl-info').textContent = `${rl.capacity} cap / ${rl.refill_rate}/s refill`;
      const pct = Math.min(100, (rl.active_buckets / 50) * 100);
      const bar = document.getElementById('rl-bar');
      bar.style.width = pct + '%';
      bar.className = pct > 75 ? 'pool-bar-fill warn' : 'pool-bar-fill';
    }

    // Top hosts
    const tbody = document.getElementById('topHosts');
    if (hosts.length > 0) {
      const maxCount = hosts[0][1];
      tbody.innerHTML = hosts.slice(0, 10).map(([host, count], i) => {
        const pct = (count / maxCount * 100).toFixed(0);
        return `<tr>
          <td class="rank">${i+1}</td>
          <td>${host}<div class="host-bar" style="width:${pct}%"></div></td>
          <td style="text-align:right;font-variant-numeric:tabular-nums;color:var(--text-secondary)">${count}</td>
        </tr>`;
      }).join('');
    }
  });

  es.addEventListener('log', (e) => {
    const entry = JSON.parse(e.data);
    const feed = document.getElementById('logFeed');

    // Remove placeholder
    if (feed.children.length === 1 && !feed.children[0].classList.contains('log-entry')) {
      feed.innerHTML = '';
    }

    const ts = entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : '';
    const action = entry.action || 'PROXY';
    const method = entry.method || '';
    const host = entry.host || '';
    const port = entry.port || '';
    const latency = entry.latency_ms ? entry.latency_ms + 'ms' : '';
    const target = port && ![80,443].includes(port) ? `${host}:${port}` : host;

    const div = document.createElement('div');
    div.className = 'log-entry fade-in';
    div.innerHTML = `
      <span class="time">${ts}</span>
      <span class="method">${method}</span>
      <span class="host">${target}${entry.path || ''}</span>
      <span class="action action-${action}">${action}</span>
      <span class="latency">${latency}</span>
    `;

    feed.insertBefore(div, feed.firstChild);

    // Keep max 50 entries
    while (feed.children.length > 50) feed.removeChild(feed.lastChild);
  });
}

connectSSE();

// Uptime ticker
setInterval(() => {
  document.getElementById('uptime').textContent = '↑ ' + formatUptime(Date.now() - startTime);
}, 1000);
</script>
</body>
</html>"""
