// The 3x3 grid: criteria headers, hand-drawn marks and the stroke through a winning line.

import { $, escapeHtml } from './dom.js';
import { drawPlays, hash, seeded, smooth, wobble } from './plays.js';

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

// Drawn by hand, a little differently in every box: an X of two wavering strokes that
// never quite meet where they should, an O that doesn't quite close, tilted its own way.
// `rand` is seeded by the game and the box, so a mark keeps its shape across redraws.
function markSvg(mark, fresh, rand) {
  const jitter = (amount) => (rand() * 2 - 1) * amount;
  let paths;
  if (mark === 'X') {
    const stroke = ([x1, y1], [x2, y2]) => {
      const start = [x1 + jitter(5), y1 + jitter(5)];
      const end = [x2 + jitter(5), y2 + jitter(5)];
      const length = Math.hypot(end[0] - start[0], end[1] - start[1]);
      const normal = [-(end[1] - start[1]) / length, (end[0] - start[0]) / length];
      const bow = jitter(6);
      const along = (t) => [start[0] + (end[0] - start[0]) * t + normal[0] * 4 * t * (1 - t) * bow,
                            start[1] + (end[1] - start[1]) * t + normal[1] * 4 * t * (1 - t) * bow];
      return `<path pathLength="1" d="${smooth(wobble(along, 5, 2.2, rand, normal))}"/>`;
    };
    paths = stroke([19, 16], [82, 85]) + stroke([81, 14], [20, 86]);
  } else {
    const turn = jitter(28).toFixed(1);
    const scale = (0.92 + rand() * 0.12).toFixed(3);
    paths = `<g transform="rotate(${turn} 50 50) translate(50 50) scale(${scale}) translate(-50 -50)">` +
      '<path pathLength="1" d="M54 15 C 77 14, 89 33, 87 53 C 85 75, 67 89, 47 87 C 26 85, 13 69, 14 48 C 15 28, 31 14, 58 17"/></g>';
  }
  return `<svg class="mark mark-${mark.toLowerCase()}${fresh ? ' fresh' : ''}" viewBox="0 0 100 100" aria-hidden="true">${paths}</svg>`;
}

/** True when all nine boxes are claimed. */
export function isFull(game) {
  return game.grid.flat().every(cell => cell.claimed_by);
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
          ${markSvg(data.claimed_by, isFresh, seeded(hash(`${game.game_id}:${r}${c}`)))}
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
  corner.innerHTML = over ? '' : `<span class="turn-letter">${turn}</span>`;
  corner.className = `corner turn-${turn.toLowerCase()}`;

  // Plays between each team's answers, and the winning arrow. Measuring the boxes lays the
  // page out there and then, so these draw straight away rather than on the next frame.
  drawPlays(game, fresh);
  if (game.winning_line) {
    drawWinStroke(game.winning_line, game.winner);
  } else {
    $('win-stroke').innerHTML = '';
  }
}

export function drawWinStroke(line, winner) {
  if (!$('board-wrap').getBoundingClientRect().width) return; // not on screen yet
  const wrap = $('board-wrap').getBoundingClientRect();
  // The centre of the X or O drawn in a box (it sits above the name, not in the box's middle)
  const centre = ([r, c]) => {
    const box = $(`box-${r}-${c}`);
    const rect = (box.querySelector('.mark') || box).getBoundingClientRect();
    return [rect.left + rect.width / 2 - wrap.left, rect.top + rect.height / 2 - wrap.top];
  };
  const [x1, y1] = centre(line[0]);
  const [x2, y2] = centre(line[2]);
  // A straight red line through the marks' middles, starting a little before the first
  // and running on a little past the last (about 40% of a mark's width at each end)
  const markWidth = ($(`box-${line[0][0]}-${line[0][1]}`).querySelector('.mark') || $('box-0-0'))
    .getBoundingClientRect().width;
  const length = Math.hypot(x2 - x1, y2 - y1) || 1;
  const ex = ((x2 - x1) / length) * markWidth * 0.4;
  const ey = ((y2 - y1) / length) * markWidth * 0.4;
  $('win-stroke').innerHTML = `<path pathLength="1" d="M${x1 - ex} ${y1 - ey}L${x2 + ex} ${y2 + ey}"/>`;
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
