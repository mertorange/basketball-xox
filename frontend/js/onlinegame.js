// Online play: the server runs the game and the clock; this renders what it sends and
// forwards the local player's actions.

import { lockBoard, renderBoard, showFocus } from './board.js';
import { RoomConnection } from './online.js';
import { renderTallies, setStatus } from './scoresheet.js';
import { sfx } from './sound.js';

const ONLINE_MIN_CHARS = 3; // autocomplete helps less when the opponent can't see you type

export class OnlineGame {
  /**
   * @param {object} ui  shared screen parts from main.js (see HotSeatGame) plus
   *                     showLobby(room, code), hideFinal(), setPresence(seats, you), showMenu(error)
   */
  /** spectator: watch the room without a seat */
  constructor(ui, code, name, { spectator = false } = {}) {
    this.ui = ui;
    this.code = code;
    this.spectator = spectator;
    this.room = null;
    this.cell = null;
    this.fresh = null;          // box claimed by the last move, to animate its mark
    this.note = null;           // last thing that happened, shown before whose turn it is
    this.gameId = null;
    this.finalShownFor = null;
    this.conn = new RoomConnection(code, name, {
      onRoom: (room) => this.onRoom(room),
      onEvent: (event) => this.onEvent(event),
      onError: (reason) => this.onError(reason),
      onStatus: (status) => this.onStatus(status)
    }, spectator ? 'spectator' : 'player');
  }

  start() {
    this.ui.showLobby(null, this.code, this.spectator);
    this.conn.open();
  }

  get game() {
    return this.room ? this.room.game : null;
  }

  // ---------- From the server ----------

  onRoom(room) {
    this.room = room;
    const { phase, game } = room;
    if (phase === 'waiting' || phase === 'lobby' || !game) {
      this.ui.clock.stop();
      this.ui.hideFinal();
      this.ui.showLobby(room, room.code, this.spectator);
      return;
    }

    if (game.game_id !== this.gameId) {
      this.gameId = game.game_id;
      this.note = null;
      this.ui.playByPlay.reset();
      this.ui.hideFinal();
    }
    const league = room.settings.league;
    this.ui.showGame({ league, gameId: game.game_id, names: this.names(), room: room.code, you: room.you,
      spectators: room.spectators });
    renderBoard(game, league, this.fresh);
    this.fresh = null;
    renderTallies(room.scores);
    this.ui.setPresence(room.seats, room.you);

    const myTurn = phase === 'playing' && game.current_player === room.you;
    lockBoard(!myTurn);
    showFocus(phase === 'playing' && !myTurn ? room.focus : null, game.current_player);
    if (!myTurn && this.ui.slip.isOpen) this.ui.slip.close();

    if (phase === 'playing') {
      this.ui.clock.follow(room.turn_ms_left, room.settings.shot_clock);
      this.showTurn(myTurn);
    } else {
      this.ui.clock.stop();
      this.showFinal();
    }
  }

  onEvent(event) {
    const who = this.nameOf(event.mark);
    const mine = this.room && event.mark === this.room.you;
    switch (event.kind) {
      case 'move': {
        sfx.playScore();
        this.fresh = { row: event.row, col: event.col };
        const game = this.room.game;
        this.ui.playByPlay.log(event.mark,
          `${event.player} · ${game.row_criteria[event.row].display} × ${game.col_criteria[event.col].display}`);
        this.note = { text: mine ? `Good: ${event.player}.` : `${who} placed ${event.player}.`, type: 'success' };
        break;
      }
      case 'turnover':
        sfx.playTurnover();
        this.ui.playByPlay.log(event.mark, `Turnover: ${event.player}`, true);
        this.note = { text: event.text.replace(/^Turnover!\s*/, 'Turnover. '), type: 'error' };
        break;
      case 'violation':
        sfx.playArenaBuzzer();
        this.ui.playByPlay.log(event.mark, 'Shot clock violation', true);
        this.note = { text: `Shot clock violation by ${who}.`, type: 'error' };
        break;
      case 'final':
        if (event.mark === this.room?.you) sfx.playWin();
        break;
      case 'forfeit':
        this.note = { text: `${who} did not come back in time.`, type: 'error' };
        break;
      case 'left':
        this.note = { text: `${who} left the room.`, type: 'error' };
        break;
      default:
        break; // joined / reconnected / disconnected show through the seats in the next snapshot
    }
  }

  onError(reason) {
    if (this.room && this.room.game) setStatus(reason, 'error');
    else this.ui.showLobbyError(reason);
  }

  onStatus(status) {
    if (status === 'reconnecting') setStatus('Connection lost. Reconnecting...', 'error');
    if (status === 'closed' && !this.conn.leaving) this.ui.showMenu('Lost the connection to the room.');
    if (status === 'closed' && this.conn.leaving && !this.room) this.ui.showMenu(null, true);
  }

  // ---------- Status lines ----------

  names() {
    const seats = this.room.seats;
    const game = this.room.game;
    return {
      X: seats.X ? seats.X.name : (game ? game.player1_name : 'Player 1'),
      O: seats.O ? seats.O.name : (game ? game.player2_name : 'Player 2')
    };
  }

  nameOf(mark) {
    if (!this.room) return mark;
    return this.names()[mark] || mark;
  }

  showTurn(myTurn) {
    const room = this.room;
    // Watching: talk about whoever is on the clock
    const opponent = this.spectator ? room.game.current_player : (room.you === 'X' ? 'O' : 'X');
    let line;
    if (myTurn) {
      line = 'Your turn. Pick a box.';
    } else if (room.seats[opponent] && !room.seats[opponent].connected) {
      line = `${this.nameOf(opponent)} lost connection; they have two minutes to come back.`;
    } else if (room.focus) {
      const g = room.game;
      line = `${this.nameOf(opponent)} is looking at ${g.row_criteria[room.focus.row].display} × ${g.col_criteria[room.focus.col].display}.`;
    } else {
      line = `${this.nameOf(opponent)} is on the clock.`;
    }
    setStatus(this.note ? `${this.note.text} ${line}` : line, this.note ? this.note.type : '');
  }

  showFinal() {
    const room = this.room;
    const winner = room.game.winner;
    const opponent = room.you === 'X' ? 'O' : 'X';
    const me = room.seats[room.you];
    const them = room.seats[opponent];
    let waiting = null;
    if (!them) waiting = 'Your opponent left the room.';
    else if (me && me.rematch) waiting = `Waiting for ${them.name}...`;
    else if (them.rematch) waiting = `${them.name} wants a rematch.`;

    if (this.spectator) waiting = null;
    const verdict = winner === 'DRAW' ? 'Draw.' : winner === room.you ? 'You win the grid.' : `${this.nameOf(winner)} wins the grid.`;
    setStatus(this.note ? `${this.note.text} ${verdict}` : verdict, winner === room.you ? 'success' : '');

    const details = {
      winner,
      winnerName: winner === 'DRAW' ? null : (winner === room.you ? 'You' : this.nameOf(winner)),
      names: this.names(),
      scores: room.scores,
      waiting,
      canRematch: Boolean(them) && !(me && me.rematch),
      byForfeit: winner !== 'DRAW' && !room.game.winning_line,
      spectating: this.spectator
    };
    if (this.finalShownFor === room.game.game_id) {
      this.ui.showFinal(details);
    } else {
      this.finalShownFor = room.game.game_id;
      setTimeout(() => this.ui.showFinal(details), 900); // let the winning stroke draw first
    }
  }

  // ---------- From the local player ----------

  cellClicked(row, col) {
    const room = this.room;
    if (!room || room.phase !== 'playing') return;
    if (this.spectator) {
      setStatus('You are watching this game.');
      return;
    }
    if (room.game.current_player !== room.you) {
      setStatus(`Wait for ${this.nameOf(room.game.current_player)} to finish their turn.`, 'error');
      return;
    }
    if (room.game.grid[row][col].claimed_by) {
      setStatus('That box is taken. Pick an open one.', 'error');
      return;
    }
    this.cell = { row, col };
    this.conn.send('focus', { row, col });
    this.ui.slip.open(room.settings.league, row, col, room.game.row_criteria[row].display,
      room.game.col_criteria[col].display, ONLINE_MIN_CHARS);
  }

  slipCancelled() {
    this.conn.send('focus', { row: null, col: null });
  }

  pick(name) {
    if (!this.cell) return;
    setStatus(`Checking ${name}...`);
    this.conn.send('pick', { row: this.cell.row, col: this.cell.col, name });
  }

  ready() {
    this.conn.send('ready');
  }

  rematch() {
    this.conn.send('rematch');
  }

  clockExpired() {} // the server calls it

  leave() {
    this.ui.clock.stop();
    this.conn.leave();
  }
}
