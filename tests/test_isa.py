import pytest

from isa import (
    ADDRESS_ARG,
    ARG_MASK,
    NUMBER_ARG,
    PUSH_MAX,
    PUSH_MIN,
    Instr,
    Opcode,
    decode,
    encode,
    from_bytes,
    listing,
    to_bytes,
)


@pytest.mark.parametrize("opcode", list(Opcode))
def test_roundtrip(opcode: Opcode) -> None:
    instr = Instr(opcode, 5) if opcode in ADDRESS_ARG | NUMBER_ARG else Instr(opcode)
    assert decode(encode(instr)) == instr


@pytest.mark.parametrize("value", [0, 1, -1, 42, -42, PUSH_MIN, PUSH_MAX])
def test_push_keeps_sign(value: int) -> None:
    assert decode(encode(Instr(Opcode.PUSH, value))).arg == value


def test_encoding_layout() -> None:
    assert encode(Instr(Opcode.PUSH, 42)) == 0x1000002A
    assert encode(Instr(Opcode.PUSH, -1)) == 0x10FFFFFF
    assert encode(Instr(Opcode.CALL, 0x40)) == 0x42000040
    assert encode(Instr(Opcode.ADD)) == 0x20000000


@pytest.mark.parametrize(
    ("opcode", "arg"),
    [
        (Opcode.PUSH, PUSH_MAX + 1),
        (Opcode.PUSH, PUSH_MIN - 1),
        (Opcode.JMP, -1),
        (Opcode.JMP, ARG_MASK + 1),
        (Opcode.ADD, 1),
    ],
)
def test_bad_argument(opcode: Opcode, arg: int) -> None:
    with pytest.raises(ValueError, match="bad argument"):
        Instr(opcode, arg)


def test_bytes_roundtrip() -> None:
    code = [Instr(Opcode.PUSH, -7), Instr(Opcode.CALL, 0x10), Instr(Opcode.HALT)]
    data = to_bytes(code)
    assert len(data) == 12
    assert data[:4] == bytes.fromhex("10FFFFF9")
    assert from_bytes(data) == code


def test_from_bytes_rejects_partial_word() -> None:
    with pytest.raises(ValueError, match="multiple of 4"):
        from_bytes(b"\x00\x00\x00")


def test_listing() -> None:
    code = [
        Instr(Opcode.JMP, 0x08),
        Instr(Opcode.IRET),
        Instr(Opcode.PUSH, 65),
        Instr(Opcode.OUT, 1),
        Instr(Opcode.HALT),
    ]
    assert listing(code) == (
        "0000 - 40000008 - jmp 0x0008\n"
        "0004 - 62000000 - iret\n"
        "0008 - 10000041 - push 65\n"
        "000C - 51000001 - out 1\n"
        "0010 - 00000000 - halt"
    )
