"""The layout preview serves a whole career history, so its closure is the test.

Each test below names a way the page could leak rather than a method it calls.
"""

from __future__ import annotations

import urllib.error
import urllib.request

import pytest

from cv_consultant_pro.corpus import load_corpus_text
from cv_consultant_pro.document import CvDocument
from cv_consultant_pro.jd import parse_jd
from cv_consultant_pro.match import Scorecard, score
from cv_consultant_pro.preview import LOOPBACK, start_preview
from cv_consultant_pro.render import build_document, select
from cv_consultant_pro.templates import TEMPLATES

from .fixtures import NURSE


@pytest.fixture
def document() -> CvDocument:
    corpus = load_corpus_text(NURSE.corpus)
    jd = parse_jd(NURSE.posting)
    card = score(jd, corpus)
    doc, _trace, _placeholders = build_document(corpus, jd, card, select(corpus, card))
    return doc


@pytest.fixture
def preview(document: CvDocument):
    running = start_preview(document, open_browser=False)
    yield running
    running.stop()


def _get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


def test_every_layout_is_rendered_so_the_choice_is_made_by_looking(preview) -> None:
    assert set(preview.layouts) == set(TEMPLATES)
    index = _get(preview.url)
    for template in TEMPLATES.values():
        assert template.name in index


def test_the_index_says_which_layouts_are_safe_to_submit(preview) -> None:
    """The distinction is the whole point of having two kinds of layout."""
    index = _get(preview.url)
    assert "portal-safe" in index
    assert "send to a person" in index


def test_the_cv_is_actually_in_the_page_not_a_stock_sample(preview, document) -> None:
    page = _get(f"{preview.url}/{preview.layouts[0]}")
    assert document.name in page


def test_it_binds_to_loopback_and_not_the_network(preview) -> None:
    """On shared wifi, a career history on 0.0.0.0 is a career history published."""
    assert preview.url.startswith(f"http://{LOOPBACK}:")
    assert preview._server.server_address[0] == LOOPBACK


def test_the_port_is_ephemeral_so_nothing_can_sit_waiting_on_a_known_one(preview) -> None:
    assert preview.port != 0
    assert preview.port > 1024


def test_the_path_carries_a_token_a_neighbouring_process_cannot_guess(preview) -> None:
    token = preview.url.rsplit("/", 1)[1]
    assert len(token) >= 16


def test_a_wrong_token_gets_nothing(preview) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        _get(f"http://{LOOPBACK}:{preview.port}/not-the-token/{preview.layouts[0]}")
    assert err.value.code == 404


def test_a_wrong_token_and_a_wrong_path_answer_identically(preview) -> None:
    """Two different errors would let the token be probed for one guess at a time."""
    codes = []
    for path in (f"/not-the-token/{preview.layouts[0]}", "/nonsense"):
        with pytest.raises(urllib.error.HTTPError) as err:
            _get(f"http://{LOOPBACK}:{preview.port}{path}")
        codes.append(err.value.code)
    assert codes[0] == codes[1]


def test_it_serves_nothing_from_disk(preview) -> None:
    """It answers from a dict of prepared strings, so traversal has nowhere to go."""
    with pytest.raises(urllib.error.HTTPError):
        _get(f"http://{LOOPBACK}:{preview.port}/../pyproject.toml")


def test_stopping_it_actually_closes_the_port(document) -> None:
    running = start_preview(document, open_browser=False)
    url = running.url
    running.stop()
    with pytest.raises(Exception):  # noqa: B017 - refused or reset, both are fine
        _get(url)


def test_a_document_with_no_roles_still_previews(document) -> None:
    """A brand-new corpus is the first thing a stranger will point this at."""
    empty = CvDocument(name="Nobody Yet", contact=[], roles=[])
    running = start_preview(empty, open_browser=False)
    try:
        assert "Nobody Yet" in _get(f"{running.url}/{running.layouts[0]}")
    finally:
        running.stop()


def test_scoring_is_not_required_to_preview_a_layout() -> None:
    """Layout is chosen before a posting exists, so preview cannot depend on one."""
    corpus = load_corpus_text(NURSE.corpus)
    empty = Scorecard()
    doc, _t, _p = build_document(corpus, parse_jd(""), empty, select(corpus, empty))
    running = start_preview(doc, open_browser=False)
    try:
        assert corpus.person.name in _get(f"{running.url}/{running.layouts[0]}")
    finally:
        running.stop()
