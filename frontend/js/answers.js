// After the final whistle: every box's valid answers, the best known first.

import { api } from './api.js';
import { $, escapeHtml, openModal } from './dom.js';

const SHOWN_PER_BOX = 12;

export async function showAnswers(gameId) {
  const modal = $('modal-answers');
  const grid = $('answers-grid');
  grid.innerHTML = '<p class="hint">Looking up the records...</p>';
  openModal(modal);
  try {
    const { cells } = await api.answers(gameId);
    grid.innerHTML = cells.flat().map(renderBox).join('');
  } catch (err) {
    grid.innerHTML = '<p class="hint">The answers are not available for this game.</p>';
  }
}

function renderBox(cell) {
  const mark = cell.claimed_by ? cell.claimed_by.toLowerCase() : null;
  const others = cell.answers.filter(name => name !== cell.picked).slice(0, SHOWN_PER_BOX);
  const more = cell.count - others.length - (cell.picked ? 1 : 0);
  const picked = cell.picked
    ? `<p class="ans-picked"><b class="ink-${mark}">${cell.claimed_by}</b> ${escapeHtml(cell.picked)}</p>`
    : '<p class="ans-picked ans-open">Left open</p>';
  return `
    <section class="ans-box">
      <h3 class="ans-head">${escapeHtml(cell.row)} <span>×</span> ${escapeHtml(cell.col)}</h3>
      ${picked}
      <p class="ans-count">${cell.count} ${cell.count === 1 ? 'answer' : 'answers'}</p>
      <p class="ans-list">${others.map(escapeHtml).join(', ')}${more > 0 ? ` <span>+${more} more</span>` : ''}</p>
    </section>`;
}
