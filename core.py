#!/usr/bin/env python3
import time, random, threading, os, sys, requests
from pathlib import Path
from urllib.request import urlopen
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
os.environ["PYGAME_DETECT_AVX2"] = "1"

class _DevNull:
    def write(self, *_): pass
    def flush(self): pass
    
real_stderr = sys.stderr
sys.stderr = _DevNull()

import pygame

sys.stderr = real_stderr
if len(sys.argv) < 2:
    print("usage: pvm <file>.pvm (OPTIONAL FLAGS)")
    sys.exit(1)

mem_size = None
regs = None
if "--regs" in sys.argv:
    regs = int(sys.argv.index("--regs") + 1)
if "--mem-size" in sys.argv:
    mem_size = int(sys.argv.index("--mem-size") + 1)

path = Path(sys.argv[1])

if path.suffix.lower() != ".pvm":
    print("error: file must have a .pvm extension")
    sys.exit(1)

if not path.is_file():
    print("error: file does not exist")
    sys.exit(1)

filename = str(path)

pygame.init()
pygame.mixer.init()

class SSD:
    def __init__(self, file="mem", size=1073741824):
        if not os.path.exists(file):
            open(file, 'a').close()

        self.curr_size = os.path.getsize(file)
        if self.curr_size > size:
            print("You are out of storage!")
            sys.exit(0)

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

    def delete_key(self, section_name, data_title):
        target = f"[{section_name}]"
        key = f"{data_title}="

        with open(self.filename, "r") as f:
            lines = f.readlines()

        new_lines = []
        in_section = False
        deleted = False

        for line in lines:
            stripped = line.strip()

            if stripped == target:
                in_section = True
                new_lines.append(line)
                continue

            if in_section and stripped.startswith("[") and stripped.endswith("]"):
                in_section = False

            if in_section and stripped.startswith(key):
                deleted = True
                continue  # skip this key

            self._cleanup_excess_newlines(new_lines, line)

        if deleted:
            with open(self.filename, "w") as f:
                f.writelines(new_lines)

        return deleted


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
        self.__window_thread = None
        self.__colors = {
            "RED": pygame.Color(255,0,0),
            "GREEN": pygame.Color(0,255,0),
            "BLUE": pygame.Color(0,0,255),
            "YELLOW": pygame.Color(255,255,0),
            "CYAN": pygame.Color(0,255,255),
            "BROWN": pygame.Color(125,60,0),
            "MAGENTA": pygame.Color(255,0,255),
            "WHITE": pygame.Color(255,255,255),
            "BLACK": pygame.Color(0,0,0),
            "GRAY": pygame.Color(155,155,155),
            "DARK_GRAY": pygame.Color(100,100,100)
        }
        self.__flags = {
            "TRUE": False
        }
        self.__font_cache = {}
        self.__window_click_areas = []
        self.__loaded_sounds = {}
        self.__window_key_press_functions = {}
        self.__window_key_rel_functions = {}
        self.__call_stack = []
        self.__loaded_images = {}
        self.__graphics_lock = threading.Lock()
        self.__operators = {
            "==": lambda a, b: a==b,
            "!=": lambda a, b: a!=b,
            ">": lambda a, b: a>b,
            "<": lambda a, b: a<b,
            "<=": lambda a, b: a<=b,
            ">=": lambda a, b: a>=b,
            "STARTWITH": lambda a, b: a.startswith(b),
            "ENDWITH": lambda a, b: a.endswith(b),
        }
        ssd_path = os.path.expanduser("~/.pvm/storage")
        os.makedirs(os.path.dirname(ssd_path), exist_ok=True)
        self.__ssd = SSD(ssd_path)
        self.__pending_graphical_calls = []
        if not "--no-network" in sys.argv:
            self.__session = requests.Session()
        self.__memid = ""

    def fetch(self):
        instr = self.__memory[self.__pc]
        self.__pc += 1
        return instr
    
    def start_window(self,h,w):
        self.__graphics_running = True
        self.__graphics_screen = pygame.display.set_mode((w,h))
        pygame.display.set_caption("PVM GRAPHICAL WINDOW")
        clock = pygame.time.Clock()
        while self.__graphics_running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.__graphics_running = False
                    self.__running = False
                elif event.type == pygame.KEYDOWN:
                    keycode = event.key
                    if keycode in self.__window_key_press_functions:
                        self.__pending_graphical_calls.append(
                            self.__window_key_press_functions[keycode]
                        )
                elif event.type == pygame.KEYUP:
                    keycode = event.key
                    if keycode in self.__window_key_rel_functions:
                        self.__pending_graphical_calls.append(
                            self.__window_key_rel_functions[keycode]
                        )
                elif event.type == pygame.MOUSEBUTTONUP:
                    for i in range(len(self.__window_click_areas)):
                        indx = self.__window_click_areas[i]
                        t,l,w,h,f = indx[0], indx[1], indx[2], indx[3], indx[4]
                        t=int(t)
                        l=int(l)
                        w=int(w)
                        h=int(h)
                        rect = pygame.Rect(l,t,w,h)
                        if rect.collidepoint(pygame.mouse.get_pos()):
                            self.__pending_graphical_calls.append(f)
                            del rect
                            continue
            with self.__graphics_lock:
                pygame.display.flip()
            clock.tick(60)
        pygame.quit()
        self.__running = False
        
    def load_program(self, program):
        """
        Load a program into memory.

        :param program: List of commands.
        """
        if len(program) > len(self.__memory):
            print("NOT ENOUGH MEMORY FOR PROGRAM.")
            return
        for i, instruction in enumerate(program):
            if not instruction.strip():
                continue
            if instruction.startswith(";"):
                continue
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
            num1,num2,reg = instruction[1], instruction[2], instruction[3]
            if num1.startswith("REG"):
                num1 = self.__registers[num1]
            else:
                num1 = int(num1)
            if num2.startswith("REG"):
                num2 = self.__registers[num2]
            else:
                num2 = int(num2)
            self.__registers[reg] = num1+num2
        elif op == "SUB":
            num1,num2,reg = instruction[1], instruction[2], instruction[3]
            if num1.startswith("REG"):
                num1 = self.__registers[num1]
            else:
                num1 = int(num1)
            if num2.startswith("REG"):
                num2 = self.__registers[num2]
            else:
                num2 = int(num2)
            self.__registers[reg] = num1-num2
        elif op == "MULT":
            num1,num2,reg = instruction[1], instruction[2], instruction[3]
            if num1.startswith("REG"):
                num1 = self.__registers[num1]
            else:
                num1 = int(num1)
            if num2.startswith("REG"):
                num2 = self.__registers[num2]
            else:
                num2 = int(num2)
            self.__registers[reg] = num1*num2
        elif op == "DIV":
            num1,num2,reg = instruction[1], instruction[2], instruction[3]
            if num1.startswith("REG"):
                num1 = self.__registers[num1]
            else:
                num1 = int(num1)
            if num2.startswith("REG"):
                num2 = self.__registers[num2]
            else:
                num2 = int(num2)
            self.__registers[reg] = num1/num2
        elif op == "TM":
            reg = instruction[1]
            self.__registers[reg] = time.time()
        elif op == "LOADSOUND":
            sound, name = instruction[1], instruction[2]
            if not self.__graphics_running:
                print("Cannot load sounds without a graphical window!")
                raise Exception
            soundclass = pygame.mixer.Sound(sound)
            self.__loaded_sounds[name] = soundclass
        elif op == "PLAYSOUND":
            name, islooped = instruction[1], instruction[2]
            if not self.__graphics_running:
                print("Can't play sounds without a graphical window!")
                raise Exception
            if not name in self.__loaded_sounds:
                print(f"The sound {name} is not loaded!")
                raise Exception
            soundclass = self.__loaded_sounds[name]
            loops = -1 if islooped.upper() == "TRUE" else 0
            soundclass.play(loops=loops)
        elif op == "STOPSOUND":
            name = instruction[1]
            if not self.__graphics_running:
                print("There isn't any graphical window running to play sounds from!")
                raise Exception
            if not name in self.__loaded_sounds:
                print(f"The sound {name} isn't loaded!")
                raise Exception
            self.__loaded_sounds[name].stop()
        elif op == "REMSOUND":
            name = instruction[1]
            if not self.__graphics_running:
                print("There's no graphical window to remove sounds from.")
                raise Exception
            if not name in self.__loaded_sounds:
                print("This sound isn't even loaded!")
                raise Exception
            self.__loaded_sounds[name] = None
        elif op == "LSSOUND":
            reg = instruction[1]
            self.__registers[reg] = len(self.__loaded_sounds)
        elif op == "IN":
            reg,q = instruction[1], ' '.join(instruction[2:]).strip('"')
            self.__registers[reg] = input(q)
        elif op == "CLR":
            reg = instruction[1]
            self.__registers[reg] = 0
        elif op == "READSITE":
            if no_network: return
            site, reg = instruction[1], instruction[2]
            print(f"[NETWORK]: READSITE on line {self.get_pc()} to website {site}.")
            with urlopen(url=site, timeout=5) as res:
                self.__registers[reg] = res.read().decode("utf-8")
        elif op == "POSTWEB":
            if no_network: return
            site = instruction[1]
            data = instruction[2:]
            body = {}
            print(f"[NETWORK]: POSTWEB on line {self.get_pc()} to website {site}")
            for v in data:
                full = v.split("=")
                key = full[0]
                value = full[1]
                if value.startswith("REG"):
                    value = self.__registers[value]
                body[key] = value
            self.__session.post(site, json=body, timeout=5)
        elif op == "FILLGRA":
            with self.__graphics_lock:
                self.__graphics_screen.fill(self.__colors[instruction[1]])
        elif op == "OUT":
            reg = instruction[1]
            print(self.__registers[reg])
        elif op == "MEMID":
            memid = instruction[1]
            self.__memid = memid
        elif op == "BINDKEY":
            if self.__graphics_running == False:
                print("You cannot bind a key without a graphical window!")
                raise Exception
            func_name, key = instruction[1], instruction[2]
            keycode = pygame.key.key_code(key)
            self.__window_key_press_functions[keycode] = func_name
        elif op == "BINDKEYREL":
            if self.__graphics_running == False:
                print("You cannot bind a key release without a graphical window!")
                raise Exception
            func_name, key = instruction[1], instruction[2]
            keycode = pygame.key.key_code(key)
            self.__window_key_rel_functions[keycode] = func_name
        elif op == "GETMEM":
            reg, key = instruction[1], instruction[2]
            self.__registers[reg] = self.__ssd.return_data(self.__memid, key)
        elif op == "DELSAVE":
            key = instruction[1]
            self.__ssd.wipe_section(self.__memid)
        elif op == "DELMEM":
            key = instruction[1]
            self.__ssd.delete_key(self.__memid, key)
        elif op == "ADDMEM":
            data_title, data = instruction[1], instruction[2]
            if data.startswith("REG"):
                data=self.__registers[data]
            try:
                data = int(data)
            except ValueError:
                try:
                    data = float(data)
                except ValueError:
                    if instruction[2].startswith('"') and instruction[-1].endswith('"'):
                        data = ' '.join(instruction[2:])
                    else:
                        print("Invalid data type")
                        raise Exception
            
            
            self.__ssd.write_to(self.__memid, data_title, data)
        elif op == "MOV":
            reg1, reg2 = instruction[1], instruction[2]
            self.__registers[reg1] = self.__registers[reg2]
        elif op == "DELAY":
            delay = float(instruction[1])
            time.sleep(delay)
        elif op == "RECT":
            l, t, w, h, c = instruction[2], instruction[1], instruction[3], instruction[4], instruction[5]
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
            with self.__graphics_lock:
                pygame.draw.rect(self.__graphics_screen, self.__colors[c], pygame.Rect(l, t, w, h))
        elif op == "CFONT":
            size, italic, name = instruction[1], instruction[2], instruction[3]
            if size.startswith("REG"):
                size = self.__registers[size]
            size=int(size)
            italic = {"TRUE": True, "FALSE": False}.get(italic.upper())
            if italic is None:
                print("Invalid italic value")
                raise Exception
            self.__font_cache[name] = pygame.font.SysFont("Monaco", size, False, italic)
        elif op == "DFONT":
            font_name, x, y, color, text = instruction[1], instruction[2], instruction[3], instruction[4], instruction[5]
            if text.startswith('"') and instruction[-1].endswith('"'):
                text = ' '.join(instruction[5:])
            text = text[1:-1]
            if x.startswith("REG"):
                x=self.__registers[x]
            if y.startswith("REG"):
                y=self.__registers[y]
            y=int(y)
            x=int(x)
            font = self.__font_cache[font_name]
            surface_f = font.render(text, False, self.__colors[color])
            self.__graphics_screen.blit(surface_f, (y,x))
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
            with self.__graphics_lock:
                pygame.draw.circle(self.__graphics_screen, c, (x,y), r)
        elif op == "PIX":
            c, t, l = instruction[1], instruction[2], instruction[3]
            if t.startswith("REG"):
                t = self.__registers[t]
            if l.startswith("REG"):
                l = self.__registers[l]
            l = int(l)
            t = int(t)
            with self.__graphics_lock:
                pygame.draw.circle(self.__graphics_screen, self.__colors[c], (l,t), 2)
        elif op == "IF":
            reg1,oper,reg2 = instruction[1],instruction[2],instruction[3]
            reg1 = self.__registers[reg1]
            reg2 = self.__registers[reg2]
            try:
                self.__flags["TRUE"] = self.__operators[oper](reg1,reg2)
            except KeyError:
                print("Invalid operator")
                raise Exception
            if self.__flags["TRUE"] == False:
                depth = 1
                while depth > 0:
                    instr = self.__memory[self.__pc]
                    self.__pc += 1
                    if isinstance(instr, str):
                        s = instr.strip()
                        if s.startswith("IF "):
                            depth += 1
                        elif s.startswith("ENDIF"):
                            depth -= 1
                        elif s.startswith("ELSE"):
                            break


        elif op == "CLOCK":
            t = instruction[1]
            d = 1 / int(t)
            time.sleep(d)
        elif op == "ENDIF":
            pass
        elif op == "ELSE":
            depth = 1
            while depth > 0:
                instr = self.__memory[self.__pc]
                self.__pc += 1
                if isinstance(instr, str):
                    s = instr.strip()
                    if s.startswith("IF "):
                        depth += 1
                    elif s == "ENDIF":
                        depth -= 1
        elif op == "RET":
            self.__pc = self.__call_stack.pop()
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
                self.__call_stack.append(self.__pc)
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
        elif op == "GRATITLE":
            title = instruction[1]
            if title.startswith('"') and instruction[-1].endswith('"'):
                title = ' '.join(instruction[1:])
                title = title[1:-1]
            pygame.display.set_caption(title)
        elif op == "GRA":
            w,h = int(instruction[1]),int(instruction[2])
            self.__window_thread = threading.Thread(target=self.start_window, args=(h,w))
            self.__window_thread.start()
            while not self.__graphics_screen:
                time.sleep(0.01)
        elif op == "GETMX":
            reg = instruction[1]
            if self.__graphics_running == False:
                print("Must have a graphical window open for getting mouse coordinates!")
            self.__registers[reg] = pygame.mouse.get_pos()[0]
        elif op == "GETMY":
            reg = instruction[1]
            if self.__graphics_running == False:
                print("Must have a graphical window open for getting mouse coordinates!")
            self.__registers[reg] = pygame.mouse.get_pos()[1]
        elif op == "SPRITELOAD":
            path, name = instruction[1], instruction[2]
            img = pygame.image.load(path)
            self.__loaded_images[name] = img
        elif op == "DSPRITE":
            name, top, left = instruction[1], instruction[2], instruction[3]
            if top.startswith("REG"):
                top = self.__registers[top]
            if left.startswith("REG"):
                left = self.__registers[left]
            top=int(top)
            left=int(left)
            if not self.__graphics_running:
                print("You cannot draw sprites without a graphical window!")
                raise Exception
            img = self.__loaded_images[name]
            with self.__graphics_lock:
                self.__graphics_screen.blit(img, (left,top))
        elif op == "BINDCLICK":
            t, l, w, h, func_name = instruction[1], instruction[2], instruction[3], instruction[4], instruction[5]
            if t.startswith("REG"):
                t=self.__registers[t]
            if l.startswith("REG"):
                l=self.__registers[l]
            if w.startswith("REG"):
                w=self.__registers[w]
            if h.startswith("REG"):
                h=self.__registers[h]
            
            self.__window_click_areas.append(
                (t,l,w,h,func_name)
            )
        elif op == "DEC":
            reg = instruction[1]
            self.__registers[reg] -= 1
        elif op == "ENDF":
            self.__pc = self.__call_stack.pop()
        elif op.startswith(";"):
            pass
        elif op == "TOINT":
            reg = instruction[1]
            try:
                val = self.__registers[reg]
                if val is None:
                    val = 0
                if isinstance(val, str):
                    val = val.strip()
                self.__registers[reg] = int(val)
            except Exception:
                print(f"ERROR ON TOINT AT PC {self.__pc} WITH VALUE {self.__registers[reg]}")
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
        elif op == "REGDUMP":
            for k, v in self.__registers.items():
                print(f"{k}: {v}")
        elif op == "CUT":
            reg = instruction[1]
            start, end = instruction[2], instruction[3]
            if start.startswith("REG"):
                start = self.__registers[start]
            if end.startswith("REG"):
                end = self.__registers[end]
            self.__registers[reg] = self.__registers[reg][start:end]
        elif op == "HLT":
            self.__graphics_running = False
            self.__running = False
            if self.__window_thread:
                self.__window_thread.join()
            sys.exit(0)
        else:
            print("UNRECOGNIZED COMMAND ERROR")
            self.__running = False
            raise Exception
    
    def get_pc(self):
        """Get the Program Counter value."""
        return self.__pc

    def run(self):
        self.__running = True
        while self.__running:
            if self.__pending_graphical_calls:
                fn = self.__pending_graphical_calls.pop(0)
                self.execute(("CALL", fn))

            inst = self.fetch()
            if isinstance(inst, int):
                print("EMPTY INSTRUCTION DATA")
                break

            inst = inst.strip()
            if not inst:
                continue

            inst = inst.split()
            self.execute(inst)

verbose = False
if len(sys.argv) == 3 and sys.argv[2] == "--verbose":
    verbose = True

no_network = False
if "--no-network" in sys.argv:
    no_network = True

with open(filename, "r") as f:
    content = f.readlines()

if any("POSTWEB" in line or "READSITE" in line for line in content):
    proceed = input("[WARNING]: This program uses the READSITE and POSTWEB opcodes. This may be harmless but it also could be used to log your sensitive information to unknown websites. Do you wish to proceed? (y/N): ")
    if proceed.lower().strip() != "y":
        print("Aborting execution.")
        sys.exit(0)

cpu = CPU(mem_size=mem_size if mem_size else 256, regs=regs if regs else 200)
cpu.load_program(content)

if not verbose:
    try:
        cpu.run()
    except KeyboardInterrupt:
        pass
    except Exception:
        print(f"An error has occured on line {cpu.get_pc()}. This might be a syntax error on your part or the core might be bugged. Check your syntax, if it is correct, report a bug with your source file for the PVM program and the --verbose output.")
else:
    try:
        cpu.run()
    except KeyboardInterrupt:
        pass
