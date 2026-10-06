"""디버거 실습용 예제. The Debugging Book 의 버그 있는 remove_html_markup() 그대로다."""


def remove_html_markup(s):
    tag = False
    quote = False
    out = ""

    for c in s:
        if c == '<' and not quote:
            tag = True
        elif c == '>' and not quote:
            tag = False
        elif c == '"' or c == "'" and tag:
            quote = not quote
        elif not tag:
            out = out + c

    return out


def clean_all(pages):
    results = []
    for page in pages:
        results.append(remove_html_markup(page))
    return results


if __name__ == '__main__':
    pages = ['<b>foo</b>', '"foo"', '<a href="x">bar</a>']
    print(clean_all(pages))
