// Everything around the grid: status line, the series score on the scoreboard, play-by-play.

import { buildSegments, showNumber } from './clock.js';
import { $, escapeHtml } from './dom.js';

export function setStatus(msg, type = '') {
  const el = $('game-status-text');
  el.textContent = msg;
  el.className = 'status' + (type ? ` ${type}` : '');
}

// Each team's wins in the series, in seven-segment digits like the shot clock
export function renderScores(scores) {
  [['X', scores.X], ['O', scores.O]].forEach(([mark, wins]) => {
    const unit = $(`score-${mark.toLowerCase()}`);
    const digits = unit.querySelector('svg');
    const slots = String(wins).length;
    if (digits.querySelectorAll('g').length !== slots) buildSegments(digits, slots);
    showNumber(digits, wins);
    unit.setAttribute('aria-label', `${wins} ${wins === 1 ? 'win' : 'wins'}`);
  });
}

export class PlayByPlay {
  constructor(list) {
    this.list = list;
    this.entries = [];
  }

  reset() {
    this.entries = [];
    this.render();
  }

  log(mark, text, turnover = false) {
    this.entries.unshift({ no: this.entries.length + 1, mark, text, turnover });
    this.render();
  }

  render() {
    if (!this.entries.length) {
      this.list.innerHTML = '<li><span></span><span></span><span class="pbp-empty">Nothing yet. Tip-off.</span></li>';
      return;
    }
    this.list.innerHTML = this.entries.map(p => `
      <li>
        <span class="pbp-no">${String(p.no).padStart(2, '0')}</span>
        <span class="pbp-mark ${p.mark.toLowerCase()}">${p.mark}</span>
        <span class="pbp-text${p.turnover ? ' turnover' : ''}">${escapeHtml(p.text)}</span>
      </li>`).join('');
  }
}
