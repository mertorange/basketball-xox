// Hoop Grid: two-player basketball XOX on a scorer's sheet. Game flow lives here; every
// part of the screen has its own module.

import { api } from './api.js';
import { drawWinStroke, renderBoard } from './board.js';
import { ShotClock } from './clock.js';
import { $, closeModal, isOpen, openModal } from './dom.js';
import { PlayByPlay, renderTallies, setStatus } from './scoresheet.js';
import { PlayerSlip } from './slip.js';
import { sfx } from './sound.js';

const state = {
  game: null,
  settings: { league: 'nba', clock: 60, density: 2, style: 'mixed' },
  scores: { X: 0, O: 0 },
  cell: null,          // the box the slip is open for
  pending: false       // a pick is being checked; the clock must not also fire
};

const screens = { menu: $('screen-menu'), game: $('screen-game') };
const modals = { gameover: $('modal-gameover'), rules: $('modal-rules-popup') };
const playByPlay = new PlayByPlay($('pbp-log'));
const clock = new ShotClock($('shotclock-display'), $('clock-digits'), $('modal-clock-num'), onShotClockExpired);
const slip = new PlayerSlip(confirmPick);

const playerName = (mark) => (mark === 'X' ? state.game.player1_name : state.game.player2_name);

window.addEventListener('DOMContentLoaded', setupHandlers);

function setupHandlers() {
  $('setup-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const data = new FormData(e.target);
    state.settings = {
      league: data.get('league'),
      clock: parseInt(data.get('clock'), 10) || 0,
      density: parseInt(data.get('density'), 10) || 2,
      style: data.get('style') || 'mixed'
    };
    startNewGame(true);
  });

  $('btn-game-exit').addEventListener('click', showMenu);
  $('btn-game-new').addEventListener('click', () => startNewGame(false));
  $('btn-game-rules').addEventListener('click', () => openModal(modals.rules));
  $('btn-ack-rules').addEventListener('click', () => closeModal(modals.rules));
  $('btn-rematch-match').addEventListener('click', () => {
    closeModal(modals.gameover);
    startNewGame(false);
  });
  $('btn-return-menu-go').addEventListener('click', () => {
    closeModal(modals.gameover);
    showMenu();
  });

  document.querySelectorAll('.cell').forEach(cell => {
    cell.addEventListener('click', () => onCellClicked(Number(cell.dataset.row), Number(cell.dataset.col)));
  });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (slip.isOpen) slip.close();
    else if (isOpen(modals.rules)) closeModal(modals.rules);
  });

  window.addEventListener('resize', () => {
    if (state.game && state.game.winning_line) drawWinStroke(state.game.winning_line, state.game.winner);
  });
}

function showMenu() {
  clock.stop();
  screens.game.classList.add('hidden');
  screens.menu.classList.remove('hidden');
}

async function startNewGame(isNewMatch) {
  clock.stop();
  $('menu-error').textContent = '';
  setStatus('Drawing up a new grid...');
  const { league, clock: shotClock, density, style } = state.settings;

  try {
    state.game = await api.newGame({
      league,
      player1_name: $('name-p1').value.trim() || 'Player 1',
      player2_name: $('name-p2').value.trim() || 'Player 2',
      min_answers: density,
      shot_clock: shotClock,
      grid_style: style
    });
  } catch (err) {
    console.error(err);
    if (isNewMatch) $('menu-error').textContent = 'Could not reach the game server. Is it running?';
    else setStatus('Could not reach the game server.', 'error');
    return;
  }

  if (isNewMatch) {
    state.scores = { X: 0, O: 0 };
    screens.menu.classList.add('hidden');
    screens.game.classList.remove('hidden');
  }
  $('meta-league').textContent = league === 'euroleague' ? 'EuroLeague' : 'NBA';
  $('meta-game').textContent = state.game.game_id.toUpperCase();
  $('text-name-x').textContent = state.game.player1_name;
  $('text-name-o').textContent = state.game.player2_name;
  renderTallies(state.scores);
  renderBoard(state.game, league);
  playByPlay.reset();
  setStatus(`${state.game.player1_name} to start. Pick a box.`);
  clock.start(shotClock);
}

async function refreshGame(fresh = null) {
  state.game = await api.getGame(state.game.game_id);
  renderBoard(state.game, state.settings.league, fresh);
}

function onCellClicked(row, col) {
  const game = state.game;
  if (!game || game.status === 'finished' || state.pending) return;
  if (game.grid[row][col].claimed_by) {
    setStatus('That box is taken. Pick an open one.', 'error');
    return;
  }
  state.cell = { row, col };
  slip.open(state.settings.league, row, col, game.row_criteria[row].display, game.col_criteria[col].display);
}

async function confirmPick(name) {
  if (!state.cell || state.pending) return;
  state.pending = true;
  clock.stop();
  const mover = state.game.current_player;
  const { row, col } = state.cell;
  setStatus(`Checking ${name}...`);

  try {
    const result = await api.move(state.game.game_id, row, col, name);
    if (result.success) {
      sfx.playScore();
      await refreshGame({ row, col });
      const placed = state.game.grid[row][col].player_name || name;
      playByPlay.log(mover, `${placed} · ${state.game.row_criteria[row].display} × ${state.game.col_criteria[col].display}`);
      if (result.game_over) {
        finishGame(result);
      } else {
        setStatus(`Good. ${playerName(state.game.current_player)} is up.`, 'success');
        clock.start(state.settings.clock);
      }
    } else {
      sfx.playTurnover();
      await refreshGame();
      playByPlay.log(mover, `Turnover: ${name}`, true);
      setStatus(`${result.message.replace(/^Turnover!\s*/, 'Turnover. ')} ${playerName(state.game.current_player)} has the ball.`, 'error');
      clock.start(state.settings.clock);
    }
  } catch (err) {
    console.error(err);
    setStatus('Could not reach the game server.', 'error');
  } finally {
    state.pending = false;
  }
}

async function onShotClockExpired() {
  if (state.pending || !state.game || state.game.status === 'finished') return;
  sfx.playArenaBuzzer();
  slip.close();
  const offender = state.game.current_player;
  try {
    await api.shotClockViolation(state.game.game_id);
    await refreshGame();
    playByPlay.log(offender, 'Shot clock violation', true);
    setStatus(`Shot clock violation. ${playerName(state.game.current_player)} has the ball.`, 'error');
    clock.start(state.settings.clock);
  } catch (err) {
    console.error(err);
  }
}

function finishGame(result) {
  clock.stop();
  const stamp = $('go-stamp');
  stamp.className = 'stamp';
  if (result.winner === 'X' || result.winner === 'O') {
    sfx.playWin();
    state.scores[result.winner]++;
    renderTallies(state.scores);
    const winner = playerName(result.winner);
    stamp.textContent = 'Final';
    stamp.classList.add(result.winner.toLowerCase());
    $('go-title').textContent = `${winner} wins`;
    $('go-desc').textContent =
      `Three in a row. Series: ${state.game.player1_name} ${state.scores.X} – ${state.scores.O} ${state.game.player2_name}`;
    setStatus(`${winner} wins the grid.`, 'success');
  } else {
    stamp.textContent = 'Draw';
    stamp.classList.add('draw');
    $('go-title').textContent = 'No winner';
    $('go-desc').textContent = 'All nine boxes filled without a line.';
    setStatus('Draw. All nine boxes filled.');
  }
  setTimeout(() => openModal(modals.gameover), 900);
}
