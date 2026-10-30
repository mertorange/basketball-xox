from backend.catalog.criteria import AWARD, TEAM
from backend.game.manager import to_criterion
from backend.game.rules import is_full, other_player, winning_line


def test_winning_line_and_draw():
    assert winning_line([["X", "X", "X"], [None] * 3, [None] * 3]) == [[0, 0], [0, 1], [0, 2]]
    assert winning_line([["O", None, None], [None, "O", None], [None, None, "O"]]) == [[0, 0], [1, 1], [2, 2]]
    assert winning_line([["X", "O", "X"], ["X", "O", "O"], ["O", "X", "X"]]) is None
    assert is_full([["X", "O", "X"], ["X", "O", "O"], ["O", "X", "X"]])
    assert other_player("X") == "O" and other_player("O") == "X"


def set_board(game, index, rows, cols):
    game.row_criteria = [to_criterion(index.get(*key)) for key in rows]
    game.col_criteria = [to_criterion(index.get(*key)) for key in cols]


def test_move_flow(manager, nba_index):
    game = manager.create_game("nba", grid_style="classic")
    set_board(game, nba_index,
              [(TEAM, "Boston Celtics"), (TEAM, "Miami Heat"), (AWARD, "champion")],
              [(TEAM, "Los Angeles Lakers"), (TEAM, "Chicago Bulls"), (TEAM, "Golden State Warriors")])

    ok = manager.make_move(game.game_id, 0, 0, "alpha one")
    assert ok.success and ok.cell.player_name == "Alpha One" and game.current_player == "O"

    used = manager.make_move(game.game_id, 1, 1, "Alpha One")
    assert not used.success and "already picked" in used.message and game.current_player == "X"

    wrong = manager.make_move(game.game_id, 2, 2, "Gamma Three")
    assert not wrong.success
    assert wrong.message == ("Turnover! Gamma Three never won an NBA title and "
                             "did not play for Golden State Warriors.")
    assert game.current_player == "O"

    unknown = manager.make_move(game.game_id, 1, 0, "Nobody")
    assert "not found" in unknown.message and game.current_player == "X"


def test_same_named_players(manager, nba_index):
    game = manager.create_game("nba", grid_style="classic")
    set_board(game, nba_index,
              [(TEAM, "Miami Heat"), (TEAM, "Boston Celtics"), (TEAM, "Chicago Bulls")],
              [(AWARD, "mvp"), (TEAM, "San Antonio Spurs"), (TEAM, "Golden State Warriors")])
    # Two players are called Twin Name; only the Heat one won MVP
    result = manager.make_move(game.game_id, 0, 0, "Twin Name")
    assert result.success


def twin_keys(nba_index):
    celtics, heat = sorted(nba_index.catalog.find("Twin Name"), key=lambda p: p["teams"])
    return celtics["key"], heat["key"]


def test_a_picked_key_names_the_player(manager, nba_index):
    game = manager.create_game("nba", grid_style="classic")
    set_board(game, nba_index,
              [(TEAM, "Boston Celtics"), (TEAM, "Chicago Bulls"), (TEAM, "Miami Heat")],
              [(TEAM, "Los Angeles Lakers"), (TEAM, "Golden State Warriors"), (TEAM, "San Antonio Spurs")])
    celtics_key, heat_key = twin_keys(nba_index)
    assert celtics_key != heat_key
    # The Heat Twin was chosen from the list; he never played for Boston, so that's a turnover
    wrong = manager.make_move(game.game_id, 0, 1, "Twin Name", player_key=heat_key)
    assert not wrong.success and "did not play for Boston Celtics" in wrong.message


def test_same_named_players_are_used_separately(manager, nba_index):
    game = manager.create_game("nba", grid_style="classic")
    set_board(game, nba_index,
              [(TEAM, "Boston Celtics"), (TEAM, "Miami Heat"), (TEAM, "Chicago Bulls")],
              [(TEAM, "Boston Celtics"), (TEAM, "Miami Heat"), (TEAM, "Golden State Warriors")])
    celtics_key, heat_key = twin_keys(nba_index)
    assert manager.make_move(game.game_id, 0, 0, "Twin Name", player_key=celtics_key).success
    # The other Twin Name is still free, but the same one can't come back
    assert manager.make_move(game.game_id, 1, 1, "Twin Name", player_key=heat_key).success
    again = manager.make_move(game.game_id, 0, 1, "Twin Name", player_key=celtics_key)
    assert not again.success and "already picked" in again.message
    assert game.used_keys == [celtics_key, heat_key]
    # Without a key, a name whose players are all used is a used name
    assert "already picked" in manager.make_move(game.game_id, 2, 2, "Twin Name").message


def test_win(manager, nba_index):
    game = manager.create_game("nba", grid_style="classic")
    set_board(game, nba_index,
              [(TEAM, "Boston Celtics"), (TEAM, "Chicago Bulls"), (TEAM, "Miami Heat")],
              [(TEAM, "Los Angeles Lakers"), (TEAM, "Boston Celtics"), (TEAM, "Chicago Bulls")])
    assert manager.make_move(game.game_id, 0, 0, "Alpha One").success     # X: Celtics x Lakers
    assert manager.make_move(game.game_id, 1, 0, "Gamma Three").success   # O: Bulls x Lakers
    assert manager.make_move(game.game_id, 0, 1, "Beta Two").success      # X: Celtics x Celtics
    assert not manager.make_move(game.game_id, 2, 0, "Nobody").success    # O: turnover
    final = manager.make_move(game.game_id, 0, 2, "Delta Four")           # X: Celtics x Bulls
    assert final.success and final.game_over and final.winner == "X"
    assert final.winning_line == [[0, 0], [0, 1], [0, 2]]
    assert game.status == "finished"
    assert manager.make_move(game.game_id, 2, 2, "Twin Name").game_over


def test_shot_clock_violation(manager):
    game = manager.create_game("nba")
    assert manager.trigger_shot_clock_violation(game.game_id).current_player == "O"
    assert manager.trigger_shot_clock_violation("missing") is None


def test_another_name_is_the_same_player(nba_catalog, nba_index):
    from backend.catalog.criteria import build_index
    from backend.catalog.players import PlayerCatalog
    from backend.game.manager import GameManager
    players = [dict(p) for p in nba_catalog.players]
    players[0]["aliases"] = ["Al One"]
    index = build_index(PlayerCatalog("nba", {"teams": nba_catalog.teams, "countries": nba_catalog.countries,
                                              "players": players}))
    assert [p["name"] for p in index.catalog.find("al one")] == ["Alpha One"]
    assert index.catalog.name_list["aliases"]["Al One"] == {"name": "Alpha One", "key": None}

    manager = GameManager({"nba": index})
    game = manager.create_game("nba", grid_style="classic")
    set_board(game, index, [(TEAM, "Boston Celtics"), (TEAM, "Chicago Bulls"), (TEAM, "Miami Heat")],
              [(TEAM, "Los Angeles Lakers"), (TEAM, "Boston Celtics"), (TEAM, "Golden State Warriors")])
    placed = manager.make_move(game.game_id, 0, 0, "Al One")
    assert placed.success and placed.cell.player_name == "Alpha One"  # the box shows the real name
    again = manager.make_move(game.game_id, 0, 1, "Alpha One")        # O can't use the same player
    assert not again.success and "already picked" in again.message
