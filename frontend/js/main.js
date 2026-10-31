// Hoop-Tac-Toe: two-player basketball XOX on a scorer's sheet. This module owns the menu, the
// screens and the dialogs; the game itself runs in a controller: HotSeatGame (one device)
// or OnlineGame (a room shared over a WebSocket).

import { renderActions } from './actions.js';
import { api } from './api.js';
import { showAnswers } from './answers.js';
import { drawWinStroke } from './board.js';
import { drawPlays } from './plays.js';
import { ShotClock } from './clock.js';
import { $, closeModal, escapeHtml, isOpen, openModal } from './dom.js';
import { HotSeatGame, readNames } from './hotseat.js';
import { hasSeat } from './online.js';
import { OnlineGame } from './onlinegame.js';
import { PlayByPlay } from './scoresheet.js';
import { loadNames } from './names.js';
import { PlayerSlip } from './slip.js';
import { sfx } from './sound.js';

let active = null; // the running controller

const screens = { menu: $('screen-menu'), join: $('screen-join'), lobby: $('screen-lobby'), game: $('screen-game') };
const modals = { gameover: $('modal-gameover'), rules: $('modal-rules-popup'), answers: $('modal-answers') };

const ui = {
  clock: new ShotClock($('shotclock-display'), $('clock-digits'), $('modal-clock-num'),
    () => active && active.clockExpired()),
  slip: new PlayerSlip((name, key) => active && active.pick(name, key), () => active && active.slipCancelled()),
  playByPlay: new PlayByPlay($('pbp-log')),
  showGame,
  showLobby,
  showLobbyError: (reason) => { $('lobby-error').textContent = reason; },
  showFinal,
  hideFinal: () => closeModal(modals.gameover),
  setPresence,
  showMenu
};

window.addEventListener('DOMContentLoaded', setupHandlers);

// ---------- Menu ----------

// What the category boxes mean, for the lobby line
const CATEGORY_LABELS = {
  country: 'birth country', college: 'college', draft: 'draft slot', award: 'awards', career: 'career marks',
  teammate: 'teammates',
  era: 'eras'
};

/** Custom grids: the ticked categories the chosen league has (teams are always in). */
function readCategories(form) {
  return [...form.querySelectorAll('input[name=category]:checked')]
    .filter(input => !input.closest('.choice').hidden)
    .map(input => input.value);
}

function readSettings(form) {
  const data = new FormData(form);
  const style = data.get('style') || 'mixed';
  return {
    categories: style === 'custom' ? readCategories(form) : null,
    mode: data.get('mode'),
    league: data.get('league'),
    clock: parseInt(data.get('clock'), 10) || 0,
    difficulty: data.get('difficulty') || 'medium',
    style: data.get('style') || 'mixed',
    bestOf: parseInt(data.get('best_of'), 10) || 1
  };
}

function syncMenuMode() {
  const data = new FormData($('setup-form'));
  const mode = data.get('mode');
  $('setup-form').dataset.mode = mode;
  $('btn-launch-game').textContent = mode === 'online' ? 'Create room' : 'Tip-off';
  // The category picker only shows for custom grids, with the chosen league's categories
  $('custom-categories').hidden = data.get('style') !== 'custom';
  const league = data.get('league');
  $('custom-categories').querySelectorAll('[data-leagues]').forEach(choice => {
    choice.hidden = !choice.dataset.leagues.split(' ').includes(league);
  });
}

function setupHandlers() {
  const form = $('setup-form');
  form.querySelectorAll('input[name=mode], input[name=style], input[name=league]')
    .forEach(input => input.addEventListener('change', syncMenuMode));

  // An invite link (?room=KQ7M) opens the menu in online mode with the code filled in;
  // a watch link (?room=KQ7M&watch=1) goes straight in as a spectator
  const params = new URLSearchParams(location.search);
  const invited = (params.get('room') || '').toUpperCase();
  if (invited) {
    form.querySelector('input[name=mode][value=online]').checked = true;
    $('join-code').value = invited;
  }
  syncMenuMode();
  if (invited && params.get('watch')) {
    startController(new OnlineGame(ui, invited, 'Spectator', { spectator: true }));
  } else if (invited && hasSeat(invited)) {
    // A reload mid-game: this tab already has a seat, so go straight back to it
    startController(new OnlineGame(ui, invited, onlineName()));
  } else if (invited) {
    // An invite: the room's settings are fixed, so a page with just a name and Ready
    showJoin(invited);
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const settings = readSettings(form);
    $('menu-error').textContent = '';
    if (settings.mode === 'online') {
      await createRoom(settings);
    } else {
      startController(new HotSeatGame(ui, settings, readNames()));
    }
  });
  $('btn-join-room').addEventListener('click', joinRoom);
  $('btn-join-ready').addEventListener('click', joinAndReady);
  $('join-name').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (!$('btn-join-ready').disabled) joinAndReady();
    }
  });
  $('btn-join-menu').addEventListener('click', () => showMenu());
  $('name-online').value = $('name-online').value || savedName();
  $('join-code').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      joinRoom();
    }
  });

  $('btn-game-exit').addEventListener('click', leaveToMenu);
  $('btn-lobby-leave').addEventListener('click', leaveToMenu);
  $('btn-ready').addEventListener('click', () => {
    if (!active || !active.ready) return;
    active.ready();
    $('btn-ready').disabled = true;
  });
  $('btn-copy-link').addEventListener('click', () => copyLink('lobby-link', 'btn-copy-link'));
  $('btn-copy-watch').addEventListener('click', () => copyLink('lobby-watch-link', 'btn-copy-watch'));
  $('btn-show-answers').addEventListener('click', () => {
    if (active && active.game) showAnswers(active.game.game_id);
  });
  $('btn-close-answers').addEventListener('click', () => closeModal(modals.answers));

  $('btn-skip').addEventListener('click', () => active && active.skip());
  $('btn-draw').addEventListener('click', () => active && active.drawPressed());
  $('btn-draw-yes').addEventListener('click', () => active && active.answerDraw && active.answerDraw(true));
  $('btn-draw-no').addEventListener('click', () => active && active.answerDraw && active.answerDraw(false));

  $('btn-sound').addEventListener('click', () => {
    sfx.setMuted(!sfx.muted);
    renderSoundButton();
  });
  renderSoundButton();

  $('btn-game-rules').addEventListener('click', () => openModal(modals.rules));
  $('btn-ack-rules').addEventListener('click', () => closeModal(modals.rules));
  $('btn-rematch-match').addEventListener('click', () => {
    if (!active) return;
    if (active instanceof HotSeatGame) closeModal(modals.gameover);
    active.rematch();
  });
  $('btn-return-menu-go').addEventListener('click', () => {
    closeModal(modals.gameover);
    leaveToMenu();
  });

  document.querySelectorAll('.cell').forEach(cell => {
    cell.addEventListener('click', () => active && active.cellClicked(Number(cell.dataset.row), Number(cell.dataset.col)));
  });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (ui.slip.isOpen) ui.slip.cancel();
    else if (isOpen(modals.answers)) closeModal(modals.answers);
    else if (isOpen(modals.rules)) closeModal(modals.rules);
  });

  window.addEventListener('resize', () => {
    const line = document.querySelector('#win-stroke line');
    if (line && active && active.game) drawWinStroke(active.game.winning_line, active.game.winner);
    if (active && active.game) drawPlays(active.game);
  });
}

function renderSoundButton() {
  const button = $('btn-sound');
  button.classList.toggle('muted', sfx.muted);
  button.setAttribute('aria-pressed', String(sfx.muted));
  button.setAttribute('aria-label', sfx.muted ? 'Sound is off; turn it on' : 'Sound is on; turn it off');
  $('sound-label').textContent = sfx.muted ? 'Muted' : 'Sound';
}

async function startController(controller) {
  if (active) active.leave();
  active = controller;
  try {
    await controller.start();
  } catch (err) {
    console.error(err);
    active = null;
    showMenu('Could not reach the game server. Is it running?');
  }
}

function onlineName() {
  return $('name-online').value.trim() || 'Player';
}

async function createRoom(settings) {
  try {
    localStorage.setItem(NAME_KEY, onlineName());
  } catch (e) {}
  try {
    const { code } = await api.createRoom({
      league: settings.league,
      difficulty: settings.difficulty,
      shot_clock: settings.clock,
      grid_style: settings.style,
      categories: settings.categories,
      best_of: settings.bestOf
    });
    startController(new OnlineGame(ui, code, onlineName()));
  } catch (err) {
    console.error(err);
    $('menu-error').textContent = 'Could not create a room. Is the server running?';
  }
}

async function joinRoom() {
  const code = $('join-code').value.trim().toUpperCase();
  $('menu-error').textContent = '';
  if (code.length !== 4) {
    $('menu-error').textContent = 'Room codes have four letters.';
    return;
  }
  try {
    await api.roomInfo(code);
  } catch (err) {
    $('menu-error').textContent = `No room with the code ${code}.`;
    return;
  }
  showJoin(code, $('name-online').value.trim());
}

// ---------- Joining a room ----------

const NAME_KEY = 'hoopgrid:name';

function savedName() {
  try {
    return localStorage.getItem(NAME_KEY) || '';
  } catch (e) {
    return '';
  }
}

/** The join page: the room's options as text, a name, and Ready (nothing else to change). */
async function showJoin(code, name = '') {
  show('join');
  history.replaceState(null, '', `?room=${code}`);
  $('join-code-title').textContent = code;
  $('join-settings').textContent = 'Looking up the room...';
  $('join-error').textContent = '';
  $('join-name').value = name || savedName();
  $('join-name-field').hidden = false;
  $('btn-join-ready').hidden = false;
  $('btn-join-ready').disabled = true;
  $('btn-join-menu').hidden = true;
  $('btn-join-ready').dataset.code = code;

  let room;
  try {
    room = await api.roomInfo(code);
  } catch (err) {
    joinClosed(`There's no room ${code} any more. It may have ended.`);
    return;
  }
  $('join-settings').textContent = settingsText(room.settings, ', ');
  if (room.players >= 2) {
    joinClosed('This room already has two players.');
    return;
  }
  $('btn-join-ready').disabled = false;
  $('join-name').focus();
}

function joinClosed(reason) {
  if ($('join-settings').textContent === 'Looking up the room...') $('join-settings').textContent = '—';
  $('join-error').textContent = reason;
  $('join-name-field').hidden = true;
  $('btn-join-ready').hidden = true;
  $('btn-join-menu').hidden = false;
}

function joinAndReady() {
  const code = $('btn-join-ready').dataset.code;
  const name = $('join-name').value.trim() || 'Player';
  try {
    localStorage.setItem(NAME_KEY, name);
  } catch (e) {}
  $('btn-join-ready').disabled = true;
  startController(new OnlineGame(ui, code, name, { autoReady: true }));
}

function leaveToMenu() {
  if (active) active.leave();
  active = null;
  showMenu();
}

// ---------- Screens ----------

function show(name) {
  Object.entries(screens).forEach(([key, el]) => el.classList.toggle('hidden', key !== name));
}

function showMenu(error = null) {
  ui.clock.stop();
  renderActions({ visible: false });
  ui.slip.close();
  closeModal(modals.gameover);
  closeModal(modals.answers);
  if (active && error) active = null;
  history.replaceState(null, '', location.pathname);
  $('menu-error').textContent = error || '';
  show('menu');
}

/**
 * names: { X, O }; room: the room code online, null on one device; you: the local seat online
 * (null when watching); spectators: how many are watching an online room;
 * series: { bestOf, grid } where grid counts the grids dealt in this series
 */
function showGame({ league, gameId, names, room, you = null, spectators = 0, series }) {
  show('game');
  loadNames(league).catch(() => {}); // fetched once, so the first suggestions are instant too
  $('meta-league').textContent = league === 'euroleague' ? 'EuroLeague' : 'NBA';
  $('meta-game').textContent = gameId.toUpperCase();
  $('meta-room-wrap').hidden = !room;
  $('meta-room').textContent = room || '';
  $('meta-watch-wrap').hidden = !spectators;
  $('meta-watch').textContent = spectators;
  $('meta-series').textContent = series.bestOf > 1 ? `Best of ${series.bestOf} · Grid ${series.grid}` : 'Best of 1';
  $('text-name-x').textContent = names.X;
  $('text-name-o').textContent = names.O;
  $('label-x').textContent = you === 'X' ? 'Team A · You' : 'Team A';
  $('label-o').textContent = you === 'O' ? 'Team B · You' : 'Team B';
  if (!room) setPresence(null);
}

function setPresence(seats, you) {
  ['X', 'O'].forEach(mark => {
    const panel = $(`panel-${mark.toLowerCase()}`);
    const seat = seats && seats[mark];
    panel.classList.toggle('offline', Boolean(seats) && (!seat || !seat.connected) && mark !== you);
  });
}

const CLOCK_LABEL = (s) => (s ? `${s} sec shot clock` : 'no shot clock');

/** A room's options in words, e.g. 'NBA, mixed grid, best of 3, 60 sec shot clock, medium difficulty'. */
function settingsText(s, separator) {
  const grid = s.grid_style === 'custom'
    ? `custom grid: teams${(s.categories || []).map(c => ` + ${CATEGORY_LABELS[c] || c}`).join('')}`
    : `${s.grid_style} grid`;
  return [
    s.league === 'euroleague' ? 'EuroLeague' : 'NBA',
    grid,
    `best of ${s.best_of}`,
    CLOCK_LABEL(s.shot_clock),
    `${s.difficulty} difficulty`
  ].join(separator);
}

function showLobby(room, code, spectator = false) {
  show('lobby');
  $('lobby-error').textContent = '';
  $('lobby-code').textContent = code;
  const base = `${location.origin}${location.pathname}?room=${code}`;
  $('lobby-link').textContent = base;
  $('lobby-watch-link').textContent = `${base}&watch=1`;
  $('lobby-invite').hidden = spectator;
  $('btn-ready').hidden = spectator;
  history.replaceState(null, '', spectator ? `?room=${code}&watch=1` : `?room=${code}`);

  if (!room) {
    $('lobby-settings').textContent = 'Connecting...';
    $('lobby-seats').innerHTML = '';
    $('btn-ready').disabled = true;
    return;
  }
  $('lobby-settings').textContent = settingsText(room.settings, ' · ');

  $('lobby-seats').innerHTML = ['X', 'O'].map(mark => {
    const seat = room.seats[mark];
    const label = mark === 'X' ? 'Team A' : 'Team B';
    if (!seat) return `<li><b class="ink-${mark.toLowerCase()}">${mark}</b><span class="seat-name empty">Waiting for a player</span><span class="seat-state">${label}</span></li>`;
    const state = !seat.connected ? 'Offline' : seat.ready ? 'Ready' : 'Not ready';
    const you = mark === room.you ? ' <small>(you)</small>' : '';
    return `<li class="${seat.ready ? 'is-ready' : ''}"><b class="ink-${mark.toLowerCase()}">${mark}</b>` +
      `<span class="seat-name">${escapeHtml(seat.name)}${you}</span><span class="seat-state">${state}</span></li>`;
  }).join('');

  const me = room.seats[room.you];
  const full = Boolean(room.seats.X && room.seats.O);
  $('btn-ready').disabled = !full || Boolean(me && me.ready);
  $('btn-ready').textContent = me && me.ready ? 'Ready ✓' : 'Ready';
  const watching = room.spectators ? ` ${room.spectators} watching.` : '';
  $('lobby-hint').textContent = (spectator ? 'You are watching; the game starts when both players are ready.'
    : full ? 'Tip-off when both players are ready.' : 'Send the link or the code to your opponent.') + watching;
}

async function copyLink(sourceId, buttonId) {
  const button = $(buttonId);
  const label = button.textContent;
  try {
    await navigator.clipboard.writeText($(sourceId).textContent);
    button.textContent = 'Copied';
  } catch (err) {
    button.textContent = 'Copy failed';
  }
  setTimeout(() => { button.textContent = label; }, 1600);
}

/** The series line under a result: 'Best of 3: Ann 2 – 1 Ben', or nothing for a single grid. */
function seriesLine(names, scores, bestOf) {
  return bestOf > 1 ? ` Best of ${bestOf}: ${names.X} ${scores.X} – ${scores.O} ${names.O}.` : '';
}

/**
 * winner: 'X' | 'O' | 'DRAW' for the grid; winnerName: shown in the title ('You' for the local
 * player online); seriesWinner: the mark that has taken the series, or null while it goes on;
 * waiting: online status line for the next grid; canRematch: false once the local player is ready;
 * byForfeit: the other side left; boardFull: a draw with all nine boxes filled, rather than one
 * called early because neither team could complete a line; spectating: no next-grid button at all
 */
function showFinal({ winner, winnerName, names, scores, bestOf, seriesWinner = null, waiting = null,
                     canRematch = true, byForfeit = false, boardFull = true, spectating = false }) {
  renderActions({ visible: false });
  const stamp = $('go-stamp');
  stamp.className = 'stamp';
  const tally = seriesLine(names, scores, bestOf);
  if (winner === 'X' || winner === 'O') {
    const what = seriesWinner && bestOf > 1 ? 'the series' : 'the grid';
    stamp.textContent = seriesWinner ? 'Final' : 'Grid';
    stamp.classList.add(winner.toLowerCase());
    $('go-title').textContent = winnerName === 'You' ? `You win ${what}` : `${winnerName} wins ${what}`;
    $('go-desc').textContent = `${byForfeit ? 'By forfeit' : 'Three in a row'}.${tally}`;
  } else {
    stamp.textContent = 'Draw';
    stamp.classList.add('draw');
    $('go-title').textContent = 'No winner';
    const how = boardFull ? 'All nine boxes filled without a line.' : 'Neither team can complete a line.';
    $('go-desc').textContent = `${how}${tally}`;
  }
  $('go-waiting').textContent = waiting || '';
  const next = $('btn-rematch-match');
  next.textContent = !seriesWinner ? 'Next grid' : bestOf > 1 ? 'New series' : 'Play again';
  next.disabled = !canRematch;
  next.hidden = spectating;
  openModal(modals.gameover);
}
