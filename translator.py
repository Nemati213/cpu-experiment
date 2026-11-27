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
    "c@": Opcode.LOAD8,
    "execute": Opcode.EXEC,
    "ei": Opcode.EI,
    "di": Opcode.DI,
    "bye": Opcode.HALT,
}

STORE_WORDS = {"!": Opcode.STORE, "c!": Opcode.STORE8}

PORT_WORDS = {"in": Opcode.IN, "out": Opcode.OUT}
DEFINING_WORDS = (":", ":interrupt")
VECTOR = 1


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
    code: list[Instr] = field(default_factory=lambda: [Instr(Opcode.JMP), Instr(Opcode.IRET)])
    data: bytearray = field(default_factory=bytearray)
    words: dict[str, int] = field(default_factory=dict)
    current: Token | None = None
    skip: int | None = 0

    def here(self) -> int:
        return len(self.code) * WORD_SIZE

    def emit(self, opcode: Opcode, arg: int = 0) -> None:
        if self.current is None and self.skip is not None:
            self.code[self.skip] = Instr(Opcode.JMP, self.here())
            self.skip = None
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

    def begin_definition(self, token: Token, name: str) -> None:
        if self.skip is None:
            self.skip = len(self.code)
            self.code.append(Instr(Opcode.JMP))
        self.current = token
        self.words[name] = self.here()
        if token.word == ":interrupt":
            self.code[VECTOR] = Instr(Opcode.JMP, self.here())

    def end_definition(self, token: Token) -> None:
        if self.current is None:
            msg = f"line {token.line}: ; without :"
            raise ValueError(msg)
        self.emit(Opcode.IRET if self.current.word == ":interrupt" else Opcode.RET)
        self.current = None


def parse_number(token: Token) -> int | None:
    if not NUMBER.fullmatch(token.word):
        return None
    value = int(token.word)
    if not WORD_MIN <= value < WORD_LIMIT:
        msg = f"line {token.line}: number {value} does not fit in 32 bits"
        raise ValueError(msg)
    return value


def start_definition(program: Program, tokens: list[Token], pos: int) -> int:
    token = tokens[pos]
    if program.current is not None:
        msg = f"line {token.line}: {token.word} inside a definition"
        raise ValueError(msg)
    if pos + 1 == len(tokens) or parse_number(tokens[pos + 1]) is not None:
        msg = f"line {token.line}: {token.word} needs a name"
        raise ValueError(msg)
    if token.word == ":interrupt" and program.code[VECTOR].opcode is Opcode.JMP:
        msg = f"line {token.line}: second :interrupt"
        raise ValueError(msg)
    program.begin_definition(token, tokens[pos + 1].word)
    return pos + 2


def compile_number(program: Program, tokens: list[Token], pos: int, number: int) -> int:
    after = tokens[pos + 1].word if pos + 1 < len(tokens) else ""
    if after in PORT_WORDS:
        program.emit(PORT_WORDS[after], number)
        return pos + 2
    program.push(number)
    return pos + 1


def compile_word(program: Program, token: Token) -> None:
    if token.word == ";":
        program.end_definition(token)
    elif token.word in program.words:
        program.emit(Opcode.CALL, program.words[token.word])
    elif token.word in BUILTINS:
        program.emit(BUILTINS[token.word])
    elif token.word in STORE_WORDS:
        program.emit(STORE_WORDS[token.word])
        program.emit(Opcode.DROP)
    elif token.word in PORT_WORDS:
        msg = f"line {token.line}: {token.word} needs a port number right before it"
        raise ValueError(msg)
    else:
        msg = f"line {token.line}: unknown word {token.word}"
        raise ValueError(msg)


def compile_token(program: Program, tokens: list[Token], pos: int) -> int:
    token = tokens[pos]
    if token.word in DEFINING_WORDS:
        return start_definition(program, tokens, pos)
    number = parse_number(token)
    if number is not None:
        return compile_number(program, tokens, pos, number)
    compile_word(program, token)
    return pos + 1


def translate(source: str) -> tuple[list[Instr], bytes]:
    tokens = tokenize(source)
    program = Program()
    pos = 0
    while pos < len(tokens):
        pos = compile_token(program, tokens, pos)
    if program.current is not None:
        msg = f"line {program.current.line}: missing ;"
        raise ValueError(msg)
    program.emit(Opcode.HALT)
    return program.code, bytes(program.data)
