from pprint import *

# Classe per il parsing dell'input da file
class ReadAttributes:

    def __init__(self, path='Input'):

        with open(path, encoding="utf-8") as f:
            self.input_lines = f.readlines()

        self.input_lines = [x.strip() for x in self.input_lines
                            if x.strip() != '' and x.strip()[0] != '#']

        self.title = self.input_lines[0].split(':')[1].strip()
        self.input_lines.pop(0)

        self.head_conc = self.input_lines[0].split(':')[1].strip()
        self.input_lines.pop(0)

        self.mod_conc = self.input_lines[0].split(':')[1].strip()
        self.input_lines.pop(0)

        self.tipical_attrs = []
        self.attrs = []

        for l in self.input_lines:
            l = [k.strip() for k in l.split(',')]

            if len(l) == 3 and l[0][0] == 'T':
                self.tipical_attrs.append((
                    l[1], float(l[2]),
                    (True if l[0][2:-1] == 'head' else False)
                ))

            if len(l) == 2:
                self.attrs.append((
                    l[1],
                    (True if l[0] == 'head' else False)
                ))

        # --- FIX: gestisci casi senza "Result:" ---
        if self.input_lines and self.input_lines[-1].startswith("Result:"):
            self.result = self.input_lines[-1].split(':', 1)[1].strip()
        else:
            self.result = "[]"
