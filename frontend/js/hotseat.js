// Same-device play: both players share one screen; the browser runs the shot clock.

import { renderActions } from './actions.js';
import { api } from './api.js';
import { renderBoard } from './board.js';
import { $ } from './dom.js';
import { renderScores, setStatus } from './scoresheet.js';
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
    this.gridNo = 0;        // grids dealt in the current series
    this.cell = null;
    this.pending = false; // a pick is being checked; the clock must not also fire
    this.drawArmed = false; // Draw this grid was pressed once; the second press confirms
    this.drawTimer = null;
  }

  playerName(mark) {
    return mark === 'X' ? this.game.player1_name : this.game.player2_name;
  }

  /** The mark that has won more than half of the best-of, once one has. */
  seriesWinner() {
    const target = Math.floor(this.settings.bestOf / 2) + 1;
    return ['X', 'O'].find(mark => this.scores[mark] >= target) || null;
  }

  /** Deals the next grid of the series; note goes before the tip-off line (an agreed draw). */
  async start(note = '') {
    this.ui.clock.stop();
    setStatus('Drawing up a new grid...');
    const { league, clock, difficulty, style, categories } = this.settings;
    // The first move alternates between grids
    const first = this.gamesPlayed % 2 === 0 ? 'X' : 'O';
    this.game = await api.newGame({
      league,
      player1_name: this.names.X,
      player2_name: this.names.O,
      difficulty,
      shot_clock: clock,
      grid_style: style,
      categories,
      first_player: first
    });
    this.gamesPlayed++;
    this.gridNo++;
    this.ui.showGame({ league, gameId: this.game.game_id, names: this.names, room: null,
      series: { bestOf: this.settings.bestOf, grid: this.gridNo } });
    renderScores(this.scores);
    renderBoard(this.game, league);
    this.ui.playByPlay.reset();
    setStatus(`${note}${this.playerName(first)} to start. Pick a box.`);
    this.disarmDraw();
    this.ui.clock.start(clock);
  }

  async refresh(fresh = null) {
    this.game = await api.getGame(this.game.game_id);
    renderBoard(this.game, this.settings.league, fresh);
    this.renderActions();
  }

  renderActions() {
    const running = Boolean(this.game) && this.game.status !== 'finished';
    renderActions({
      visible: running,
      skip: running && !this.pending,
      draw: this.drawArmed
        ? { label: 'Press again to draw', pending: true }
        : { disabled: this.pending }
    });
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

  async pick(name, key = null) {
    if (!this.cell || this.pending) return;
    this.pending = true;
    this.ui.clock.stop();
    const mover = this.game.current_player;
    const { row, col } = this.cell;
    setStatus(`Checking ${name}...`);
    try {
      const result = await api.move(this.game.game_id, row, col, name, key);
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
      this.renderActions();
    }
  }

  async skip() {
    if (this.pending || !this.game || this.game.status === 'finished') return;
    this.pending = true;
    this.disarmDraw();
    this.ui.clock.stop();
    const skipper = this.game.current_player;
    try {
      await api.skipTurn(this.game.game_id);
      await this.refresh();
      this.ui.playByPlay.log(skipper, 'Skipped the turn', true);
      setStatus(`${this.playerName(skipper)} skipped. ${this.playerName(this.game.current_player)} has the ball.`);
      this.ui.clock.start(this.settings.clock);
    } catch (err) {
      console.error(err);
      setStatus('Could not reach the game server.', 'error');
    } finally {
      this.pending = false;
      this.renderActions();
    }
  }

  // Both players share the screen, so pressing twice is the agreement. The grid is written off
  // and a new one dealt; the series score stays as it is.
  drawPressed() {
    if (this.pending || !this.game || this.game.status === 'finished') return;
    if (!this.drawArmed) {
      this.drawArmed = true;
      this.drawTimer = setTimeout(() => this.disarmDraw(), 3000);
      this.renderActions();
      return;
    }
    this.disarmDraw();
    this.drawGrid();
  }

  disarmDraw() {
    clearTimeout(this.drawTimer);
    this.drawTimer = null;
    this.drawArmed = false;
    this.renderActions();
  }

  async drawGrid() {
    this.pending = true;
    this.ui.clock.stop();
    try {
      await api.endInDraw(this.game.game_id);
      this.pending = false;
      await this.start('Grid drawn by agreement. New grid: ');
    } catch (err) {
      console.error(err);
      setStatus('Could not reach the game server.', 'error');
      this.ui.clock.start(this.settings.clock);
    } finally {
      this.pending = false;
    }
  }

  async clockExpired() {
    if (this.pending || !this.game || this.game.status === 'finished') return;
    sfx.playArenaBuzzer();
    this.ui.slip.close();
    this.disarmDraw();
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
      renderScores(this.scores);
      const what = this.seriesWinner() && this.settings.bestOf > 1 ? 'the series' : 'the grid';
      setStatus(`${this.playerName(winner)} wins ${what}.`, 'success');
    } else {
      setStatus('Draw. All nine boxes filled.');
    }
    setTimeout(() => this.ui.showFinal({
      winner,
      winnerName: winner === 'DRAW' ? null : this.playerName(winner),
      names: this.names,
      scores: this.scores,
      bestOf: this.settings.bestOf,
      seriesWinner: this.seriesWinner()
    }), 900);
  }

  /** Next grid; once the series is decided, a new series from 0–0. */
  rematch() {
    if (this.seriesWinner()) {
      this.scores = { X: 0, O: 0 };
      this.gridNo = 0;
    }
    return this.start();
  }

  leave() {
    this.ui.clock.stop();
    clearTimeout(this.drawTimer);
  }
}

export function readNames() {
  return {
    X: $('name-p1').value.trim() || 'Player 1',
    O: $('name-p2').value.trim() || 'Player 2'
  };
}
