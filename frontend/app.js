/**
 * Hoop Grid - 2-player basketball XOX on a scorer's sheet
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
    if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume();
  }

  // Warning beep for last 5 seconds of shot clock
  playClockBeep() {
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'square';
      osc.frequency.setValueAtTime(880, this.ctx.currentTime);
      gain.gain.setValueAtTime(0.08, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.08);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + 0.08);
    } catch (e) {}
  }

  // Arena buzzer horn (dual-tone sawtooth)
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

// Game state
let currentGame = null;
let currentLeague = 'nba';
let currentShotClockSetting = 60; // 30, 60, 120, 0 = off
let currentMinAnswers = 2;
let selectedCell = null;
let scores = { X: 0, O: 0 };
let searchDebounce = null;
let searchSeq = 0;
let pickPending = false;
let playByPlay = [];
let freshCell = null;
let activeSuggestion = -1;

// Timer state
let timerSecondsLeft = 60;
let timerInterval = null;

const $ = (id) => document.getElementById(id);

const screenMenu = $('screen-menu');
const screenGame = $('screen-game');
const setupForm = $('setup-form');
const nameP1 = $('name-p1');
const nameP2 = $('name-p2');
const menuError = $('menu-error');

const metaLeague = $('meta-league');
const metaGame = $('meta-game');
const panelX = $('panel-x');
const panelO = $('panel-o');
const textNameX = $('text-name-x');
const textNameO = $('text-name-o');
const tallyX = $('tally-x');
const tallyO = $('tally-o');
const gameStatusText = $('game-status-text');
const shotclockDisplay = $('shotclock-display');
const clockDigits = $('clock-digits');
const cornerMark = $('corner-mark');
const boardWrap = $('board-wrap');
const winStroke = $('win-stroke');
const pbpLog = $('pbp-log');

const modalSelect = $('modal-select');
const reqRow = $('req-row');
const reqCol = $('req-col');
const modalClockNum = $('modal-clock-num');
const searchPlayerInput = $('search-player-input');
const searchResultsList = $('search-results-list');
const btnConfirmSelect = $('btn-confirm-select');
const btnCancelSelect = $('btn-cancel-select');

const modalGameover = $('modal-gameover');
const goStamp = $('go-stamp');
const goTitle = $('go-title');
const goDesc = $('go-desc');

const modalRulesPopup = $('modal-rules-popup');

window.addEventListener('DOMContentLoaded', () => {
  buildClockDigits();
  setupHandlers();
});

function setupHandlers() {
  setupForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const data = new FormData(setupForm);
    currentLeague = data.get('league');
    currentShotClockSetting = parseInt(data.get('clock'), 10) || 0;
    currentMinAnswers = parseInt(data.get('density'), 10) || 2;
    startNewGame(true);
  });

  $('btn-game-exit').addEventListener('click', showMenu);
  $('btn-game-new').addEventListener('click', () => startNewGame(false));
  $('btn-game-rules').addEventListener('click', () => openModal(modalRulesPopup));
  $('btn-ack-rules').addEventListener('click', () => closeModal(modalRulesPopup));

  $('btn-rematch-match').addEventListener('click', () => {
    closeModal(modalGameover);
    startNewGame(false);
  });
  $('btn-return-menu-go').addEventListener('click', () => {
    closeModal(modalGameover);
    showMenu();
  });

  btnCancelSelect.addEventListener('click', closeSlip);

  document.querySelectorAll('.cell').forEach(cell => {
    cell.addEventListener('click', () => {
      handleCellClicked(parseInt(cell.dataset.row, 10), parseInt(cell.dataset.col, 10));
    });
  });

  searchPlayerInput.addEventListener('input', () => {
    const val = searchPlayerInput.value.trim();
    btnConfirmSelect.disabled = val.length === 0;
    clearTimeout(searchDebounce);
    if (val.length < 2) {
      renderSuggestions([], '');
      return;
    }
    searchDebounce = setTimeout(() => fetchPlayerAutocomplete(val), 150);
  });

  searchPlayerInput.addEventListener('keydown', (e) => {
    const items = [...searchResultsList.querySelectorAll('li[data-name]')];
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (!items.length) return;
      e.preventDefault();
      const step = e.key === 'ArrowDown' ? 1 : -1;
      setActiveSuggestion((activeSuggestion + step + items.length) % items.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeSuggestion >= 0 && items[activeSuggestion]) {
        confirmPick(items[activeSuggestion].dataset.name);
      } else if (!btnConfirmSelect.disabled) {
        confirmPick(searchPlayerInput.value.trim());
      }
    }
  });

  btnConfirmSelect.addEventListener('click', () => confirmPick(searchPlayerInput.value.trim()));

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (modalSelect.classList.contains('active')) closeSlip();
    else if (modalRulesPopup.classList.contains('active')) closeModal(modalRulesPopup);
  });

  window.addEventListener('resize', () => {
    if (currentGame && currentGame.winning_line) drawWinStroke(currentGame.winning_line, currentGame.winner);
  });
}

function showMenu() {
  stopShotClock();
  screenGame.classList.add('hidden');
  screenMenu.classList.remove('hidden');
}

async function startNewGame(isNewMatch = true) {
  stopShotClock();
  menuError.textContent = '';
  const p1 = nameP1.value.trim() || 'Player 1';
  const p2 = nameP2.value.trim() || 'Player 2';

  setStatus('Drawing up a new grid...');

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
      scores = { X: 0, O: 0 };
      screenMenu.classList.add('hidden');
      screenGame.classList.remove('hidden');
    }

    playByPlay = [];
    freshCell = null;
    metaLeague.textContent = currentGame.league === 'EUROLEAGUE' ? 'EuroLeague' : currentGame.league;
    metaGame.textContent = currentGame.game_id.toUpperCase();
    textNameX.textContent = currentGame.player1_name;
    textNameO.textContent = currentGame.player2_name;
    renderTallies();
    renderBoard(currentGame);
    renderPlayByPlay();
    setStatus(`${currentGame.player1_name} to start. Pick a box.`);
    startShotClock();
  } catch (err) {
    console.error(err);
    if (isNewMatch) menuError.textContent = 'Could not reach the game server. Is it running?';
    else setStatus('Could not reach the game server.', 'error');
  }
}

/* ---------- Rendering ---------- */

function critHtml(crit) {
  const type = crit.type === 'country' ? 'Born in' : (currentLeague === 'euroleague' ? 'Club' : 'Team');
  return `<span class="crit-type">${type}</span><span class="crit-name">${escapeHtml(crit.display)}</span>`;
}

function markSvg(mark, fresh) {
  // Drawn by hand: slightly bowed strokes, an O that doesn't quite close
  const paths = mark === 'X'
    ? '<path pathLength="1" d="M18 15 C 36 35, 58 58, 83 86"/><path pathLength="1" d="M81 13 C 63 34, 41 60, 19 87"/>'
    : '<path pathLength="1" d="M54 15 C 77 14, 89 33, 87 53 C 85 75, 67 89, 47 87 C 26 85, 13 69, 14 48 C 15 28, 31 14, 58 17"/>';
  return `<svg class="mark mark-${mark.toLowerCase()}${fresh ? ' fresh' : ''}" viewBox="0 0 100 100" aria-hidden="true">${paths}</svg>`;
}

function renderBoard(game) {
  game.col_criteria.forEach((crit, i) => { $(`ch-${i}`).innerHTML = critHtml(crit); });
  game.row_criteria.forEach((crit, i) => { $(`rh-${i}`).innerHTML = critHtml(crit); });

  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 3; c++) {
      const data = game.grid[r][c];
      const cell = $(`box-${r}-${c}`);
      const rowName = game.row_criteria[r].display;
      const colName = game.col_criteria[c].display;
      cell.className = 'cell';
      if (data.claimed_by) {
        const fresh = freshCell && freshCell.row === r && freshCell.col === c;
        cell.classList.add('claimed');
        cell.innerHTML = `
          ${markSvg(data.claimed_by, fresh)}
          <span class="cell-player">${escapeHtml(data.player_name || '')}</span>
          <span class="cell-meta">b. ${escapeHtml(data.player_country || '?')}</span>`;
        cell.setAttribute('aria-label', `${rowName} and ${colName}: ${data.claimed_by}, ${data.player_name}`);
      } else {
        cell.innerHTML = '';
        cell.setAttribute('aria-label', `${rowName} and ${colName}: open`);
      }
    }
  }
  freshCell = null;

  const turn = game.current_player;
  const over = game.status === 'finished';
  panelX.classList.toggle('active-turn', !over && turn === 'X');
  panelO.classList.toggle('active-turn', !over && turn === 'O');
  cornerMark.textContent = over ? '' : turn;
  cornerMark.className = `corner turn-${turn.toLowerCase()}`;

  if (game.winning_line) {
    requestAnimationFrame(() => drawWinStroke(game.winning_line, game.winner));
  } else {
    winStroke.innerHTML = '';
  }
}

function drawWinStroke(line, winner) {
  const wrap = boardWrap.getBoundingClientRect();
  const centre = ([r, c]) => {
    const rect = $(`box-${r}-${c}`).getBoundingClientRect();
    return [rect.left + rect.width / 2 - wrap.left, rect.top + rect.height / 2 - wrap.top];
  };
  const [x1, y1] = centre(line[0]);
  const [x2, y2] = centre(line[2]);
  // Overshoot a little past the outer boxes, like a pen stroke
  const dx = (x2 - x1) * 0.18;
  const dy = (y2 - y1) * 0.18;
  const colour = winner === 'O' ? 'var(--o)' : 'var(--x)';
  winStroke.innerHTML = `<line pathLength="1" x1="${x1 - dx}" y1="${y1 - dy}" x2="${x2 + dx}" y2="${y2 + dy}" style="stroke:${colour}"/>`;
}

function renderTallies() {
  [[tallyX, scores.X], [tallyO, scores.O]].forEach(([el, wins]) => {
    let html = '';
    for (let left = wins; left > 0; left -= 5) {
      const n = Math.min(left, 5);
      html += `<span class="tally-gate${n === 5 ? ' full' : ''}">${'<i></i>'.repeat(Math.min(n, 4))}</span>`;
    }
    el.innerHTML = html;
    el.setAttribute('aria-label', `${wins} ${wins === 1 ? 'win' : 'wins'}`);
  });
}

function logPlay(mark, text, turnover = false) {
  playByPlay.unshift({ no: playByPlay.length + 1, mark, text, turnover });
  renderPlayByPlay();
}

function renderPlayByPlay() {
  if (!playByPlay.length) {
    pbpLog.innerHTML = '<li><span></span><span></span><span class="pbp-empty">Nothing yet. Tip-off.</span></li>';
    return;
  }
  pbpLog.innerHTML = playByPlay.map(p => `
    <li>
      <span class="pbp-no">${String(p.no).padStart(2, '0')}</span>
      <span class="pbp-mark ${p.mark.toLowerCase()}">${p.mark}</span>
      <span class="pbp-text${p.turnover ? ' turnover' : ''}">${escapeHtml(p.text)}</span>
    </li>`).join('');
}

/* ---------- Shot clock: a two-digit seven-segment display ---------- */

const SEGMENTS = {
  a: '5,1 19,1 21,3 19,5 5,5 3,3',
  b: '19,5 21,3 23,5 23,19 21,21 19,19',
  c: '19,25 21,23 23,25 23,39 21,41 19,39',
  d: '5,39 19,39 21,41 19,43 5,43 3,41',
  e: '1,25 3,23 5,25 5,39 3,41 1,39',
  f: '1,5 3,3 5,5 5,19 3,21 1,19',
  g: '5,20 19,20 21,22 19,24 5,24 3,22'
};
const DIGITS = ['abcdef', 'bc', 'abdeg', 'abcdg', 'bcfg', 'acdfg', 'acdefg', 'abc', 'abcdefg', 'abcdfg'];

function buildClockDigits(slots = 2) {
  let html = '';
  for (let slot = 0; slot < slots; slot++) {
    html += `<g transform="translate(${3 + slot * 27} 1) skewX(-6)">`;
    Object.entries(SEGMENTS).forEach(([seg, pts]) => {
      html += `<polygon data-slot="${slot}" data-seg="${seg}" points="${pts}"/>`;
    });
    html += '</g>';
  }
  clockDigits.setAttribute('viewBox', `0 0 ${slots * 27} 46`);
  clockDigits.classList.toggle('three', slots === 3);
  clockDigits.innerHTML = html;
}

function showClockValue(value) {
  // Right-aligned, no leading zeros: ' 9' rather than '09'
  const slots = clockDigits.querySelectorAll('g').length;
  const text = String(value).padStart(slots, ' ');
  clockDigits.querySelectorAll('polygon').forEach(p => {
    const ch = text[Number(p.dataset.slot)];
    p.classList.toggle('on', ch !== ' ' && DIGITS[Number(ch)].includes(p.dataset.seg));
  });
}

function startShotClock() {
  stopShotClock();
  if (currentShotClockSetting <= 0) {
    shotclockDisplay.classList.add('off');
    modalClockNum.textContent = '';
    return;
  }
  shotclockDisplay.classList.remove('off');
  const slots = currentShotClockSetting >= 100 ? 3 : 2;
  if (clockDigits.querySelectorAll('g').length !== slots) buildClockDigits(slots);
  timerSecondsLeft = currentShotClockSetting;
  updateShotClockUI();

  timerInterval = setInterval(() => {
    if (!currentGame || currentGame.status === 'finished') {
      stopShotClock();
      return;
    }
    timerSecondsLeft--;
    updateShotClockUI();
    if (timerSecondsLeft <= 5 && timerSecondsLeft > 0) sfx.playClockBeep();
    if (timerSecondsLeft <= 0) handleShotClockExpired();
  }, 1000);
}

function stopShotClock() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
}

function updateShotClockUI() {
  showClockValue(Math.max(timerSecondsLeft, 0));
  modalClockNum.textContent = timerSecondsLeft;
  const warn = timerSecondsLeft <= 5;
  shotclockDisplay.classList.toggle('warning', warn);
  modalClockNum.classList.toggle('warning', warn);
}

async function handleShotClockExpired() {
  stopShotClock();
  if (pickPending) return;
  sfx.playArenaBuzzer();
  closeSlip();
  const offender = currentGame.current_player;

  try {
    const res = await fetch('/api/shot-clock-violation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ game_id: currentGame.game_id })
    });
    if (res.ok) {
      await refreshGame();
      logPlay(offender, 'Shot clock violation', true);
      setStatus(`Shot clock violation. ${playerName(currentGame.current_player)} has the ball.`, 'error');
      startShotClock();
    }
  } catch (err) {
    console.error(err);
  }
}

/* ---------- Picking a player ---------- */

function handleCellClicked(row, col) {
  if (!currentGame || currentGame.status === 'finished' || pickPending) return;
  if (currentGame.grid[row][col].claimed_by) {
    setStatus('That box is taken. Pick an open one.', 'error');
    return;
  }

  selectedCell = { row, col };
  document.querySelectorAll('.cell.selected').forEach(c => c.classList.remove('selected'));
  $(`box-${row}-${col}`).classList.add('selected');

  reqRow.textContent = currentGame.row_criteria[row].display;
  reqCol.textContent = currentGame.col_criteria[col].display;
  searchPlayerInput.value = '';
  renderSuggestions([], '');
  btnConfirmSelect.disabled = true;

  openModal(modalSelect);
  setTimeout(() => searchPlayerInput.focus(), 30);
}

function closeSlip() {
  closeModal(modalSelect);
  document.querySelectorAll('.cell.selected').forEach(c => c.classList.remove('selected'));
}

async function fetchPlayerAutocomplete(query) {
  const seq = ++searchSeq;
  try {
    const res = await fetch(`/api/search-players?league=${currentLeague}&q=${encodeURIComponent(query)}`);
    const players = await res.json();
    if (seq !== searchSeq) return; // a newer query already answered
    renderSuggestions(players, query);
  } catch (err) {}
}

function renderSuggestions(players, query) {
  activeSuggestion = -1;
  searchPlayerInput.removeAttribute('aria-activedescendant');
  if (!query) {
    searchResultsList.innerHTML = '';
    searchPlayerInput.setAttribute('aria-expanded', 'false');
    return;
  }
  if (!players.length) {
    searchResultsList.innerHTML = '<li class="none">No player by that name in the records</li>';
  } else {
    // Names only: showing countries or teams here would give the answer away
    searchResultsList.innerHTML = players.map((p, i) =>
      `<li role="option" id="sugg-${i}" data-name="${escapeHtml(p.name)}" aria-selected="false">${highlight(p.name, query)}</li>`
    ).join('');
    searchResultsList.querySelectorAll('li[data-name]').forEach((li, i) => {
      li.addEventListener('mousedown', (e) => e.preventDefault());
      li.addEventListener('click', () => confirmPick(li.dataset.name));
      li.addEventListener('mousemove', () => setActiveSuggestion(i));
    });
  }
  searchPlayerInput.setAttribute('aria-expanded', 'true');
}

function setActiveSuggestion(index) {
  const items = searchResultsList.querySelectorAll('li[data-name]');
  items.forEach((li, i) => li.setAttribute('aria-selected', String(i === index)));
  activeSuggestion = index;
  if (items[index]) {
    searchPlayerInput.setAttribute('aria-activedescendant', items[index].id);
    items[index].scrollIntoView({ block: 'nearest' });
  }
}

function highlight(name, query) {
  const i = name.toLowerCase().indexOf(query.toLowerCase());
  if (i < 0) return escapeHtml(name);
  return escapeHtml(name.slice(0, i)) + '<mark>' + escapeHtml(name.slice(i, i + query.length)) + '</mark>' +
    escapeHtml(name.slice(i + query.length));
}

async function confirmPick(name) {
  if (!name || !selectedCell || pickPending) return;
  pickPending = true;
  stopShotClock();
  closeSlip();
  const mover = currentGame.current_player;
  const cell = selectedCell;
  setStatus(`Checking ${name}...`);

  try {
    const res = await fetch('/api/move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ game_id: currentGame.game_id, row: cell.row, col: cell.col, player_name: name })
    });
    const result = await res.json();

    if (result.success) {
      sfx.playScore();
      freshCell = cell;
      await refreshGame();
      const placed = currentGame.grid[cell.row][cell.col].player_name || name;
      logPlay(mover, `${placed} · ${currentGame.row_criteria[cell.row].display} × ${currentGame.col_criteria[cell.col].display}`);
      if (result.game_over) {
        handleGameOver(result);
      } else {
        setStatus(`Good. ${playerName(currentGame.current_player)} is up.`, 'success');
        startShotClock();
      }
    } else {
      sfx.playTurnover();
      await refreshGame();
      logPlay(mover, `Turnover: ${name}`, true);
      setStatus(`${result.message.replace(/^Turnover!\s*/, 'Turnover. ')} ${playerName(currentGame.current_player)} has the ball.`, 'error');
      startShotClock();
    }
  } catch (err) {
    console.error(err);
    setStatus('Could not reach the game server.', 'error');
  } finally {
    pickPending = false;
  }
}

async function refreshGame() {
  const res = await fetch(`/api/game/${currentGame.game_id}`);
  currentGame = await res.json();
  renderBoard(currentGame);
}

function handleGameOver(result) {
  stopShotClock();
  goStamp.className = 'stamp';
  if (result.winner === 'X' || result.winner === 'O') {
    sfx.playWin();
    scores[result.winner]++;
    renderTallies();
    const winner = playerName(result.winner);
    goStamp.textContent = 'Final';
    goStamp.classList.add(result.winner.toLowerCase());
    goTitle.textContent = `${winner} wins`;
    goDesc.textContent = `Three in a row. Series: ${currentGame.player1_name} ${scores.X} – ${scores.O} ${currentGame.player2_name}`;
    setStatus(`${winner} wins the grid.`, 'success');
  } else {
    goStamp.textContent = 'Draw';
    goStamp.classList.add('draw');
    goTitle.textContent = 'No winner';
    goDesc.textContent = 'All nine boxes filled without a line.';
    setStatus('Draw. All nine boxes filled.');
  }
  setTimeout(() => openModal(modalGameover), 900);
}

/* ---------- Helpers ---------- */

function playerName(mark) {
  return mark === 'X' ? currentGame.player1_name : currentGame.player2_name;
}

function setStatus(msg, type = '') {
  gameStatusText.textContent = msg;
  gameStatusText.className = 'status' + (type ? ` ${type}` : '');
}

function openModal(modal) {
  modal.classList.add('active');
}

function closeModal(modal) {
  modal.classList.remove('active');
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
