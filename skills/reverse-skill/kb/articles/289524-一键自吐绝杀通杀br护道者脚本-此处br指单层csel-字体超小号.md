---
title: '[原创]一键自吐绝杀通杀br护道者脚本(此处br指单层csel(字体超小号))'
url: https://bbs.kanxue.com/thread-289524.htm
tid: 289524
author: DirtyAngle
date: '2025-12-22'
tags: [Android安全, 原创, 逆向分析, 工具脚本]
crawled_at: '2026-07-31T15:19:08+08:00'
replies: 267
---

拒绝白嫖, 回复 护道者 查看全文

拜师雪球搜索: br护道者

感谢恩师逆向护阴者

```
import json
import logging
import os
import angr
import capstone.arm64
import claripy
from angr.block import CapstoneInsn, DisassemblerInsn
from capstone import *
from capstone.arm64_const import *
from keystone import *
import pyvex
import archinfo

from patch_br.br_info import BrIfInfo, br_list_to_json, load_br_list, serialize_instruction_list
from patch_br.mico import find_reg_dep_inst
from patch_br.patch_so import PatchSo
from patch_br.tools import bytes_to_chunks, move_none_to_end, chunks_to_bytes, disasm

cs = capstone.Cs(CS_ARCH_ARM64, CS_MODE_ARM)
ks = keystone.Ks(KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN)
nop = ks.asm("nop", 0, True)[0]

logging.getLogger('angr').setLevel(logging.ERROR)
logging.getLogger('claripy').setLevel(logging.ERROR)
logging.getLogger('pyvex').setLevel(logging.ERROR)
logging.getLogger('cle').setLevel(logging.ERROR)

so_path = r'D:\desktop\保活\1215\2.so'

project = angr.Project(so_path, auto_load_libs=False,
                       load_options={'main_opts': {'base_addr': 0}})
text_section = project.loader.main_object.sections_map['.text']
text_start = text_section.vaddr
text_end = text_section.vaddr + text_section.filesize
print("text_start", text_start)
print("text_end", text_end)

state = project.factory.entry_state()

symbols = {}

for item in project.loader.extern_object.symbols:
    symbols[item.rebased_addr] = item.name

def angr_get_reg_idx_by_name(name):
    return state.arch.registers[name][0]

# 14F394
def guess_func_start(start):
    def guess(block):
        has_SUB_SP_SP = False
        has_STP_X29_X30 = False

        for inst in block.capstone.insns:
            if inst and hasattr(inst, "mnemonic"):
                if inst.mnemonic == "sub" and \
                        inst.operands[0].value.reg == ARM64_REG_SP and \
                        inst.operands[1].value.reg == ARM64_REG_SP:
                    has_SUB_SP_SP = True
                if inst.mnemonic == "stp" and \
                        ((inst.operands[0].value.reg == ARM64_REG_X29 and
                          inst.operands[1].value.reg == ARM64_REG_X30) or
                         (inst.operands[0].value.reg == ARM64_REG_X30 and
                          inst.operands[1].value.reg == ARM64_REG_X29)):
                    has_STP_X29_X30 = True
                if has_SUB_SP_SP and has_STP_X29_X30:
                    return True
        return False

    while start <= text_end:
        block = project.factory.block(start)

        if guess(block):
            return start

        if block.size == 0:
            start += 4
        else:
            start += block.size

    return None

def guess_func_end(start):
    def guess(block):
        has_ADD_SP_SP = False
        has_LDP_X29_X30 = False
        has_RET = False

        for inst in block.capstone.insns:
            if inst and hasattr(inst, "mnemonic"):
                if inst.mnemonic == "ret":
                    has_RET = True
                if inst.mnemonic == "add" and \
                        inst.operands[0].value.reg == ARM64_REG_SP and \
                        inst.operands[1].value.reg == ARM64_REG_SP:
                    has_ADD_SP_SP = True
                if inst.mnemonic == "ldp" and \
                        ((inst.operands[0].value.reg == ARM64_REG_X29 and
                          inst.operands[1].value.reg == ARM64_REG_X30) or
                         (inst.operands[0].value.reg == ARM64_REG_X30 and
                          inst.operands[1].value.reg == ARM64_REG_X29)):
                    has_LDP_X29_X30 = True
                if has_ADD_SP_SP and has_LDP_X29_X30 and has_RET:
                    return True
        return False

    while start <= text_end:
        block = project.factory.block(start)

        if guess(block):
            return start + block.size - 4

        if block.size == 0:
            start += 4
        else:
            start += block.size

    return None

def guess_func_range(start):
    func_start = guess_func_start(start)
    if func_start == None:
        return None
    func_end = guess_func_end(func_start + 4)
    if func_end == None:
        return None
    func2_start = guess_func_start(func_end + 4)
    return [func_start, func_end, func2_start]

def get_all_block(start, end):
    blocks = {}
    while start <= end:
        block = project.factory.block(start)
        blocks[start] = {
            "block": block,
        }
        if block.size == 0:
            start += 4
        else:
            start += block.size
    return blocks

def find_br_dep_inst(block: angr.Block):
    depend = []
    lastInst = block.capstone.insns[len(block.capstone.insns) - 1]
    code_bytes = project.loader.memory.load(block.addr, block.size)
    irsb = pyvex.lift(code_bytes, block.addr, archinfo.ArchAArch64(), opt_level=0)
    dep_inst_addr = find_reg_dep_inst(irsb, cs.reg_name(lastInst.operands[0].value.reg))
    for inst in block.capstone.insns:
        if inst.address in dep_inst_addr:
            depend.append(inst)
    depend.append(lastInst)
    return depend

def run_block(block: angr.Block, state, start_addr=None, stop_addr=None):
    sim = project.factory.simgr(state)
    if start_addr:
        pc = start_addr
    else:
        pc = block.addr
    sim.active[0].regs.pc = pc
    while pc < block.addr + block.size - 4:
        # print(disasm(state, pc).mnemonic)
        if stop_addr is not None and pc == stop_addr:
            break
        sim.step(num_inst=1)
        pc += 4
        for active_state in sim.active[:]:
            active_state.regs.pc = pc
    if len(sim.active) != 1:
        print("sim.active ", len(sim.active))
    return sim.active[0]

def solve_symbolic(block: angr.Block, state):
    successors = project.factory.successors(state, opt_level=1)  # 计算后继
    next_list = []
    for succ in successors.flat_successors + successors.unsat_successors:
        if succ.solver.satisfiable():
            addr = succ.addr
            if hasattr(addr, "symbolic"):
                try:
                    possible_addrs = succ.solver.any_n(addr, 10)
                    for p in possible_addrs:
                        constrained_state = succ.copy()
                        constrained_state.add_constraints(addr == p)
                        next_list.append((p, constrained_state))
                except claripy.errors.ClaripySolverError:
                    continue  # 无法解决，跳过
            else:
                next_list.append((succ.addr, succ))
    return next_list

def count_inst(name, depend):
    count = 0
    for inst in depend:
        if inst.mnemonic == name:
            count += 1
    return count

def is_complex(block):
    depend = find_br_dep_inst(block)
    if (count_inst("csel", depend) > 0 or
            count_inst("cset", depend) > 0 or
            count_inst("csetm", depend) > 0 or
            count_inst("cinc", depend) > 0 or
            count_inst("cinv", depend) > 0 or
            count_inst("cneg", depend) > 0):
        return True, depend
    return False, depend

def visit_block(block, state, on_fix_br, on_complex_br):
    if block.capstone.insns[0].address == 0x1501ac:
        print("")
    new_state = run_block(block, state.copy())

    inst = block.capstone.insns[len(block.capstone.insns) - 1]
    if inst.mnemonic == "b":
        return [(inst.operands[0].value.imm, new_state)]

    elif inst.mnemonic == "bl":
        return [(block.addr + block.size, new_state)]

    elif inst.mnemonic == "blr":
        if inst.operands[0].type == CS_OP_REG:
            value = new_state.regs.get(cs.reg_name(inst.operands[0].value.reg))
            if not value.symbolic:
                on_fix_br(inst, value.v)
            return [(block.addr + block.size, new_state)]
        print("wtf3")

    elif inst.mnemonic == "br":
        if inst.operands[0].type == CS_OP_REG:
            cmp, depend = is_complex(block)
            if cmp:
                result_next = on_complex_br(state, new_state, block, depend)
                if result_next:
                    return result_next
                return solve_symbolic(block, new_state)
            else:
                value = new_state.regs.get(cs.reg_name(inst.operands[0].value.reg))
                on_fix_br(inst, value.v)
                return [(value.v, new_state)]
        print("wtf1")

    elif inst.mnemonic == "ret":
        return []

    elif inst.mnemonic == "cbz":
        return [(block.addr + block.size, new_state),
                (inst.operands[1].value.imm, new_state)]

    elif inst.mnemonic == "tbnz":
        return [(block.addr + block.size, new_state),
                (inst.operands[2].value.imm, new_state)]

    elif (inst.mnemonic == "b.eq" or
          inst.mnemonic == "b.ne" or
          inst.mnemonic == "b.cs" or
          inst.mnemonic == "b.hs" or
          inst.mnemonic == "b.cc" or
          inst.mnemonic == "b.lo" or
          inst.mnemonic == "b.mi" or
          inst.mnemonic == "b.pl" or
          inst.mnemonic == "b.vs" or
          inst.mnemonic == "b.vc" or
          inst.mnemonic == "b.hi" or
          inst.mnemonic == "b.ls" or
          inst.mnemonic == "b.ge" or
          inst.mnemonic == "b.lt" or
          inst.mnemonic == "b.gt" or
          inst.mnemonic == "b.le" or
          inst.mnemonic == "b.al"):
        return [(block.addr + block.size, new_state),
                (inst.operands[0].value.imm, new_state)]
    elif inst.mnemonic == "tbz":
        return [(block.addr + block.size, new_state),
                (inst.operands[2].value.imm, new_state)]

    print("wtf2", hex(inst.address), inst.mnemonic)

def fix_complex_csel_br(start_state, end_state, block: angr.Block, depend):
    def find_inst(name):
        for inst in depend:
            if inst.mnemonic == name:
                return inst
        return None

    br = block.capstone.insns[len(block.capstone.insns) - 1]
    csel = find_inst("csel")
    pre_state = run_block(block, start_state.copy(), stop_addr=csel.address)
    rd = csel.operands[0].value.reg
    rn = csel.operands[1].value.reg
    rm = csel.operands[2].value.reg
    cond = csel.op_str.split(", ")[3]

    start = csel.address + 4

    rn_cond_value = pre_state.regs.get(cs.reg_name(rn))
    rm_cond_value = pre_state.regs.get(cs.reg_name(rm))

    pre_state.registers.store(cs.reg_name(rd), rn_cond_value)
    rn_state = run_block(block, pre_state.copy(), start_addr=start)
    rn_value = rn_state.regs.get(cs.reg_name(br.operands[0].value.reg))
    if rn_value.symbolic:
        return None, None

    pre_state.registers.store(cs.reg_name(rd), rm_cond_value)
    rm_state = run_block(block, pre_state.copy(), start_addr=start)
    rm_value = rm_state.regs.get(cs.reg_name(br.operands[0].value.reg))
    if rm_value.symbolic:
        return None, None

    new_inst = [
        {
            "inst": "b." + cond,
            "real_addr": rn_value.v,
        }, {
            "inst": "b",
            "real_addr": rm_value.v,
        }
    ]
    nop_idx = [
        csel.address,
        br.address
    ]
    print("new_inst ", new_inst)
    print("nop_idx ", nop_idx)
    return new_inst, nop_idx, [
        rn_value.v, rm_value.v
    ]

def fix_complex_br(start_state, end_state, block: angr.Block, depend):
    if not (count_inst("cmp", depend) >= 0 or
            count_inst("tst", depend) >= 0 or
            count_inst("fcmp", depend) >= 0 or
            count_inst("cmn", depend) >= 0):
        print("no one cmp")
        return None, None
    new_13 = None
    nop_addr = None
    next_block = None
    if count_inst("csel", depend) == 1:
        new_13, nop_addr, next_block = fix_complex_csel_br(start_state, end_state, block, depend)
    elif count_inst("csel", depend) > 1:
        print("more than one csel")
        return None, None

    if len(new_13) > len(nop_addr):
        print("new_13 > nop_addr")
        return None, None

    br = block.capstone.insns[len(block.capstone.insns) - 1]
    start_addr = block.capstone.insns[0].address
    size = br.address - start_addr + 4
    code = state.memory.load(start_addr, size)
    code_bytes = state.solver.eval(code, cast_to=bytes)
    codes = bytes_to_chunks(code_bytes)

    def addr2idx(addr):
        return int((addr - start_addr) / 4)

    for item in nop_addr:
        codes[addr2idx(item)] = None
    codes = move_none_to_end(codes)

    def get_nop_addr():
        index = 0
        for idx in range(0, len(codes)):
            if codes[idx] == None:
                index = idx
                break

        return index, start_addr + index * 4

    for item in new_13:
        idx, addr = get_nop_addr()
        codes[idx] = ks.asm(item["inst"] + " " + hex(item["real_addr"]), addr, True)[0]

    next_result = []
    for item in next_block:
        next_result.append((item, end_state))
    return {
        "addr": start_addr,
        "code": chunks_to_bytes(codes).hex()
    }, next_result

def process_func(addr):
    func_start, func_end, func2_start = guess_func_range(addr)
    print(hex(func_start), hex(func_end), hex(func2_start))
    blocks = get_all_block(func_start, func_end)
    print("blocks size ", len(blocks))

    state = project.factory.blank_state(addr=func_start)
    state.options.add(angr.options.CALLLESS)
    state.options.add(angr.options.SYMBOLIC_INITIAL_VALUES)
    stack = [(func_start, state)]
    visited = set()
    patch_info = []

    def on_fix_br(inst, real_target):
        print("fix ", inst, hex(real_target))
        fix_inst = ""
        if inst.mnemonic == "blr":
            fix_inst = "bl "
        elif inst.mnemonic == "br":
            fix_inst = "b "
        else:
            print("wtf4")
        if symbols.get(real_target):
            info = {
                "addr": inst.address,
                "inst": fix_inst,
                "sym": symbols.get(real_target)
            }
        else:
            info = {
                "addr": inst.address,
                "code": ks.asm(fix_inst + hex(real_target), inst.address, True)[0].hex()
            }
        patch_info.append(info)

    def on_complex_br(start_state, end_state, block, depend):
        result, next_block = fix_complex_br(start_state, end_state, block, depend)
        if result is None:
            return None
        patch_info.append(result)
        return next_block

    while stack:
        current_addr, current_state = stack.pop()
        if current_addr in visited:
            continue
        visited.add(current_addr)

        if current_addr not in blocks:
            print("new block", hex(current_addr))
            blocks[current_addr] = {
                "block": project.factory.block(current_addr)
            }
        block = blocks[current_addr]["block"]

        log_next_addr = ""
        next_states = visit_block(block, current_state, on_fix_br, on_complex_br)
        for next_addr, next_state in next_states:
            # if func_start <= next_addr < func_end and next_addr not in visited:  # 限制在函数内
            stack.append((next_addr, next_state))
            log_next_addr += hex(next_addr) + ", "

        print("visit", hex(current_addr), "next", log_next_addr)

    visited_sorted = ', '.join(map(hex, sorted(visited)))
    print("visited", visited_sorted)

    blocks_keys_sorted = ', '.join(map(hex, sorted(blocks.keys())))
    print("all", blocks_keys_sorted)

    print("patch_info", json.dumps(patch_info))

process_func(0x14F394)

# print(serialize_instruction_list()

# find_br_dep_inst(project.factory.block(0x150138))
```

```
import ida_funcs
import idautils

def undefine_and_redefine_function(start, end):
    # 步骤1: 找到并删除范围[start, end)内的所有函数
    for func_start in idautils.Functions(start, end):
        if ida_funcs.del_func(func_start):
            print(f"Deleted function at {hex(func_start)}")
        else:
            print(f"Failed to delete function at {hex(func_start)}")

    # 步骤2: 添加新函数从start到end (end为exclusive)
    if ida_funcs.add_func(start, end):
        print(f"Successfully added new function from {hex(start)} to {hex(end)}")
    else:
        print(f"Failed to add new function from {hex(start)} to {hex(end)}")

# 示例调用: 替换为实际地址
undefine_and_redefine_function(0x14f394, 0x1503e8)

import json

import idc

import ida_name
import idaapi
from keystone import *

ks = keystone.Ks(KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN)

patch_info = json.loads(open("D:\desktop\ollvm_python\ida\patch_info.json").read())

for item in patch_info:
    print("patch " + hex(item["addr"]))
    if item.get("sym"):
        target_ea = idc.get_name_ea_simple(item["sym"])
        if target_ea == idc.BADADDR or target_ea == idaapi.BADADDR:
            print("not find " + item["sym"])
            continue
        asm_inst = "bl " + hex(target_ea)
        code = ks.asm(asm_inst, item["addr"], True)[0]
        idaapi.patch_bytes(item["addr"], code)
    else:
        idaapi.patch_bytes(item["addr"], bytes.fromhex(item["code"]))
```

```
from capstone import *

cs = Cs(CS_ARCH_ARM64, CS_MODE_ARM)

def disasm(state, pc):
    code = state.memory.load(pc, 4)
    code_bytes = state.solver.eval(code, cast_to=bytes)
    for item in cs.disasm(code_bytes, pc):
        return item
    return None

def chunks_to_bytes(chunks: list[bytes]) -> bytes:
    return b''.join(chunks)

def bytes_to_chunks(data: bytes) -> list[bytes]:
    return [data[i:i + 4] for i in range(0, len(data), 4)]

def move_none_to_end(arr: list) -> list:
    result = arr.copy()
    non_none_pos = 0
    for i in range(len(result)):
        if result[i] is not None:
            result[non_none_pos], result[i] = result[i], result[non_none_pos]
            non_none_pos += 1
    return result
```

```
import archinfo
import pyvex

def find_reg_dep_inst(irsb, target_reg):
    def get_add_mapping(statements):
        result = {}
        last_addr = None
        for idx in range(len(statements)):
            stmt = statements[idx]
            if isinstance(stmt, pyvex.IRStmt.IMark):
                last_addr = stmt.addr
            else:
                result[idx] = last_addr
        return result

    def get_tmp_offset_key(offset):
        return f"tmp_{offset}"

    def get_reg_offset_key(offset):
        return f"reg_{offset}"

    def make_interested_value(datas):
        result = {}
        if not isinstance(datas, list) and not isinstance(datas, tuple):
            datas = [datas]
        for data in datas:
            if isinstance(data, pyvex.expr.RdTmp):
                result[get_tmp_offset_key(data.tmp)] = {
                    "type": "tmp",
                    "value": data.tmp,
                }
            elif isinstance(data, pyvex.expr.Unop):
                result.update(make_interested_value(data.args))
            elif isinstance(data, pyvex.expr.Load):
                # print("waring read mem")
                result.update(make_interested_value(data.addr))
            elif isinstance(data, pyvex.expr.Binop):
                result.update(make_interested_value(data.args))
            elif isinstance(data, pyvex.expr.CCall):
                result.update(make_interested_value(data.args))
            elif isinstance(data, pyvex.expr.ITE):
                result.update(make_interested_value(data.child_expressions))
                result.update(make_interested_value(data.cond))
            elif isinstance(data, pyvex.expr.Get):
                result[get_reg_offset_key(data.offset)] = {
                    "type": "reg",
                    "value": data.offset,
                }
            elif isinstance(data, pyvex.expr.Const):
                pass
            else:
                print("unknow put.data op", data)
        return result

    target_reg_offset = archinfo.ArchAArch64().get_register_offset(target_reg)
    statements = list(reversed(irsb.statements))
    dependencies_idx = []
    interested_value = {}
    interested_value[get_reg_offset_key(target_reg_offset)] = {
        "type": "reg",
        "value": target_reg_offset,
    }

    for idx in range(len(statements)):
        stmt = statements[idx]

        find_key = None
        find_value = None

        if isinstance(stmt, pyvex.IRStmt.IMark):
            continue
        elif isinstance(stmt, pyvex.IRStmt.Put):
            if get_reg_offset_key(stmt.offset) in interested_value.keys():
                find_key = get_reg_offset_key(stmt.offset)
                find_value = make_interested_value(stmt.data)
        elif isinstance(stmt, pyvex.IRStmt.WrTmp):
            if get_tmp_offset_key(stmt.tmp) in interested_value.keys():
                find_key = get_tmp_offset_key(stmt.tmp)
                find_value = make_interested_value(stmt.data)
        elif isinstance(stmt, pyvex.IRStmt.Store):
            if hasattr(stmt.data, "tmp") and get_tmp_offset_key(stmt.data.tmp) in interested_value.keys():
                find_key = get_tmp_offset_key(stmt.data.tmp)
                find_value = make_interested_value(stmt.data)
        else:
            print("unknow vex op ", stmt)

        if find_key:
            interested_value.update(find_value)
            del interested_value[find_key]
            dependencies_idx.append(idx)

    count = len(irsb.statements)
    addr_mapping = get_add_mapping(irsb.statements)
    dependencies_addr = set()
    for item in dependencies_idx:
        dependencies_addr.add(addr_mapping[count - item - 1])

    dependencies_addr = list(dependencies_addr)
    dependencies_addr.sort()
    return dependencies_addr
```

---

# 回复

## 回复 by 带带弟弟吧 (#2)

*2025-12-22 15:43*

111

## 回复 by 乐子人 (#3)

*2025-12-22 15:44*

护道者

## 回复 by New对象处 (#4)

*2025-12-22 15:45*

护道者

## 回复 by DirtyAngle (#5)

*2025-12-22 15:45*

>
> [乐子人](https://bbs.kanxue.com/user-872365.htm)
>
>  护道者
>
>

护道者![image](https://bbs.kanxue.com/view/img/face/082.gif)

## 回复 by ghostrong (#6)

*2025-12-22 15:45*

护道者

## 回复 by zzw_xjx (#7)

*2025-12-22 15:48*

护道者

## 回复 by wx_0.0_522 (#8)

*2025-12-22 15:54*

6啊 阿伦

## 回复 by DirtyAngle (#9)

*2025-12-22 15:55*

>
> [wx_0.0_522](https://bbs.kanxue.com/user-926731.htm)
>
>  6啊 阿伦
>
>

回复护道者 谢谢

## 回复 by wangzehua (#10)

*2025-12-22 16:12*

护道者

## 回复 by mb_iesvmzqc (#11)

*2025-12-22 16:15*

护道者

## 回复 by dreamerqq (#12)

*2025-12-22 16:23*

护道者

## 回复 by 拾海 (#13)

*2025-12-22 16:34*

护道者

## 回复 by 月清晖 (#14)

*2025-12-22 17:11*

护道者

## 回复 by Imxz (#15)

*2025-12-22 17:39*

tql

## 回复 by wx_。。。。_455 (#16)

*2025-12-22 17:46*

111

## 回复 by mb_qimctavn (#17)

*2025-12-22 17:47*

6

## 回复 by mb_hfbssgnc (#18)

*2025-12-22 17:55*

6

## 回复 by fjqisba (#19)

*2025-12-22 18:17*

111

## 回复 by mb_roiscepd (#20)

*2025-12-22 18:27*

护道者

## 回复 by JWPL (#21)

*2025-12-22 18:34*

6

## 回复 by mb_ldbucrik (#22)

*2025-12-22 18:42*

666

## 回复 by mb_4nrpVMxJ (#23)

*2025-12-22 18:57*

护道者

## 回复 by 快乐的小跳蛙 (#24)

*2025-12-22 19:08*

护道者

## 回复 by mb_asiwnxyv (#25)

*2025-12-22 19:09*

666

## 回复 by xianhuimin (#26)

*2025-12-22 19:12*

看看说什么的

## 回复 by 壹久玖 (#27)

*2025-12-22 19:23*

123

## 回复 by 逆天而行 (#28)

*2025-12-22 21:12*

似乎 这个 from patch_br.patch_so import PatchSo  好像 没有

## 回复 by kingking888 (#29)

*2025-12-22 21:59*

666

## 回复 by mb_yyvcbkli (#30)

*2025-12-22 22:07*

护道者，学习先进经验

## 回复 by zkbutt (#31)

*2025-12-22 23:22*

学习

## 回复 by bisoso (#32)

*2025-12-22 23:31*

6666666666

## 回复 by xifgg (#33)

*2025-12-22 23:40*

66

## 回复 by mb_nkjfyhkg (#34)

*2025-12-23 03:18*

mark

## 回复 by buluo533 (#35)

*2025-12-23 07:40*

护道者

## 回复 by 黑屏 (#36)

*2025-12-23 08:05*

护道者

## 回复 by Ascend_202904 (#37)

*2025-12-23 08:53*

ddddddddddddddddddddddd6

## 回复 by huangjw (#38)

*2025-12-23 09:15*

看看是啥

## 回复 by koflfy (#39)

*2025-12-23 10:40*

护道者

## 回复 by git_71735namngsec-netizen (#40)

*2025-12-23 10:50*

666

## 回复 by wujimaa (#41)

*2025-12-23 11:02*

5555

## 回复 by MaYil (#42)

*2025-12-23 11:14*

感谢分享

## 回复 by bedaway (#43)

*2025-12-23 11:24*

666

## 回复 by 温泉划水鱼 (#44)

*2025-12-23 11:41*

啥玩意

## 回复 by mb_tewbhakr (#45)

*2025-12-23 13:02*

看看隐藏

## 回复 by KanXue_NG (#46)

*2025-12-23 13:39*

护道者

## 回复 by guijingwen (#47)

*2025-12-23 13:44*

66

## 回复 by guijingwen (#48)

*2025-12-23 13:44*

66

## 回复 by guijingwen (#49)

*2025-12-23 13:46*

护道者

## 回复 by 文西哥 (#50)

*2025-12-23 14:05*

护道者

## 回复 by Kevin· (#51)

*2025-12-23 14:07*

666

## 回复 by 飞机上唱山歌 (#52)

*2025-12-23 14:12*

1

## 回复 by 樂樂 (#53)

*2025-12-23 14:14*

厉害了

## 回复 by wina (#54)

*2025-12-23 15:00*

护道者

## 回复 by 祝枝山 (#55)

*2025-12-23 15:37*

66

## 回复 by niceday (#56)

*2025-12-23 15:59*

感谢分享

## 回复 by ClPrada (#57)

*2025-12-23 16:37*

护道者

## 回复 by 丶咖啡猫丶 (#58)

*2025-12-23 16:50*

666

## 回复 by Arsylk (#59)

*2025-12-23 16:56*

1

## 回复 by nevinhappy (#60)

*2025-12-23 17:01*

qqq

## 回复 by 梧桐生 (#61)

*2025-12-23 18:00*

666

## 回复 by wx_插曲 (#62)

*2025-12-23 18:06*

666

## 回复 by 烬奇小云 (#63)

*2025-12-23 18:34*

666

## 回复 by .KK (#64)

*2025-12-23 19:44*

护道者

## 回复 by niceli (#65)

*2025-12-23 19:51*

护道者

## 回复 by tubecityman (#66)

*2025-12-23 19:57*

6666

## 回复 by mb_nrqlqhee (#67)

*2025-12-23 20:01*

护道者

## 回复 by wx_还是叫我阿万吧 (#68)

*2025-12-23 20:56*

666

## 回复 by 啊你好哇123 (#69)

*2025-12-23 21:34*

学习

## 回复 by MsScotch (#70)

*2025-12-23 21:35*

***

## 回复 by godiand (#71)

*2025-12-23 23:06*

护道者

## 回复 by zylyy (#72)

*2025-12-23 23:13*

6

## 回复 by mb_cbgtaveo (#73)

*2025-12-23 23:16*

6666666666666666666

## 回复 by Boosted (#74)

*2025-12-23 23:54*

![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by lidongyooo (#75)

*2025-12-24 08:54*

66666

## 回复 by wx_ㅤ_683 (#76)

*2025-12-24 09:42*

护道者

## 回复 by 苏幻墨 (#77)

*2025-12-24 10:50*

护道者

## 回复 by 夜惜风雨 (#78)

*2025-12-24 11:18*

6666666666

## 回复 by tigericon (#79)

*2025-12-24 11:27*

护道者

## 回复 by 毕索 (#80)

*2025-12-24 11:49*

666

## 回复 by mb_zcudycuk (#81)

*2025-12-24 12:58*

你的分享对大家帮助很大，非常感谢！

## 回复 by ldehua (#82)

*2025-12-24 13:13*

666

## 回复 by wx_故事与酒 (#83)

*2025-12-24 13:32*

66666666666666666666666

## 回复 by mb_simteado (#84)

*2025-12-24 15:23*

6

## 回复 by mb_pmgifpme (#85)

*2025-12-24 15:34*

1

## 回复 by lqfcugo (#86)

*2025-12-24 15:34*

？？

## 回复 by mb_xjdhrmck (#87)

*2025-12-24 15:43*

6666

## 回复 by mb_mlyojneh (#88)

*2025-12-24 15:57*

护道者

## 回复 by mb_yfmtnfii (#89)

*2025-12-24 16:07*

111

## 回复 by mb_pfsyglzv (#90)

*2025-12-24 16:08*

护道者

## 回复 by 做好事不留名 (#91)

*2025-12-24 16:10*

1

## 回复 by mb_urzqsoer (#92)

*2025-12-24 18:19*

666666666666666

## 回复 by DragKing (#93)

*2025-12-24 20:09*

6

## 回复 by Dlnn (#94)

*2025-12-24 21:15*

666

## 回复 by 江树 (#95)

*2025-12-24 23:17*

缪

## 回复 by mb_eizetlni (#96)

*2025-12-25 07:59*

666

## 回复 by dsfa (#97)

*2025-12-25 09:30*

护道者

## 回复 by 不具名的悲伤 (#98)

*2025-12-25 09:35*

6

## 回复 by 口艾口牙女马口牙 (#99)

*2025-12-25 09:39*

护道者

## 回复 by amwpecel (#100)

*2025-12-25 09:50*

66666

## 回复 by hpphpp (#101)

*2025-12-25 10:07*

ModuleNotFoundError: No module named 'patch_br'

## 回复 by hpphpp (#102)

*2025-12-25 10:07*

护道者

## 回复 by mb_eiufitqh (#103)

*2025-12-25 10:23*

护道者

## 回复 by XCicada (#104)

*2025-12-25 10:50*

厉害

## 回复 by mb_pesxllvn (#105)

*2025-12-25 10:57*

666

## 回复 by hpphpp (#106)

*2025-12-25 11:21*

修复并创建了了仓库

https://github.com/hpp0hpp/deobfuscate_br

## 回复 by DirtyAngle (#107)

*2025-12-25 11:33*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  hpphpp](https://bbs.kanxue.com/user-226208.htm)
>
>  修复并创建了了仓库https://github.com/hpp0hpp/deobfuscate_br
>
>

好家伙![image](https://bbs.kanxue.com/view/img/face/049.gif)

## 回复 by mb_ykavguun (#108)

*2025-12-25 12:34*

6

## 回复 by mb_nkgphjuz (#109)

*2025-12-25 13:40*

护道者

## 回复 by cdline (#110)

*2025-12-25 14:21*

6

## 回复 by 流光岁影 (#111)

*2025-12-25 15:05*

护道者

## 回复 by mb_garozvwc (#112)

*2025-12-25 15:10*

666

## 回复 by 零_721409 (#113)

*2025-12-25 15:19*

666

## 回复 by hhhhyyyyy (#114)

*2025-12-25 20:46*

6

## 回复 by mb_haaygihg (#115)

*2025-12-25 20:52*

护道者

## 回复 by 机车王子 (#116)

*2025-12-25 22:08*

期待更多优质内容的分享，论坛有你更精彩！

## 回复 by Thehepta (#117)

*2025-12-26 11:21*

111

## 回复 by git_94730eaydwshawke-gif (#118)

*2025-12-26 12:02*

666666

## 回复 by byhk (#119)

*2025-12-26 12:48*

谢谢分享

## 回复 by 错过 (#120)

*2025-12-26 17:24*

666

## 回复 by wx-LL- (#121)

*2025-12-26 17:32*

护道者

## 回复 by mb_pkudpfvu (#122)

*2025-12-26 21:13*

6666

## 回复 by mb_dcjxxhsk (#123)

*2025-12-27 02:24*

6666

## 回复 by pyth0nDev (#124)

*2025-12-27 03:19*

666

## 回复 by mb_dmryhnwz (#125)

*2025-12-27 13:33*

666

## 回复 by wx_马 (#126)

*2025-12-27 13:45*

666

## 回复 by xuanzee (#127)

*2025-12-27 15:31*

护道者

## 回复 by wen55444 (#128)

*2025-12-27 22:29*

666

## 回复 by roysue (#129)

*2025-12-29 10:15*

666

## 回复 by 蜜蜂啊 (#130)

*2025-12-29 10:27*

谢谢分享

## 回复 by 猎人猎枪 (#131)

*2025-12-29 10:33*

谢谢附件收到了

## 回复 by FindCall (#132)

*2025-12-29 10:45*

666

## 回复 by 李不空 (#133)

*2025-12-29 12:08*

6666

## 回复 by mb_xkddanpb (#134)

*2025-12-29 12:28*

护道者

## 回复 by 天下有敌 (#135)

*2025-12-29 12:54*

1

## 回复 by wx_Dispa1r (#136)

*2025-12-29 13:03*

宝宝你是个宝宝

## 回复 by mb_dejlmkfe (#137)

*2025-12-29 13:11*

666

## 回复 by GitRoy (#138)

*2025-12-29 13:46*

666

## 回复 by mb_kkftavzg (#139)

*2025-12-29 14:03*

护道者

## 回复 by mb_yaiyynco (#140)

*2025-12-29 14:33*

不错

## 回复 by tjytjy (#141)

*2025-12-29 14:37*

护道者

## 回复 by ID蝴蝶 (#142)

*2025-12-29 15:06*

66666

## 回复 by ID蝴蝶 (#143)

*2025-12-29 15:07*

护道者

## 回复 by 方子敬xiao (#144)

*2025-12-29 15:34*

666

## 回复 by 鹿耳哟 (#145)

*2025-12-29 15:40*

666

## 回复 by didiid (#146)

*2025-12-29 16:02*

888

## 回复 by wx_小友 (#147)

*2025-12-29 17:01*

kankan

## 回复 by Tom-gogo (#148)

*2025-12-29 17:30*

护道者

## 回复 by 夜的静night (#149)

*2025-12-29 17:38*

看看。。。。。。

## 回复 by baitongling (#150)

*2025-12-29 17:46*

6

## 回复 by Whoami默 (#151)

*2025-12-29 17:46*

666

## 回复 by 复活甲 (#152)

*2025-12-29 18:07*

修道者

## 回复 by ulong9527 (#153)

*2025-12-29 22:08*

6

## 回复 by 胖虎汇邦 (#154)

*2025-12-30 00:23*

666

## 回复 by mb_elqwyvnm (#155)

*2025-12-30 00:30*

护道者

## 回复 by dreameriii (#156)

*2025-12-30 10:47*

太强了，学习学习！

## 回复 by mb_ezphxtar (#157)

*2025-12-30 12:58*

6666

## 回复 by mb_ohzsxaph (#158)

*2025-12-30 17:13*

护道者

## 回复 by asdfsadff (#159)

*2025-12-30 17:59*

啊大大阿达是的

## 回复 by gaoyanggnay (#160)

*2025-12-30 18:24*

护道者

## 回复 by mb_dfutauur (#161)

*2025-12-30 22:16*

护道者

## 回复 by 莱茵 (#162)

*2025-12-30 22:28*

666

## 回复 by eroy (#163)

*2025-12-30 22:53*

666666666

## 回复 by 猪会被杀掉 (#164)

*2025-12-31 00:00*

1111

## 回复 by apxar (#165)

*2025-12-31 16:12*

1

## 回复 by 荧光之夏 (#166)

*2025-12-31 17:10*

1

## 回复 by mb_uvyukvot (#167)

*2025-12-31 18:03*

666

## 回复 by mb_fwxjxcgi (#168)

*2026-1-1 03:24*

666

## 回复 by 飆汗吉米 (#169)

*2026-1-1 14:50*

666

## 回复 by mb_vywouypi (#170)

*2026-1-2 22:10*

666

## 回复 by cangwuhu (#171)

*2026-1-4 19:56*

护道者

## 回复 by Zedddd3 (#172)

*2026-1-4 20:48*

护道者

## 回复 by hanjiefang (#173)

*2026-1-6 17:37*

感谢

## 回复 by 乌鸡哥 (#174)

*2026-1-7 12:31*

护道者

## 回复 by iBa0 (#175)

*2026-1-9 15:09*

2123

## 回复 by Kill_Log (#176)

*2026-1-11 17:39*

护道者

## 回复 by Arsylk (#177)

*2026-1-11 17:41*

6

## 回复 by pigsub (#178)

*2026-1-11 18:06*

护道者

## 回复 by 问南山 (#179)

*2026-1-11 19:05*

666

## 回复 by Viseris (#180)

*2026-1-11 21:30*

333

## 回复 by mb_cunjebvg (#181)

*2026-1-14 22:04*

厉害

## 回复 by mb_otxpsqvh (#182)

*2026-1-17 21:25*

护道者

## 回复 by mb_hdiusdyf (#183)

*2026-1-18 03:43*

护道者

## 回复 by guardia (#184)

*2026-1-18 04:06*

护道者

## 回复 by PangBai (#185)

*2026-1-18 23:29*

1

## 回复 by mb_auylfslb (#186)

*2026-1-20 10:48*

7

## 回复 by gcodeer (#187)

*2026-1-20 10:50*

护道者

## 回复 by Superoot (#188)

*2026-1-20 11:13*

互道者

## 回复 by Very_good (#189)

*2026-1-20 19:34*

mark

## 回复 by mb_ssnabqqf (#190)

*2026-1-20 19:39*

111

## 回复 by skyhall (#191)

*2026-1-20 20:15*

学习一下

## 回复 by SInnon (#192)

*2026-1-23 18:13*

护道者

## 回复 by wx_huhu_859 (#193)

*2026-1-23 18:20*

1

## 回复 by Gift1a (#194)

*2026-1-26 14:11*

1

## 回复 by mb_usuztsmd (#195)

*2026-1-27 09:16*

6666

## 回复 by dx苹果的心愿 (#196)

*2026-1-27 09:55*

6

## 回复 by mb_obrkxtbn (#197)

*2026-1-27 23:34*

护道者

## 回复 by Lnju (#198)

*2026-1-30 01:11*

护道者

## 回复 by Azhan_ (#199)

*2026-1-30 10:14*

666

## 回复 by 牛牛很牛 (#200)

*2026-1-30 18:09*

6666

## 回复 by wx_king of the world (#201)

*2026-1-30 19:14*

666

## 回复 by 小白不会逆向 (#202)

*2026-1-31 12:24*

护道者

## 回复 by mb_evlxbmwv (#203)

*2026-2-1 01:39*

666

## 回复 by mb_hfpmtthz (#204)

*2026-2-3 08:47*

666

## 回复 by 灌者为王 (#205)

*2026-2-3 09:32*

护道者

## 回复 by mb_kfrkwwjb (#206)

*2026-2-4 00:40*

66

## 回复 by Fushen99 (#207)

*2026-2-4 14:58*

护道者

## 回复 by 5h3r10(l{ (#208)

*2026-2-4 15:26*

666

## 回复 by Migc (#209)

*2026-2-4 15:46*

护道者

## 回复 by caydemlendi (#210)

*2026-2-7 05:53*

666

## 回复 by mb_eahujfpt (#211)

*2026-2-7 17:22*

感谢分享

## 回复 by mb_ysikfhxt (#212)

*2026-2-7 19:16*

护道者

## 回复 by tjytjy (#213)

*2026-2-10 21:35*

666

## 回复 by tjytjy (#214)

*2026-2-10 21:36*

护道者

## 回复 by kccp (#215)

*2026-2-10 22:38*

go

## 回复 by mb_cluujvok (#216)

*2026-2-11 05:41*

咳咳咳

## 回复 by mb_csnwuokx (#217)

*2026-2-11 15:29*

护道者

## 回复 by Oo风之恋oO (#218)

*2026-2-11 15:47*

这是在干什么

## 回复 by git_99841xmsnmo444 (#219)

*2026-2-13 17:46*

护道者

## 回复 by puppet_w (#220)

*2026-2-14 15:36*

护道者

## 回复 by mJqalJqN (#221)

*2026-2-15 15:15*

1

## 回复 by mb_vvpefhit (#222)

*2026-2-16 09:18*

喷墨

## 回复 by wx_Kerberos (#223)

*2026-2-18 08:39*

![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by myios (#224)

*2026-2-18 10:16*

666

## 回复 by Zireael (#225)

*2026-2-22 17:14*

护道者

## 回复 by 啥也不会2 (#226)

*2026-2-24 13:57*

护道者

## 回复 by pan_634488 (#227)

*2026-2-24 14:35*

666

## 回复 by mb_nulzrwjk (#228)

*2026-2-24 14:41*

666

## 回复 by mb_owfvtagq (#229)

*2026-3-1 21:24*

护道者

## 回复 by wx_coddvccwyh (#230)

*2026-3-1 22:37*

666

## 回复 by Elice (#231)

*2026-3-3 10:40*

666

## 回复 by Elice (#232)

*2026-3-3 10:40*

666

## 回复 by Ram98 (#233)

*2026-3-3 17:26*

护道者

## 回复 by logeye (#234)

*2026-3-3 21:03*

666

## 回复 by Layer1 (#235)

*2026-3-3 22:56*

护道者

## 回复 by mb_sezgvuqb (#236)

*2026-3-4 10:54*

111

## 回复 by 林懋 (#237)

*2026-3-4 11:25*

![image](https://bbs.kanxue.com/view/img/face/005.gif)

## 回复 by ben_ (#238)

*2026-3-9 16:03*

护道者

## 回复 by mb_ybvqgbkl (#239)

*2026-3-10 15:56*

666666666

## 回复 by 九黎 (#240)

*2026-3-10 16:00*

666

## 回复 by xqq524148626 (#241)

*2026-3-11 13:38*

学习下

## 回复 by 红皮西瓜 (#242)

*2026-3-11 14:56*

护道者

## 回复 by cobe (#243)

*2026-3-12 10:45*

666

## 回复 by 勒LI (#244)

*2026-3-12 11:07*

6666

## 回复 by 后来学习 (#245)

*2026-3-15 05:58*

我要品一品这个

## 回复 by AndroidDev (#246)

*2026-3-15 10:28*

666

## 回复 by 熊猫吃鱼 (#247)

*2026-3-15 10:31*

66666

## 回复 by FindCall (#248)

*2026-3-17 20:49*

护道者

## 回复 by A00乐淘 (#249)

*2026-3-17 21:14*

护道者

## 回复 by 帅君 (#250)

*2026-3-19 15:12*

666

## 回复 by 亮亮0107 (#251)

*2026-4-4 19:06*

护道者

## 回复 by fengvmu (#252)

*2026-4-4 19:49*

6

## 回复 by hygzs (#253)

*2026-4-13 17:48*

看看啥情况

## 回复 by mb_stdlrcgp (#254)

*2026-4-20 16:04*

666

## 回复 by mb_eumnbkwy (#255)

*2026-5-1 16:52*

999

## 回复 by Lychow (#256)

*2026-5-6 11:12*

护道者

## 回复 by SoulCat_ (#257)

*2026-5-9 14:27*

护道者

## 回复 by mb_cmdpqcqn (#258)

*2026-5-9 14:31*

666

## 回复 by mb_lzotvdxv (#259)

*2026-5-9 19:53*

请在 Telegram 上联系我，我有一个重要的付费任务要交给你。 2000$ 任务
Telegram：@dlopenext

## 回复 by mb_irrqcmsq (#260)

*2026-5-15 10:01*

谢谢，太厉害了

## 回复 by mb_stdlrcgp (#261)

*2026-5-15 14:16*

666

## 回复 by huluxia (#262)

*2026-5-16 22:56*

护道者

## 回复 by hacker521 (#263)

*2026-5-18 11:04*

thanks

## 回复 by Wh1tebird (#264)

*2026-5-20 14:53*

护道者

## 回复 by ugui (#265)

*2026-5-26 18:31*

0.0

## 回复 by wx_fly_397447 (#266)

*2026-5-27 00:29*

66666

## 回复 by ycdear (#267)

*2026-5-27 00:34*

111

## 回复 by baichisi (#268)

*2026-5-27 09:43*

66
