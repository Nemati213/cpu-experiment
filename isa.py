from dataclasses import dataclass
from enum import IntEnum

WORD_SIZE = 4
ARG_BITS = 24
ARG_MASK = (1 << ARG_BITS) - 1
PUSH_MIN = -(1 << (ARG_BITS - 1))
PUSH_MAX = (1 << (ARG_BITS - 1)) - 1


class Opcode(IntEnum):
    HALT = 0x00
    NOP = 0x01

    PUSH = 0x10
    DUP = 0x11
    DROP = 0x12
    SWAP = 0x13
    OVER = 0x14

    ADD = 0x20
    SUB = 0x21
    MUL = 0x22
    DIV = 0x23
    MOD = 0x24
    AND = 0x25
    OR = 0x26
    XOR = 0x27
    NEG = 0x28
    NOT = 0x29
    EQ = 0x2A
    LT = 0x2B
    GT = 0x2C
    ULT = 0x2D

    LOAD = 0x30
    STORE = 0x31
    LOAD8 = 0x32
    STORE8 = 0x33

    TOR = 0x38
    FROMR = 0x39
    RFETCH = 0x3A

    JMP = 0x40
    JZ = 0x41
    CALL = 0x42
    RET = 0x43
    EXEC = 0x44

    IN = 0x50
    OUT = 0x51

    EI = 0x60
    DI = 0x61
    IRET = 0x62


ADDRESS_ARG = frozenset({Opcode.JMP, Opcode.JZ, Opcode.CALL})
NUMBER_ARG = frozenset({Opcode.PUSH, Opcode.IN, Opcode.OUT})


def arg_range(opcode: Opcode) -> tuple[int, int]:
    if opcode is Opcode.PUSH:
        return PUSH_MIN, PUSH_MAX
    if opcode in ADDRESS_ARG or opcode in NUMBER_ARG:
        return 0, ARG_MASK
    return 0, 0


@dataclass(frozen=True)
class Instr:
    opcode: Opcode
    arg: int = 0

    def __post_init__(self) -> None:
        low, high = arg_range(self.opcode)
        if not low <= self.arg <= high:
            msg = f"{self.opcode.name.lower()}: bad argument {self.arg}"
            raise ValueError(msg)

    def __str__(self) -> str:
        name = self.opcode.name.lower()
        if self.opcode in ADDRESS_ARG:
            return f"{name} 0x{self.arg:04X}"
        if self.opcode in NUMBER_ARG:
            return f"{name} {self.arg}"
        return name


def encode(instr: Instr) -> int:
    return (instr.opcode << ARG_BITS) | (instr.arg & ARG_MASK)


def decode(word: int) -> Instr:
    opcode = Opcode(word >> ARG_BITS)
    arg = word & ARG_MASK
    if opcode is Opcode.PUSH and arg > PUSH_MAX:
        arg -= 1 << ARG_BITS
    return Instr(opcode, arg)


def to_bytes(code: list[Instr]) -> bytes:
    return b"".join(encode(instr).to_bytes(WORD_SIZE, "big") for instr in code)


def from_bytes(data: bytes) -> list[Instr]:
    if len(data) % WORD_SIZE != 0:
        msg = f"code size {len(data)} is not a multiple of {WORD_SIZE}"
        raise ValueError(msg)
    return [
        decode(int.from_bytes(data[addr : addr + WORD_SIZE], "big"))
        for addr in range(0, len(data), WORD_SIZE)
    ]


def pack_program(code: list[Instr], data: bytes) -> bytes:
    code_bytes = to_bytes(code)
    return len(code_bytes).to_bytes(WORD_SIZE, "big") + code_bytes + data


def unpack_program(image: bytes) -> tuple[list[Instr], bytes]:
    if len(image) < WORD_SIZE:
        msg = "file is too short"
        raise ValueError(msg)
    code_end = WORD_SIZE + int.from_bytes(image[:WORD_SIZE], "big")
    if code_end > len(image):
        msg = "code size is bigger than the file"
        raise ValueError(msg)
    return from_bytes(image[WORD_SIZE:code_end]), image[code_end:]


def listing(code: list[Instr]) -> str:
    return "\n".join(
        f"{index * WORD_SIZE:04X} - {encode(instr):08X} - {instr}"
        for index, instr in enumerate(code)
    )
