

```mermaid
graph TD
    subgraph Program Execution
        A["Start: if __name__ == '__main__'"] --> B{"Loop through tests"};
        B --> C["Instantiate regex = BacktrackingRegex(pattern)"];
        C --> D{"Call regex.match(), regex.search(), or regex.findall()"};
        D --> B;
    end

    subgraph "Parsing Phase"
        C --> P1["BacktrackingRegex.__init__(pattern)"];
        P1 --> P2["RegexParser.parse()"];
        P2 --> P3["parse_alternation()"];
        P3 --> P4["parse_sequence()"];
        P4 --> P5["parse_factor()"];
        P5 --> P6["parse_atom()"];

        P6 --> P7{"What is the character?"};
        P7 -- "literal 'a'" --> P8["Return Literal Node"];
        P7 -- "wildcard '.'" --> P9["Return Dot Node"];
        P7 -- "group '('" --> P3_rec[("(Recursively call parse_alternation)")];
        P3_rec --> P10["Return Group Node"];
        P7 -- "class '['" --> P11["parse_char_class()"];
        P11 --> P12["Return CharClass Node"];
        
        P8 --> P5_ret;
        P9 --> P5_ret;
        P10 --> P5_ret;
        P12 --> P5_ret;

        P5_ret{"Followed by quantifier?"};
        P5_ret -- "'*'" --> P13["Return Star Node"];
        P5_ret -- "'+'" --> P14["Return Plus Node"];
        P5_ret -- "'?'" --> P15["Return Question Node"];
        P5_ret -- "no" --> P16["Return Atom Node as is"];

        P13 --> P4;
        P14 --> P4;
        P15 --> P4;
        P16 --> P4;

        P4 -- "end of sequence" --> P3;
        P3 -- "end of alternation" --> P2;
        P2 --> P_End["Return complete AST to BacktrackingRegex"];
        P_End --> D;
    end

    subgraph "Matching Phase"
        D --> M1{"Which method?"};
        M1 -- "match()" --> M2["Loop: for end_pos in ast.match(text, 0)"];
        M2 --> M3{"end_pos == len(text)?"};
        M3 -- "Yes" --> M_Success["Return True"];
        M3 -- "No" --> M2;
        M2 -- "exhausted" --> M_Fail["Return False"];

        M1 -- "search()" --> M4["Loop: for start_pos in text"];
        M4 --> M5["Loop: for end_pos in ast.match(text, start_pos)"];
        M5 --> M_Success_Search["Return (start_pos, end_pos)"];
        M5 -- "exhausted" --> M4;
        M4 -- "exhausted" --> M_Fail_Search["Return None"];

        M1 -- "findall()" --> M6["Loop while pos <= len(text)"];
        M6 --> M7["Loop: for end_pos in ast.match(text, pos)"];
        M7 --> M8["Append match, advance pos"];
        M7 -- "exhausted" --> M9["Advance pos by 1"];
        M8 --> M6;
        M9 --> M6;
        M6 -- "exhausted" --> M_Return_List["Return list of matches"];
    end
    
    subgraph "Core Backtracking Logic: ast.match()"
        M_Node_Match["ast.match() calls node.match() recursively"] --> M_Node_Type{"Node Type?"};
        M_Node_Type -- "Sequence" --> M_Seq["Call _match_sequence(pos, node_idx=0)"];
        M_Seq --> M_Seq_Rec{"For each child node's match..."};
        M_Seq_Rec -- "success" --> M_Seq_Call["_match_sequence(new_pos, node_idx+1)"];
        M_Seq_Call --> M_Seq_Rec;
        M_Seq_Rec -- "failure/exhausted" --> M_BT1["Backtrack"];

        M_Node_Type -- "Alternation" --> M_Alt["Yield from left.match()"];
        M_Alt --> M_Alt2["Yield from right.match()"];
        M_Alt2 --> M_BT2["Backtrack if subsequent patterns fail"];

        M_Node_Type -- "Star" --> M_Star["Yield pos (zero-match case)"];
        M_Star --> M_Star2["Loop: try to match inner node"];
        M_Star2 -- "success" --> M_Star3["Yield new_pos (greedy match)"];
        M_Star3 --> M_Star2;
        M_Star2 -- "failure" --> M_BT3["Backtrack"];

        M_Node_Type -- "Literal/Dot/CharClass" --> M_Lit["Check character at pos"];
        M_Lit -- "match" --> M_Lit_Yield["Yield pos + 1"];
        M_Lit -- "no match" --> M_BT4["Backtrack"];
    end
	
```

### 1. Program Execution (Top-Level Flow)

This is the entry point when the script is run.
* Start at the `if __name__ == '__main__'` block.
* Iterate through a list of predefined test cases.
* For each test case, create an instance of the `BacktrackingRegex` class. This single action kicks off the entire **Parsing Phase**.
* Call one of the matching methods (`.match()`, `.search()`, or `.findall()`) on the instance, which begins the **Matching Phase**.

---

### 2. Parsing Phase (Building the Abstract Syntax Tree)

This phase happens inside the `BacktrackingRegex.__init__` method. Its goal is to convert the raw regex string (e.g., `"(a|b)*c"`) into a tree of `RegexNode` objects (an AST) that the engine can execute.

* The flow starts with `RegexParser.parse()`, which calls `parse_alternation()`.
* The parser uses a method hierarchy that respects regex operator precedence, a technique called "recursive descent":
    1.  `parse_alternation()` looks for `|`. It calls `parse_sequence()` to get the content on either side.
    2.  `parse_sequence()` handles concatenated items (like `abc`). It repeatedly calls `parse_factor()` to get each item in the sequence.
    3.  `parse_factor()` handles quantifiers (`*`, `+`, `?`). It calls `parse_atom()` to get the base item and then wraps it in a `Star`, `Plus`, or `Question` node if a quantifier is present.
    4.  `parse_atom()` is the final step, identifying the most basic parts: a `Literal` character, a `.` `Dot` node, a `[...]` `CharClass` node, or a `(...)` group. If it finds a group, it recursively calls `parse_alternation()` to build the sub-tree for the group's contents.
* This process continues until the entire pattern string is consumed. The final, complete AST is returned and stored in the `BacktrackingRegex` instance.

---

### 3. Matching Phase (Executing the AST)

This phase begins when `match()`, `search()`, or `findall()` is called. These methods are wrappers around the core matching logic.

* **`match()`**: Tries to match the AST starting only at position `0` of the text. It succeeds only if one of the possible matches consumes the *entire* string (i.e., `end_pos == len(text)`).
* **`search()`**: This method is more flexible. It loops through every possible starting position in the text (`for start_pos in text...`) and tries to match the AST from there. It returns immediately with the first successful match it finds.
* **`findall()`**: This method also loops from every position. When it finds a match, it records it and then importantly, advances its starting position to the end of that match to find the next *non-overlapping* one. It continues until the end of the string is reached and returns the complete list of all matches found.

---

### 4. Core Backtracking Logic (The `node.match()` Generators)

This is the heart of the engine, highlighted in the diagram. It's not one method, but the collective behavior of the `match()` methods on every node in the AST. The use of generators (`yield`) is key.

* When a node's `match()` method is called, it `yields` every possible way it can match.
* **Sequence Node**: It tries to match its child nodes one by one. If `child_2` fails, the engine "backtracks". The `Sequence` node's loop then asks `child_1`'s generator for its *next* possible match. If `child_1` can match in a different way (e.g., if it was a `Star` node), the sequence tries again from that new state. If not, the `Sequence` itself fails.
* **Alternation Node**: It first `yields` all possible matches from its left child. If the rest of the regex pattern fails with all of those options, the engine backtracks to the `Alternation` node, which then starts yielding all possible matches from its right child.
* **Star Node (`*`)**: It first `yields` the current position (the "zero-match" case). If that path fails, the engine backtracks, and the `Star` node then tries to match its inner content once, yields that new position, and so on. It offers up every possibility, from zero matches to the maximum possible number of greedy matches.
* **Literal/Dot/CharClass**: These are the simplest. They check the character at the current position. If it matches, they `yield pos + 1`. If not, they yield nothing, causing an immediate backtrack in the node that called them.