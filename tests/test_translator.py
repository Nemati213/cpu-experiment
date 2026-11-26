import pytest

from isa import Instr, Opcode
from translator import BUILTINS, Token, tokenize, translate


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


def main_code(source: str) -> list[str]:
    code, _ = translate(source)
    return [str(instr) for instr in code[2:-1]]


def test_empty_program() -> None:
    code, data = translate("")
    assert [str(instr) for instr in code] == ["jmp 0x0008", "iret", "halt"]
    assert data == b""


def test_arithmetic() -> None:
    assert main_code("2 3 + 4 *") == ["push 2", "push 3", "add", "push 4", "mul"]


@pytest.mark.parametrize(("word", "opcode"), BUILTINS.items())
def test_builtin(word: str, opcode: Opcode) -> None:
    code, _ = translate(word.upper())
    assert code[2] == Instr(opcode)


def test_ports() -> None:
    assert main_code("72 1 out 0 in") == ["push 72", "out 1", "in 0"]


@pytest.mark.parametrize("source", ["in", "1 2 + out"])
def test_port_without_number(source: str) -> None:
    with pytest.raises(ValueError, match="needs a port number"):
        translate(source)


def test_negative_number() -> None:
    assert main_code("-5") == ["push -5"]


def test_big_numbers_go_to_data() -> None:
    source = "8388607 8388608 -1000000000 4294967295"
    assert main_code(source) == [
        "push 8388607",
        "push 0",
        "load",
        "push 4",
        "load",
        "push 8",
        "load",
    ]
    assert translate(source)[1] == bytes.fromhex("00800000C4653600FFFFFFFF")


@pytest.mark.parametrize("number", ["4294967296", "-2147483649"])
def test_number_too_big(number: str) -> None:
    with pytest.raises(ValueError, match="does not fit in 32 bits"):
        translate(number)


def test_unknown_word() -> None:
    with pytest.raises(ValueError, match="line 2: unknown word foo"):
        translate("1 2\n+ foo")
