# let's get this done... minor, major regex processing engine
# just like we do abstract syntax trees
# toy version
# will imrprove (probably) as we go along...

class RegexNode:
    # AST: every node must have a `match` method.
    def match(self, text, pos):
        raise NotImplementedError(
            "Subclasses must implement the match method.")


class Literal(RegexNode):
    def __init__(self, char):
        self.char = char

    def match(self, text, pos):
        if pos < len(text) and text[pos] == self.char:
            yield pos + 1


class Dot(RegexNode):
    def match(self, text, pos):
        if pos < len(text):
            yield pos + 1


class CharClass(RegexNode):
    def __init__(self, chars, negated=False):
        self.chars = set(chars)
        self.negated = negated

    def match(self, text, pos):
        if pos < len(text):
            char_in_text = text[pos]
            if (char_in_text in self.chars) != self.negated:
                yield pos + 1


class Start(RegexNode):
    def match(self, text, pos):

        if pos == 0:
            yield pos


class End(RegexNode):
    def match(self, text, pos):
        if pos == len(text):
            yield pos


class Star(RegexNode):
    # Match the preceding node zero or more times ('*').Greedy quantifier.
    def __init__(self, node):
        self.node = node  # The node that '*' applies to.

    def match(self, text, pos):

        yield pos

        current_pos = pos
        while True:
            match_found_in_iteration = False
            for new_pos in self.node.match(text, current_pos):
                yield new_pos

                current_pos = new_pos
                match_found_in_iteration = True
                break

            if not match_found_in_iteration:
                break


class Plus(RegexNode):
    def __init__(self, node):
        self.node = node

    def match(self, text, pos):

        for first_pos in self.node.match(text, pos):
            yield first_pos

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
    def __init__(self, node):
        self.node = node

    def match(self, text, pos):
        yield pos
        yield from self.node.match(text, pos)


class Alternation(RegexNode):
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def match(self, text, pos):
        yield from self.left.match(text, pos)
        yield from self.right.match(text, pos)


class Sequence(RegexNode):
    def __init__(self, nodes):
        self.nodes = nodes

    def match(self, text, pos):
        yield from self._match_sequence(text, pos, 0)

    def _match_sequence(self, text, pos, node_idx):
        if node_idx == len(self.nodes):
            yield pos
            return

        current_node = self.nodes[node_idx]
        for new_pos in current_node.match(text, pos):

            yield from self._match_sequence(text, new_pos, node_idx + 1)


class RegexParser:

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


class BacktrackingRegex:
    def __init__(self, pattern):
        self.pattern = pattern
        self.ast = RegexParser(pattern).parse()

    def match(self, text):
        # if the entire text matches the pattern exactly.
        for end_pos in self.ast.match(text, 0):
            if end_pos == len(text):
                return True
        return False

    def search(self, text):
        for start_pos in range(len(text) + 1):
            for end_pos in self.ast.match(text, start_pos):
                return (start_pos, end_pos)
        return None

    def findall(self, text):
        matches = []
        pos = 0
        while pos <= len(text):
            found_match = False
            for end_pos in self.ast.match(text, pos):
                matches.append((pos, end_pos))

                pos = max(pos + 1, end_pos)
                found_match = True
                break
            if not found_match:
                pos += 1
        return matches


# testing.
if __name__ == "__main__":

    tests = [
        ("abc", "abc", True),
        ("a.c", "abc", True),
        ("a.c", "axc", True),
        ("a.c", "ac", False),
        ("a*", "aaaa", True),
        ("a*", "", True),
        ("a+", "aaaa", True),
        ("a+", "", False),
        ("a?", "a", True),
        ("a?", "", True),
        ("a?b", "b", True),
        ("a|b", "a", True),
        ("a|b", "b", True),
        ("a|b", "c", False),
        ("(ab)+", "ababab", True),
        ("(ab)+", "abc", False),
        ("[abc]", "b", True),
        ("[^abc]", "d", True),
        ("[^abc]", "a", False),
        ("^abc", "abc", True),
        ("^abc", "xabc", False),
        ("abc$", "abc", True),
        ("abc$", "abcd", False),
        ("a\\.c", "a.c", True),
        ("a\\.c", "abc", False),
        ("\\[a\\]", "[a]", True),
        ("a*b", "aaab", True),
        ("a*b", "b", True),
        ("(a|b)*c", "abac", True),
        ("(a|b)*c", "abaz", False),
        ("^a|b$", "a", True),
        ("^a|b$", "b", True),
        ("^a|b$", "ab", False),
    ]

    all_passed = True
    for pattern, text, expected in tests:
        regex = BacktrackingRegex(pattern)
        result = regex.match(text)
        status = "OK" if result == expected else "FAIL"
        if result != expected:
            all_passed = False
        print(
            f"Pattern: {pattern:<10} Text: {text:<10} Expected: {str(expected):<5} Got: {str(result):<5} -> {status}")

    if all_passed:
        print("\n tests OK")
    else:
        print("\n tests failed, be less dumb")

    regex_search = BacktrackingRegex("a+b")
    search_result = regex_search.search('xaaabyz')
    print(f"Result: {search_result}")

    regex_findall_simple = BacktrackingRegex("a+")
    findall_result_1 = regex_findall_simple.findall('aabaaacaa')
    print(f"Result: {findall_result_1}")

    regex_findall_words = BacktrackingRegex("[^ ,]+")
    findall_result_2 = regex_findall_words.findall('one two, three')
    print(f"Result: {findall_result_2}")  # Expected: [(0, 3), (4, 7), (9, 14)]

    regex_findall_zero = BacktrackingRegex("z*")
    findall_result_3 = regex_findall_zero.findall('abc')
    # Expected: [(0, 0), (1, 1), (2, 2), (3, 3)]
    print(f"Result: {findall_result_3}")
