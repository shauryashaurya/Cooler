# backtracking regular expression engine.
# ...we show how regex parsing and matching works by
# breaking a pattern down into a tree of nodes (an Abstract Syntax Tree or AST)
# and then executing that tree against a text.

import os
from ast_tracer import persist_ast, visualize_ast, ASTTracer


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


class LazyStar(RegexNode):
    def __init__(self, node):
        self.node = node

    def match(self, text, pos):
        # non-greedy: first zero repeats
        yield pos
        # then try consuming one and recurse
        for mid in self.node.match(text, pos):
            for end in self.match(text, mid):
                yield end


class LazyPlus(RegexNode):
    def __init__(self, node):
        self.node = node

    def match(self, text, pos):
        # must match one first
        for mid in self.node.match(text, pos):
            yield mid
            # then behave like LazyStar on the rest
            for end in LazyStar(self.node).match(text, mid):
                yield end


class LazyQuestion(RegexNode):
    def __init__(self, node):
        self.node = node

    def match(self, text, pos):
        # zero or one, but zero first
        yield pos
        for end in self.node.match(text, pos):
            yield end


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


class NonCaptureGroup(RegexNode):
    def __init__(self, inner):
        self.inner = inner

    def match(self, text, pos):
        # just delegate to inner
        yield from self.inner.match(text, pos)


class Lookahead(RegexNode):
    def __init__(self, inner, positive=True):
        self.inner = inner
        self.positive = positive

    def match(self, text, pos):
        ok = any(self.inner.match(text, pos))
        if ok is self.positive:
            yield pos


class Lookbehind(RegexNode):
    def __init__(self, inner, positive=True):
        self.inner = inner
        self.positive = positive

    def match(self, text, pos):
        # try all possible start points so that inner.match(start)->pos
        found = False
        for start in range(0, pos+1):
            for end in self.inner.match(text, start):
                if end == pos:
                    found = True
                    break
            if found:
                break
        if found is self.positive:
            yield pos


# --- PARSER: Converts a pattern string into an AST. ---

class RegexParser:
    # A recursive descent parser that builds an AST from a regex pattern string.
    # The grammar precedence is handled by the call order of the parse methods:
    # Alternation ('|') < Sequence ('abc') < Quantifiers (*,+,?) < Atom ('a', '()', '[]')
    def __init__(self, pattern):
        self.pattern = pattern
        self.pos = 0

    ##
    def parse(self):
        node = self.parse_alternation()
        if self.pos < len(self.pattern):
            raise ValueError(f"Unexpected character at position {self.pos}")
        return node

    ##
    def parse_alternation(self):
        left = self.parse_sequence()
        if self.pos < len(self.pattern) and self.pattern[self.pos] == '|':
            self.pos += 1
            right = self.parse_alternation()
            return Alternation(left, right)
        return left

    ##
    def parse_sequence(self):
        nodes = []
        while self.pos < len(self.pattern) and self.pattern[self.pos] not in ')|':
            nodes.append(self.parse_factor())

        if len(nodes) == 1:
            return nodes[0]
        return Sequence(nodes)

    ##
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

    ##
    def parse_atom(self):
        if self.pos >= len(self.pattern):
            raise ValueError("Unexpected end of pattern")
        c = self.pattern[self.pos]

        # GROUPS & LOOKAROUNDS
        if c == '(':
            self.pos += 1  # consume '('

            # detect lookaround or non-capturing
            if self.pos+1 < len(self.pattern) and self.pattern[self.pos] == '?':
                op = self.pattern[self.pos+1]
                # non-capturing
                if op == ':':
                    self.pos += 2
                    node = self.parse_alternation()
                    if self.pattern[self.pos] != ')':
                        raise ValueError("Unclosed group")
                    self.pos += 1
                    return NonCaptureGroup(node)

                # positive lookahead
                if op == '=':
                    self.pos += 2
                    node = self.parse_alternation()
                    if self.pattern[self.pos] != ')':
                        raise ValueError("Unclosed lookahead")
                    self.pos += 1
                    return Lookahead(node, positive=True)

                # negative lookahead
                if op == '!':
                    self.pos += 2
                    node = self.parse_alternation()
                    if self.pattern[self.pos] != ')':
                        raise ValueError("Unclosed neg lookahead")
                    self.pos += 1
                    return Lookahead(node, positive=False)

                # positive lookbehind
                if self.pattern[self.pos+1:self.pos+3] == '<=':
                    self.pos += 3
                    node = self.parse_alternation()
                    if self.pattern[self.pos] != ')':
                        raise ValueError("Unclosed lookbehind")
                    self.pos += 1
                    return Lookbehind(node, positive=True)

                # negative lookbehind
                if self.pattern[self.pos+1:self.pos+3] == '<!':
                    self.pos += 3
                    node = self.parse_alternation()
                    if self.pattern[self.pos] != ')':
                        raise ValueError("Unclosed neg lookbehind")
                    self.pos += 1
                    return Lookbehind(node, positive=False)

            # plain capturing group
            node = self.parse_alternation()
            if self.pos >= len(self.pattern) or self.pattern[self.pos] != ')':
                raise ValueError("Missing closing parenthesis")
            self.pos += 1
            return node

        # CHARACTER CLASS
        elif c == '[':
            return self.parse_char_class()

        # WILDCARD DOT
        elif c == '.':
            self.pos += 1
            return Dot()

        # ANCHORS
        elif c == '^':
            self.pos += 1
            return Start()
        elif c == '$':
            self.pos += 1
            return End()

        # ESCAPE SEQUENCE
        elif c == '\\':
            self.pos += 1
            if self.pos >= len(self.pattern):
                raise ValueError("Pattern ends with '\\\\'")
            lit = self.pattern[self.pos]
            self.pos += 1
            return Literal(lit)

        # UNESCAPED SPECIALS
        elif c in '*+?|)[]^$':
            raise ValueError(
                f"Unescaped special character '{c}' at position {self.pos}")

        # LITERAL
        else:
            self.pos += 1
            return Literal(c)

    ##
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
    if not os.path.exists("./ast"):
        os.mkdir("./ast")

    # --- Match tests ---
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
        ("a(b|c)*d", "abcbcd", True),  # nested alternation + star
        ("[abc]+d?e", "abcee", True),  # char class + plus + optional + literal
        ("ab?c+", "accc", True),       # optional + plus
        ("(a|bc)d+", "bcd", True),     # alternation grouping + plus
        ("[ab][cd]*", "accc", True),   # char class sequence + star
        ("^a(bc)?d$", "ad", True),     # anchors + optional group
        ("(ab|cd|ef)+", "abcdefab", True),  # multiple alternations + plus
        ("[xy]?z+", "zzzzz", True),    # optional class + plus literal
        ("([ab][cd])+e?", "acac", True),  # sequence class + plus + optional
        ("a((b|c)d)+e", "abcdcde", True),  # nested group + plus
        ("(ab?c)*", "abcabc", True),   # optional inside star
        ("([abc]|d)+", "abcdabc", True),  # alternation class + literal + plus
        ("a?b?c?", "abc", True),       # multiple optionals
        ("(a|b)?c+", "cc", True),      # optional group + plus
        ("[01]+1?", "01011", True),   # class + plus + optional
        ("(ab|a)b", "abb", True),     # ambiguous alternation
        ("((a|b)c?)+d", "acd", True),  # nested quantifiers + grouping
        ("(x|y)*(z|w)?", "xyxz", True),  # star + optional on groups
        ("abc|def", "def", True),      # top-level alternation
        ("(a|b)(c|d)(e|f)", "bdf", True),  # concatenated alternations
        ("a+b+c+", "aaabbbccc", True),   # successive plus quantifiers
        ("(ab)*c?", "abab", True),    # group star + optional
        ("[abc]?[def]*g+", "defgg", True),  # optional + star + plus + literal
        ("(a(b(c)d)e)f", "abcdef", True),  # deeply nested groups
        ("[^ab]c+", "dcc", True),     # negated class + plus
        # Negative test cases
        ("a+b", "ab", True),           # 'a+' requires one or more 'a', then 'b'
        ("a+b", "b", False),          # no leading 'a'
        ("^hello$", "hello world", False),  # anchor mismatch
        ("colou?r", "color", True),   # optional 'u'
        ("colou?r", "colour", True),  # optional 'u'
        ("colou?r", "colouur", False),  # extra 'u'
        # vowel-consonant-vowel
        (".*[aeiou][^aeiou][aeiou].*", "Douglas Adams", True),
        # anchors + sequence
        ("^[Tt]ime.*illusion.*", "Time is an illusion. Lunchtime doubly so.", True),
        (".*lunchtime.*", "Time is an illusion. Lunchtime doubly so.",
         True),       # substring
        # alternation
        (".*(dead|die).*", "No one is actually dead until the ripples they cause in the world die away.", True),
        (".*story.*life.*", "If you don't turn your life into a story, you just become a part of someone else's story.", True),  # sequence
        # optional group
        (".*cats? were.*", "In ancient times cats were worshipped as gods; they have not forgotten this.", True),
        # optional quantifier
        (".*gods?;.*", "In ancient times cats were worshipped as gods; they have not forgotten this.", True),
        (".*hammers and screwdrivers.*", "The reason that cliches become cliches is that they are the hammers and screwdrivers in the toolbox of communication.", True),  # literal phrase
        (".*toolbox.*", "The reason that cliches become cliches is that they are the hammers and screwdrivers in the toolbox of communication.",
         True),               # substring
        # char class + plus
        (".*[A-Za-z]+ing.*", "The trouble with having an open mind is that people will insist on coming along and trying to put things in it.", True),
        # substring
        (".*being.*", "Evil begins when you begin to treat people as things.", True),
        # substring
        (".*experience.*", "Wisdom comes from experience. Experience is often a result of lack of wisdom.", True),
        # substring
        (".*lack.*", "Wisdom comes from experience. Experience is often a result of lack of wisdom.", True),
        (".*knowledge.*", "They say a little knowledge is a dangerous thing, but it’s not one half so bad as a lot of ignorance.", True),  # substring
        (".*ignorance.*", "They say a little knowledge is a dangerous thing, but it’s not one half so bad as a lot of ignorance.", True),  # substring
        # composite
        (".*dead.*ripples.*",
         "No one is actually dead until the ripples they cause in the world die away.", True),
        # anchor + char class
        ("^[Nn]ight", "Night doesn’t seem so bad once you’re accustomed to it.", True),
    ]

    print("--- Running Full Match Tests ---")
    counter = 0

    # for pattern, text, expected in tests:
    #     regex = BacktrackingRegex(pattern)

    #     counter += 1
    #     # Dump the AST out to JSON:
    #     persist_ast(regex.ast, "./ast/match_"+str(counter)+"_regex_ast.json")

    #     result = regex.match(text)
    #     status = 'PASSED' if result == expected else 'FAILED'

    #     print(
    #         f"Pattern: {pattern:<8} Text: {text:<8} Expected: {str(expected):<5} Got: {str(result):<5} {status}")

    #     # Render a PNG (or SVG) of the AST:
    #     png_path = visualize_ast(
    #         regex.ast, output_path="./ast/match_"+str(counter)+"regex_ast_diagram")

    # print("\n--- Running Search and Findall Tests ---")

    # ---------Search and Find All ------------
    # # Search finds the first occurrence. 'a+b' will find 'aaab'.
    # regex_search = BacktrackingRegex("a+b")
    # print(f"Search 'a+b' in 'xaaabyz': {regex_search.search('xaaabyz')}")
    # TESTING SEARCH -----------
    SEARCH_TESTS = [
        # (pattern, text, expected_bool)
        (r"a+b", "aaab", True),
        (r"a+b", "b", False),
        (r"\bthe\b", "In the beginning", True),
        (r"\bThe\b", "in the Beginning", False),
        # (?: … ) (the “non-capturing” group syntax)
        (r"(?:foo|bar)", "xxbarxx", True),
        (r"(foo|bar)", "xxbarxx", True),
        (r"(foo|bar)", "xxbazxx", False),
        (r".+'s", "Hitchhiker's", True),
        (r".+'s", "Hitchhikers", False),
        (r"colou?r", "color", True),
        (r"colou?r", "colour", True),
        (r"colou?r", "colouur", False),
        (r"\d{4}", "Year 2025 AD", True),
        (r"\d{4}", "No digits here", False),
        (r"\b\w{5}\b", "hello world", True),
        (r"\b\w{5}\b", "hi all", False),
        (r"[A-Z][a-z]+", "Douglas Adams", True),
        (r"[A-Z][a-z]+", "douglas", False),
        (r"(Lunchtime|lunchtime)", "Lunchtime doubly", True),
        (r"(Lunchtime|lunchtime)", "lunchtime doubly", True),
        (r"(Lunchtime|lunchtime)", "afternoon", False),
        (r"^Night", "Night doesn’t...", True),
        (r"^Night", "At nightfall...", False),
        (r"foo.*bar", "foo123bar", True),
        (r"foo.*bar", "foobar", True),
        (r"foo.*bar", "fooBAZ", False),
        (r"([^aeiou]{2})", "rhythm", True),
        (r"[A-Z]{2,}", "NASA", True),
        (r"[A-Z]{2,}", "Nasa", False),
        (r"\w+-\w+", "back-tract", True),
        (r"\w+-\w+", "no-dash", True),
        (r"\w+-\w+", "nodash", False),
        (r"a.*?b", "axxb", True),
        (r"a.*b", "axxb", True),
        (r"(dog|cat)s?", "dogs and cats", True),
        (r"(dog|cat)s?", "dog and cat", True),
        (r"(dog|cat)s?", "bird", False),
        (r"(ha){3}", "hahaha", True),
        (r"(ha){3}", "haha", False),
        (r"\d{3}-\d{2}-\d{4}", "123-45-6789", True),
        (r"\d{3}-\d{2}-\d{4}", "12-345-6789", False),
        (r"[A-Za-z0-9]+@[A-Za-z]+\.[A-Za-z]{2,4}", "user@example.com", True),
        (r"[A-Za-z0-9]+@[A-Za-z]+\.[A-Za-z]{2,4}", "userexample.com", False),
        (r"https?://[^\s]+", "Visit http://example.com now", True),
        (r"https?://[^\s]+", "Secure https://site.org", True),
        (r"https?://[^\s]+", "no protocol site.org", False),
        (r"\b[A-Fa-f0-9]{6}\b", "Color FF5733 is nice", True),
        (r"\b[A-Fa-f0-9]{6}\b", "Color 123ABZ is invalid", False),
        (r"\d{1,2}:\d{2}", "Time 09:45", True),
        (r"\d{1,2}:\d{2}", "At 7:5", False),
        (r"([01]?\d|2[0-3]):[0-5]\d", "23:59", True),
        (r"(?:[^aeiou]{2})", "rhythm", True),
        (r"[A-Z]{2,}", "NASA", True),
        (r"[A-Z]{2,}", "Nasa", False),
        (r"\w+-\w+", "back-tract", True),
        (r"\w+-\w+", "no-dash", True),
        (r"\w+-\w+", "nodash", False),
        (r"a.*?b", "axxb", True),
        (r"a.*b", "axxb", True),
        (r"(dog|cat)s?", "dogs and cats", True),
        (r"(dog|cat)s?", "dog and cat", True),
        (r"(dog|cat)s?", "bird", False),
        (r"(ha){3}", "hahaha", True),
        (r"(ha){3}", "haha", False),
        (r"\d{3}-\d{2}-\d{4}", "123-45-6789", True),
        (r"\d{3}-\d{2}-\d{4}", "12-345-6789", False),
        (r"[A-Za-z0-9]+@[A-Za-z]+\.[A-Za-z]{2,4}", "user@example.com", True),
        (r"[A-Za-z0-9]+@[A-Za-z]+\.[A-Za-z]{2,4}", "userexample.com", False),
        (r"https?://[^\s]+", "Visit http://example.com now", True),
        (r"https?://[^\s]+", "Secure https://site.org", True),
        (r"https?://[^\s]+", "no protocol site.org", False),
        (r"\b[A-Fa-f0-9]{6}\b", "Color FF5733 is nice", True),
        (r"\b[A-Fa-f0-9]{6}\b", "Color 123ABZ is invalid", False),
        (r"\d{1,2}:\d{2}", "Time 09:45", True),
        (r"\d{1,2}:\d{2}", "At 7:5", False),
        (r"([01]?\d|2[0-3]):[0-5]\d", "23:59", True),
    ]

    counter = 0

    for pattern, text, expected in SEARCH_TESTS:
        counter += 1

        print(f"[SEARCH] {pattern!r} in {text!r} → expected={expected}")
        regex = BacktrackingRegex(pattern)

        # build & snapshot AST
        ast = regex.ast
        persist_ast(ast, "./ast/search_"+str(counter)+"_regex_ast.json")
        visualize_ast(ast, output_path="./ast/search_" +
                      str(counter)+"_regex_ast")

        # # trace & run search()
        # tracer = ASTTracer()
        # tracer.instrument(ast)
        found = regex.search(text) is not None
        # tracer.restore()

        print("  → result:", found, "| PASS" if found == expected else "FAIL")
        # for evt in tracer.get_trace():
        #     print("    ", evt)
        print()

    # Testing FIND ALL ---------------
    # Findall finds all non-overlapping occurrences.
    regex_findall = BacktrackingRegex("a+")
    print(
        f"Find all 'a+' in 'aabaaacaa': {regex_findall.findall('aabaaacaa')}")
    # This tests the zero-length match edge case. 'z*' can match an empty string
    # at every position. The `max(pos + 1, ...)` logic ensures we advance.
    print(f"Find all 'z*' in 'abc': {regex_findall.findall('abc')}")

    # --- FIND_ALL TESTS ---
    FINDALL_TESTS = [
        # (pattern, text, expected_count)
        (r"\b\w+\b", "One two three", 3),
        (r"\d+", "ID: 123, 456; 789", 3),
        (r"[aeiou]", "Douglas Adams", 5),
        (r"[A-Z]", "Hitchhiker's Guide", 2),
        (r"[xy]{2,}", "xyxyz", 2),
        (r"so+", "soooo... so so", 3),
        (r"lun?ch", "lunch LunCh lch", 2),
        (r"colou?r", "color colour colouur", 2),
        (r"don't", "Don't panic, don't worry", 2),
        (r"\bthe\b", "the The tHe THE the", 2),
        (r"\w+ing", "running jogging walking", 3),
        (r"^Night", "Night Nightfall Night", 2),
        (r"\.", "Mr. Adams. Dr. Who.", 3),
        (r"[,.!?]", "Hello, world! Goodbye?", 3),
        (r"foo", "foofoo foo foo", 4),
        (r"bar", "bar baz barbar", 3),
        (r"[A-Za-z]{4}", "This is four char", 2),
        (r"\b\w{1,3}\b", "a an the of", 3),
        (r"h.{2}p", "hop hip hep hxp", 4),
        (r"(?:ha){2}", "hahaha haha ha", 2),
        (r"[^aeiou\s]+", "crypt rhythm myth", 3),
        (r"\d{2}", "12 3456 78 9", 3),
        (r"\b\w+['’]\w+\b", "don't won't it's", 3),
        (r"\b\w+:\b", "key:value bad:case", 2),
        (r"\b\w+ly\b", "quickly slowly surely", 3),
        (r"\w{4}", "This code test", 3),
        (r"\b\w*[aeiou]{2}\w*\b", "cooperation beautiful queue", 3),
        (r"\d+", "Phone: +123 456 7890", 3),
        (r"[A-Z][a-z]+", "Home in CamelCase", 3),
        (r"[A-Z][a-z]+", "lowercase uppercase", 1),
        (r"colou?r", "color colour colouur color", 3),
        (r"(?:Mr|Mrs)\.", "Mr. and Mrs. Smith", 2),
        (r"(?:Mr|Mrs)\.", "No titles here", 0),
        (r"(na){2}", "banana banana", 2),
        (r"cat|dog", "catdogdogcat", 4),
        (r"\b[a-z]{3}\b", "one two six seven", 3),
        (r"[^\w\s]+", "Hello, world!???", 3),
        (r"\b\w+ing\b", "sing singing bringing string", 3),
        (r"\b\w{5}\b", "large small tiny short", 3),
        (r"\d{2,4}", "1 12 123 1234 12345", 3),
        (r"(ha)+", "hahaha haha ha", 3),
        (r"\b\w+\b", "word1 word2", 2),
        (r"[A-Z]{2}", "AA BB C", 2),
        (r"[A-Z]{2}", "A B", 0),
        (r"\.\.\.", "Wait... Really...", 2),
        (r'"[^"\r\n]+"', 'She said "Hi" and left', 1),
        (r"-{2,}", "dash-- dash--- dash-", 2),
        (r"\b\w+['’]\w+\b", "don't won't it's", 3),
        (r"\b\w+:\b", "key:value bad:case", 2),
        (r"\b\w+ly\b", "quickly slowly surely", 3),
        (r"(?:foo|bar)", "foofoobarbarbar", 4),
        (r"foo(?=bar)", "foobar foofoobarbar foo", 3),
        (r"foo(?!bar)", "foobaz fooqux foobar", 2),
        (r"(?<=foo)bar", "foobar foo barfoobar", 2),
        (r"(?<!foo)bar", "bar foo barbar", 2),
        (r"(?<=\d)\D", "1a2b3c", 3),
        (r"(?=\d)", "a1b2c3", 3),
        (r"\b(?:a|b)c\b", "ac bc dc ac bc", 4),
        (r"(?<=\s)\w+", " one two three ", 3),
        (r"\w+(?=\.)", "Mr. Smith. Dr. Who.", 3),
        (r"(?<!\.)\w+(?<!\.)", "hello.world test...", 1),
        (r"(?:ha){2,}", "hahaha haha hah", 2),
        (r"(?<=un)matched", "unmatched unmatched", 2),
        (r"(?<!un)matched", "unmatched unmatched", 1),
        (r"(?<=\b)\w{3}\b", "one two three four", 3),
        (r"(?<!\b)\w{3}\b", "one two three four", 0),
        (r"(?:colou?r)", "color colour colouur color", 3),
        (r"(?=\b\w{5}\b)", "hello world there", 1),
        (r"(?<=\b\w{5}\b)", "hello world there", 1),
        (r"(?<!\w)\w{4}(?!\w)", "test code hard here", 3),
        (r"(?<=\b)\d{2}(?=\b)", "12 3456 78 9 01", 3),
        (r"(?<=\D)\d+(?=\D)", "a123b456c7", 2),
        (r"(?<!\d)\d+(?!\d)", "a123b456c7", 2),
        (r"(?<=\b)(?:dog|cat)(?=\b)", "dog cat pig dog", 3),
        (r"(?<=\b)(?!pig)\w+\b", "dog pig cat", 2),
        (r"(?<=a)b+(?=c)", "abbbc abc", 2),
        (r"(?<!a)b+(?!c)", "bb bc bb", 1),
        (r"(?:ab){2}", "abab ab ababab", 2),
        (r"(?=ab)", "ababab", 3),
        (r"(?<=ab)", "ababab", 3),
        (r"(?:a|b)+c", "aababc", 1),
        (r"(?<=a)b+c", "abbbc abc", 1),
        (r"(?<!x)x+y", "xxy yy xyy", 2),
        (r"(?:x|y){1,3}", "xyx yyy xxxx", 3),
        (r"(?<=\.)\w+", "end. start middle.", 2),
        (r"(?<!\.)\w+", "end. start middle.", 2),
        (r"\b(?=\w{4}\b)\w+\b", "four five six seven", 1),
        (r"\b(?<=\w{4}\b)\w+\b", "four five six seven", 1),
        (r"(?<=un)happy", "unhappy happy", 1),
    ]

    for pattern, text, expected_count in FINDALL_TESTS:
        print(f"[FIND_ALL] {pattern!r} in {text!r} → expect {expected_count}")
        regex = BacktrackingRegex(pattern)

        # build & snapshot AST
        ast = build_ast(pattern)
        persist_ast(ast, f"findall_ast_{pattern}.json")
        visualize_ast(ast, output_path=f"findall_ast_{pattern}")

        # # trace & run find_all()
        # tracer = ASTTracer(); tracer.instrument(ast)
        # all_matches = regex.find_all(text)
        # tracer.restore()

        print("  → found:", len(all_matches), "| PASS" if len(
            all_matches) == expected_count else "FAIL")
        # for evt in tracer.get_trace(): print("    ", evt)
        print()
