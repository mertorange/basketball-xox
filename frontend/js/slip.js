// The player slip: the dialog where the current player names someone for a box.
// A pick always comes from the suggestions: the top one is chosen as soon as they arrive,
// Enter or Submit takes the chosen one, and a name with no suggestions can't be sent, so a
// typo never costs the turn.

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
    this.names = [];        // the suggestions on screen
    this.searching = false; // the list on screen is for an older text; new results are coming
    this.queued = false;    // Enter was pressed before they came: pick the top one on arrival
    this.searchSeq = 0;
    this.debounce = null;

    $('btn-cancel-select').addEventListener('click', () => this.cancel());
    this.confirm.addEventListener('click', () => this.submitChosen());
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
    this.searching = this.queued = false;
    this.renderSuggestions([], '');
    openModal(this.modal);
    this.input.focus();
  }

  close() {
    clearTimeout(this.debounce);
    this.searchSeq++; // drop any answer still on its way
    this.searching = this.queued = false;
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

  /** Sends the chosen suggestion; while results are still coming, waits for them. */
  submitChosen() {
    if (this.searching) {
      this.queued = true;
      return;
    }
    const name = this.names[this.active];
    if (name) this.submit(name);
  }

  onInput() {
    const val = this.input.value.trim();
    clearTimeout(this.debounce);
    this.queued = false;
    if (val.length < this.minChars) {
      this.searchSeq++;
      this.searching = false;
      this.renderSuggestions([], '');
      return;
    }
    // The names on screen are for the old text: don't let Enter send one of them
    this.searching = true;
    this.updateConfirm();
    this.debounce = setTimeout(() => this.search(val), 150);
  }

  updateConfirm() {
    this.confirm.disabled = !this.searching && this.active < 0;
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
      this.submitChosen();
    }
  }

  async search(query) {
    const seq = ++this.searchSeq;
    let players = [];
    try {
      players = await api.searchPlayers(this.league, query);
    } catch (err) {}
    if (seq !== this.searchSeq) return; // a newer search is on its way
    this.searching = false;
    this.renderSuggestions(players, query);
    if (this.queued) {
      this.queued = false;
      this.submitChosen();
    }
  }

  renderSuggestions(players, query) {
    this.active = -1;
    this.names = players.map(p => p.name);
    this.input.removeAttribute('aria-activedescendant');
    if (!query) {
      this.list.innerHTML = '';
      this.input.setAttribute('aria-expanded', 'false');
      this.updateConfirm();
      return;
    }
    if (!players.length) {
      this.list.innerHTML = '<li class="none">No player by that name in the records. Check the spelling.</li>';
    } else {
      // Names only: showing countries or teams here would give the answer away
      this.list.innerHTML = players.map((p, i) =>
        `<li role="option" id="sugg-${i}" data-name="${escapeHtml(p.name)}" aria-selected="false"><span>${highlight(p.name, query)}</span></li>`
      ).join('');
      this.list.querySelectorAll('li[data-name]').forEach((li, i) => {
        li.addEventListener('mousedown', (e) => e.preventDefault());
        li.addEventListener('click', () => this.submit(li.dataset.name));
        li.addEventListener('mousemove', () => this.setActive(i));
      });
      this.setActive(0); // the top match is chosen until the player picks another
    }
    this.input.setAttribute('aria-expanded', 'true');
    this.updateConfirm();
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
