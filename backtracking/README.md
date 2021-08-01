# CooleRE - backtracking.

A regular expressions engine written in Python.
This variant is built using the backtracking algorithm.
The algorithm is also called Recursive Descent Parser.

A sort of straight forward approach:
1. Lexer breaks string into Tokens
1. Build a tree structure with operations as nodes and operands as leaves.
  1. Operands could be operations themselves, so this is recursive
1. Evaluate the tree 

Yeah. I know.
