import pytest

from translator import Token, tokenize


def words(source: str) -> list[str]:
    return [token.word for token in tokenize(source)]


def test_empty() -> None:
    assert tokenize("") == []
    assert tokenize("  \n\t ") == []


def test_words_and_numbers() -> None:
    assert words("2 3 + dup *") == ["2", "3", "+", "dup", "*"]
    assert words("  -5\t\n  negate  ") == ["-5", "negate"]


def test_words_are_lowercased() -> None:
    assert words("DUP Swap") == ["dup", "swap"]


def test_line_numbers() -> None:
    assert [token.line for token in tokenize("a\nb c\n\nd")] == [1, 2, 2, 4]


def test_comments() -> None:
    assert words("1 ( skip this ) 2") == ["1", "2"]
    assert words("1 ( multi\nline ) 2") == ["1", "2"]
    assert words("1 \\ rest of line\n2") == ["1", "2"]
    assert words("1 \\ comment at the end") == ["1"]


def test_strings() -> None:
    assert tokenize('s" Hello, World!" print') == [
        Token('s"', 1, "Hello, World!"),
        Token("print", 1),
    ]
    assert tokenize('." a  b"') == [Token('."', 1, "a  b")]
    assert tokenize('s" "') == [Token('s"', 1, "")]


def test_string_keeps_comment_chars() -> None:
    assert tokenize('s" ( \\ "') == [Token('s"', 1, "( \\ ")]


@pytest.mark.parametrize(
    ("source", "error"),
    [
        ('s" no end', 'line 1: missing "'),
        ('1\n."', 'line 2: missing "'),
        ("1 ( no end", "line 1: missing \\)"),
    ],
)
def test_unclosed(source: str, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        tokenize(source)
