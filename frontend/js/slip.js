// The player slip: the dialog where the current player names someone for a box.

import { api } from './api.js';
import { $, closeModal, escapeHtml, isOpen, openModal } from './dom.js';
import { clearSelection, selectCell } from './board.js';

export class PlayerSlip {
  /**
   * @param {(name: string) => void} onSubmit called with the chosen player name
   * @param {() => void} onCancel called when the slip is closed without a pick
   */
  constructor(onSubmit, onCancel = () => {}) {
    this.onSubmit = onSubmit;
    this.onCancel = onCancel;
    this.minChars = 2;
    this.modal = $('modal-select');
    this.input = $('search-player-input');
    this.list = $('search-results-list');
    this.confirm = $('btn-confirm-select');
    this.league = 'nba';
    this.active = -1;
    this.searchSeq = 0;
    this.debounce = null;

    $('btn-cancel-select').addEventListener('click', () => this.cancel());
    this.confirm.addEventListener('click', () => this.submit(this.input.value.trim()));
    this.input.addEventListener('input', () => this.onInput());
    this.input.addEventListener('keydown', (e) => this.onKeydown(e));
  }

  get isOpen() {
    return isOpen(this.modal);
  }

  /** minChars: letters before suggestions appear (online play asks for more) */
  open(league, row, col, rowLabel, colLabel, minChars = 2) {
    this.league = league;
    this.minChars = minChars;
    selectCell(row, col);
    $('req-row').textContent = rowLabel;
    $('req-col').textContent = colLabel;
    this.input.value = '';
    this.renderSuggestions([], '');
    this.confirm.disabled = true;
    openModal(this.modal);
    this.input.focus();
  }

  close() {
    closeModal(this.modal);
    clearSelection();
  }

  cancel() {
    if (!this.isOpen) return;
    this.close();
    this.onCancel();
  }

  submit(name) {
    if (!name) return;
    this.close();
    this.onSubmit(name);
  }

  onInput() {
    const val = this.input.value.trim();
    this.confirm.disabled = val.length === 0;
    clearTimeout(this.debounce);
    if (val.length < this.minChars) {
      this.renderSuggestions([], '');
      return;
    }
    this.debounce = setTimeout(() => this.search(val), 150);
  }

  onKeydown(e) {
    const items = [...this.list.querySelectorAll('li[data-name]')];
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (!items.length) return;
      e.preventDefault();
      const step = e.key === 'ArrowDown' ? 1 : -1;
      this.setActive((this.active + step + items.length) % items.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (this.active >= 0 && items[this.active]) this.submit(items[this.active].dataset.name);
      else if (!this.confirm.disabled) this.submit(this.input.value.trim());
    }
  }

  async search(query) {
    const seq = ++this.searchSeq;
    try {
      const players = await api.searchPlayers(this.league, query);
      if (seq === this.searchSeq) this.renderSuggestions(players, query); // ignore stale answers
    } catch (err) {}
  }

  renderSuggestions(players, query) {
    this.active = -1;
    this.input.removeAttribute('aria-activedescendant');
    if (!query) {
      this.list.innerHTML = '';
      this.input.setAttribute('aria-expanded', 'false');
      return;
    }
    if (!players.length) {
      this.list.innerHTML = '<li class="none">No player by that name in the records</li>';
    } else {
      // Names only: showing countries or teams here would give the answer away
      this.list.innerHTML = players.map((p, i) =>
        `<li role="option" id="sugg-${i}" data-name="${escapeHtml(p.name)}" aria-selected="false">${highlight(p.name, query)}</li>`
      ).join('');
      this.list.querySelectorAll('li[data-name]').forEach((li, i) => {
        li.addEventListener('mousedown', (e) => e.preventDefault());
        li.addEventListener('click', () => this.submit(li.dataset.name));
        li.addEventListener('mousemove', () => this.setActive(i));
      });
    }
    this.input.setAttribute('aria-expanded', 'true');
  }

  setActive(index) {
    const items = this.list.querySelectorAll('li[data-name]');
    items.forEach((li, i) => li.setAttribute('aria-selected', String(i === index)));
    this.active = index;
    if (items[index]) {
      this.input.setAttribute('aria-activedescendant', items[index].id);
      items[index].scrollIntoView({ block: 'nearest' });
    }
  }
}

function highlight(name, query) {
  const i = name.toLowerCase().indexOf(query.toLowerCase());
  if (i < 0) return escapeHtml(name);
  return escapeHtml(name.slice(0, i)) + '<mark>' + escapeHtml(name.slice(i, i + query.length)) + '</mark>' +
    escapeHtml(name.slice(i + query.length));
}
