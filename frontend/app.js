/**
 * Basketball XOX - Interactive Client Application
 */

// Web Audio sound synthesizer (Zero external dependencies)
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

  playSwish() {
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(440, this.ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(880, this.ctx.currentTime + 0.25);
      gain.gain.setValueAtTime(0.25, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + 0.25);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + 0.25);
    } catch (e) {
      // Audio autoplay policy fallback
    }
  }

  playBuzzer() {
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(160, this.ctx.currentTime);
      osc.frequency.setValueAtTime(140, this.ctx.currentTime + 0.15);
      gain.gain.setValueAtTime(0.2, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + 0.35);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + 0.35);
    } catch (e) {}
  }

  playFanfare() {
    try {
      this.init();
      if (!this.ctx) return;
      const notes = [523.25, 659.25, 783.99, 1046.50]; // C E G C
      notes.forEach((freq, idx) => {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.frequency.value = freq;
        const start = this.ctx.currentTime + idx * 0.12;
        gain.gain.setValueAtTime(0.2, start);
        gain.gain.exponentialRampToValueAtTime(0.01, start + 0.3);
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(start);
        osc.stop(start + 0.3);
      });
    } catch (e) {}
  }
}

const sfx = new SoundFX();

// App State
let currentGame = null;
let currentLeague = 'nba';
let selectedCell = null;
let searchDebounceTimer = null;
let scores = { X: 0, O: 0 };

// DOM Elements
const gridBoard = document.getElementById('game-grid');
const cardPlayerX = document.getElementById('card-player-x');
const cardPlayerO = document.getElementById('card-player-o');
const scorePlayerX = document.getElementById('score-player-x');
const scorePlayerO = document.getElementById('score-player-o');
const statusAlert = document.getElementById('status-alert');
const statusMessage = document.getElementById('status-message');
const statusIcon = document.getElementById('status-icon');
const usedPlayersList = document.getElementById('used-players-list');

// League Buttons
const btnLeagueNBA = document.getElementById('btn-league-nba');
const btnLeagueEuro = document.getElementById('btn-league-euro');
const btnNewGame = document.getElementById('btn-new-game');
const btnRules = document.getElementById('btn-rules');

// Player Modal
const playerModal = document.getElementById('player-modal');
const modalReqRow = document.getElementById('modal-req-row');
const modalReqCol = document.getElementById('modal-req-col');
const playerInput = document.getElementById('player-input');
const suggestionsList = document.getElementById('suggestions-list');
const btnSubmitPlayer = document.getElementById('btn-submit-player');
const btnCancelMove = document.getElementById('btn-cancel-move');
const btnCloseModal = document.getElementById('btn-close-modal');
const searchSpinner = document.getElementById('search-spinner');

// Game Over Modal
const gameoverModal = document.getElementById('gameover-modal');
const gameoverTitle = document.getElementById('gameover-title');
const gameoverDesc = document.getElementById('gameover-desc');
const btnPlayAgain = document.getElementById('btn-play-again');

// Rules Modal
const rulesModal = document.getElementById('rules-modal');
const btnCloseRules = document.getElementById('btn-close-rules');
const btnRulesOk = document.getElementById('btn-rules-ok');

// Initialize
window.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  startNewGame();
});

function setupEventListeners() {
  btnLeagueNBA.addEventListener('click', () => switchLeague('nba'));
  btnLeagueEuro.addEventListener('click', () => switchLeague('euroleague'));
  btnNewGame.addEventListener('click', () => startNewGame());
  btnPlayAgain.addEventListener('click', () => {
    closeModal(gameoverModal);
    startNewGame();
  });

  // Modal close handlers
  btnCancelMove.addEventListener('click', () => closeModal(playerModal));
  btnCloseModal.addEventListener('click', () => closeModal(playerModal));

  btnRules.addEventListener('click', () => openModal(rulesModal));
  btnCloseRules.addEventListener('click', () => closeModal(rulesModal));
  btnRulesOk.addEventListener('click', () => closeModal(rulesModal));

  // Cell clicks
  document.querySelectorAll('.grid-cell').forEach(cell => {
    cell.addEventListener('click', () => {
      const row = parseInt(cell.dataset.row);
      const col = parseInt(cell.dataset.col);
      handleCellClick(row, col);
    });
  });

  // Search input autocomplete
  playerInput.addEventListener('input', (e) => {
    const val = e.target.value.trim();
    btnSubmitPlayer.disabled = val.length === 0;

    clearTimeout(searchDebounceTimer);
    if (val.length < 2) {
      suggestionsList.innerHTML = '';
      suggestionsList.classList.remove('visible');
      return;
    }

    searchDebounceTimer = setTimeout(() => {
      fetchSuggestions(val);
    }, 200);
  });

  playerInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !btnSubmitPlayer.disabled) {
      e.preventDefault();
      confirmDraft(playerInput.value.trim());
    }
  });

  btnSubmitPlayer.addEventListener('click', () => {
    confirmDraft(playerInput.value.trim());
  });
}

function switchLeague(league) {
  if (currentLeague === league) return;
  currentLeague = league;
  btnLeagueNBA.classList.toggle('active', league === 'nba');
  btnLeagueEuro.classList.toggle('active', league === 'euroleague');
  startNewGame();
}

async function startNewGame() {
  setStatus('Setting up a fresh basketball grid...', 'info', '🏀');
  clearBoardHighlights();

  try {
    const res = await fetch('/api/new-game', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        league: currentLeague,
        player1_name: 'Player 1',
        player2_name: 'Player 2'
      })
    });

    if (!res.ok) throw new Error('Failed to create new game');
    currentGame = await res.json();
    renderGame(currentGame);
    setStatus(`Game started! Player 1 (X) turn. Click an open box!`, 'info', '🏀');
  } catch (err) {
    console.error(err);
    setStatus('Error connecting to backend server.', 'error', '⚠️');
  }
}

function renderGame(game) {
  // Render Headers
  game.col_criteria.forEach((crit, idx) => {
    const textEl = document.getElementById(`col-text-${idx}`);
    if (textEl) textEl.textContent = crit.display;
  });

  game.row_criteria.forEach((crit, idx) => {
    const textEl = document.getElementById(`row-text-${idx}`);
    if (textEl) textEl.textContent = crit.display;
  });

  // Render Grid Cells
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 3; c++) {
      const cellData = game.grid[r][c];
      const cellEl = document.getElementById(`cell-${r}-${c}`);
      const innerEl = cellEl.querySelector('.cell-inner');

      cellEl.className = 'grid-cell';
      innerEl.innerHTML = '';

      if (cellData.claimed_by) {
        cellEl.classList.add('claimed', `claimed-${cellData.claimed_by.toLowerCase()}`);
        innerEl.innerHTML = `
          <div class="cell-badge">${cellData.claimed_by}</div>
          <div class="cell-player-name">${escapeHtml(cellData.player_name || '')}</div>
          <div class="cell-country">${escapeHtml(cellData.player_country || '')}</div>
        `;
      } else {
        innerEl.innerHTML = `<span class="cell-placeholder">➕</span>`;
      }
    }
  }

  // Update Turn Banner
  updateTurnDisplay(game.current_player);

  // Update Used Players
  renderUsedPlayers(game.used_players);

  // Highlight Winning line if present
  if (game.winning_line) {
    highlightWinningLine(game.winning_line);
  }
}

function updateTurnDisplay(currentPlayer) {
  if (currentPlayer === 'X') {
    cardPlayerX.classList.add('active-turn');
    cardPlayerO.classList.remove('active-turn');
  } else {
    cardPlayerO.classList.add('active-turn');
    cardPlayerX.classList.remove('active-turn');
  }
}

function renderUsedPlayers(players) {
  if (!players || players.length === 0) {
    usedPlayersList.innerHTML = '<span class="empty-note">None yet.</span>';
    return;
  }
  usedPlayersList.innerHTML = players.map(p => `
    <span class="player-chip">🏀 ${escapeHtml(p)}</span>
  `).join('');
}

function handleCellClick(row, col) {
  if (!currentGame || currentGame.status === 'finished') return;

  const cell = currentGame.grid[row][col];
  if (cell.claimed_by) {
    setStatus('This square is already claimed! Pick another empty cell.', 'error', '🚫');
    return;
  }

  selectedCell = { row, col };
  const rCrit = currentGame.row_criteria[row];
  const cCrit = currentGame.col_criteria[col];

  modalReqRow.textContent = rCrit.display;
  modalReqCol.textContent = cCrit.display;

  playerInput.value = '';
  suggestionsList.innerHTML = '';
  suggestionsList.classList.remove('visible');
  btnSubmitPlayer.disabled = true;

  openModal(playerModal);
  setTimeout(() => playerInput.focus(), 100);
}

async function fetchSuggestions(query) {
  searchSpinner.style.display = 'block';
  try {
    const res = await fetch(`/api/search-players?league=${currentLeague}&q=${encodeURIComponent(query)}`);
    const players = await res.json();
    searchSpinner.style.display = 'none';

    if (players.length === 0) {
      suggestionsList.innerHTML = '<div class="suggestion-item"><em>No players found matching</em></div>';
      suggestionsList.classList.add('visible');
      return;
    }

    suggestionsList.innerHTML = players.map(p => `
      <div class="suggestion-item" data-name="${escapeHtml(p.name)}">
        <span class="suggestion-name">${escapeHtml(p.name)}</span>
        <span class="suggestion-country">${escapeHtml(p.country)}</span>
      </div>
    `).join('');
    suggestionsList.classList.add('visible');

    // Attach click events
    suggestionsList.querySelectorAll('.suggestion-item').forEach(item => {
      item.addEventListener('click', () => {
        const name = item.dataset.name;
        if (name) {
          playerInput.value = name;
          btnSubmitPlayer.disabled = false;
          confirmDraft(name);
        }
      });
    });
  } catch (err) {
    searchSpinner.style.display = 'none';
  }
}

async function confirmDraft(playerName) {
  if (!playerName || !selectedCell) return;

  closeModal(playerModal);
  setStatus(`Checking if ${playerName} satisfies the criteria...`, 'info', '⏳');

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
      sfx.playSwish();
      setStatus(result.message, 'success', '🎯');

      // Refresh game state
      const gRes = await fetch(`/api/game/${currentGame.game_id}`);
      currentGame = await gRes.json();
      renderGame(currentGame);

      if (result.game_over) {
        handleGameOver(result);
      }
    } else {
      // Missed / foul
      sfx.playBuzzer();
      setStatus(result.message, 'error', '❌');

      // Refresh to reflect switched turn
      const gRes = await fetch(`/api/game/${currentGame.game_id}`);
      currentGame = await gRes.json();
      renderGame(currentGame);
    }
  } catch (err) {
    console.error(err);
    setStatus('Connection error while submitting move.', 'error', '⚠️');
  }
}

function handleGameOver(result) {
  if (result.winner === 'X' || result.winner === 'O') {
    sfx.playFanfare();
    scores[result.winner]++;
    scorePlayerX.textContent = `${scores.X} Wins`;
    scorePlayerO.textContent = `${scores.O} Wins`;

    gameoverTitle.textContent = `PLAYER ${result.winner} WINS!`;
    gameoverDesc.textContent = `Spectacular 3-in-a-row victory!`;
  } else {
    gameoverTitle.textContent = `IT'S A DRAW!`;
    gameoverDesc.textContent = `All 9 grid boxes completed with no 3-in-a-row.`;
  }

  setTimeout(() => {
    openModal(gameoverModal);
  }, 900);
}

function highlightWinningLine(line) {
  line.forEach(([r, c]) => {
    const el = document.getElementById(`cell-${r}-${c}`);
    if (el) el.classList.add('winning-cell');
  });
}

function clearBoardHighlights() {
  document.querySelectorAll('.grid-cell').forEach(el => {
    el.classList.remove('winning-cell');
  });
}

function setStatus(msg, type = 'info', icon = '📢') {
  statusMessage.textContent = msg;
  statusIcon.textContent = icon;
  statusAlert.className = 'status-alert ' + type;
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
