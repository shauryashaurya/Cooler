import json
from graphviz import Digraph

# AST tooling for cooler_bktrak_01 
# trying to avoid dumbness and circular dependencies


def build_ast(pattern: str):
    """
    Parse a regex pattern into its AST using the engine’s RegexParser.
    """
    # Lazy import to avoid circular import
    from cooler_bktrak_01 import RegexParser
    parser = RegexParser(pattern)
    return parser.parse()


def _collect_children(node):
    """
    Helper to collect child nodes for various AST node types via duck typing.
    """
    children = []
    # Quantifiers: have attribute 'node'
    if hasattr(node, 'node'):
        children.append(node.node)
    # Sequence: attribute 'nodes' as list
    if hasattr(node, 'nodes'):
        children.extend(node.nodes)
    # Alternation: left & right
    if hasattr(node, 'left') and hasattr(node, 'right'):
        children.append(node.left)
        children.append(node.right)
    return children


def ast_to_dict(node):
    """
    Convert an AST into a JSON-serializable dictionary via duck typing.
    """
    node_id = str(id(node))
    data = {
        "id": node_id,
        "type": type(node).__name__,
        "repr": None,
        "children": []
    }
    # Detect literal node
    if hasattr(node, 'char'):
        data['repr'] = node.char
    # Detect char class node
    elif hasattr(node, 'chars') and hasattr(node, 'negated'):
        data['repr'] = {
            "chars": list(node.chars),
            "negated": node.negated
        }
    # Recursively process children
    for child in _collect_children(node):
        data['children'].append(ast_to_dict(child))
    return data


def persist_ast(node, filename: str) -> None:
    """
    Serialize the AST to a JSON file.
    """
    with open(filename, 'w') as f:
        json.dump(ast_to_dict(node), f, indent=2)


def visualize_ast(node, output_path: str = 'ast', format: str = 'png') -> str:
    """
    Create a Graphviz visualization of the AST.
    Returns the path to the rendered file.
    """
    graph = Digraph(comment='Regex AST', format=format)

    def recurse(n):
        nid = str(id(n))
        label = type(n).__name__
        # Duck-type extra details
        if hasattr(n, 'char'):
            label += f"('{n.char}')"
        elif hasattr(n, 'chars') and hasattr(n, 'negated'):
            chars = ''.join(sorted(n.chars))
            label += f"([{chars}]){'^' if n.negated else ''}"
        graph.node(nid, label)
        for child in _collect_children(n):
            cid = str(id(child))
            graph.edge(nid, cid)
            recurse(child)

    recurse(node)
    return graph.render(output_path, cleanup=True)


class ASTTracer:
    """
    Instrument AST nodes to record match() entry, exit, and successful matches.
    Use duck typing to wrap match() methods.
    """

    def __init__(self):
        self.trace = []
        self._orig_methods = {}

    def instrument(self, node):
        """
        Wrap `match` methods on the AST nodes to record tracing info.
        """
        # Only instrument once
        if node in self._orig_methods:
            return
        if not hasattr(node, 'match'):
            # No match method, skip
            return
        orig_match = node.match

        def wrapped_match(text, pos):
            self.trace.append(f"ENTER {type(node).__name__} pos={pos}")
            for end_pos in orig_match(text, pos):
                self.trace.append(
                    f"MATCH {type(node).__name__} {pos}->{end_pos}")
                yield end_pos
            self.trace.append(f"EXIT {type(node).__name__} pos={pos}")

        # Monkey-patch the node
        setattr(node, 'match', wrapped_match)
        self._orig_methods[node] = orig_match

        # Recurse into children
        for child in _collect_children(node):
            self.instrument(child)

    def restore(self) -> None:
        """
        Restore original match methods.
        """
        for node, orig in self._orig_methods.items():
            setattr(node, 'match', orig)
        self._orig_methods.clear()

    def get_trace(self) -> list:
        """
        Get the collected trace entries.
        """
        return self.trace
