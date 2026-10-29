// Same-device play: both players share one screen; the browser runs the shot clock.

import { api } from './api.js';
import { renderBoard } from './board.js';
import { $ } from './dom.js';
import { renderTallies, setStatus } from './scoresheet.js';
import { sfx } from './sound.js';

export class HotSeatGame {
  /**
   * @param {object} ui  shared screen parts from main.js: clock, slip, playByPlay,
   *                     showGame(), showMenu(), showFinal(result, names, scores)
   */
  constructor(ui, settings, names) {
    this.ui = ui;
    this.settings = settings;
    this.names = names;
    this.game = null;
    this.scores = { X: 0, O: 0 };
    this.gamesPlayed = 0;
    this.cell = null;
    this.pending = false; // a pick is being checked; the clock must not also fire
  }

  playerName(mark) {
    return mark === 'X' ? this.game.player1_name : this.game.player2_name;
  }

  async start() {
    this.ui.clock.stop();
    setStatus('Drawing up a new grid...');
    const { league, clock, density, style } = this.settings;
    // The first move alternates between grids
    const first = this.gamesPlayed % 2 === 0 ? 'X' : 'O';
    this.game = await api.newGame({
      league,
      player1_name: this.names.X,
      player2_name: this.names.O,
      min_answers: density,
      shot_clock: clock,
      grid_style: style,
      first_player: first
    });
    this.gamesPlayed++;
    this.ui.showGame({ league, gameId: this.game.game_id, names: this.names, room: null });
    renderTallies(this.scores);
    renderBoard(this.game, league);
    this.ui.playByPlay.reset();
    setStatus(`${this.playerName(first)} to start. Pick a box.`);
    this.ui.clock.start(clock);
  }

  async refresh(fresh = null) {
    this.game = await api.getGame(this.game.game_id);
    renderBoard(this.game, this.settings.league, fresh);
  }

  cellClicked(row, col) {
    const game = this.game;
    if (!game || game.status === 'finished' || this.pending) return;
    if (game.grid[row][col].claimed_by) {
      setStatus('That box is taken. Pick an open one.', 'error');
      return;
    }
    this.cell = { row, col };
    this.ui.slip.open(this.settings.league, row, col, game.row_criteria[row].display, game.col_criteria[col].display);
  }

  slipCancelled() {}

  async pick(name) {
    if (!this.cell || this.pending) return;
    this.pending = true;
    this.ui.clock.stop();
    const mover = this.game.current_player;
    const { row, col } = this.cell;
    setStatus(`Checking ${name}...`);
    try {
      const result = await api.move(this.game.game_id, row, col, name);
      if (result.success) {
        sfx.playScore();
        await this.refresh({ row, col });
        const placed = this.game.grid[row][col].player_name || name;
        this.ui.playByPlay.log(mover, `${placed} · ${this.game.row_criteria[row].display} × ${this.game.col_criteria[col].display}`);
        if (result.game_over) {
          this.finish(result.winner);
        } else {
          setStatus(`Good. ${this.playerName(this.game.current_player)} is up.`, 'success');
          this.ui.clock.start(this.settings.clock);
        }
      } else {
        sfx.playTurnover();
        await this.refresh();
        this.ui.playByPlay.log(mover, `Turnover: ${name}`, true);
        setStatus(`${result.message.replace(/^Turnover!\s*/, 'Turnover. ')} ${this.playerName(this.game.current_player)} has the ball.`, 'error');
        this.ui.clock.start(this.settings.clock);
      }
    } catch (err) {
      console.error(err);
      setStatus('Could not reach the game server.', 'error');
    } finally {
      this.pending = false;
    }
  }

  async clockExpired() {
    if (this.pending || !this.game || this.game.status === 'finished') return;
    sfx.playArenaBuzzer();
    this.ui.slip.close();
    const offender = this.game.current_player;
    try {
      await api.shotClockViolation(this.game.game_id);
      await this.refresh();
      this.ui.playByPlay.log(offender, 'Shot clock violation', true);
      setStatus(`Shot clock violation. ${this.playerName(this.game.current_player)} has the ball.`, 'error');
      this.ui.clock.start(this.settings.clock);
    } catch (err) {
      console.error(err);
    }
  }

  finish(winner) {
    this.ui.clock.stop();
    if (winner === 'X' || winner === 'O') {
      sfx.playWin();
      this.scores[winner]++;
      renderTallies(this.scores);
      setStatus(`${this.playerName(winner)} wins the grid.`, 'success');
    } else {
      setStatus('Draw. All nine boxes filled.');
    }
    setTimeout(() => this.ui.showFinal({
      winner,
      winnerName: winner === 'DRAW' ? null : this.playerName(winner),
      names: this.names,
      scores: this.scores,
      waiting: null
    }), 900);
  }

  rematch() {
    return this.start();
  }

  newGrid() {
    return this.start();
  }

  leave() {
    this.ui.clock.stop();
  }
}

export function readNames() {
  return {
    X: $('name-p1').value.trim() || 'Player 1',
    O: $('name-p2').value.trim() || 'Player 2'
  };
}
