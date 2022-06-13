def is_start(c):
    return c == "^"


def is_end(c):
    return c == "$"


def is_star(c):
    return c == "*"


def is_plus(c):
    return c == "+"


def is_question(c):
    return c == "?"


def is_operator(c):
    return is_star(c) or is_plus(c) or is_question(c)


def is_literal(c):
    return c.isalpha() or c.isdigit() or c in [" ", ":", "/"]


def is_open_set(c):
    return c == "["


def is_close_set(c):
    return c == "]"


def is_open_alternate(c):
    return c == "("


def is_close_alternate(c):
    return c == ")"


def is_dot(c):
    return c == "."


def is_set(s):
    return is_open_set(s[0]) and is_close_set(s[-1])


def is_alternate(s):
    return is_open_alternate(s[0]) and is_close_alternate(s[-1])


def is_escape(c):
    return c == "\\"


def is_escape_sequence(s):
    return is_escape(s[0])


def is_unit(s):
    return is_literal(s[0]) or is_dot(s[0]) or is_set(s) or is_escape_sequence(s)


def split_set(e):
    if is_set(e):
        return e[1:][:-1]
    else:
        return None


# clumsy computer implementation:


def split_set_cc(e):
    set_inside = e[1:-1]
    # for a string 'abc' this returns ['a','b','c']
    set_terms = list(set_inside)
    # another way to do this would be:
    # set_terms = ''.split(set_inside)
    return set_terms


def split_alternate(alternate):
    return alternate[1:-1].split("|")


def does_unit_match(e, s):
    if len(s) == 0:
        return False

    h, o, r = split_expr(e)
    if is_literal(h):
        return h[0] == s[0]
    elif is_dot(h):
        return True
    elif is_escape_sequence(h):
        if h == "\\a":
            return s[0].isalpha()
        elif h == "\\d":
            return s[0].isdigit()
        else:
            return False
    elif is_set(h):
        split_head = split_set_cc(h)
        match_head = s[0] in split_head
        return match_head
    return False


# return the first token which could be a [set] or a (group) or a literal character as 'head'
# then any '*', '+' or '?' found as 'operator'
# and then the remainder of the expression as 'rest'
# the idea is that a recursive call to this will result in
# a token-by-token match
# THIS IS BASICALLY YOUR LEXER - IT'LL FIND OUT THE FIRST UNIT, THE NEXT OPERATOR IF AROUND AND THE REMAINDER OF THE REGEX
def split_expr(e):
    head = None
    operator = None
    rest = None
    last_token_position = 0

    if is_open_set(e[0]):
        last_token_position = e.find("]") + 1
        head = e[0:last_token_position]
    elif is_open_alternate(e[0]):
        last_token_position = e.find(")") + 1
        head = e[:last_token_position]
    elif is_escape(e[0]):
        last_token_position += 2
        head = e[:2]
    else:
        last_token_position = 1
        head = e[0]

    if last_token_position < len(e) and is_operator(e[last_token_position]):
        operator = e[last_token_position]
        last_token_position += 1

    rest = e[last_token_position:]

    return head, operator, rest


def match_multiple(
    expr, string, match_length, min_match_length=None, max_match_length=None
):
    head, operator, rest = split_expr(expr)

    if not min_match_length:
        min_match_length = 0

    submatch_length = -1
    while not max_match_length or (submatch_length < max_match_length):
        [subexpr_matched, subexpr_length] = match_expr_recursive(
            (head * (submatch_length + 1)), string, match_length, "match_multiple 01"
        )
        if subexpr_matched:
            submatch_length += 1
        else:
            break

    while submatch_length >= min_match_length:
        [matched, new_match_length] = match_expr_recursive(
            (head * submatch_length) + rest, string, match_length, "match_multiple 02"
        )
        if matched:
            return [matched, new_match_length]
        submatch_length -= 1

    return [False, None]


def match_star(expression, text, match_length):
    return match_multiple(expression, text, match_length, None, None)


def match_plus(expression, text, match_length):
    return match_multiple(expression, text, match_length, 1, None)


def match_question(expression, text, match_length):
    return match_multiple(expression, text, match_length, 0, 1)


def match_alternate(expr, text, match_length):

    # if len(text) == 0:
    #     return False

    head, op, rest = split_expr(expr)
    options = split_alternate(head)

    for option in options:
        [matched, new_match_length] = match_expr_recursive(
            option + rest, text, match_length, "match_alternate"
        )
        if matched:
            return [matched, new_match_length]

    return [False, None]


# this is NOT tail recursive - not optimal
def match_expr_recursive(expr, string, match_length=0, coming_from=""):
    # nothing left to match
    if len(expr) == 0:
        return [True, match_length]
    elif is_end(expr[0]):
        if len(string) == 0:
            return [True, match_length]
        else:
            return [False, None]

    # gotta do this in order of precedence...

    # more to match...recurse through the expression and the string
    head, operator, rest = split_expr(expr)
    if is_star(operator):
        return match_star(expr, string, match_length)
    elif is_plus(operator):
        return match_plus(expr, string, match_length)
    elif is_question(operator):
        return match_question(expr, string, match_length)
    elif is_alternate(head):
        return match_alternate(expr, string, match_length)
    elif is_unit(head):
        if does_unit_match(expr, string):
            return match_expr_recursive(
                rest, string[1:], match_length + 1, "match_expr_recursive"
            )
    else:
        print(f"match_expr_recursive: unknown token in {expr}")

    return [False, None]


def match(expr, text):
    match_pos = 0
    matched = False
    # the most you can match is to the end of the text
    if is_start(expr[0]):
        max_match_pos = 0
        expr = expr[1:]
    else:
        max_match_pos = len(text) - 1
    while not matched and match_pos <= max_match_pos:
        # if the pattern starts to match, it'll create a recursive stack of match_expr_recursive
        [matched, match_length] = match_expr_recursive(
            expr, text[match_pos:], 0, "match"
        )
        if matched:
            return [matched, match_pos, match_length]
        match_pos += 1
    return [False, None, None]


def run_regex(expr, string):
    print(f"\n***\nrun_regex: {expr}, {string}")
    [matched, match_pos, match_length] = match(expr, string)
    if matched:
        print(
            f'run_regex(" {expr} ",  " {string} ") = {match_pos}, " {string[match_pos:match_pos+match_length]} "'
        )
    else:
        print(f'run_regex(" {expr} ",  " {string} ") = False')

    return [matched, match_pos, match_length]


def main():

    print(
        run_regex(
            "^http://(\\a|\\d)+.(com|net|org)", "http://clumsy123computer.com/hey/there"
        )
    )
    print(run_regex('^abc', 'abc'))
    print(run_regex('^abc', '1abc'))
    print(run_regex('^abc', 'abc1'))
    print(run_regex('c', 'abc'))
    print(run_regex('abc$', '123abc'))
    print(run_regex('I am a (cat|dog)+$', 'Hello! I am a cat'))
    print(run_regex('1(cat|dog)2', '1cat2'))
    print(run_regex('I am a (cat|dog)', 'Hello! I am a cat!'))
    print(run_regex('I am a (cat|dog)', 'Hello! I am a dog!'))
    print(run_regex('I am a (cat|dog)+', 'Hello! I am a catdog!'))
    print(run_regex('I am a (cat|dog)*', 'Hello! I am a catdog!'))
    print (run_regex('1(cat|dog)2', '1tue2'))
    # print(split_expr('abc'))
    # print(split_expr('[123]bc'))
    # print(split_expr('a*bc'))
    # print(split_expr('[123]*bc'))
    # print(split_expr('[123]+bc'))
    # print(split_expr('[123]+'))
    # print(split_expr('[123]?abc'))
    # print(split_expr('[123?]abc'))
    # print(split_expr('ab[c]'))
    # print(split_expr('a[b]*c'))
    # print(split_expr('[]abc]'))

    print(run_regex('[Hh][Ee]llo', 'Hi! HEllo...here!'))
    print(run_regex('[Hh][Ee][Ll][Ll][Oo]', 'Hi! HeLlO...here!'))
    print(run_regex('hello', 'Hi! a hello HEllo...here!'))

    # # tests for []
    print(run_regex('[123]ab*c', '1abc'))
    print(run_regex('[123]ab*c', '2abc'))
    print(run_regex('[123]ab*c', '3abc'))
    print(run_regex('[123]ab*c', '4abc'))
    print(run_regex('[123]ab*c', '1abc'))
    print(run_regex('[123]ab*c', '12abc'))
    print(run_regex('[123]*ab*c', '123abc'))
    print(run_regex('[123]*ab*c', '1231abc'))
    print(run_regex('[123]*ab*c', '1231ac'))
    print(run_regex('[123]*ab*c', '1231abbc'))
    print(run_regex('[123]*ab*c', '1231abbbc'))
    print(run_regex('[123]*ab*c', '1231abbbc'))

    # # 0 or more b
    print(run_regex('ab*c', 'ab'))
    print(run_regex('ab*c', 'ac'))
    print(run_regex('ab*c', 'abc'))
    print(run_regex('ab*c', 'abbc'))
    # # 1 or more b
    print(run_regex('ab+c', 'ab'))
    print(run_regex('ab+c', 'ac'))
    print(run_regex('ab+c', 'abc'))
    print(run_regex('ab+c', 'abbc'))
    # # 0 or 1 b
    print(run_regex('ab?c', 'ab'))
    print(run_regex('ab?c', 'ac'))
    print(run_regex('ab?c', 'abc'))
    print(run_regex('ab?c', 'abbc'))

    return 0


if __name__ == "__main__":
    main()
