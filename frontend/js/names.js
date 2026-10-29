// The league's player names for the autocomplete: fetched once per league, then filtered
// right here as the player types, so suggestions show with no round trip. The list holds
// names only (and, for players who share a name, a birth date and position): nothing that
// would give an answer away.

import { api } from './api.js';

const loading = {};   // league -> promise of the entries
const loaded = {};    // league -> entries, once they are here

// Letters that don't split into a base letter and an accent
const PLAIN = { 'ı': 'i', 'İ': 'i', 'ø': 'o', 'Ø': 'o', 'đ': 'd', 'Đ': 'd', 'ł': 'l', 'Ł': 'l', 'ß': 'ss', 'æ': 'ae' };

/** Lower case without accents: 'Dončić' and 'Doncic' match the same name (the data is ASCII). */
export function fold(text) {
  return text.replace(/[ıİøØđĐłŁßæ]/g, ch => PLAIN[ch])
    .normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

export function loadNames(league) {
  if (!loading[league]) {
    loading[league] = api.playerNames(league)
      .then(({ names, twins }) => {
        loaded[league] = names.map(name => ({ name, folded: fold(name), twins: twins[name] || null }));
        return loaded[league];
      })
      .catch(err => {
        delete loading[league]; // try again next time
        throw err;
      });
  }
  return loading[league];
}

/** The entries if the list is already here, else null. */
export function namesFor(league) {
  return loaded[league] || null;
}

/**
 * Suggestions for what has been typed: names starting with it first, then names containing
 * it, alphabetically (the list comes sorted). Each same-named player is a suggestion of its
 * own: {name, key, born, pos}; other players have no key.
 */
export function matchNames(entries, query, limit = 8) {
  const q = fold(query.trim());
  if (!q) return [];
  const starts = [];
  const inside = [];
  for (const entry of entries) {
    const at = entry.folded.indexOf(q);
    if (at === 0) starts.push(entry);
    else if (at > 0) inside.push(entry);
  }
  const options = [];
  for (const entry of starts.concat(inside)) {
    if (entry.twins) entry.twins.forEach(t => options.push({ name: entry.name, key: t.key, born: t.born, pos: t.pos }));
    else options.push({ name: entry.name, key: null });
    if (options.length >= limit) break;
  }
  return options.slice(0, limit);
}
