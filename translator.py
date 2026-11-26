import re
from dataclasses import dataclass, field

from isa import PUSH_MAX, PUSH_MIN, WORD_SIZE, Instr, Opcode

STRING_WORDS = ('s"', '."')
NUMBER = re.compile(r"-?\d+")
WORD_MIN = -(1 << 31)
WORD_LIMIT = 1 << 32

BUILTINS = {
    "+": Opcode.ADD,
    "-": Opcode.SUB,
    "*": Opcode.MUL,
    "/": Opcode.DIV,
    "mod": Opcode.MOD,
    "and": Opcode.AND,
    "or": Opcode.OR,
    "xor": Opcode.XOR,
    "negate": Opcode.NEG,
    "invert": Opcode.NOT,
    "=": Opcode.EQ,
    "<": Opcode.LT,
    ">": Opcode.GT,
    "u<": Opcode.ULT,
    "dup": Opcode.DUP,
    "drop": Opcode.DROP,
    "swap": Opcode.SWAP,
    "over": Opcode.OVER,
    ">r": Opcode.TOR,
    "r>": Opcode.FROMR,
    "r@": Opcode.RFETCH,
    "@": Opcode.LOAD,
    "!": Opcode.STORE,
    "c@": Opcode.LOAD8,
    "c!": Opcode.STORE8,
    "execute": Opcode.EXEC,
    "ei": Opcode.EI,
    "di": Opcode.DI,
    "bye": Opcode.HALT,
}

PORT_WORDS = {"in": Opcode.IN, "out": Opcode.OUT}


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


@dataclass
class Program:
    code: list[Instr] = field(default_factory=list)
    data: bytearray = field(default_factory=bytearray)

    def emit(self, opcode: Opcode, arg: int = 0) -> None:
        self.code.append(Instr(opcode, arg))

    def align_data(self) -> None:
        self.data += bytes(-len(self.data) % WORD_SIZE)

    def add_word(self, value: int) -> int:
        self.align_data()
        addr = len(self.data)
        self.data += (value % WORD_LIMIT).to_bytes(WORD_SIZE, "big")
        return addr

    def push(self, value: int) -> None:
        if PUSH_MIN <= value <= PUSH_MAX:
            self.emit(Opcode.PUSH, value)
        else:
            self.emit(Opcode.PUSH, self.add_word(value))
            self.emit(Opcode.LOAD)


def parse_number(token: Token) -> int | None:
    if not NUMBER.fullmatch(token.word):
        return None
    value = int(token.word)
    if not WORD_MIN <= value < WORD_LIMIT:
        msg = f"line {token.line}: number {value} does not fit in 32 bits"
        raise ValueError(msg)
    return value


def compile_token(program: Program, tokens: list[Token], pos: int) -> int:
    token = tokens[pos]
    number = parse_number(token)
    if number is not None:
        after = tokens[pos + 1].word if pos + 1 < len(tokens) else ""
        if after in PORT_WORDS:
            program.emit(PORT_WORDS[after], number)
            return pos + 2
        program.push(number)
        return pos + 1
    if token.word in BUILTINS:
        program.emit(BUILTINS[token.word])
        return pos + 1
    if token.word in PORT_WORDS:
        msg = f"line {token.line}: {token.word} needs a port number right before it"
        raise ValueError(msg)
    msg = f"line {token.line}: unknown word {token.word}"
    raise ValueError(msg)


def translate(source: str) -> tuple[list[Instr], bytes]:
    tokens = tokenize(source)
    program = Program()
    program.emit(Opcode.JMP)
    program.emit(Opcode.IRET)
    start = len(program.code) * WORD_SIZE
    pos = 0
    while pos < len(tokens):
        pos = compile_token(program, tokens, pos)
    program.emit(Opcode.HALT)
    program.code[0] = Instr(Opcode.JMP, start)
    return program.code, bytes(program.data)
