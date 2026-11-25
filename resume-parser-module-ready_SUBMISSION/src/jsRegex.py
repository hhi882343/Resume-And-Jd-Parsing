"""
JavaScript Regular Expression and String Utility Layer for Python.
Provides 100% character-and-boundary parity with Node.js V8 RegExp and String methods.
"""
import math
import regex

# Full JavaScript whitespace character set matching V8 \s:
# [ \t\n\r\f\v\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]
JS_WHITESPACE_CHARS = ' \t\n\r\f\v\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff'
JS_WS_CLASS_BODY = r'\s\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff'
JS_WS_BRACKET = r'[' + JS_WS_CLASS_BODY + r']'
JS_DOT_CLASS = r'[^\n\r\u2028\u2029]'


def to_js_utf16_surrogates(s: str) -> str:
    """
    In JavaScript, strings are UTF-16 code units. Non-BMP Unicode characters (code points > 0xFFFF,
    such as emojis) are represented as two 16-bit surrogate units (0xD800..0xDFFF).
    Python 3 natively represents all code points directly. This function converts non-BMP characters
    into isolated surrogate code units to achieve 100% match index and length parity with V8.
    """
    if not any(ord(ch) > 0xFFFF for ch in s):
        return s
    res = []
    for ch in s:
        cp = ord(ch)
        if cp > 0xFFFF:
            cp -= 0x10000
            high = 0xD800 + (cp >> 10)
            low = 0xDC00 + (cp & 0x3FF)
            res.append(chr(high))
            res.append(chr(low))
        else:
            res.append(ch)
    return ''.join(res)


def js_len(s: str | None) -> int:
    """Returns string length in UTF-16 code units, matching JavaScript .length."""
    if not s:
        return 0
    return len(s.encode('utf-16-le')) // 2


def from_js_utf16_surrogates(s: str | None) -> str | None:
    """Recombines valid surrogate pairs back into Unicode code points, leaving isolated surrogates intact."""
    if s is None:
        return None
    res = []
    i = 0
    s_len = len(s)
    while i < s_len:
        ch = s[i]
        if 0xD800 <= ord(ch) <= 0xDBFF and i + 1 < s_len and 0xDC00 <= ord(s[i + 1]) <= 0xDFFF:
            high = ord(ch) - 0xD800
            low = ord(s[i + 1]) - 0xDC00
            cp = 0x10000 + (high << 10) + low
            res.append(chr(cp))
            i += 2
        else:
            res.append(ch)
            i += 1
    return ''.join(res)


def js_trim(s: str | None) -> str:
    """Strips all ASCII and Unicode whitespace recognized by JavaScript String.prototype.trim()."""
    if s is None:
        return ''
    return s.strip(JS_WHITESPACE_CHARS)


def js_trim_start(s: str | None) -> str:
    """Strips leading whitespace matching String.prototype.trimStart()."""
    if s is None:
        return ''
    return s.lstrip(JS_WHITESPACE_CHARS)


def js_trim_end(s: str | None) -> str:
    """Strips trailing whitespace matching String.prototype.trimEnd()."""
    if s is None:
        return ''
    return s.rstrip(JS_WHITESPACE_CHARS)


_JS_WS_SPLIT_RE = regex.compile(r'[' + JS_WS_CLASS_BODY + r']+', regex.ASCII)


def js_split_whitespace(s: str | None) -> list[str]:
    """
    Implements JavaScript String.prototype.trim().split(/\\s+/) semantics.
    - Applies js_trim(s) first.
    - If trimmed is empty string "", returns [""] (matching JS "".split(/\\s+/) -> [""]).
    - Otherwise splits by 1 or more JS whitespace characters.
    """
    trimmed = js_trim(s)
    if not trimmed:
        return [""]
    return _JS_WS_SPLIT_RE.split(trimmed)


def js_split_whitespace_raw(s: str | None) -> list[str]:
    """
    Implements JavaScript String.prototype.split(/\\s+/) semantics without prior trim.
    - If s is empty or None, returns [""] (matching JS "".split(/\\s+/) -> [""]).
    - Otherwise splits by 1 or more JS whitespace characters.
    """
    if not s:
        return [""]
    return _JS_WS_SPLIT_RE.split(s)


def js_round(x: float | int) -> int:
    """
    Implements JavaScript Math.round() semantics (round half up towards +infinity).
    E.g.: Math.round(2.5) -> 3, Math.round(3.5) -> 4, Math.round(-1.5) -> -1.
    """
    return math.floor(x + 0.5)


def translate_pattern(pattern: str, flags: str = "") -> str:
    """
    Translates a JavaScript RegExp pattern string to a Python regex pattern string.
    Applies strict translation rules:
    - Replaces \\s (both inside and outside character classes) with the full JS whitespace definition.
    - Translates unescaped non-multiline $ to \\z (strict end of input, matching V8 non-multiline $ semantics).
    - Translates unescaped . outside character classes to [^\\n\\r\\u2028\\u2029].
    - Preserves variable-length lookbehinds.
    """
    out = []
    in_class = False
    escaped = False
    i = 0
    p_len = len(pattern)
    has_m = 'm' in flags
    has_s = 's' in flags

    while i < p_len:
        ch = pattern[i]
        if escaped:
            if ch == 's':
                if in_class:
                    out.append(JS_WS_CLASS_BODY)
                else:
                    out.append(JS_WS_BRACKET)
            else:
                out.append('\\' + ch)
            escaped = False
            i += 1
            continue

        if ch == '\\':
            escaped = True
            i += 1
            continue

        if ch == '[' and not in_class:
            in_class = True
            out.append(ch)
            i += 1
            continue

        if ch == ']' and in_class:
            in_class = False
            out.append(ch)
            i += 1
            continue

        # In non-multiline mode, replace unescaped $ outside character classes with \z
        if ch == '$' and not in_class and not has_m:
            out.append(r'\Z')
            i += 1
            continue

        # Outside character classes and when 's' (dotAll) flag is absent, replace unescaped . with JS_DOT_CLASS
        if ch == '.' and not in_class and not has_s:
            out.append(JS_DOT_CLASS)
            i += 1
            continue

        out.append(ch)
        i += 1

    if escaped:
        out.append('\\')

    return ''.join(out)


def compile_re(pattern: str | regex.Pattern, flags: str = "") -> regex.Pattern:
    """
    Compiles a regular expression pattern using the regex engine with JavaScript-compatible rules.
    - regex.ASCII is always applied for \\d, \\w, \\b to match V8 ASCII word boundary semantics.
    - 'i' flag enables regex.IGNORECASE.
    - 'm' flag enables regex.MULTILINE.
    - 's' flag enables regex.DOTALL.
    """
    if isinstance(pattern, regex.Pattern):
        return pattern

    reg_flags = regex.ASCII

    if 'i' in flags:
        reg_flags |= regex.IGNORECASE
    if 'm' in flags:
        reg_flags |= regex.MULTILINE
    if 's' in flags:
        reg_flags |= regex.DOTALL

    translated = translate_pattern(pattern, flags)
    return regex.compile(translated, reg_flags)


def js_finditer(pattern: str | regex.Pattern, text: str, flags: str = ""):
    """Finds all matches in text with JavaScript UTF-16 code unit semantics."""
    surr_text = to_js_utf16_surrogates(text)
    cre = compile_re(pattern, flags)
    return cre.finditer(surr_text)


def js_replace(text: str, pat: str | regex.Pattern, replacement, flags: str = "") -> str:
    """
    Replaces matches in text matching JavaScript String.prototype.replace semantics:
    If 'g' flag is not present, only the FIRST match is replaced (count=1).
    If 'g' flag is present, ALL matches are replaced.
    """
    surr_text = to_js_utf16_surrogates(text)
    re_obj = compile_re(pat, flags)
    count = 0 if 'g' in flags else 1

    if callable(replacement):
        def repl_wrapper(match):
            args = [match.group(0)] + list(match.groups()) + [match.start(), surr_text]
            return str(replacement(*args[:replacement.__code__.co_argcount]))
        res = re_obj.sub(repl_wrapper, surr_text, count=count)
    else:
        res = re_obj.sub(replacement, surr_text, count=count)

    return from_js_utf16_surrogates(res)
