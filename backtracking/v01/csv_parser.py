from cooler_bktrak_01 import BacktrackingRegex

# CSV field pattern:
#  - Quoted fields: "..." with double-" escape
#  - Unquoted fields: no commas, no CR/LF
FIELD_PATTERN = r'"(?:[^"]|"")*"|[^,\r\n]*'

# Compile once
_field_regex = BacktrackingRegex(FIELD_PATTERN)
_comma_regex = BacktrackingRegex(r',')


#
#
def parse_csv_line(line: str) -> list:
    # Parse a single CSV line into a list of field strings using the backtracking regex engine.
    # Handles quoted fields with "" escapes and unquoted fields.

    fields = []
    pos = 0
    length = len(line)

    while pos <= length:
        # match a FIELD at current position
        m = _field_regex.search(line[pos:])
        if not m:
            break
        start, end = m
        raw = line[pos + start: pos + end]
        # Unescape quoted fields
        if raw.startswith('"') and raw.endswith('"'):
            inner = raw[1:-1]
            field = inner.replace('""', '"')
        else:
            field = raw
        fields.append(field)
        pos += end
        # skip one comma if present
        comma = _comma_regex.search(line[pos:])
        if comma and comma[0] == 0:
            pos += 1
        else:
            break
    return fields


#
#
def parse_csv(data: str) -> list:
    # Parse a full CSV text (multiple lines) into a list of record lists.
    # Splits on CR, LF, or CRLF, preserves empty fields.

    records = []
    # split on CRLF or LF or CR
    lines = data.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    for line in lines:
        if line:  # skip any completely empty trailing lines
            records.append(parse_csv_line(line))
    return records
