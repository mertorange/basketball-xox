// Plays drawn between a team's answers, the way a coach links players on a tactics board:
// each new answer connects to the same team's previous one with a pass, a cut, a dribble or
// a screen. Which one, and every wobble of the line, is random but fixed for the game and
// the two boxes, so everyone in an online room sees the same drawing and a redraw never
// changes it. A new play is drawn on like a marker stroke, line first, then its head.

import { $ } from './dom.js';

const KINDS = ['pass', 'cut', 'dribble', 'screen'];

// When the newest play starts, after its box's mark has been drawn (see .mark.fresh)
const PLAY_DELAY = 0.5;
const PLAY_DRAW = 0.5;
const HEAD_DRAW = 0.16;

/**
 * @param {object} game   the server's GameState
 * @param {{row:number,col:number}|null} fresh  the box claimed just now: its play draws on
 */
export function drawPlays(game, fresh = null) {
  const svg = $('plays');
  const board = $('grid-table');
  const origin = board.getBoundingClientRect();
  const size = $('box-0-0').getBoundingClientRect().width;
  if (!size) return; // the board isn't on screen yet; the next draw places the plays
  // The svg covers the board inside its border
  const left = origin.left + board.clientLeft;
  const top = origin.top + board.clientTop;
  const centre = ({ row, col }) => {
    const rect = $(`box-${row}-${col}`).getBoundingClientRect();
    return [rect.left + rect.width / 2 - left, rect.top + rect.height / 2 - top];
  };

  let html = '';
  const claims = claimOrder(game);
  for (const mark of ['X', 'O']) {
    const team = claims.filter(claim => claim.mark === mark);
    for (let i = 1; i < team.length; i++) {
      const from = team[i - 1];
      const to = team[i];
      const seed = hash(`${game.game_id}:${from.row}${from.col}>${to.row}${to.col}`);
      const kind = KINDS[seed % KINDS.length];
      const isFresh = Boolean(fresh) && fresh.row === to.row && fresh.col === to.col;
      html += play(kind, centre(from), centre(to), size, isFresh, seeded(seed));
    }
  }
  svg.innerHTML = html;
}

/** Claimed boxes in the order they were claimed (used_players is in pick order). */
function claimOrder(game) {
  const claimed = game.grid.flat().filter(cell => cell.claimed_by);
  const order = [];
  for (const name of game.used_players) {
    const cell = claimed.find(c => c.player_name === name && !order.includes(c));
    if (cell) order.push(cell);
  }
  return order.map(cell => ({ row: cell.row, col: cell.col, mark: cell.claimed_by }));
}

/** A small, stable string hash (FNV-1a). */
export function hash(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** A seeded random number source (mulberry32): the same seed always draws the same hand. */
export function seeded(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const fmt = (x, y) => `${x.toFixed(1)} ${y.toFixed(1)}`;

/** A smooth path through points, the way a hand rounds a line off between wobbles. */
export function smooth(points) {
  let d = `M${fmt(...points[0])}`;
  for (let i = 1; i < points.length - 1; i++) {
    const [x, y] = points[i];
    const [nx, ny] = points[i + 1];
    d += `Q${fmt(x, y)} ${fmt((x + nx) / 2, (y + ny) / 2)}`;
  }
  return d + `L${fmt(...points[points.length - 1])}`;
}

/** Points along a hand-drawn stroke: the path a straight or bent line takes, with a wobble. */
export function wobble(along, count, amount, rand, [nx, ny]) {
  const points = [];
  for (let i = 0; i <= count; i++) {
    const [x, y] = along(i / count);
    // The ends stay put; the middle drifts a little either side
    const drift = i === 0 || i === count ? 0 : (rand() * 2 - 1) * amount;
    points.push([x + nx * drift, y + ny * drift]);
  }
  return points;
}

/** An open arrowhead at the end of a stroke, its two wings never quite the same. */
export function arrowhead([ex, ey], angle, length, rand) {
  const wing = (turn) => {
    const l = length * (0.85 + rand() * 0.3);
    const a = angle + turn + (rand() * 2 - 1) * 0.12;
    return [ex - l * Math.cos(a), ey - l * Math.sin(a)];
  };
  return `M${fmt(...wing(0.55))}L${fmt(ex, ey)}L${fmt(...wing(-0.55))}`;
}

function play(kind, [ax, ay], [bx, by], size, fresh, rand) {
  const jitter = (amount) => (rand() * 2 - 1) * amount;
  // From the edge of one mark to the edge of the next, not through them
  const length = Math.hypot(bx - ax, by - ay);
  const [ux, uy] = [(bx - ax) / length, (by - ay) / length];
  const normal = [-uy, ux];
  const gapStart = size * (0.3 + jitter(0.03));
  const gapEnd = size * (0.3 + jitter(0.03));
  const [sx, sy] = [ax + ux * gapStart, ay + uy * gapStart];
  const [ex, ey] = [bx - ux * gapEnd, by - uy * gapEnd];
  const span = Math.hypot(ex - sx, ey - sy);
  const shaky = size * 0.014;

  // The path the stroke follows: a slight bow for straight lines, a real bend for a cut
  const bend = kind === 'cut'
    ? span * (0.18 + rand() * 0.1) * (rand() < 0.5 ? 1 : -1)
    : jitter(span * 0.05);
  const along = (t) => {
    const bow = 4 * t * (1 - t) * bend;
    return [sx + (ex - sx) * t + normal[0] * bow, sy + (ey - sy) * t + normal[1] * bow];
  };

  const strokes = [];
  if (kind === 'dribble') {
    // Zigzag most of the way, each tooth a little different, then straight into the head
    const steps = Math.max(4, Math.round((span * 0.75) / (size * 0.075)));
    const amp = size * 0.045;
    const points = [[sx, sy]];
    for (let i = 1; i <= steps; i++) {
      const t = (i / steps) * 0.75 + jitter(0.012);
      const side = (i % 2 ? 1 : -1) * amp * (0.7 + rand() * 0.6);
      const [x, y] = along(t);
      points.push([x + normal[0] * side, y + normal[1] * side]);
    }
    points.push(along(0.88), [ex, ey]);
    strokes.push(`M${points.map(p => fmt(...p)).join('L')}`);
  } else if (kind === 'pass') {
    // Dashes of uneven length along a wobbly line, each its own little stroke
    const points = wobble(along, 40, shaky, rand, normal);
    let dash = [];
    let drawn = 0;
    let target = size * (0.08 + jitter(0.02));
    let gap = false;
    for (let i = 1; i < points.length; i++) {
      const step = Math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]);
      drawn += step;
      if (!gap) dash.push(points[i - 1]);
      if (drawn >= target || i === points.length - 1) {
        if (!gap) {
          dash.push(points[i]);
          if (dash.length > 1) strokes.push(smooth(dash));
          dash = [];
        }
        gap = !gap;
        drawn = 0;
        target = gap ? size * (0.055 + jitter(0.015)) : size * (0.08 + jitter(0.02));
      }
    }
  } else {
    strokes.push(smooth(wobble(along, 6, shaky, rand, normal)));
  }

  // The end: a bar across the line for a screen, an arrowhead for everything else
  const [px, py] = along(0.9);
  const angle = Math.atan2(ey - py, ex - px);
  let end;
  if (kind === 'screen') {
    const tilt = angle + Math.PI / 2 + jitter(0.18);
    const half = size * (0.1 + jitter(0.015));
    end = `M${fmt(ex + Math.cos(tilt) * half, ey + Math.sin(tilt) * half)}` +
      `L${fmt(ex - Math.cos(tilt) * half * (0.9 + rand() * 0.2), ey - Math.sin(tilt) * half * (0.9 + rand() * 0.2))}`;
  } else {
    end = arrowhead([ex, ey], angle, size * 0.09, rand);
  }

  // A new play draws on stroke by stroke, then its head; older ones are simply there
  const timing = (delay, duration) =>
    fresh ? ` style="animation-delay:${delay.toFixed(3)}s;animation-duration:${duration.toFixed(3)}s"` : '';
  const each = PLAY_DRAW / strokes.length;
  const lines = strokes
    .map((d, i) => `<path pathLength="1" d="${d}"${timing(PLAY_DELAY + i * each, Math.max(each, 0.04))}/>`)
    .join('');
  const head = `<path class="end" pathLength="1" d="${end}"${timing(PLAY_DELAY + PLAY_DRAW, HEAD_DRAW)}/>`;
  return `<g class="play ${kind}${fresh ? ' fresh' : ''}">${lines}${head}</g>`;
}
