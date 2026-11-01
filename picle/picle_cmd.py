"""Standard-library command interpreter with PICLE's input and completion hooks."""

import cmd

__all__ = ["Cmd"]

PROMPT = cmd.PROMPT
IDENTCHARS = cmd.IDENTCHARS


class Cmd(cmd.Cmd):
    """Use standard command dispatch with a replaceable interactive reader."""

    def cmdloop(self, intro=None):
        """Repeatedly issue a prompt, accept input, parse an initial prefix
        off the received input, and dispatch to action methods, passing them
        the remainder of the line as argument.

        """

        self.preloop()
        if intro is not None:
            self.intro = intro
        if self.intro:
            self.stdout.write(str(self.intro) + "\n")
        stop = None
        while not stop:
            if self.cmdqueue:
                line = self.cmdqueue.pop(0)
            else:
                if self.use_rawinput:
                    try:
                        line = self._read_interactive_input(self.prompt)
                    except EOFError:
                        line = "EOF"
                else:
                    self.stdout.write(self.prompt)
                    self.stdout.flush()
                    line = self.stdin.readline()
                    if not len(line):
                        line = "EOF"
                    else:
                        line = line.rstrip("\r\n")
            line = self.precmd(line)
            stop = self.onecmd(line)
            stop = self.postcmd(stop, line)
        self.postloop()

    def _read_interactive_input(self, prompt):
        """Read one line from the active interactive input backend."""
        return input(prompt)

    def get_completion_matches(self, text, line, begidx, endidx):
        """Return completion matches for the supplied input context."""
        if begidx > 0:
            cmd, args, foo = self.parseline(line)
            if not cmd:
                compfunc = self.completedefault
            else:
                try:
                    compfunc = getattr(self, "complete_" + cmd)
                except AttributeError:
                    compfunc = self.completedefault
        else:
            compfunc = self.completenames
        return compfunc(text, line, begidx, endidx)
