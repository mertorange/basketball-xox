/**
 * Hoop Grid - Clean 2-Player Basketball XOX with Shot Clock
 */

class SoundFX {
  constructor() {
    this.ctx = null;
  }

  init() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) this.ctx = new AudioCtx();
    }
  }

  // Warning beep for last 5 seconds of shot clock
  playClockBeep() {
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'square';
      osc.frequency.setValueAtTime(880, this.ctx.currentTime); // High-pitched A5 warning
      gain.gain.setValueAtTime(0.08, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.08);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + 0.08);
    } catch (e) {}
  }

  // Authentic Basketball Arena Buzzer Horn (Dual-tone sawtooth)
  playArenaBuzzer() {
    try {
      this.init();
      if (!this.ctx) return;
      const t = this.ctx.currentTime;
      const osc1 = this.ctx.createOscillator();
      const osc2 = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc1.type = 'sawtooth';
      osc2.type = 'sawtooth';
      osc1.frequency.setValueAtTime(146.83, t); // D3
      osc2.frequency.setValueAtTime(220.00, t); // A3

      gain.gain.setValueAtTime(0.25, t);
      gain.gain.setValueAtTime(0.25, t + 0.5);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.7);

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(this.ctx.destination);

      osc1.start(t);
      osc2.start(t);
      osc1.stop(t + 0.7);
      osc2.stop(t + 0.7);
    } catch (e) {}
  }

  // Net swish / basket made
  playScore() {
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(480, this.ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(720, this.ctx.currentTime + 0.15);
      gain.gain.setValueAtTime(0.12, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.2);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + 0.2);
    } catch (e) {}
  }

  // Turnover / wrong pick
  playTurnover() {
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(220, this.ctx.currentTime);
      osc.frequency.setValueAtTime(160, this.ctx.currentTime + 0.1);
      gain.gain.setValueAtTime(0.15, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.25);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + 0.25);
    } catch (e) {}
  }

  // Win fanfare
  playWin() {
    try {
      this.init();
      if (!this.ctx) return;
      [523.25, 659.25, 783.99, 1046.50].forEach((freq, idx) => {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = 'sine';
        osc.frequency.value = freq;
        const start = this.ctx.currentTime + idx * 0.12;
        gain.gain.setValueAtTime(0.15, start);
        gain.gain.exponentialRampToValueAtTime(0.001, start + 0.35);
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(start);
        osc.stop(start + 0.35);
      });
    } catch (e) {}
  }
}

const sfx = new SoundFX();

// Game State
let currentGame = null;
let currentLeague = 'nba';
let currentShotClockSetting = 60; // 30, 60, 120, 0
let currentMinAnswers = 2;
let selectedCell = null;
let scores = { X: 0, O: 0 };
let searchDebounce = null;

// Timer State
let timerSecondsLeft = 60;
let timerInterval = null;

// DOM Elements
const screenMenu = document.getElementById('screen-menu');
const screenGame = document.getElementById('screen-game');

// Menu Controls
const btnOptNBA = document.getElementById('btn-opt-nba');
const btnOptEuro = document.getElementById('btn-opt-euro');
const shotclockRow = document.getElementById('shotclock-row');
const densityRow = document.getElementById('density-row');
const nameP1 = document.getElementById('name-p1');
const nameP2 = document.getElementById('name-p2');
const btnLaunchGame = document.getElementById('btn-launch-game');

// Game Elements
const headLeagueTag = document.getElementById('head-league-tag');
const btnGameRules = document.getElementById('btn-game-rules');
const btnGameNew = document.getElementById('btn-game-new');
const btnGameExit = document.getElementById('btn-game-exit');
const panelX = document.getElementById('panel-x');
const panelO = document.getElementById('panel-o');
const textNameX = document.getElementById('text-name-x');
const textNameO = document.getElementById('text-name-o');
const textScoreX = document.getElementById('text-score-x');
const textScoreO = document.getElementById('text-score-o');
const gameStatusText = document.getElementById('game-status-text');
const shotclockDisplay = document.getElementById('shotclock-display');
const shotclockNumber = document.getElementById('shotclock-number');
const modalShotclock = document.getElementById('modal-shotclock');
const modalClockNum = document.getElementById('modal-clock-num');
const usedPlayersTray = document.getElementById('used-players-tray');

// Draft Modal
const modalSelect = document.getElementById('modal-select');
const reqRow = document.getElementById('req-row');
const reqCol = document.getElementById('req-col');
const searchPlayerInput = document.getElementById('search-player-input');
const searchResultsList = document.getElementById('search-results-list');
const btnConfirmSelect = document.getElementById('btn-confirm-select');
const btnCancelSelect = document.getElementById('btn-cancel-select');

// Game Over Modal
const modalGameover = document.getElementById('modal-gameover');
const goTitle = document.getElementById('go-title');
const goDesc = document.getElementById('go-desc');
const btnRematchMatch = document.getElementById('btn-rematch-match');
const btnReturnMenuGo = document.getElementById('btn-return-menu-go');

// Rules Modal
const modalRulesPopup = document.getElementById('modal-rules-popup');
const btnAckRules = document.getElementById('btn-ack-rules');

// Init
window.addEventListener('DOMContentLoaded', () => {
  setupHandlers();
});

function setupHandlers() {
  // League Toggle
  btnOptNBA.addEventListener('click', () => {
    currentLeague = 'nba';
    btnOptNBA.classList.add('active');
    btnOptEuro.classList.remove('active');
  });

  btnOptEuro.addEventListener('click', () => {
    currentLeague = 'euroleague';
    btnOptEuro.classList.add('active');
    btnOptNBA.classList.remove('active');
  });

  // Shot Clock Toggle
  shotclockRow.querySelectorAll('.option-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      shotclockRow.querySelectorAll('.option-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentShotClockSetting = parseInt(btn.dataset.time) || 0;
    });
  });

  // Density Toggle
  densityRow.querySelectorAll('.option-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      densityRow.querySelectorAll('.option-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentMinAnswers = parseInt(btn.dataset.density) || 2;
    });
  });

  // Launch Game
  btnLaunchGame.addEventListener('click', () => {
    startNewGame(true);
  });

  // Header Nav
  btnGameExit.addEventListener('click', () => {
    stopShotClock();
    screenGame.classList.add('hidden');
    screenMenu.classList.remove('hidden');
  });

  btnGameNew.addEventListener('click', () => {
    startNewGame(false);
  });

  btnGameRules.addEventListener('click', () => openModal(modalRulesPopup));
  btnAckRules.addEventListener('click', () => closeModal(modalRulesPopup));

  // Rematch / Gameover
  btnRematchMatch.addEventListener('click', () => {
    closeModal(modalGameover);
    startNewGame(false);
  });

  btnReturnMenuGo.addEventListener('click', () => {
    closeModal(modalGameover);
    stopShotClock();
    screenGame.classList.add('hidden');
    screenMenu.classList.remove('hidden');
  });

  // Modal Cancel
  btnCancelSelect.addEventListener('click', () => {
    closeModal(modalSelect);
  });

  // Cell clicks
  document.querySelectorAll('.grid-box').forEach(box => {
    box.addEventListener('click', () => {
      const r = parseInt(box.dataset.row);
      const c = parseInt(box.dataset.col);
      handleCellClicked(r, c);
    });
  });

  // Search input
  searchPlayerInput.addEventListener('input', (e) => {
    const val = e.target.value.trim();
    btnConfirmSelect.disabled = val.length === 0;

    clearTimeout(searchDebounce);
    if (val.length < 2) {
      searchResultsList.innerHTML = '';
      searchResultsList.classList.remove('visible');
      return;
    }

    searchDebounce = setTimeout(() => {
      fetchPlayerAutocomplete(val);
    }, 150);
  });

  searchPlayerInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !btnConfirmSelect.disabled) {
      e.preventDefault();
      confirmPick(searchPlayerInput.value.trim());
    }
  });

  btnConfirmSelect.addEventListener('click', () => {
    confirmPick(searchPlayerInput.value.trim());
  });
}

async function startNewGame(isNewMatch = true) {
  stopShotClock();
  clearWinningHighlights();

  const p1 = nameP1.value.trim() || 'Player 1';
  const p2 = nameP2.value.trim() || 'Player 2';

  setStatus('Generating grid...', 'normal');

  try {
    const res = await fetch('/api/new-game', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        league: currentLeague,
        player1_name: p1,
        player2_name: p2,
        min_answers: currentMinAnswers,
        shot_clock: currentShotClockSetting
      })
    });

    if (!res.ok) throw new Error('Failed to start game');
    currentGame = await res.json();

    if (isNewMatch) {
      screenMenu.classList.add('hidden');
      screenGame.classList.remove('hidden');
    }

    headLeagueTag.textContent = currentGame.league;
    textNameX.textContent = currentGame.player1_name;
    textNameO.textContent = currentGame.player2_name;
    textScoreX.textContent = `${scores.X} wins`;
    textScoreO.textContent = `${scores.O} wins`;

    renderBoard(currentGame);
    setStatus(`${currentGame.player1_name}'s turn (X)`, 'normal');

    startShotClock();
  } catch (err) {
    console.error(err);
    setStatus('Connection error starting game.', 'error');
  }
}

function renderBoard(game) {
  // Render Col headers
  game.col_criteria.forEach((crit, i) => {
    const badge = document.getElementById(`ch-type-${i}`);
    const text = document.getElementById(`ch-text-${i}`);
    if (badge) badge.textContent = crit.type.toUpperCase();
    if (text) text.textContent = crit.display;
  });

  // Render Row headers
  game.row_criteria.forEach((crit, i) => {
    const badge = document.getElementById(`rh-type-${i}`);
    const text = document.getElementById(`rh-text-${i}`);
    if (badge) badge.textContent = crit.type.toUpperCase();
    if (text) text.textContent = crit.display;
  });

  // Render 3x3 boxes
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 3; c++) {
      const data = game.grid[r][c];
      const box = document.getElementById(`box-${r}-${c}`);
      const body = box.querySelector('.box-body');

      box.className = 'grid-box';
      body.innerHTML = '';

      if (data.claimed_by) {
        box.classList.add('claimed', `claimed-${data.claimed_by.toLowerCase()}`);
        body.innerHTML = `
          <div class="box-token">${data.claimed_by}</div>
          <div class="box-player-name">${escapeHtml(data.player_name || '')}</div>
          <div class="box-player-sub">${escapeHtml(data.player_country || '')}</div>
        `;
      }
    }
  }

  // Active Player Highlight
  if (game.current_player === 'X') {
    panelX.classList.add('active-turn');
    panelO.classList.remove('active-turn');
  } else {
    panelO.classList.add('active-turn');
    panelX.classList.remove('active-turn');
  }

  // Used drafted list
  renderUsedTray(game.used_players);

  // Winning cells
  if (game.winning_line) {
    highlightWinner(game.winning_line);
  }
}

function renderUsedTray(players) {
  if (!players || players.length === 0) {
    usedPlayersTray.innerHTML = '<span class="empty-tray-text">None</span>';
    return;
  }
  usedPlayersTray.innerHTML = players.map(p => `
    <span class="used-chip">${escapeHtml(p)}</span>
  `).join('');
}

/* ============================================================
   SHOT CLOCK (TIMER) ENGINE
   ============================================================ */

function startShotClock() {
  stopShotClock();

  if (currentShotClockSetting <= 0) {
    shotclockDisplay.style.display = 'none';
    modalShotclock.style.display = 'none';
    return;
  }

  shotclockDisplay.style.display = 'flex';
  modalShotclock.style.display = 'block';

  timerSecondsLeft = currentShotClockSetting;
  updateShotClockUI();

  timerInterval = setInterval(() => {
    if (!currentGame || currentGame.status === 'finished') {
      stopShotClock();
      return;
    }

    timerSecondsLeft--;
    updateShotClockUI();

    // Sound effect on last 5 seconds (5, 4, 3, 2, 1)
    if (timerSecondsLeft <= 5 && timerSecondsLeft > 0) {
      sfx.playClockBeep();
    }

    // Shot clock expiration
    if (timerSecondsLeft <= 0) {
      handleShotClockExpired();
    }
  }, 1000);
}

function stopShotClock() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
  shotclockDisplay.classList.remove('warning');
  modalShotclock.classList.remove('warning');
}

function updateShotClockUI() {
  shotclockNumber.textContent = timerSecondsLeft;
  modalClockNum.textContent = timerSecondsLeft;

  if (timerSecondsLeft <= 5) {
    shotclockDisplay.classList.add('warning');
    modalShotclock.classList.add('warning');
  } else {
    shotclockDisplay.classList.remove('warning');
    modalShotclock.classList.remove('warning');
  }
}

async function handleShotClockExpired() {
  stopShotClock();
  sfx.playArenaBuzzer();
  closeModal(modalSelect);

  setStatus('Shot clock violation! Turnover.', 'error');

  try {
    const res = await fetch('/api/shot-clock-violation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ game_id: currentGame.game_id })
    });

    if (res.ok) {
      const gRes = await fetch(`/api/game/${currentGame.game_id}`);
      currentGame = await gRes.json();
      renderBoard(currentGame);

      const nextName = currentGame.current_player === 'X' ? currentGame.player1_name : currentGame.player2_name;
      setStatus(`Shot clock turnover! ${nextName}'s turn (${currentGame.current_player})`, 'error');

      // Restart shot clock for next player
      startShotClock();
    }
  } catch (err) {
    console.error(err);
  }
}

/* ============================================================
   BOX CLICK & MOVE DRAFTING
   ============================================================ */

function handleCellClicked(row, col) {
  if (!currentGame || currentGame.status === 'finished') return;

  const cell = currentGame.grid[row][col];
  if (cell.claimed_by) {
    setStatus('Box already claimed. Pick an open square.', 'error');
    return;
  }

  selectedCell = { row, col };
  const rCrit = currentGame.row_criteria[row];
  const cCrit = currentGame.col_criteria[col];

  reqRow.textContent = rCrit.display;
  reqCol.textContent = cCrit.display;

  searchPlayerInput.value = '';
  searchResultsList.innerHTML = '';
  searchResultsList.classList.remove('visible');
  btnConfirmSelect.disabled = true;

  openModal(modalSelect);
  setTimeout(() => searchPlayerInput.focus(), 60);
}

async function fetchPlayerAutocomplete(query) {
  try {
    const res = await fetch(`/api/search-players?league=${currentLeague}&q=${encodeURIComponent(query)}`);
    const players = await res.json();

    if (players.length === 0) {
      searchResultsList.innerHTML = '<div class="result-row"><em>No player found in database</em></div>';
      searchResultsList.classList.add('visible');
      return;
    }

    searchResultsList.innerHTML = players.map(p => `
      <div class="result-row" data-name="${escapeHtml(p.name)}">
        <span class="res-name">${escapeHtml(p.name)}</span>
        <span class="res-sub">${escapeHtml(p.country)}</span>
      </div>
    `).join('');
    searchResultsList.classList.add('visible');

    searchResultsList.querySelectorAll('.result-row').forEach(row => {
      row.addEventListener('click', () => {
        const name = row.dataset.name;
        if (name) {
          searchPlayerInput.value = name;
          btnConfirmSelect.disabled = false;
          confirmPick(name);
        }
      });
    });
  } catch (err) {}
}

async function confirmPick(playerName) {
  if (!playerName || !selectedCell) return;

  closeModal(modalSelect);
  setStatus(`Checking ${playerName}...`, 'normal');

  try {
    const res = await fetch('/api/move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        game_id: currentGame.game_id,
        row: selectedCell.row,
        col: selectedCell.col,
        player_name: playerName
      })
    });

    const result = await res.json();

    if (result.success) {
      sfx.playScore();
      setStatus(result.message, 'success');

      const gRes = await fetch(`/api/game/${currentGame.game_id}`);
      currentGame = await gRes.json();
      renderBoard(currentGame);

      if (result.game_over) {
        stopShotClock();
        handleGameOver(result);
      } else {
        // Reset shot clock for next player
        startShotClock();
      }
    } else {
      // Turnover
      sfx.playTurnover();
      setStatus(result.message, 'error');

      const gRes = await fetch(`/api/game/${currentGame.game_id}`);
      currentGame = await gRes.json();
      renderBoard(currentGame);

      // Reset shot clock for next player
      startShotClock();
    }
  } catch (err) {
    console.error(err);
    setStatus('Connection error submitting pick.', 'error');
  }
}

function handleGameOver(result) {
  stopShotClock();

  if (result.winner === 'X' || result.winner === 'O') {
    sfx.playWin();
    scores[result.winner]++;
    textScoreX.textContent = `${scores.X} wins`;
    textScoreO.textContent = `${scores.O} wins`;

    const winnerName = result.winner === 'X' ? currentGame.player1_name : currentGame.player2_name;
    goTitle.textContent = `${winnerName.toUpperCase()} WINS`;
    goDesc.textContent = `Three in a row! Connected by Player ${result.winner}.`;
  } else {
    goTitle.textContent = `MATCH DRAW`;
    goDesc.textContent = `All 9 grid boxes drafted with no 3 in a row.`;
  }

  setTimeout(() => {
    openModal(modalGameover);
  }, 600);
}

function highlightWinner(line) {
  line.forEach(([r, c]) => {
    const el = document.getElementById(`box-${r}-${c}`);
    if (el) el.classList.add('winning-cell');
  });
}

function clearWinningHighlights() {
  document.querySelectorAll('.grid-box').forEach(el => {
    el.classList.remove('winning-cell');
  });
}

function setStatus(msg, type = 'normal') {
  gameStatusText.textContent = msg;
  gameStatusText.className = 'game-status ' + (type !== 'normal' ? type : '');
}

function openModal(modal) {
  modal.classList.add('active');
}

function closeModal(modal) {
  modal.classList.remove('active');
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
