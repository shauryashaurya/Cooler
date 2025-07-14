class RegexNode:
    def match(self, text, pos):
        raise NotImplementedError


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


class Star(RegexNode):
    def __init__(self, node):
        self.node = node

    def match(self, text, pos):
        yield pos  # zero matches
        current_pos = pos
        while True:
            matched = False
            for new_pos in self.node.match(text, current_pos):
                matched = True
                current_pos = new_pos
                yield current_pos
                break
            if not matched:
                break


class Plus(RegexNode):
    def __init__(self, node):
        self.node = node

    def match(self, text, pos):
        for first_pos in self.node.match(text, pos):
            yield first_pos
            current_pos = first_pos
            while True:
                matched = False
                for new_pos in self.node.match(text, current_pos):
                    matched = True
                    current_pos = new_pos
                    yield current_pos
                    break
                if not matched:
                    break


class Question(RegexNode):
    def __init__(self, node):
        self.node = node

    def match(self, text, pos):
        yield pos  # zero matches
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

        for new_pos in self.nodes[node_idx].match(text, pos):
            yield from self._match_sequence(text, new_pos, node_idx + 1)


class CharClass(RegexNode):
    def __init__(self, chars, negated=False):
        self.chars = set(chars)
        self.negated = negated

    def match(self, text, pos):
        if pos < len(text):
            char = text[pos]
            if (char in self.chars) != self.negated:
                yield pos + 1


class Start(RegexNode):
    def match(self, text, pos):
        if pos == 0:
            yield pos


class End(RegexNode):
    def match(self, text, pos):
        if pos == len(text):
            yield pos


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

        if not nodes:
            return Literal('')  # empty sequence
        if len(nodes) == 1:
            return nodes[0]
        return Sequence(nodes)

    def parse_factor(self):
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
        if self.pos >= len(self.pattern):
            raise ValueError("Unexpected end of pattern")

        char = self.pattern[self.pos]

        if char == '(':
            self.pos += 1
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
            self.pos += 1
            if self.pos >= len(self.pattern):
                raise ValueError("Unexpected end of pattern after backslash")
            escaped = self.pattern[self.pos]
            self.pos += 1
            return Literal(escaped)

        elif char in '*+?|()[]^$\\':
            raise ValueError(
                f"Unexpected special character '{char}' at position {self.pos}")

        else:
            self.pos += 1
            return Literal(char)

    def parse_char_class(self):
        self.pos += 1  # skip '['

        negated = False
        if self.pos < len(self.pattern) and self.pattern[self.pos] == '^':
            negated = True
            self.pos += 1

        chars = []
        while self.pos < len(self.pattern) and self.pattern[self.pos] != ']':
            if self.pattern[self.pos] == '\\':
                self.pos += 1
                if self.pos >= len(self.pattern):
                    raise ValueError(
                        "Unexpected end of pattern in character class")
                chars.append(self.pattern[self.pos])
            else:
                chars.append(self.pattern[self.pos])
            self.pos += 1

        if self.pos >= len(self.pattern):
            raise ValueError("Missing closing bracket for character class")

        self.pos += 1  # skip ']'
        return CharClass(chars, negated)


class BacktrackingRegex:
    def __init__(self, pattern):
        self.pattern = pattern
        self.ast = RegexParser(pattern).parse()

    def match(self, text):
        """Full match from start to end"""
        for end_pos in self.ast.match(text, 0):
            if end_pos == len(text):
                return True
        return False

    def search(self, text):
        """Find first occurrence anywhere in text"""
        for start in range(len(text) + 1):
            for end_pos in self.ast.match(text, start):
                return (start, end_pos)
        return None

    def findall(self, text):
        """Find all non-overlapping matches"""
        matches = []
        pos = 0
        while pos <= len(text):
            found = False
            for end_pos in self.ast.match(text, pos):
                matches.append((pos, end_pos))
                # avoid infinite loop on empty matches
                pos = max(pos + 1, end_pos)
                found = True
                break
            if not found:
                pos += 1
        return matches


# Test the engine
if __name__ == "__main__":
    # Test cases
    tests = [
        ("abc", "abc", True),
        ("a.c", "abc", True),
        ("a*", "aaaa", True),
        ("a+", "", False),
        ("a?", "b", True),
        ("a|b", "c", False),
        ("(ab)+", "ababab", True),
        ("[abc]", "b", True),
        ("[^abc]", "d", True),
        ("^abc", "abc", True),
        ("abc$", "abc", True),
        ("a*b", "aaab", True),
    ]

    for pattern, text, expected in tests:
        regex = BacktrackingRegex(pattern)
        result = regex.match(text)
        print(
            f"Pattern: {pattern:8} Text: {text:8} Expected: {expected} Got: {result} {'✓' if result == expected else '✗'}")

    # Search examples
    regex = BacktrackingRegex("a+b")
    print(f"\nSearch 'a+b' in 'xaaabyz': {regex.search('xaaabyz')}")
    print(f"Find all 'a+' in 'aabaaab': {regex.findall('aabaaab')}")
