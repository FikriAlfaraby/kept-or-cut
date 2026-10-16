# kept-or-cut

**Does the error line a coding agent needs survive token compression?**

Token-compression tools for coding agents (rtk, caveman, headroom; 75k to 113k GitHub stars each) shrink what
an agent reads from the shell. Their claims are averages: "60–90% fewer tokens", "same answers". An agent fixing a
failing run needs a few specific lines: the failing test's name, the error message, the file and line.

This study plants 16 real bugs in real repositories, runs each failing command the way an agent would, and
checks which needed lines each tool keeps. The predictions were committed before any tool ran on the cases:
[PREDICTIONS.md](PREDICTIONS.md). Results follow.
