// The buttons under the grid: skip the turn, end the game as a draw.

import { $ } from './dom.js';

/**
 * visible: false hides the whole row (no game running);
 * skip: whether the skip button can be pressed now;
 * draw: { label, disabled, pending, answer }: pending marks an open offer (or a press waiting
 *       for its confirmation), answer shows the small Yes / No under the button
 */
export function renderActions({ visible = true, skip = false, draw = {} } = {}) {
  $('game-actions').hidden = !visible;
  $('btn-skip').disabled = !skip;
  const button = $('btn-draw');
  button.textContent = draw.label || 'End as draw';
  button.disabled = Boolean(draw.disabled);
  button.classList.toggle('pending', Boolean(draw.pending));
  $('draw-answer').hidden = !draw.answer;
}

/** True when a finished game still had open boxes and no line: the players agreed to stop. */
export function isAgreedDraw(game) {
  return game.winner === 'DRAW' && game.grid.flat().some(cell => !cell.claimed_by);
}
