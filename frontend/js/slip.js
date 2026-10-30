// The player slip: the dialog where the current player names someone for a box.
// Suggestions come from the league's name list (names.js), filtered here on every keystroke,
// so they show as fast as the player types. A pick always comes from the suggestions: the
// top one is chosen as soon as they show, Enter or Submit takes the chosen one, and a name
// with no suggestions can't be sent, so a typo never costs the turn. Players who share a
// name are listed one by one with their birth date and position.

import { fold, loadNames, matchNames, namesFor } from './names.js';
import { $, closeModal, escapeHtml, isOpen, openModal } from './dom.js';
import { clearSelection, selectCell } from './board.js';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export class PlayerSlip {
  /**
   * @param {(name: string, key: string|null) => void} onSubmit called with the chosen player;
   *   key tells same-named players apart (null for everyone else)
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
    this.options = [];      // the suggestions on screen: {name, key, born, pos}
    this.waiting = false;   // the name list is still loading (only ever the first time)
    this.queued = false;    // Enter was pressed before it came: pick the top one on arrival

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
    loadNames(league).catch(() => {}); // usually loaded already, when the game started
    selectCell(row, col);
    $('req-row').textContent = rowLabel;
    $('req-col').textContent = colLabel;
    this.input.value = '';
    this.waiting = this.queued = false;
    this.renderSuggestions([], '');
    openModal(this.modal);
    this.input.focus();
  }

  close() {
    this.waiting = this.queued = false;
    closeModal(this.modal);
    clearSelection();
  }

  cancel() {
    if (!this.isOpen) return;
    this.close();
    this.onCancel();
  }

  submit(option) {
    if (!option) return;
    this.close();
    this.onSubmit(option.name, option.key);
  }

  /** Sends the chosen suggestion; while the name list is still loading, waits for it. */
  submitChosen() {
    if (this.waiting) {
      this.queued = true;
      return;
    }
    this.submit(this.options[this.active]);
  }

  onInput() {
    const query = this.input.value.trim();
    this.queued = false;
    if (query.length < this.minChars) {
      this.renderSuggestions([], '');
      return;
    }
    const entries = namesFor(this.league);
    if (entries) {
      this.renderSuggestions(matchNames(entries, query), query);
      return;
    }
    // First use before the list arrived: show the matches as soon as it does
    this.waiting = true;
    this.updateConfirm();
    const league = this.league;
    loadNames(league)
      .then(() => {
        if (!this.isOpen || league !== this.league) return;
        this.waiting = false;
        const queued = this.queued;
        this.onInput();
        if (queued) this.submitChosen();
      })
      .catch(() => {
        this.waiting = false;
        this.list.innerHTML = '<li class="none">Could not load the player names. Check the connection.</li>';
        this.updateConfirm();
      });
  }

  updateConfirm() {
    this.confirm.disabled = !this.waiting && this.active < 0;
  }

  onKeydown(e) {
    const items = [...this.list.querySelectorAll('li[data-index]')];
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

  renderSuggestions(options, query) {
    this.active = -1;
    this.options = options;
    this.input.removeAttribute('aria-activedescendant');
    if (!query) {
      this.list.innerHTML = '';
      this.input.setAttribute('aria-expanded', 'false');
      this.updateConfirm();
      return;
    }
    if (!options.length) {
      this.list.innerHTML = '<li class="none">No player by that name in the records. Check the spelling.</li>';
    } else {
      // Names only: showing countries or teams here would give the answer away. Same-named
      // players also show when they were born and where they played on the floor.
      this.list.innerHTML = options.map((option, i) =>
        `<li role="option" id="sugg-${i}" data-index="${i}" aria-selected="false">` +
        `<span>${highlight(option.name, query)}</span>${optionInfo(option)}</li>`
      ).join('');
      this.list.querySelectorAll('li[data-index]').forEach((li, i) => {
        li.addEventListener('mousedown', (e) => e.preventDefault());
        li.addEventListener('click', () => this.submit(this.options[i]));
        li.addEventListener('mousemove', () => this.setActive(i));
      });
      this.setActive(0); // the top match is chosen until the player picks another
    }
    this.input.setAttribute('aria-expanded', 'true');
    this.updateConfirm();
  }

  setActive(index) {
    const items = this.list.querySelectorAll('li[data-index]');
    items.forEach((li, i) => li.setAttribute('aria-selected', String(i === index)));
    this.active = index;
    if (items[index]) {
      this.input.setAttribute('aria-activedescendant', items[index].id);
      items[index].scrollIntoView({ block: 'nearest' });
    }
  }
}

/** The small box beside a name: the other name it matched, what tells twins apart, or both. */
function optionInfo({ key, born, pos, aka }) {
  const parts = aka ? [aka] : [];
  if (born) {
    const [year, month, day] = born.split('-');
    parts.push(month && day ? `b. ${Number(day)} ${MONTHS[Number(month) - 1]} ${year}` : `b. ${year}`);
  }
  if (pos) parts.push(pos);
  if (!parts.length) return key ? '<span class="twin-info">same name</span>' : '';
  return `<span class="twin-info">${escapeHtml(parts.join(' · '))}</span>`;
}

function highlight(name, query) {
  // The names are ASCII, so the folded query lines up with the name letter for letter
  const q = fold(query);
  const i = name.toLowerCase().indexOf(q); // no highlight when dots or an alias don't line up
  if (i < 0) return escapeHtml(name);
  return escapeHtml(name.slice(0, i)) + '<mark>' + escapeHtml(name.slice(i, i + q.length)) + '</mark>' +
    escapeHtml(name.slice(i + q.length));
}
