"""Smoke tests: the real frontend in a real browser, against the real server and datasets.

Skipped unless Playwright is installed. Uses Playwright's Chromium if present, else Edge or
Chrome from the machine, so `playwright install chromium` is optional.
"""

import re
import socket
import threading
import time

import pytest
import uvicorn

from backend import config
from backend.app import create_app
from backend.game.manager import GameManager

sync_api = pytest.importorskip("playwright.sync_api")
expect = sync_api.expect


@pytest.fixture(scope="module")
def server():
    """The app on a free port, in this process so tests can look up a grid's answers."""
    limits = config.RATE_LIMITS_ENABLED
    config.RATE_LIMITS_ENABLED = False
    app = create_app()
    config.RATE_LIMITS_ENABLED = limits
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    uv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=uv.run, daemon=True)
    thread.start()
    while not uv.started:
        time.sleep(0.05)
    yield app, f"http://127.0.0.1:{port}"
    uv.should_exit = True
    thread.join(timeout=10)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        for channel in (None, "msedge", "chrome"):
            try:
                found = playwright.chromium.launch(channel=channel)
                break
            except sync_api.Error:
                continue
        else:
            pytest.skip("no Chromium, Edge or Chrome to run")
        yield found
        found.close()


@pytest.fixture
def open_page(browser, server):
    """Opens the site in a fresh browser profile; any uncaught script error fails the test."""
    contexts, errors = [], []

    def opener(path="/"):
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        contexts.append(context)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(server[1] + path)
        return page

    yield opener
    for context in contexts:
        context.close()
    assert not errors


def tip_off(page):
    page.click("#btn-launch-game")
    expect(page.locator("#screen-game")).to_be_visible()
    expect(page.locator("#panel-x")).to_have_class(re.compile("active-turn"))


def unique_answer(app, row, col) -> str:
    """A right answer for a box of the newest game, with no namesake to confuse the list."""
    manager: GameManager = app.state.game_manager
    game = list(manager.active_games.values())[-1]
    index = manager.index_for(game)
    r, c = game.row_criteria[row], game.col_criteria[col]
    answers = index.answers(index.get(r.type.value, r.value), index.get(c.type.value, c.value))
    return next(p["name"] for p in answers
                if p["key"] not in game.used_keys and len(index.catalog.find(p["name"])) == 1)


def test_menu_shows_custom_categories_only_when_ticked(open_page):
    page = open_page()
    expect(page.locator("#screen-menu")).to_be_visible()
    expect(page.locator("#screen-menu .form-sub")).to_contain_text("not affiliated")
    expect(page.locator("#custom-categories")).to_be_hidden()
    page.locator("input[name=style][value=custom]").check(force=True)
    expect(page.locator("#custom-categories")).to_be_visible()


def test_board_fits_the_screen_with_every_header_filled(open_page):
    page = open_page()
    tip_off(page)
    for header in ("#ch-0", "#ch-1", "#ch-2", "#rh-0", "#rh-1", "#rh-2"):
        expect(page.locator(header)).not_to_be_empty()
    expect(page.locator(".cell")).to_have_count(9)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_a_right_answer_marks_the_box_and_passes_the_turn(open_page, server):
    page = open_page()
    tip_off(page)
    page.click("#box-0-0")
    page.fill("#search-player-input", unique_answer(server[0], 0, 0))
    expect(page.locator("#search-results-list li[aria-selected=true]")).to_have_count(1)
    page.press("#search-player-input", "Enter")
    expect(page.locator("#box-0-0.claimed svg")).to_be_visible()
    expect(page.locator("#panel-o")).to_have_class(re.compile("active-turn"))


def test_a_typo_cannot_be_submitted(open_page):
    page = open_page()
    tip_off(page)
    page.click("#box-1-1")
    page.fill("#search-player-input", "zzzzqq")
    expect(page.locator("#search-results-list .none")).to_be_visible()
    expect(page.locator("#btn-confirm-select")).to_be_disabled()
    page.press("#search-player-input", "Enter")
    expect(page.locator("#modal-select")).to_be_visible()
    page.click("#btn-cancel-select")
    expect(page.locator("#panel-x")).to_have_class(re.compile("active-turn"))


def test_skip_passes_the_turn(open_page):
    page = open_page()
    tip_off(page)
    page.click("#btn-skip")
    expect(page.locator("#panel-o")).to_have_class(re.compile("active-turn"))


def test_drawing_a_grid_needs_a_second_press_and_deals_a_new_one(open_page):
    page = open_page()
    tip_off(page)
    page.click("#btn-draw")
    expect(page.locator("#btn-draw")).to_have_text("Press again to draw")
    page.click("#btn-draw")
    expect(page.locator("#game-status-text")).to_contain_text("Grid drawn by agreement")
    expect(page.locator("#btn-draw")).to_have_text("Draw this grid")


def test_three_in_a_row_wins_and_shows_the_answers(open_page, server):
    page = open_page()
    tip_off(page)
    for box in ((0, 0), (1, 0), (0, 1), (1, 1), (0, 2)):  # X takes the top row, O the middle
        page.click(f"#box-{box[0]}-{box[1]}")
        page.fill("#search-player-input", unique_answer(server[0], *box))
        page.press("#search-player-input", "Enter")
        expect(page.locator(f"#box-{box[0]}-{box[1]}.claimed")).to_be_visible()
    expect(page.locator("#modal-gameover")).to_be_visible()
    expect(page.locator("#win-stroke line, #win-stroke path")).to_have_count(1)
    page.click("#btn-show-answers")
    expect(page.locator("#answers-grid")).not_to_be_empty()


def test_online_room_from_invite_link_to_tip_off(open_page):
    host = open_page()
    host.locator("input[name=mode][value=online]").check(force=True)
    host.fill("#name-online", "Host")
    host.click("#btn-launch-game")
    expect(host.locator("#screen-lobby")).to_be_visible()
    expect(host.locator("#lobby-link")).to_contain_text("?room=")
    link = host.inner_text("#lobby-link")

    guest = open_page(link[link.index("/?room="):])
    expect(guest.locator("#screen-join")).to_be_visible()
    expect(guest.locator("#screen-menu")).to_be_hidden()
    guest.fill("#join-name", "Guest")
    guest.click("#btn-join-ready")
    expect(guest.locator("#screen-lobby")).to_be_visible()

    expect(host.locator("#btn-ready")).to_be_enabled()
    host.click("#btn-ready")
    for page in (host, guest):
        expect(page.locator("#screen-game")).to_be_visible()
        expect(page.locator("#text-name-x")).to_have_text("Host")
        expect(page.locator("#text-name-o")).to_have_text("Guest")
