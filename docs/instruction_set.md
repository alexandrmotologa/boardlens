# RISC-V RV32I Instruction Set Support

BoardLens implements all 37 base integer instructions of the RV32I unprivileged specification.

## Instruction Formats

```
R-type: [funct7 (7)] [rs2 (5)] [rs1 (5)] [funct3 (3)] [rd (5)] [opcode (7)]
I-type: [imm[11:0] (12)]       [rs1 (5)] [funct3 (3)] [rd (5)] [opcode (7)]
S-type: [imm[11:5] (7)] [rs2 (5)] [rs1 (5)] [funct3 (3)] [imm[4:0] (5)] [opcode (7)]
B-type: [imm[12|10:5] (7)] [rs2 (5)] [rs1 (5)] [funct3 (3)] [imm[4:1|11] (5)] [opcode (7)]
U-type: [imm[31:12] (20)]                             [rd (5)] [opcode (7)]
J-type: [imm[20|10:1|11|19:12] (20)]                  [rd (5)] [opcode (7)]
```

## Instruction Summary

### Arithmetic and Logic
- **ADD, SUB**: Register addition and subtraction with 32-bit wrap around.
- **ADDI**: Add sign-extended 12-bit immediate.
- **AND, OR, XOR**: Bitwise operations between registers.
- **ANDI, ORI, XORI**: Bitwise operations with sign-extended immediate.
- **SLL, SRL, SRA**: Logical left, logical right, and arithmetic right shifts.
- **SLLI, SRLI, SRAI**: Shifts by immediate shift amount in bits 4:0.
- **SLT, SLTU**: Set less than (signed and unsigned).
- **SLTI, SLTIU**: Set less than immediate (signed and unsigned).

### Control Flow
- **JAL**: Jump and link. Stores return address PC+4 in rd, jumps to PC + imm.
- **JALR**: Jump and link register. Jumps to (rs1 + imm) & ~1, stores PC+4 in rd.
- **BEQ, BNE**: Branch if rs1 == rs2 or rs1 != rs2.
- **BLT, BGE**: Signed branch if rs1 < rs2 or rs1 >= rs2.
- **BLTU, BGEU**: Unsigned branch comparisons.

### Memory Access
- **LW, LH, LHU, LB, LBU**: Load word, halfword, and byte with sign or zero extension.
- **SW, SH, SB**: Store word, halfword, and byte to calculated effective address.

### Upper Immediate
- **LUI**: Load upper 20 bits of immediate into rd, zeroing lower 12 bits.
- **AUIPC**: Add upper 20 bits of immediate to current PC, storing result in rd.

### System & Environment
- **ECALL**: Environment call trap.
- **EBREAK**: Software breakpoint trap.
- **CSRRW, CSRRS, CSRRC**: Atomic read and write/set/clear of Control and Status Registers.
- **CSRRWI, CSRRSI, CSRRCI**: Immediate variants using 5-bit zero-extended value.
