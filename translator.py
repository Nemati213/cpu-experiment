from dataclasses import dataclass

STRING_WORDS = ('s"', '."')


@dataclass(frozen=True)
class Token:
    word: str
    line: int
    text: str | None = None


def skip_spaces(source: str, pos: int) -> int:
    while pos < len(source) and source[pos].isspace():
        pos += 1
    return pos


def word_end(source: str, pos: int) -> int:
    while pos < len(source) and not source[pos].isspace():
        pos += 1
    return pos


def find_closing(source: str, start: int, char: str, line: int) -> int:
    pos = source.find(char, start)
    if pos == -1:
        msg = f"line {line}: missing {char}"
        raise ValueError(msg)
    return pos


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    pos = skip_spaces(source, 0)
    while pos < len(source):
        end = word_end(source, pos)
        word = source[pos:end].lower()
        line = source.count("\n", 0, pos) + 1
        if word == "\\":
            end = source.find("\n", end)
            if end == -1:
                break
        elif word == "(":
            end = find_closing(source, end, ")", line) + 1
        elif word in STRING_WORDS:
            close = find_closing(source, end + 1, '"', line)
            tokens.append(Token(word, line, source[end + 1 : close]))
            end = close + 1
        else:
            tokens.append(Token(word, line))
        pos = skip_spaces(source, end)
    return tokens
