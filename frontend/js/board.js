// The 3x3 grid: criteria headers, hand-drawn marks and the stroke through a winning line.

import { $, escapeHtml } from './dom.js';

// Small print above each criterion, by criterion type
const TYPE_LABELS = {
  team: { nba: 'Team', euroleague: 'Club' },
  country: 'Born in',
  college: 'College',
  draft: 'Draft',
  award: 'Award',
  career: 'Career',
  era: 'Era'
};

function typeLabel(type, league) {
  const label = TYPE_LABELS[type] || type;
  return typeof label === 'string' ? label : label[league];
}

function criterionHtml(crit, league) {
  return `<span class="crit-type">${typeLabel(crit.type, league)}</span>` +
    `<span class="crit-name">${escapeHtml(crit.display)}</span>`;
}

// Drawn by hand: slightly bowed strokes, an O that doesn't quite close
function markSvg(mark, fresh) {
  const paths = mark === 'X'
    ? '<path pathLength="1" d="M18 15 C 36 35, 58 58, 83 86"/><path pathLength="1" d="M81 13 C 63 34, 41 60, 19 87"/>'
    : '<path pathLength="1" d="M54 15 C 77 14, 89 33, 87 53 C 85 75, 67 89, 47 87 C 26 85, 13 69, 14 48 C 15 28, 31 14, 58 17"/>';
  return `<svg class="mark mark-${mark.toLowerCase()}${fresh ? ' fresh' : ''}" viewBox="0 0 100 100" aria-hidden="true">${paths}</svg>`;
}

/**
 * @param {object} game     the server's GameState
 * @param {string} league   'nba' | 'euroleague'
 * @param {{row:number,col:number}|null} fresh  the box claimed just now, to animate its mark
 */
export function renderBoard(game, league, fresh = null) {
  game.col_criteria.forEach((crit, i) => { $(`ch-${i}`).innerHTML = criterionHtml(crit, league); });
  game.row_criteria.forEach((crit, i) => { $(`rh-${i}`).innerHTML = criterionHtml(crit, league); });

  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 3; c++) {
      const data = game.grid[r][c];
      const cell = $(`box-${r}-${c}`);
      const where = `${game.row_criteria[r].display} and ${game.col_criteria[c].display}`;
      cell.className = 'cell';
      if (data.claimed_by) {
        const isFresh = fresh && fresh.row === r && fresh.col === c;
        cell.classList.add('claimed');
        cell.innerHTML = `
          ${markSvg(data.claimed_by, isFresh)}
          <span class="cell-player">${escapeHtml(data.player_name || '')}</span>
          <span class="cell-meta">b. ${escapeHtml(data.player_country || '?')}</span>`;
        cell.setAttribute('aria-label', `${where}: ${data.claimed_by}, ${data.player_name}`);
      } else {
        cell.innerHTML = '';
        cell.setAttribute('aria-label', `${where}: open`);
      }
    }
  }

  const over = game.status === 'finished';
  const turn = game.current_player;
  $('panel-x').classList.toggle('active-turn', !over && turn === 'X');
  $('panel-o').classList.toggle('active-turn', !over && turn === 'O');
  const corner = $('corner-mark');
  corner.textContent = over ? '' : turn;
  corner.className = `corner turn-${turn.toLowerCase()}`;

  if (game.winning_line) {
    requestAnimationFrame(() => drawWinStroke(game.winning_line, game.winner));
  } else {
    $('win-stroke').innerHTML = '';
  }
}

export function drawWinStroke(line, winner) {
  const wrap = $('board-wrap').getBoundingClientRect();
  const centre = ([r, c]) => {
    const rect = $(`box-${r}-${c}`).getBoundingClientRect();
    return [rect.left + rect.width / 2 - wrap.left, rect.top + rect.height / 2 - wrap.top];
  };
  const [x1, y1] = centre(line[0]);
  const [x2, y2] = centre(line[2]);
  // Overshoot a little past the outer boxes, like a pen stroke
  const dx = (x2 - x1) * 0.18;
  const dy = (y2 - y1) * 0.18;
  const colour = winner === 'O' ? 'var(--o)' : 'var(--x)';
  $('win-stroke').innerHTML =
    `<line pathLength="1" x1="${x1 - dx}" y1="${y1 - dy}" x2="${x2 + dx}" y2="${y2 + dy}" style="stroke:${colour}"/>`;
}

/** Online: mark the box the player on the clock has open, and lock the grid when it isn't your turn. */
export function showFocus(focus, mark) {
  document.querySelectorAll('.cell.peek').forEach(c => c.classList.remove('peek', 'peek-x', 'peek-o'));
  if (focus) $(`box-${focus.row}-${focus.col}`).classList.add('peek', `peek-${mark.toLowerCase()}`);
}

export function lockBoard(locked) {
  $('board-wrap').classList.toggle('locked', locked);
}

export function selectCell(row, col) {
  clearSelection();
  $(`box-${row}-${col}`).classList.add('selected');
}

export function clearSelection() {
  document.querySelectorAll('.cell.selected').forEach(c => c.classList.remove('selected'));
}
