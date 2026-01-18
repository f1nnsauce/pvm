#!/usr/bin/env python3
import time, random, threading, os, sys, warnings
from pathlib import Path
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
os.environ["PYGAME_DETECT_AVX2"] = "1"

class _DevNull:
    def write(self, *_): pass
    def flush(self): pass
    
real_stderr = sys.stderr
sys.stderr = _DevNull()

import pygame
sys.stderr = real_stderr
warnings.filterwarnings("ignore")
if len(sys.argv) != 2:
    print("usage: pvm <file>.pvm")
    sys.exit(1)

path = Path(sys.argv[1])

if path.suffix.lower() != ".pvm":
    print("error: file must have a .pvm extension")
    sys.exit(1)

if not path.is_file():
    print("error: file does not exist")
    sys.exit(1)

filename = str(path)

pygame.init()

class SSD:
    def __init__(self, file="mem", size=1073741824):
        if not os.path.exists(file):
            open(file, 'a').close()

        self.curr_size = os.path.getsize(file)
        if self.curr_size > size:
            with open(file, "r+") as f:
                f.truncate(0)
                f.seek(0)

        self.filename = file
        self.size = size

    def wipe(self):
        with open(self.filename, "r+") as f:
            f.truncate(0)
            f.seek(0)

    def wipe_section(self, section_name):
        """Removes an entire section and its contents."""
        target = f"[{section_name}]"

        with open(self.filename, "r") as f:
            lines = f.readlines()

        new_lines = []
        skipping = False
        found = False

        for line in lines:
            stripped = line.strip()

            if stripped == target:
                skipping = True
                found = True
                continue

            if skipping and stripped.startswith("[") and stripped.endswith("]"):
                skipping = False

            if not skipping:
                self._cleanup_excess_newlines(new_lines, line)

        if found:
            with open(self.filename, "w") as f:
                f.writelines(new_lines)

        return found

    def return_data(self, section_name, data_title):
        """Returns value from section/key or None."""
        target = f"[{section_name}]"
        key = f"{data_title}="

        with open(self.filename, "r") as f:
            in_section = False
            for line in f:
                stripped = line.strip()

                if stripped == target:
                    in_section = True
                    continue

                if in_section and stripped.startswith("[") and stripped.endswith("]"):
                    break

                if in_section and stripped.startswith(key):
                    return stripped.split("=", 1)[1]

        return None

    def _cleanup_excess_newlines(self, lines, current):
        if current.strip() == "" and lines and lines[-1].strip() == "":
            return
        lines.append(current)

    def write_to(self, section_name, data_title, data):
        if os.path.getsize(self.filename) > self.size:
            return None

        target = f"[{section_name}]"
        entry = f"{data_title}={data}\n"

        with open(self.filename, "r+") as f:
            lines = f.readlines()
            sec_idx = -1
            key_idx = -1

            for i, line in enumerate(lines):
                if line.strip() == target:
                    sec_idx = i
                elif sec_idx != -1 and line.startswith("["):
                    break
                elif sec_idx != -1 and line.startswith(f"{data_title}="):
                    key_idx = i
                    break

            if key_idx != -1:
                lines[key_idx] = entry
            elif sec_idx == -1:
                lines.append(f"\n{target}\n{entry}")
            else:
                lines.insert(sec_idx + 1, entry)

            f.seek(0)
            f.writelines(lines)
            f.truncate()

        return True

class CPU:
    def __init__(self, mem_size=256, regs=200):
        self.__running = False
        self.__memory = [0] * mem_size
        self.__registers = {f"REG{i}": 0 for i in range(1, regs+1)}
        self.__pc = 0
        self.__function_idxs = {}
        self.__last_stop_line = 0
        self.__in_loop = False
        self.__loop_begin_line = 0
        self.__loop_times = 0
        self.__loop_max = 9999
        self.__graphics_screen = None
        self.__graphics_running = False
        self.__colors = {
            "RED": pygame.Color(255,0,0),
            "GREEN": pygame.Color(0,255,0),
            "BLUE": pygame.Color(0,0,255),
            "YELLOW": pygame.Color(255,255,0),
            "CYAN": pygame.Color(0,255,255),
            "BROWN": pygame.Color(125,60,0),
            "MAGENTA": pygame.Color(255,0,255),
            "WHITE": pygame.Color(255,255,255),
            "BLACK": pygame.Color(0,0,0)
        }
        self.__flags = {
            "TRUE": False
        }
        ssd_path = os.path.expanduser("~/.pvm/storage")
        os.makedirs(os.path.dirname(ssd_path), exist_ok=True)
        self.__ssd = SSD(ssd_path)
        self.__memid = ""

    def fetch(self):
        instr = self.__memory[self.__pc]
        self.__pc += 1
        return instr
    
    def start_window(self,h,w):
        self.__graphics_running = True
        self.__graphics_screen = pygame.display.set_mode((w,h))
        clock = pygame.time.Clock()
        while self.__graphics_running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.__graphics_running = False
            pygame.display.flip()
            clock.tick(60)
        pygame.quit()
        
    def load_program(self, program):
        """
        Load a program into memory.

        :param program: List of commands.
        """
        if len(program) > len(self.__memory):
            print("NOT ENOUGH MEMORY FOR PROGRAM.")
            return
        for i, instruction in enumerate(program):
            self.__memory[i] = instruction
        self.__pc = 0
    
    def execute(self, instruction):
        op = instruction[0]
        if op == "LOAD":
            reg = instruction[1]
            val:str = instruction[2]
            try:
                val = int(val)
            except ValueError:
                try:
                    val = float(val)
                except ValueError:
                    if val.startswith('"') and instruction[-1].endswith('"'):
                        val = ' '.join(instruction[2:]).strip('"')
                    else:
                        print(f"INVALID LOAD VALUE AT PC {self.__pc}")
                        self.__running = False
            self.__registers[reg] = val
        elif op == "SUM":
            reg1,reg2 = instruction[1], instruction[2]
            self.__registers[reg1] += self.__registers[reg2]
        elif op == "SUB":
            reg1,reg2 = instruction[1], instruction[2]
            self.__registers[reg1] -= self.__registers[reg2]
        elif op == "MULT":
            reg1,reg2 = instruction[1], instruction[2]
            self.__registers[reg1] *= self.__registers[reg2]
        elif op == "TM":
            reg = instruction[1]
            self.__registers[reg] = time.time()
        elif op == "IN":
            reg,q = instruction[1], ' '.join(instruction[2:]).strip('"')
            self.__registers[reg] = input(q)
        elif op == "CLR":
            reg = instruction[1]
            self.__registers[reg] = 0
        elif op == "FILLGRA":
            self.__graphics_screen.fill(self.__colors[instruction[1]])
        elif op == "OUT":
            reg = instruction[1]
            print(self.__registers[reg])
        elif op == "MEMID":
            memid = instruction[1]
            self.__memid = memid
        elif op == "GETMEM":
            reg, key = instruction[1], instruction[2]
            self.__registers[reg] = self.__ssd.return_data(self.__memid, key)
        elif op == "DELSAVE":
            key = instruction[1]
            self.__ssd.wipe_section(self.__memid)
        elif op == "ADDMEM":
            data_title, data = instruction[1], instruction[2]
            if instruction[2].startswith('"') and instruction[-1].endswith('"'):
                data = ' '.join(instruction[2:])
            self.__ssd.write_to(self.__memid, data_title, data)
        elif op == "MOV":
            reg1, reg2 = instruction[1], instruction[2]
            self.__registers[reg1] = self.__registers[reg2]
        elif op == "DELAY":
            delay = float(instruction[1])
            time.sleep(delay)
        elif op == "RECT":
            l, t, w, h, c = instruction[1], instruction[2], instruction[3], instruction[4], instruction[5]
            if l.startswith("REG"):
                l = self.__registers[l]
            if t.startswith("REG"):
                t = self.__registers[t]
            if w.startswith("REG"):
                w = self.__registers[w]
            if h.startswith("REG"):
                h = self.__registers[h]
            l = int(l)
            t = int(t)
            w = int(w)
            h = int(h)
            pygame.draw.rect(self.__graphics_screen, self.__colors[c], pygame.Rect(l, t, w, h))
        elif op == "RANDI":
            reg,minn,maxn = instruction[1],instruction[2],instruction[3]
            self.__registers[reg] = random.randint(int(minn),int(maxn))
        elif op == "CIRC":
            x, y, r, c = instruction[1], instruction[2], instruction[3], instruction[4]
            if x.startswith("REG"):
                x = self.__registers[x]
            if y.startswith("REG"):
                y = self.__registers[y]
            if r.startswith("REG"):
                r = self.__registers[r]
            c = self.__colors[c]
            pygame.draw.circle(self.__graphics_screen, c, (x,y), r)
        elif op == "PIX":
            t, l = instruction[2], instruction[3]
            if t.startswith("REG"):
                t = self.__registers[t]
            if l.startswith("REG"):
                l = self.__registers[l]
            l = int(l)
            t = int(t)
            pygame.draw.circle(self.__graphics_screen, self.__colors[instruction[1]], (l,t), 2)
        elif op == "CMP":
            reg1,oper,reg2 = instruction[1],instruction[2],instruction[3]
            reg1 = self.__registers[reg1]
            reg2 = self.__registers[reg2]
            if oper == "==":
                if reg1 == reg2:
                    self.__flags["TRUE"] = True
                else:
                    self.__flags["TRUE"] = False
            if oper == "!=":
                if reg1 != reg2:
                    self.__flags["TRUE"] = True
                else:
                    self.__flags["TRUE"] = False
            if oper == "<":
                if reg1 < reg2:
                    self.__flags["TRUE"] = True
                else:
                    self.__flags["TRUE"] = False
            if oper == ">":
                if reg1 > reg2:
                    self.__flags["TRUE"] = True
                else:
                    self.__flags["TRUE"] = False
            if oper == "<=":
                if reg1 <= reg2:
                    self.__flags["TRUE"] = True
                else:
                    self.__flags["TRUE"] = False
            if oper == ">=":
                if reg1 >= reg2:
                    self.__flags["TRUE"] = True
                else:
                    self.__flags["TRUE"] = False
            if oper == "STARTWITH":
                if reg1.startswith(reg2):
                    self.__flags["TRUE"] = True
                else:
                    self.__flags["TRUE"] = False
            if oper == "ENDWITH":
                if reg1.endswith(reg2):
                    self.__flags["TRUE"] = True
                else:
                    self.__flags["TRUE"] = False
        elif op == "IF":
            if instruction[1] == "F":
                if self.__flags["TRUE"] == False:
                    cmd = ' '.join(instruction[2:])
                    self.execute(cmd.strip().split())
            elif instruction[1] == "T":
                if self.__flags["TRUE"] == True:
                    cmd = ' '.join(instruction[2:])
                    self.execute(cmd.strip().split())
        elif op == "SWP":
            reg1, reg2 = instruction[1], instruction[2]
            self.__registers[reg1], self.__registers[reg2] = self.__registers[reg2], self.__registers[reg1]
        elif op.startswith("$"):
            func_name = op.lstrip("$")
            self.__function_idxs[func_name] = self.__pc
            while self.__pc < len(self.__memory):
                inst = self.__memory[self.__pc]
                self.__pc += 1
                if isinstance(inst, str) and inst.strip().startswith("ENDF"):
                    break
        elif op == "CALL":
            name = instruction[1]
            if name in self.__function_idxs:
                self.__last_stop_line = self.__pc
                self.__pc = self.__function_idxs[name]
        elif op.startswith("LOOP"):
            looptimes = instruction[1]
            self.__in_loop = True
            self.__loop_begin_line = self.__pc + 1
            self.__loop_max = int(looptimes)
            self.__loop_times = 0
        elif op.startswith("ENDL"):
            if not self.__in_loop:
                print("UNEXPECTED ENDL!")
                return
            if self.__loop_times < self.__loop_max:
                self.__pc = self.__loop_begin_line
                self.__loop_times += 1
            else:
                self.__in_loop = False
        elif op == "INC":
            reg = instruction[1]
            self.__registers[reg] += 1
        elif op == "GRA":
            w,h = int(instruction[1]),int(instruction[2])
            thread = threading.Thread(target=self.start_window, args=(h,w))
            thread.start()
            while not self.__graphics_screen:
                time.sleep(0.01)
        elif op == "DEC":
            reg = instruction[1]
            self.__registers[reg] -= 1
        elif op == "ENDF":
            self.__pc = self.__last_stop_line
        elif op.startswith(";"):
            pass
        elif op == "TOINT":
            reg = instruction[1]
            try:
                self.__registers[reg] = int(self.__registers[reg])
            except:
                print(f"ERROR ON TOINT AT PC {self.__pc}")
                self.__running = False
                raise Exception
        elif op == "TOSTR":
            reg = instruction[1]
            try:
                self.__registers[reg] = str(self.__registers[reg])
            except:
                print(f"ERROR ON TOSTR AT PC {self.__pc}")
                self.__running = False
                raise Exception
        elif op == "TOFLOAT":
            reg = instruction[1]
            try:
                self.__registers[reg] = float(self.__registers[reg])
            except:
                print(f"ERROR ON TOFLOAT AT PC {self.__pc}")
                self.__running = False
                raise Exception
        elif op == "CUT":
            reg = instruction[1]
            start, end = instruction[2], instruction[3]
            if start.startswith("REG"):
                start = self.__registers[start]
            if end.startswith("REG"):
                end = self.__registers[end]
            self.__registers[reg] = self.__registers[reg][start:end]
        elif op == "HLT":
            pygame.quit()
            self.__running = False
        else:
            print("UNRECOGNIZED COMMAND ERROR")
            self.__running = False
            raise Exception
    
    def get_pc(self):
        return self.__pc

    def run(self):
        self.__pc = 0
        self.__running = True
        while self.__running:
            inst = self.fetch()
            if isinstance(inst, int):
                break
            inst = inst.strip()
            if not inst:
                continue
            inst = inst.split()
            self.execute(inst)

cpu = CPU()
with open(filename, "r") as f:
    content = f.readlines()
cpu.load_program(content)
try:
    cpu.run()
except KeyboardInterrupt:
    pass
except Exception:
    print(f"An error has occured on program-line {cpu.get_pc()-1}")
