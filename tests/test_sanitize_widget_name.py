"""Tests for WidgetCodex._sanitize_widget_name() — enforce short widget names."""

import sys, os, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend"))

from app.services.multi_agent.agents.widget_codex import WidgetCodexAgent


# ── Basic pass-through ──────────────────────────────────────────


def test_short_name_unchanged():
    """Short names pass through without modification."""
    assert WidgetCodexAgent._sanitize_widget_name("Продажи по категориям") == "Продажи по категориям"


def test_empty_string():
    assert WidgetCodexAgent._sanitize_widget_name("") == ""


def test_none_returns_none():
    assert WidgetCodexAgent._sanitize_widget_name(None) is None


# ── Quote stripping ─────────────────────────────────────────────


def test_strips_double_quotes():
    assert WidgetCodexAgent._sanitize_widget_name('"Продажи по категориям"') == "Продажи по категориям"


def test_strips_single_quotes():
    assert WidgetCodexAgent._sanitize_widget_name("'Топ-10 брендов'") == "Топ-10 брендов"


def test_strips_mixed_quotes():
    assert WidgetCodexAgent._sanitize_widget_name("\"Динамика вакансий'") == "Динамика вакансий"


# ── Trailing period / ellipsis ──────────────────────────────────


def test_strips_trailing_period():
    assert WidgetCodexAgent._sanitize_widget_name("Продажи по категориям.") == "Продажи по категориям"


def test_strips_trailing_ellipsis():
    assert WidgetCodexAgent._sanitize_widget_name("Продажи по категориям…") == "Продажи по категориям"


def test_strips_trailing_multiple_dots():
    assert WidgetCodexAgent._sanitize_widget_name("Продажи по категориям...") == "Продажи по категориям"


# ── Truncation at word boundary ─────────────────────────────────


def test_long_name_truncated():
    """A long sentence-like name should be truncated to ≤50 chars."""
    long_name = "Круговая диаграмма распределения количества вакансий по компаниям на основе данных таблицы sorted"
    result = WidgetCodexAgent._sanitize_widget_name(long_name)
    assert len(result) <= WidgetCodexAgent._MAX_WIDGET_NAME_LEN
    # Should end at a word boundary (no partial words)
    assert not result.endswith(" ")
    assert not result[-1:] in (",", ";", ":", "-", "—")


def test_long_name_preserves_meaningful_prefix():
    """Truncation should keep enough text to be meaningful (≥15 chars)."""
    long_name = "Столбчатая диаграмма сравнения объёмов продаж по категориям товаров за 2024 год с сортировкой"
    result = WidgetCodexAgent._sanitize_widget_name(long_name)
    assert len(result) >= 15
    assert len(result) <= WidgetCodexAgent._MAX_WIDGET_NAME_LEN


def test_truncation_strips_trailing_punctuation():
    """After truncation, trailing commas/dashes should be stripped."""
    # Build a name where the 50-char boundary falls right after a comma
    name = "A" * 15 + " bbbbb, ccccc, ddddd, eeeee, fffff, ggggg, hhhhh, iiiii"
    result = WidgetCodexAgent._sanitize_widget_name(name)
    assert len(result) <= WidgetCodexAgent._MAX_WIDGET_NAME_LEN
    assert not result.endswith(",")
    assert not result.endswith(", ")


# ── Real-world GigaChat patterns ────────────────────────────────


def test_real_gigachat_long_name_1():
    """Реальный пример: слишком длинное название от GigaChat."""
    name = "Круговая диаграмма распределения количества вакансий по компаниям на основе данных"
    result = WidgetCodexAgent._sanitize_widget_name(name)
    assert len(result) <= 50


def test_real_gigachat_long_name_2():
    name = "Столбчатая диаграмма топ-10 компаний по количеству вакансий с наибольшим числом предложений"
    result = WidgetCodexAgent._sanitize_widget_name(name)
    assert len(result) <= 50


def test_real_gigachat_long_name_3():
    name = "Интерактивная таблица с данными о продажах по регионам и категориям товаров за последний квартал"
    result = WidgetCodexAgent._sanitize_widget_name(name)
    assert len(result) <= 50


def test_name_exactly_at_limit():
    """A name exactly at the limit should not be truncated."""
    name = "A" * WidgetCodexAgent._MAX_WIDGET_NAME_LEN
    assert WidgetCodexAgent._sanitize_widget_name(name) == name


def test_name_one_over_limit():
    """One char over should trigger truncation."""
    name = "Abcde " * 9  # 54 chars
    result = WidgetCodexAgent._sanitize_widget_name(name)
    assert len(result) <= WidgetCodexAgent._MAX_WIDGET_NAME_LEN


def test_whitespace_only():
    """Whitespace-only input returns empty after strip."""
    result = WidgetCodexAgent._sanitize_widget_name("   ")
    assert result == ""


def test_name_with_leading_trailing_whitespace():
    result = WidgetCodexAgent._sanitize_widget_name("  Продажи по категориям  ")
    assert result == "Продажи по категориям"
