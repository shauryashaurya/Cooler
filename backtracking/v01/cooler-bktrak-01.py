# backtracking regular expression engine.
# ...we show how regex parsing and matching works by
# breaking a pattern down into a tree of nodes (an Abstract Syntax Tree or AST)
# and then executing that tree against a text.

class RegexNode:
    # The abstract base class for all nodes in the AST.
    # It establishes a contract: every node must have a `match` method.
    def match(self, text, pos):
        # The `match` method is a generator. It takes the input text and a
        # starting position. It `yields` each possible end position for a
        # successful match. A node might yield multiple positions if it can
        # match in different ways (e.g., the '*' quantifier).
        # If a node cannot match, its `match` generator simply finishes without yielding.
        raise NotImplementedError(
            "Subclasses must implement the match method.")


# --- ATOMIC NODES: Match single characters or positions. ---

class Literal(RegexNode):
    # Matches a single, specific character (e.g., 'a').
    def __init__(self, char):
        self.char = char

    def match(self, text, pos):
        if pos < len(text) and text[pos] == self.char:
            yield pos + 1


class Dot(RegexNode):
    # Matches any single character except a newline (though this engine doesn't check for newlines).
    def match(self, text, pos):
        if pos < len(text):
            yield pos + 1


class CharClass(RegexNode):
    # Matches a single character from a specified set (e.g., '[abc]' or '[^0-9]').
    def __init__(self, chars, negated=False):
        # Using a set provides O(1) average time complexity for lookups.
        self.chars = set(chars)
        self.negated = negated

    def match(self, text, pos):
        if pos < len(text):
            char_in_text = text[pos]
            # (char in set) is a boolean. `negated` is a boolean.
            # `is_match = (char in set) != negated` handles both cases concisely.
            # If not negated: we need `True != False`, so `char in set` must be True.
            # If negated: we need `False != True`, so `char in set` must be False.
            if (char_in_text in self.chars) != self.negated:
                yield pos + 1


class Start(RegexNode):
    # Matches the beginning of the text ('^'). This is a zero-width assertion.
    def match(self, text, pos):
        # This anchor only matches if the current position is 0.
        # It doesn't consume a character, so it yields the same position back.
        if pos == 0:
            yield pos


class End(RegexNode):
    # Matches the end of the text ('$'). This is a zero-width assertion.
    def match(self, text, pos):
        # This anchor only matches if the current position is at the end of the text.
        if pos == len(text):
            yield pos


# --- QUANTIFIER NODES: Modify the behavior of another node. ---

class Star(RegexNode):
    # Matches the preceding node zero or more times ('*'). This is a greedy quantifier.
    def __init__(self, node):
        self.node = node  # The node that '*' applies to.

    def match(self, text, pos):
        # First, yield the current position. This represents the "zero matches"
        # case. The engine will try this path first. If the rest of the regex
        # fails to match, the engine backtracks and asks this generator for another
        # option, which will trigger the loop below.
        yield pos

        # Now, attempt to match the underlying node one or more times.
        current_pos = pos
        while True:
            match_found_in_iteration = False
            # Try to match the node (e.g., the 'a' in 'a*').
            for new_pos in self.node.match(text, current_pos):
                # Success. Yield this new position as a potential end for the match.
                yield new_pos

                # This is the "greedy" part. We immediately accept the first match
                # found and continue trying to match more from that new position.
                current_pos = new_pos
                match_found_in_iteration = True
                break  # Exit the inner `for` loop to continue the `while`.

            # If the inner node could not match at the current position, we're done.
            if not match_found_in_iteration:
                break


class Plus(RegexNode):
    # Matches the preceding node one or more times ('+'). Greedy.
    def __init__(self, node):
        self.node = node

    def match(self, text, pos):
        # Unlike Star, Plus must match at least once. So we don't yield `pos` initially.
        # We must find at least one match to start.
        for first_pos in self.node.match(text, pos):
            # We found one match. This is a valid outcome.
            yield first_pos

            # Now, like Star, we greedily try to find more matches.
            current_pos = first_pos
            while True:
                match_found_in_iteration = False
                for new_pos in self.node.match(text, current_pos):
                    yield new_pos
                    current_pos = new_pos
                    match_found_in_iteration = True
                    break
                if not match_found_in_iteration:
                    break


class Question(RegexNode):
    # Matches the preceding node zero or one time ('?').
    def __init__(self, node):
        self.node = node

    def match(self, text, pos):
        # Yield the zero-match case first.
        yield pos
        # Then, yield the one-match case (if possible). `yield from` passes
        # through any results from the underlying node's match generator.
        yield from self.node.match(text, pos)


# --- COMBINER NODES: Combine other nodes into larger expressions. ---

class Alternation(RegexNode):
    # Handles alternation ('|'), matching either the left or the right side.
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def match(self, text, pos):
        # First, try all possible matches on the left side.
        yield from self.left.match(text, pos)
        # If those all fail and the engine backtracks, then try all
        # possible matches on the right side.
        yield from self.right.match(text, pos)


class Sequence(RegexNode):
    # Matches a sequence of nodes in order (e.g., 'abc').
    def __init__(self, nodes):
        self.nodes = nodes

    def match(self, text, pos):
        # We start a recursive process to match each node in the sequence.
        yield from self._match_sequence(text, pos, 0)

    def _match_sequence(self, text, pos, node_idx):
        # Base case: If we've matched all nodes in the sequence, we're done.
        if node_idx == len(self.nodes):
            yield pos
            return

        # Recursive step: Match the current node.
        current_node = self.nodes[node_idx]
        for new_pos in current_node.match(text, pos):
            # For each successful match of the current node, recursively try to
            # match the *rest* of the sequence starting from the new position.
            # If the recursive call fails (yields nothing), the engine backtracks
            # here, and this `for` loop will try the next available `new_pos`
            # from `current_node.match`, if one exists.
            yield from self._match_sequence(text, new_pos, node_idx + 1)


# --- PARSER: Converts a pattern string into an AST. ---

class RegexParser:
    # A recursive descent parser that builds an AST from a regex pattern string.
    # The grammar precedence is handled by the call order of the parse methods:
    # Alternation ('|') < Sequence ('abc') < Quantifiers (*,+,?) < Atom ('a', '()', '[]')
    def __init__(self, pattern):
        self.pattern = pattern
        self.pos = 0

    def parse(self):
        node = self.parse_alternation()
        if self.pos < len(self.pattern):
            raise ValueError(f"Unexpected character at position {self.pos}")
        return node

    def parse_alternation(self):
        left = self.parse_sequence()
        if self.pos < len(self.pattern) and self.pattern[self.pos] == '|':
            self.pos += 1
            right = self.parse_alternation()
            return Alternation(left, right)
        return left

    def parse_sequence(self):
        nodes = []
        while self.pos < len(self.pattern) and self.pattern[self.pos] not in ')|':
            nodes.append(self.parse_factor())

        if len(nodes) == 1:
            return nodes[0]
        return Sequence(nodes)

    def parse_factor(self):
        # A factor is an atom plus an optional quantifier.
        node = self.parse_atom()
        if self.pos < len(self.pattern):
            char = self.pattern[self.pos]
            if char == '*':
                self.pos += 1
                return Star(node)
            elif char == '+':
                self.pos += 1
                return Plus(node)
            elif char == '?':
                self.pos += 1
                return Question(node)
        return node

    def parse_atom(self):
        # An atom is the smallest unit: a literal, group, class, or anchor.
        if self.pos >= len(self.pattern):
            raise ValueError("Unexpected end of pattern")
        char = self.pattern[self.pos]

        if char == '(':
            self.pos += 1
            # A group can contain any sub-expression.
            node = self.parse_alternation()
            if self.pos >= len(self.pattern) or self.pattern[self.pos] != ')':
                raise ValueError("Missing closing parenthesis")
            self.pos += 1
            return node
        elif char == '[':
            return self.parse_char_class()
        elif char == '.':
            self.pos += 1
            return Dot()
        elif char == '^':
            self.pos += 1
            return Start()
        elif char == '$':
            self.pos += 1
            return End()
        elif char == '\\':
            self.pos += 1  # Consume '\'
            if self.pos >= len(self.pattern):
                raise ValueError("Pattern ends with an escape character")
            escaped_char = self.pattern[self.pos]
            self.pos += 1
            return Literal(escaped_char)
        elif char in '*+?|()[]^$\\':
            raise ValueError(
                f"Unescaped special character '{char}' at position {self.pos}")
        else:
            self.pos += 1
            return Literal(char)

    def parse_char_class(self):
        self.pos += 1  # Consume '['
        negated = self.pattern[self.pos] == '^'
        if negated:
            self.pos += 1

        chars = []
        while self.pos < len(self.pattern) and self.pattern[self.pos] != ']':
            char = self.pattern[self.pos]
            if char == '\\':
                self.pos += 1
                if self.pos >= len(self.pattern):
                    raise ValueError(
                        "Pattern ends with an escape character in char class")
                chars.append(self.pattern[self.pos])
            else:
                chars.append(char)
            self.pos += 1

        if self.pos >= len(self.pattern):
            raise ValueError("Unclosed character class")
        self.pos += 1  # Consume ']'
        return CharClass(chars, negated)


# --- The Public-Facing Engine Class ---

class BacktrackingRegex:
    # The main class that users interact with. It orchestrates the parsing and matching.
    def __init__(self, pattern):
        self.pattern = pattern
        self.ast = RegexParser(pattern).parse()

    def match(self, text):
        # Checks if the entire text matches the pattern exactly.
        for end_pos in self.ast.match(text, 0):
            if end_pos == len(text):
                return True
        return False

    def search(self, text):
        # Finds the first occurrence of the pattern anywhere in the text.
        for start_pos in range(len(text) + 1):
            for end_pos in self.ast.match(text, start_pos):
                return (start_pos, end_pos)  # Return the first success.
        return None

    def findall(self, text):
        # Finds all non-overlapping matches.
        matches = []
        pos = 0
        while pos <= len(text):
            found_match = False
            for end_pos in self.ast.match(text, pos):
                matches.append((pos, end_pos))
                # Advance position to the end of the match to find the next
                # non-overlapping one. The `max(pos + 1, ...)` prevents
                # infinite loops on zero-length matches (like from 'a*').
                pos = max(pos + 1, end_pos)
                found_match = True
                break  # Found the first match at this position, move on.
            if not found_match:
                pos += 1
        return matches


if __name__ == "__main__":
    # --- Test Cases ---
    # Each tuple: (pattern, text, expected_result_for_full_match)
    tests = [
        # Basic literal sequence. Must match exactly.
        ("abc", "abc", True),
        # The '.' wildcard should match any single character.
        ("a.c", "abc", True),
        ("a.c", "axc", True),
        # '.' requires a character, so it fails if none is present.
        ("a.c", "ac", False),
        # '*' (Star) quantifier: zero or more matches.
        ("a*", "aaaa", True),   # Matches multiple 'a's.
        ("a*", "", True),       # Matches an empty string (zero 'a's).
        # '+' (Plus) quantifier: one or more matches.
        ("a+", "aaaa", True),   # Matches multiple 'a's.
        # Fails on empty string (requires at least one).
        ("a+", "", False),
        # '?' (Question) quantifier: zero or one time.
        ("a?", "a", True),      # Matches one 'a'.
        ("a?", "", True),       # Matches zero 'a's.
        ("a?b", "b", True),     # 'a?' matches zero 'a's, then 'b' matches 'b'.
        # '|' (Alternation).
        ("a|b", "a", True),     # Matches left side.
        ("a|b", "b", True),     # Matches right side.
        ("a|b", "c", False),    # Matches neither.
        # '()' (Grouping).
        ("(ab)+", "ababab", True),  # The group 'ab' is matched 3 times by '+'.
        ("(ab)+", "ab", True),
        # The group 'ab' is not followed by another 'ab'.
        ("(ab)+", "abc", False),
        # '[]' (Character Class).
        ("[abc]", "b", True),      # 'b' is in the set.
        # '[^]' (Negated Character Class).
        ("[^abc]", "d", True),     # 'd' is not in the set.
        ("[^abc]", "a", False),    # 'a' is in the set, so the negation fails.
        # '^' (Start Anchor).
        ("^abc", "abc", True),     # 'abc' is at the start of the text.
        ("^abc", "xabc", False),   # 'abc' is not at the start.
        # '$' (End Anchor).
        ("abc$", "abc", True),     # 'abc' is at the end of the text.
        ("abc$", "abcd", False),   # 'abc' is not at the end.
        # Classic backtracking example: 'a*b'.
        # The 'a*' will greedily match all 'a's, leaving nothing for 'b' to match.
        # The engine must then backtrack, forcing 'a*' to give up one 'a' at a time
        # until the 'b' can match.
        ("a*b", "aaab", True),
        ("a*b", "b", True),        # 'a*' matches zero times.
    ]

    print("--- Running Full Match Tests ---")
    for pattern, text, expected in tests:
        regex = BacktrackingRegex(pattern)
        result = regex.match(text)
        status = 'PASSED' if result == expected else 'FAILED'
        print(
            f"Pattern: {pattern:<8} Text: {text:<8} Expected: {str(expected):<5} Got: {str(result):<5} {status}")

    print("\n--- Running Search and Findall Tests ---")
    # Search finds the first occurrence. 'a+b' will find 'aaab'.
    regex_search = BacktrackingRegex("a+b")
    print(f"Search 'a+b' in 'xaaabyz': {regex_search.search('xaaabyz')}")

    # Findall finds all non-overlapping occurrences.
    regex_findall = BacktrackingRegex("a+")
    print(
        f"Find all 'a+' in 'aabaaacaa': {regex_findall.findall('aabaaacaa')}")
    # This tests the zero-length match edge case. 'z*' can match an empty string
    # at every position. The `max(pos + 1, ...)` logic ensures we advance.
    print(f"Find all 'z*' in 'abc': {regex_findall.findall('abc')}")
