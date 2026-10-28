// Everything written on the sheet around the grid: status line, win tallies, play-by-play.

import { $, escapeHtml } from './dom.js';

export function setStatus(msg, type = '') {
  const el = $('game-status-text');
  el.textContent = msg;
  el.className = 'status' + (type ? ` ${type}` : '');
}

// Wins as tally marks, five to a gate
export function renderTallies(scores) {
  [[$('tally-x'), scores.X], [$('tally-o'), scores.O]].forEach(([el, wins]) => {
    let html = '';
    for (let left = wins; left > 0; left -= 5) {
      const n = Math.min(left, 5);
      html += `<span class="tally-gate${n === 5 ? ' full' : ''}">${'<i></i>'.repeat(Math.min(n, 4))}</span>`;
    }
    el.innerHTML = html;
    el.setAttribute('aria-label', `${wins} ${wins === 1 ? 'win' : 'wins'}`);
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
