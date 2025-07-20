
import sys
import argparse
from cooler_bktrak_01 import BacktrackingRegex

# look ma no 're'!
# import re


# really dumb parser to proove that we've got a regex engine that can proper parse mildly complex formats like fountain (for screenplays)
# imperfect, but proof of value for our regex parser.

# Fountain element regexes:
scene_heading_re = BacktrackingRegex(r'^(?:INT|EXT|EST|INT/EXT)\..+')
transition_re = BacktrackingRegex(r'^[A-Z ]+TO:$')
character_re = BacktrackingRegex(r'^[A-Z][A-Z0-9 ]+(?:\([^)]+\))?$')
parenthetical_re = BacktrackingRegex(r'^\(.*\)$')
blank_re = BacktrackingRegex(r'^\s*$')


# Default for any non-blank, non-specific line
# Used when line does not match other patterns
# Action or dialogue determined by context
#
# TODO: If you are really into it, focus and build a proper char-counted
# spaces only, text only, UTF-8 representation of the script from
# fountain.
# what we have here is VERY rudimentary.
def format_fountain(lines, width=80):

    # Convert Fountain lines into fixed-width screenplay text:
    #   - Scene headings: uppercase, left-aligned
    #   - Transitions: right-aligned
    #   - Character names: centered
    #   - Parentheticals: indented
    #   - Dialogue: indented under character
    #   - Action: left margin

    output = []
    for raw in lines:
        line = raw.rstrip('\n')
        if blank_re.match(line):
            output.append('')
            continue
        if scene_heading_re.match(line):
            output.append(line.upper())
        elif transition_re.match(line):
            output.append(line.rjust(width))
        elif character_re.match(line):
            output.append(line.center(width))
        elif parenthetical_re.match(line):
            output.append(' ' * 30 + line)
        else:
            # dialogue if previous line was a character
            prev = output[-1] if output else ''
            if prev and character_re.match(prev.strip()):
                output.append(' ' * 20 + line)
            else:
                output.append(line)
    return '\n'.join(output)


def main():
    # Read Fountain input from a file or stdin,
    # write formatted text to a file or stdout.
    # usage:
    # python fountain_parser input.fountain -o output.txt
    parser = argparse.ArgumentParser(
        description='Fountain to screenplay formatter')
    parser.add_argument('input', nargs='?',
                        help='Fountain file path (defaults to stdin)')
    parser.add_argument(
        '-o', '--output', help='Output file path (defaults to stdout)')
    args = parser.parse_args()

    # read
    if args.input:
        lines = open(args.input, encoding='utf-8').read().splitlines(True)
    else:
        lines = sys.stdin.read().splitlines(True)

    # format
    formatted = format_fountain(lines)

    # write
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(formatted)
    else:
        sys.stdout.write(formatted)


if __name__ == '__main__':
    main()
