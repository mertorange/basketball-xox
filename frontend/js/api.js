// The game server's HTTP API.

async function request(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(`${options.method || 'GET'} ${path} failed with ${res.status}`);
  return res.json();
}

function post(path, body) {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}

export const api = {
  newGame: (settings) => post('/api/new-game', settings),
  getGame: (gameId) => request(`/api/game/${gameId}`),
  answers: (gameId) => request(`/api/game/${gameId}/answers`),
  move: (gameId, row, col, playerName) => post('/api/move', { game_id: gameId, row, col, player_name: playerName }),
  shotClockViolation: (gameId) => post('/api/shot-clock-violation', { game_id: gameId }),
  searchPlayers: (league, query) =>
    request(`/api/search-players?league=${encodeURIComponent(league)}&q=${encodeURIComponent(query)}`),
  createRoom: (settings) => post('/api/rooms', settings),
  roomInfo: (code) => request(`/api/rooms/${encodeURIComponent(code)}`)
};
