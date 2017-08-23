def extract_line(line):
    """
    >>> extract_line("* hello world")
    ('hello world', 1)
    >>> extract_line("** this  is a ** test!!")
    ('this  is a ** test!!', 2)
    """
    depth = 0
    l = len(line)
    while (depth < l) and (line[depth] == '*'):
        depth += 1
    return (line[depth+1:], depth)


def parse_header(header):
    """
    >>> parse_header("* a\\n* b\\n* c")
    [['a', []], ['b', []], ['c', []]]
    >>> parse_header("* a\\n** b\\n* c")
    [['a', [['b', []]]], ['c', []]]
    >>> parse_header("* a\\n** b\\n** c\\n*** d\\n* e")
    [['a', [['b', []], ['c', [['d', []]]]]], ['e', []]]
    """
    nodes = []
    current_nodes = []
    for line in header.split("\n"):
        title,depth = extract_line(line.strip())
        if depth == 0:
            continue
        this_node = [title,[]]
        if depth == 1:
            nodes.append(this_node)
            current_nodes = [this_node]
        else:
            current_nodes[depth-2][1].append(this_node)
            current_nodes = current_nodes[:depth-1]
            current_nodes.append(this_node)

    return nodes


def table_header(header, prefix_columns=None, postfix_columns=None):
    nodes = parse_header(header)
    rows = {}

    def traverse(node, depth):
        title = node[0]
        children = node[1]

        if len(children) == 0:
            leaf_count = 1
            is_leaf = True
        else:
            leaf_count = 0
            for child in children:
                leaf_count += traverse(child, depth+1)
            is_leaf = False
            
        if depth not in rows:
            rows[depth] = []

        rows[depth].append((title, leaf_count, is_leaf))
        return leaf_count
    

    for n in nodes:
        traverse(n,0)
    output = []
    row_count = len(rows)
    for r in range(row_count):
        output.append('<tr>')
        if (r == 0) and (prefix_columns):
            for c in prefix_columns:
                output.append('<th rowspan="' + str(row_count) + '">' +
                              c + '</th>')
            
        for title, span, is_leaf in rows[r]:
            if is_leaf: 
                rowspan = row_count - r
                output.append('<th rowspan="' + str(rowspan) + '">' + title + '</th>')
            else:
                output.append('<th colspan="' + str(span) + '">' + title + '</th>')

        if (r == 0) and (postfix_columns):
            for c in postfix_columns:
                output.append('<th rowspan="' + str(row_count) + '">' +
                              c + '</th>')
            
        output.append('</tr>')
    return "\n".join(output)
