"""Spintax engine — recursive-descent parser for generating unique message variants.

Used as a fallback when the LLM message generator pool runs low.
Produces cryptographically random selections to defeat Telegram's
content-hashing spam detection.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass, field
from typing import Optional, Union

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class SpintaxResult:
    """Single spun output with its SHA-256 fingerprint."""

    text: str
    hash: str  # SHA-256 hex digest


# ---------------------------------------------------------------------------
# AST nodes produced by the parser
# ---------------------------------------------------------------------------


@dataclass
class LiteralNode:
    """A plain text segment (no spintax)."""

    text: str


@dataclass
class ChoiceGroupNode:
    """A {opt1|opt2|…} group.  Each option is itself a sequence of nodes."""

    options: list[list[Union[LiteralNode, "ChoiceGroupNode"]]]


# A parsed template is a flat list of nodes at the top level.
SpintaxNode = Union[LiteralNode, ChoiceGroupNode]


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

_ESCAPE = "\\"


def _tokenize(template: str) -> list[str]:
    """Split *template* into tokens: literal runs, ``{``, ``|``, ``}``.

    Escaped braces (``\\{``, ``\\}``) are emitted as literal text.
    """
    tokens: list[str] = []
    buf: list[str] = []
    i = 0
    length = len(template)

    while i < length:
        ch = template[i]

        if ch == _ESCAPE and i + 1 < length and template[i + 1] in ("{", "}", "|"):
            buf.append(template[i + 1])
            i += 2
            continue

        if ch in ("{", "}", "|"):
            if buf:
                tokens.append("".join(buf))
                buf.clear()
            tokens.append(ch)
            i += 1
            continue

        buf.append(ch)
        i += 1

    if buf:
        tokens.append("".join(buf))

    return tokens


# ---------------------------------------------------------------------------
# Recursive-descent parser
# ---------------------------------------------------------------------------


class _Parser:
    """Consume a token stream and build an AST of *SpintaxNode* objects."""

    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> Optional[str]:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _advance(self) -> str:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    # -- public entry point --------------------------------------------------

    def parse(self) -> list[SpintaxNode]:
        nodes = self._parse_sequence(top_level=True)
        if self._pos < len(self._tokens):
            raise ValueError(
                f"Unexpected token at position {self._pos}: "
                f"{self._tokens[self._pos]!r}"
            )
        return nodes

    # -- grammar rules -------------------------------------------------------

    def _parse_sequence(self, *, top_level: bool = False) -> list[SpintaxNode]:
        """Parse a sequence of literals and choice groups until a delimiter."""
        nodes: list[SpintaxNode] = []

        while True:
            tok = self._peek()
            if tok is None:
                break
            if tok in ("|", "}"):
                if top_level and tok == "}":
                    raise ValueError("Unmatched closing brace '}'")
                break
            if tok == "{":
                nodes.append(self._parse_choice_group())
            else:
                self._advance()
                nodes.append(LiteralNode(tok))

        return nodes

    def _parse_choice_group(self) -> ChoiceGroupNode:
        """Parse ``{opt1|opt2|…}`` where each option may itself contain nested groups."""
        self._advance()  # consume '{'

        options: list[list[SpintaxNode]] = []
        options.append(self._parse_sequence())

        while self._peek() == "|":
            self._advance()  # consume '|'
            options.append(self._parse_sequence())

        if self._peek() != "}":
            raise ValueError("Unmatched opening brace '{'")
        self._advance()  # consume '}'

        return ChoiceGroupNode(options)


# ---------------------------------------------------------------------------
# Tree operations
# ---------------------------------------------------------------------------


def _resolve(nodes: list[SpintaxNode]) -> str:
    """Walk the AST, making a cryptographically random choice at each group."""
    parts: list[str] = []
    for node in nodes:
        if isinstance(node, LiteralNode):
            parts.append(node.text)
        elif isinstance(node, ChoiceGroupNode):
            chosen = secrets.choice(node.options)
            parts.append(_resolve(chosen))
    return "".join(parts)


def _count_permutations(nodes: list[SpintaxNode]) -> int:
    """Return the total number of unique strings the AST can produce."""
    total = 1
    for node in nodes:
        if isinstance(node, ChoiceGroupNode):
            group_perms = sum(
                _count_permutations(option) for option in node.options
            )
            total *= group_perms
    return total


# ---------------------------------------------------------------------------
# Public engine
# ---------------------------------------------------------------------------


class SpintaxEngine:
    """High-level API for spinning, counting, and validating spintax templates."""

    def __init__(self) -> None:
        self._generated_hashes: set[str] = set()

    # -- core API ------------------------------------------------------------

    def spin(self, template: str) -> SpintaxResult:
        """Generate a single spun text from *template*."""
        if not template:
            h = self.hash_text("")
            return SpintaxResult(text="", hash=h)

        nodes = self._parse(template)
        text = _resolve(nodes)
        h = self.hash_text(text)
        self._generated_hashes.add(h)
        return SpintaxResult(text=text, hash=h)

    def spin_batch(
        self,
        template: str,
        count: int,
        max_retries: int = 100,
    ) -> list[SpintaxResult]:
        """Generate *count* unique spun texts.

        Raises ``RuntimeError`` if the engine cannot produce enough unique
        variants within *count + max_retries* attempts.
        """
        if count <= 0:
            return []

        total_perms = self.count_permutations(template)
        if total_perms < count:
            raise ValueError(
                f"Template has only {total_perms:,} permutations but "
                f"{count:,} unique messages were requested"
            )

        nodes = self._parse(template)
        results: list[SpintaxResult] = []
        seen: set[str] = set()
        attempts = 0
        max_attempts = count + max_retries

        while len(results) < count:
            if attempts >= max_attempts:
                raise RuntimeError(
                    f"Could not generate {count} unique messages after "
                    f"{attempts} attempts (got {len(results)})"
                )
            text = _resolve(nodes)
            h = self.hash_text(text)
            if h not in seen:
                seen.add(h)
                self._generated_hashes.add(h)
                results.append(SpintaxResult(text=text, hash=h))
            attempts += 1

        log.debug(
            "spin_batch: generated %d unique messages in %d attempts",
            len(results),
            attempts,
        )
        return results

    def count_permutations(self, template: str) -> int:
        """Return the total number of unique outputs *template* can produce."""
        if not template:
            return 1
        nodes = self._parse(template)
        return _count_permutations(nodes)

    def validate_template(self, template: str) -> tuple[bool, str]:
        """Check *template* for syntax errors.

        Returns ``(True, "")`` on success or ``(False, error_message)`` on failure.
        """
        if not template:
            return True, ""

        # 1. Quick brace-balance check (ignoring escaped braces).
        depth = 0
        i = 0
        while i < len(template):
            ch = template[i]
            if ch == _ESCAPE and i + 1 < len(template) and template[i + 1] in ("{", "}", "|"):
                i += 2
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth < 0:
                    return False, "Unmatched closing brace '}'"
            i += 1

        if depth != 0:
            return False, "Unmatched opening brace '{'"

        # 2. Full parse to catch structural issues.
        try:
            tokens = _tokenize(template)
            parser = _Parser(tokens)
            nodes = parser.parse()
        except ValueError as exc:
            return False, str(exc)

        # 3. Check for empty options inside choice groups.
        problems = self._check_empty_options(nodes)
        if problems:
            return False, "; ".join(problems)

        return True, ""

    def reset_hashes(self) -> None:
        """Clear the set of previously generated hashes."""
        self._generated_hashes.clear()

    @property
    def generated_count(self) -> int:
        """Number of unique messages generated so far."""
        return len(self._generated_hashes)

    # -- static helpers ------------------------------------------------------

    @staticmethod
    def hash_text(text: str) -> str:
        """Return the SHA-256 hex digest of *text*."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _parse(template: str) -> list[SpintaxNode]:
        tokens = _tokenize(template)
        return _Parser(tokens).parse()

    @classmethod
    def _check_empty_options(cls, nodes: list[SpintaxNode]) -> list[str]:
        """Recursively detect empty options in choice groups."""
        problems: list[str] = []
        for node in nodes:
            if isinstance(node, ChoiceGroupNode):
                for idx, option in enumerate(node.options):
                    if not option:
                        problems.append(
                            f"Empty option at index {idx} in a choice group"
                        )
                    else:
                        problems.extend(cls._check_empty_options(option))
        return problems


# ---------------------------------------------------------------------------
# CLI demo / smoke tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s  %(message)s")
    engine = SpintaxEngine()

    # 1. Basic spin ----------------------------------------------------------
    tpl_basic = "{Hi|Hey|Yo} there!"
    result = engine.spin(tpl_basic)
    print(f"[basic]   {tpl_basic!r}")
    print(f"  -> {result.text!r}  (hash={result.hash[:12]}…)")
    assert result.text.endswith(" there!")
    print()

    # 2. Nested spin ---------------------------------------------------------
    tpl_nested = "{I {noticed|saw}|{Noticed|Saw}} your {profile|account}"
    result = engine.spin(tpl_nested)
    print(f"[nested]  {tpl_nested!r}")
    print(f"  -> {result.text!r}")
    print()

    # 3. Deeply nested -------------------------------------------------------
    tpl_deep = "{a|{b|{c|{d|e}}}}"
    result = engine.spin(tpl_deep)
    print(f"[deep]    {tpl_deep!r}")
    print(f"  -> {result.text!r}")
    print()

    # 4. Escaped braces ------------------------------------------------------
    tpl_escaped = r"Use \{spintax\} like {this|that}"
    result = engine.spin(tpl_escaped)
    print(f"[escape]  {tpl_escaped!r}")
    print(f"  -> {result.text!r}")
    assert "{spintax}" in result.text
    print()

    # 5. Permutation counting ------------------------------------------------
    tpl_count = "{a|b|c} {x|y}"
    perms = engine.count_permutations(tpl_count)
    print(f"[count]   {tpl_count!r}  => {perms} permutations")
    assert perms == 6

    tpl_count2 = "{Hi|Hey} {mate|{good friend|buddy}}"
    perms2 = engine.count_permutations(tpl_count2)
    print(f"[count]   {tpl_count2!r}  => {perms2} permutations")
    assert perms2 == 6  # 2 * (1 + 2)
    print()

    # 6. Batch generation (100 unique) ---------------------------------------
    engine.reset_hashes()
    tpl_batch = (
        "{Hi|Hey|Yo|Hello|Sup|What's up} {friend|mate|bro|dude|boss|chief|legend},"
        " {I {noticed|saw|spotted}|{Noticed|Saw|Spotted}} your"
        " {profile|account|page|posts} {on|over on|at}"
        " {the forum|BHW|the marketplace|HF}."
        " {Interested in|Looking for|Need} {crypto|trading|web3|DeFi}"
        " {services|solutions|help}?"
    )
    total_perms = engine.count_permutations(tpl_batch)
    print(f"[batch]   template has {total_perms:,} permutations")
    batch = engine.spin_batch(tpl_batch, 100)
    texts = {r.text for r in batch}
    assert len(texts) == 100, f"Expected 100 unique, got {len(texts)}"
    print(f"[batch]   generated 100 unique messages ✓")
    print(f"  sample: {batch[0].text!r}")
    print()

    # 7. Validation ----------------------------------------------------------
    ok, err = engine.validate_template("{a|b|c}")
    assert ok, err
    print(f"[valid]   '{{a|b|c}}'  => valid ✓")

    ok, err = engine.validate_template("{a|b|c")
    assert not ok
    print(f"[invalid] '{{a|b|c'   => {err}")

    ok, err = engine.validate_template("{a||c}")
    assert not ok
    print(f"[invalid] '{{a||c}}'  => {err}")

    ok, err = engine.validate_template("no braces here")
    assert ok
    print(f"[valid]   'no braces here' => valid ✓")

    ok, err = engine.validate_template("")
    assert ok
    print(f"[valid]   '' (empty)   => valid ✓")

    # 8. Edge cases ----------------------------------------------------------
    # Single option
    r = engine.spin("{only}")
    assert r.text == "only"
    print(f"\n[edge]    '{{only}}'  => {r.text!r} ✓")

    # Adjacent groups
    perms_adj = engine.count_permutations("{a|b}{c|d}")
    assert perms_adj == 4
    print(f"[edge]    '{{a|b}}{{c|d}}' => {perms_adj} permutations ✓")

    # No spintax
    r = engine.spin("plain text")
    assert r.text == "plain text"
    print(f"[edge]    'plain text' => {r.text!r} ✓")

    print("\n✅  All smoke tests passed.")
