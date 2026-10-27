/**
 * Hoop Grid - Clean 2-Player Basketball XOX Client
 */

// Subtle Web Audio sound cues (clean, minimal)
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
  playSuccess() {
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(520, this.ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(780, this.ctx.currentTime + 0.15);
      gain.gain.setValueAtTime(0.12, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.2);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + 0.2);
    } catch (e) {}
  }
  playTurnover() {
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(220, this.ctx.currentTime);
      osc.frequency.setValueAtTime(180, this.ctx.currentTime + 0.1);
      gain.gain.setValueAtTime(0.15, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.22);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + 0.22);
    } catch (e) {}
  }
  playWin() {
    try {
      this.init();
      if (!this.ctx) return;
      [440, 554.37, 659.25].forEach((freq, idx) => {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = 'sine';
        osc.frequency.value = freq;
        const start = this.ctx.currentTime + idx * 0.1;
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
let selectedLeague = 'nba';
let selectedMinAnswers = 2;
let selectedCell = null;
let searchDebounceTimer = null;
let scores = { X: 0, O: 0 };

// DOM References
const viewMenu = document.getElementById('view-menu');
const viewGame = document.getElementById('view-game');

// Menu Controls
const optNBA = document.getElementById('opt-nba');
const optEuro = document.getElementById('opt-euroleague');
const minAnswersGroup = document.getElementById('min-answers-group');
const inputP1 = document.getElementById('input-p1');
const inputP2 = document.getElementById('input-p2');
const btnStartGame = document.getElementById('btn-start-game');

// Game Navbar & Match bar
const gameLeaguePill = document.getElementById('game-league-pill');
const btnReturnMenu = document.getElementById('btn-return-menu');
const btnResetBoard = document.getElementById('btn-reset-board');
const btnRules = document.getElementById('btn-rules');
const matchCardX = document.getElementById('match-card-x');
const matchCardO = document.getElementById('match-card-o');
const displayNameX = document.getElementById('display-name-x');
const displayNameO = document.getElementById('display-name-o');
const displayScoreX = document.getElementById('display-score-x');
const displayScoreO = document.getElementById('display-score-o');
const matchStatus = document.getElementById('match-status');
const usedTagsContainer = document.getElementById('used-tags-container');

// Selection Modal
const modalDraft = document.getElementById('modal-draft');
const modalCritRow = document.getElementById('modal-crit-row');
const modalCritCol = document.getElementById('modal-crit-col');
const playerSearchInput = document.getElementById('player-search-input');
const dropdownResults = document.getElementById('dropdown-results');
const searchLoader = document.getElementById('search-loader');
const btnConfirmDraft = document.getElementById('btn-confirm-draft');
const btnCancelDraft = document.getElementById('btn-cancel-draft');
const btnCloseDraft = document.getElementById('btn-close-draft');

// Winner Modal
const modalWinner = document.getElementById('modal-winner');
const winnerTitle = document.getElementById('winner-title');
const winnerSub = document.getElementById('winner-sub');
const btnRematch = document.getElementById('btn-rematch');
const btnWinnerMenu = document.getElementById('btn-winner-menu');

// Rules Modal
const modalRules = document.getElementById('modal-rules');
const btnCloseRules = document.getElementById('btn-close-rules');
const btnRulesAck = document.getElementById('btn-rules-ack');

// Initialize
window.addEventListener('DOMContentLoaded', () => {
  bindEvents();
});

function bindEvents() {
  // League Card Toggle
  optNBA.addEventListener('click', () => {
    selectedLeague = 'nba';
    optNBA.classList.add('selected');
    optEuro.classList.remove('selected');
  });

  optEuro.addEventListener('click', () => {
    selectedLeague = 'euroleague';
    optEuro.classList.add('selected');
    optNBA.classList.remove('selected');
  });

  // Min Answers Pill Toggle
  minAnswersGroup.querySelectorAll('.pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      minAnswersGroup.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      selectedMinAnswers = parseInt(btn.dataset.min) || 2;
    });
  });

  // Start Game
  btnStartGame.addEventListener('click', () => {
    startNewGame();
  });

  // Navigation
  btnReturnMenu.addEventListener('click', () => {
    viewGame.classList.add('hidden');
    viewMenu.classList.remove('hidden');
  });

  btnResetBoard.addEventListener('click', () => {
    startNewGame(false);
  });

  // Rules Dialog
  btnRules.addEventListener('click', () => openModal(modalRules));
  btnCloseRules.addEventListener('click', () => closeModal(modalRules));
  btnRulesAck.addEventListener('click', () => closeModal(modalRules));

  // Winner Actions
  btnRematch.addEventListener('click', () => {
    closeModal(modalWinner);
    startNewGame(false);
  });
  btnWinnerMenu.addEventListener('click', () => {
    closeModal(modalWinner);
    viewGame.classList.add('hidden');
    viewMenu.classList.remove('hidden');
  });

  // Draft Modal Handlers
  btnCancelDraft.addEventListener('click', () => closeModal(modalDraft));
  btnCloseDraft.addEventListener('click', () => closeModal(modalDraft));

  // Cell clicks
  document.querySelectorAll('.board-box').forEach(box => {
    box.addEventListener('click', () => {
      const r = parseInt(box.dataset.row);
      const c = parseInt(box.dataset.col);
      handleBoxClick(r, c);
    });
  });

  // Search input autocomplete
  playerSearchInput.addEventListener('input', (e) => {
    const query = e.target.value.trim();
    btnConfirmDraft.disabled = query.length === 0;

    clearTimeout(searchDebounceTimer);
    if (query.length < 2) {
      dropdownResults.innerHTML = '';
      dropdownResults.classList.remove('visible');
      return;
    }

    searchDebounceTimer = setTimeout(() => {
      fetchSuggestions(query);
    }, 180);
  });

  playerSearchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !btnConfirmDraft.disabled) {
      e.preventDefault();
      confirmPlayerPick(playerSearchInput.value.trim());
    }
  });

  btnConfirmDraft.addEventListener('click', () => {
    confirmPlayerPick(playerSearchInput.value.trim());
  });
}

async function startNewGame(switchView = true) {
  const p1Name = inputP1.value.trim() || 'Player 1';
  const p2Name = inputP2.value.trim() || 'Player 2';

  setStatus('Generating balanced grid with guaranteed answers...', 'normal');
  clearHighlights();

  try {
    const res = await fetch('/api/new-game', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        league: selectedLeague,
        player1_name: p1Name,
        player2_name: p2Name,
        min_answers: selectedMinAnswers
      })
    });

    if (!res.ok) throw new Error('Failed to generate match');
    currentGame = await res.json();

    if (switchView) {
      viewMenu.classList.add('hidden');
      viewGame.classList.remove('hidden');
    }

    gameLeaguePill.textContent = currentGame.league;
    displayNameX.textContent = currentGame.player1_name;
    displayNameO.textContent = currentGame.player2_name;
    displayScoreX.textContent = `${scores.X} wins`;
    displayScoreO.textContent = `${scores.O} wins`;

    renderBoard(currentGame);
    setStatus(`${currentGame.player1_name}'s turn (X). Choose an empty square.`, 'normal');
  } catch (err) {
    console.error(err);
    setStatus('Error connecting to backend server.', 'error');
  }
}

function renderBoard(game) {
  // Column criteria headers
  game.col_criteria.forEach((crit, idx) => {
    const typeEl = document.getElementById(`col-type-${idx}`);
    const titleEl = document.getElementById(`col-title-${idx}`);
    if (typeEl) typeEl.textContent = crit.type.toUpperCase();
    if (titleEl) titleEl.textContent = crit.display;
  });

  // Row criteria headers
  game.row_criteria.forEach((crit, idx) => {
    const typeEl = document.getElementById(`row-type-${idx}`);
    const titleEl = document.getElementById(`row-title-${idx}`);
    if (typeEl) typeEl.textContent = crit.type.toUpperCase();
    if (titleEl) titleEl.textContent = crit.display;
  });

  // Grid boxes
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 3; c++) {
      const cellData = game.grid[r][c];
      const boxEl = document.getElementById(`box-${r}-${c}`);
      const contentEl = boxEl.querySelector('.box-content');

      boxEl.className = 'board-box';
      contentEl.innerHTML = '';

      if (cellData.claimed_by) {
        boxEl.classList.add('claimed', `claimed-${cellData.claimed_by.toLowerCase()}`);
        contentEl.innerHTML = `
          <div class="box-mark">${cellData.claimed_by}</div>
          <div class="box-player">${escapeHtml(cellData.player_name || '')}</div>
          <div class="box-subtitle">${escapeHtml(cellData.player_country || '')}</div>
        `;
      } else {
        contentEl.innerHTML = `<span class="box-empty-icon">+</span>`;
      }
    }
  }

  // Active turn card highlight
  if (game.current_player === 'X') {
    matchCardX.classList.add('active-turn');
    matchCardO.classList.remove('active-turn');
  } else {
    matchCardO.classList.add('active-turn');
    matchCardX.classList.remove('active-turn');
  }

  // Used players
  renderUsedTray(game.used_players);

  // Winning line
  if (game.winning_line) {
    highlightLine(game.winning_line);
  }
}

function renderUsedTray(players) {
  if (!players || players.length === 0) {
    usedTagsContainer.innerHTML = '<span class="tray-empty">None</span>';
    return;
  }
  usedTagsContainer.innerHTML = players.map(p => `
    <span class="tray-chip">${escapeHtml(p)}</span>
  `).join('');
}

function handleBoxClick(row, col) {
  if (!currentGame || currentGame.status === 'finished') return;

  const cell = currentGame.grid[row][col];
  if (cell.claimed_by) {
    setStatus('This box is already claimed. Pick an open square.', 'error');
    return;
  }

  selectedCell = { row, col };
  const rCrit = currentGame.row_criteria[row];
  const cCrit = currentGame.col_criteria[col];

  modalCritRow.textContent = rCrit.display;
  modalCritCol.textContent = cCrit.display;

  playerSearchInput.value = '';
  dropdownResults.innerHTML = '';
  dropdownResults.classList.remove('visible');
  btnConfirmDraft.disabled = true;

  openModal(modalDraft);
  setTimeout(() => playerSearchInput.focus(), 80);
}

async function fetchSuggestions(query) {
  searchLoader.style.display = 'block';
  try {
    const res = await fetch(`/api/search-players?league=${selectedLeague}&q=${encodeURIComponent(query)}`);
    const players = await res.json();
    searchLoader.style.display = 'none';

    if (players.length === 0) {
      dropdownResults.innerHTML = '<div class="dropdown-item"><em>No players found in database</em></div>';
      dropdownResults.classList.add('visible');
      return;
    }

    dropdownResults.innerHTML = players.map(p => `
      <div class="dropdown-item" data-name="${escapeHtml(p.name)}">
        <span class="item-name">${escapeHtml(p.name)}</span>
        <span class="item-sub">${escapeHtml(p.country)}</span>
      </div>
    `).join('');
    dropdownResults.classList.add('visible');

    dropdownResults.querySelectorAll('.dropdown-item').forEach(item => {
      item.addEventListener('click', () => {
        const name = item.dataset.name;
        if (name) {
          playerSearchInput.value = name;
          btnConfirmDraft.disabled = false;
          confirmPlayerPick(name);
        }
      });
    });
  } catch (err) {
    searchLoader.style.display = 'none';
  }
}

async function confirmPlayerPick(playerName) {
  if (!playerName || !selectedCell) return;

  closeModal(modalDraft);
  setStatus(`Validating ${playerName}...`, 'normal');

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
      sfx.playSuccess();
      setStatus(result.message, 'success');

      const gRes = await fetch(`/api/game/${currentGame.game_id}`);
      currentGame = await gRes.json();
      renderBoard(currentGame);

      if (result.game_over) {
        handleGameOver(result);
      }
    } else {
      // Turnover / missed pick
      sfx.playTurnover();
      setStatus(result.message, 'error');

      const gRes = await fetch(`/api/game/${currentGame.game_id}`);
      currentGame = await gRes.json();
      renderBoard(currentGame);
    }
  } catch (err) {
    console.error(err);
    setStatus('Connection error submitting pick.', 'error');
  }
}

function handleGameOver(result) {
  if (result.winner === 'X' || result.winner === 'O') {
    sfx.playWin();
    scores[result.winner]++;
    displayScoreX.textContent = `${scores.X} wins`;
    displayScoreO.textContent = `${scores.O} wins`;

    const winnerName = result.winner === 'X' ? currentGame.player1_name : currentGame.player2_name;
    winnerTitle.textContent = `${winnerName.toUpperCase()} WINS`;
    winnerSub.textContent = `Three in a row! Claimed by Player ${result.winner}.`;
  } else {
    winnerTitle.textContent = `MATCH DRAW`;
    winnerSub.textContent = `All 9 grid boxes drafted with no 3 in a row.`;
  }

  setTimeout(() => {
    openModal(modalWinner);
  }, 750);
}

function highlightLine(line) {
  line.forEach(([r, c]) => {
    const el = document.getElementById(`box-${r}-${c}`);
    if (el) el.classList.add('winning-box');
  });
}

function clearHighlights() {
  document.querySelectorAll('.board-box').forEach(el => {
    el.classList.remove('winning-box');
  });
}

function setStatus(msg, type = 'normal') {
  matchStatus.textContent = msg;
  matchStatus.className = 'match-status-text ' + (type !== 'normal' ? type : '');
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
