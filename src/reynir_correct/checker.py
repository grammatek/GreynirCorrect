"""

    Reynir: Natural language processing for Icelandic

    Spelling and grammar checking module

    Copyright(C) 2019 Miðeind ehf.

        This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
        the Free Software Foundation, either version 3 of the License, or
        (at your option) any later version.

        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
        GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.


    This module exposes functions to check spelling and grammar for
    text strings.

    Error codes generated by this module:
    -------------------------------------

    E001: The sentence could not be parsed
    E002: A nonterminal tagged with 'error' is present in the parse tree
    E003: An impersonal verb occurs with an incorrect subject case

"""

from threading import Lock

from reynir import Reynir, correct_spaces
from reynir.binparser import BIN_Token
from reynir.fastparser import Fast_Parser, ParseForestNavigator
from reynir.reducer import Reducer
from reynir.settings import VerbSubjects

from .errtokenizer import tokenize as tokenize_and_correct


class Annotation:

    """ An annotation of a span of a token list for a sentence """

    def __init__(self, *, start, end, code, text):
        assert isinstance(start, int)
        assert isinstance(end, int)
        self._start = start
        self._end = end
        self._code = code
        self._text = text

    def __str__(self):
        """ Return a string representation of this annotation """
        return "{0:03}-{1:03}: {2:6} {3}".format(
            self._start, self._end, self._code, self._text
        )

    @property
    def start(self):
        """ The index of the first token to which the annotation applies """
        return self._start

    @property
    def end(self):
        """ The index of the last token to which the annotation applies """
        return self._end

    @property
    def code(self):
        """ A code for the annotation type, usually an error or warning code """
        return self._code

    @property
    def text(self):
        """ A description of the annotation """
        return self._text


class ErrorFinder(ParseForestNavigator):

    """ Utility class to find nonterminals in parse trees that are
        tagged as errors in the grammar, and terminals matching
        verb forms marked as errors """

    _CASE_NAMES = {"nf": "nefni", "þf": "þol", "þgf": "þágu", "ef": "eignar"}

    # Dictionary of functions used to explain grammar errors
    # associated with nonterminals with error tags in the grammar
    _TEXT_FUNC = {
        "VillaHeldur": lambda txt, variants: (
            # 'heldur' er ofaukið
            "'{0}' er ofaukið"
            .format(txt)
        ),
        "VillaVístAð": lambda txt, variants: (
            # 'víst að' á sennilega að vera 'fyrst að'
            "'{0}' á sennilega að vera 'fyrst að'"
            .format(txt)
        ),
        "VillaFráÞvíAð": lambda txt, variants: (
            # 'allt frá því' á sennilega að vera 'allt frá því að'
            "'{0}' á sennilega að vera '{0} að'"
            .format(txt)
        ),
        "VillaAnnaðhvort": lambda txt, variants: (
            # Í stað 'annaðhvort' á sennilega að standa 'annað hvort'
            "Í stað '{0}' á að standa 'annað hvort'"
            .format(txt)
        ),
        "VillaAnnaðHvort": lambda txt, variants: (
            # Í stað 'annað hvort' á sennilega að standa 'annaðhvort'
            "Í stað '{0}' á að standa 'annaðhvort'"
            .format(txt)
        ),
        "VillaFjöldiHluti": lambda txt, variants: (
            # Sögn sem á við 'fjöldi Evrópuríkja' á að vera í eintölu
            "Sögn sem á við '{0}' á að vera í eintölu, ekki fleirtölu"
            .format(txt)
        ),
        "VillaEinnAf": lambda txt, variants: (
            # Sögn sem á við 'einn af drengjunum' á að vera í eintölu
            "Sögn sem á við '{0}' á að vera í eintölu, ekki fleirtölu"
            .format(txt)
        ),
        "VillaAð": lambda txt, variants: (
            # 'að' er sennilega ofaukið
            "'{0}' er sennilega ofaukið"
            .format(txt)
        ),
        "VillaÞóAð": lambda txt, variants: (
            # [jafnvel] þó' á sennilega að vera '[jafnvel] þó að
            "'{0}' á sennilega að vera '{0} að' (eða 'þótt')"
            .format(txt)
        ),
    }

    def __init__(self, ann, sent):
        super().__init__(visit_all=True)
        # Annotation list
        self._ann = ann
        # The original sentence object
        self._sent = sent
        # Token list
        self._tokens = sent.tokens
        # Terminal node list
        self._terminal_nodes = sent.terminal_nodes

    @staticmethod
    def _node_span(node):
        """ Return the start and end indices of the tokens
            spanned by the given node """
        first_token, last_token = node.token_span
        return (first_token.index, last_token.index)

    def _visit_token(self, level, node):
        """ Entering a terminal/token match node """
        if (
            node.terminal.category == "so"
            and node.terminal.is_subj
            and (node.terminal.has_variant("op") or node.terminal.has_variant("subj"))
        ):
            # Check whether the associated verb is allowed
            # with a subject in this case
            # node points to a fastparser.Node instance
            # tnode points to a SimpleTree instance
            tnode = self._terminal_nodes[node.start]
            verb = tnode.lemma
            subj_case_abbr = node.terminal.variant(-1)  # so_subj_op_et_þf
            assert subj_case_abbr in {"nf", "þf", "þgf", "ef"}, (
                "Unknown case in " + node.terminal.name
            )
            # Check whether this verb has an entry in the VERBS_ERRORS
            # dictionary, and whether that entry then has an item for
            # the present subject case
            errors = VerbSubjects.VERBS_ERRORS.get(verb)
            if errors and subj_case_abbr in errors:
                # Yes, this appears to be an erroneous subject case
                wrong_case = self._CASE_NAMES[subj_case_abbr]
                # Retrieve the correct case
                correct_case_abbr = errors[subj_case_abbr]
                correct_case = self._CASE_NAMES[correct_case_abbr]
                # Try to recover the verb's subject
                subj = None
                # First, check within the enclosing verb phrase
                # (the subject may be embedded within it, as in
                # ?'Í dag langaði Páli bróður að fara í sund')
                p = tnode.enclosing_tag("VP")
                if p is not None:
                    try:
                        subj = p.NP_SUBJ
                    except AttributeError:
                        pass
                if subj is None:
                    # Then, look within the enclosing IP (inflected phrase)
                    # node, if any
                    p = tnode.enclosing_tag("IP")
                    if p is not None:
                        # Found the inflected phrase:
                        # find the NP-SUBJ node, if any
                        try:
                            subj = p.NP_SUBJ
                        except AttributeError:
                            pass
                code = "P_WRONG_CASE_" + subj_case_abbr + "_" + correct_case_abbr
                if subj is not None:
                    # We know what the subject is: annotate it
                    start, end = subj.span
                    self._ann.append(
                        Annotation(
                            start=start,
                            end=end,
                            code=code,
                            text="Frumlag sagnarinnar 'að {0}' á að vera "
                                "í {1}falli en ekki í {2}falli"
                                .format(verb, correct_case, wrong_case),
                        )
                    )
                else:
                    # We don't seem to find the subject, so just annotate the verb
                    index = node.token.index
                    self._ann.append(
                        Annotation(
                            start=index,
                            end=index,
                            code=code,
                            text="Frumlag sagnarinnar 'að {0}' á að vera "
                                "í {1}falli en ekki í {2}falli"
                                .format(verb, correct_case, wrong_case),
                        )
                    )
        return None

    def _visit_nonterminal(self, level, node):
        """ Entering a nonterminal node """
        if node.is_interior or node.nonterminal.is_optional:
            # Not an interesting node
            pass
        elif node.nonterminal.has_tag("error"):
            # This node has a nonterminal that is tagged with $tag(error)
            # in the grammar file (Reynir.grammar)
            start, end = self._node_span(node)
            span_text = correct_spaces(
                " ".join(t.txt for t in self._tokens[start : end + 1] if t.txt)
            )
            # See if we have a custom text function for this
            # error-tagged nonterminal
            name = node.nonterminal.name
            variants = ""
            if "_" in name:
                # Separate the variants
                ix = name.index("_")
                variants = name[ix + 1:]
                name = name[:ix]
            text_func = self._TEXT_FUNC.get(name)
            # The error code in this case is P_NT_ + the name of the error-tagged
            # nonterminal, however after cutting 'Villa' from its front
            code = "P_NT_" + (name[5:] if name.startswith("Villa") else name)
            if text_func is not None:
                # Yes: call it with the nonterminal's spanned text as argument
                ann_text = text_func(span_text, variants)
            else:
                # No: use a default text
                ann_text = (
                    "'{0}' er líklega rangt (regla {1})"
                    .format(span_text, node.nonterminal.name)
                )
            self._ann.append(
                # P_NT_ + nonterminal name: Probable grammatical error
                Annotation(
                    start=start,
                    end=end,
                    code=code,
                    text=ann_text,
                )
            )
        return None


class ErrorDetectionToken(BIN_Token):

    """ A subclass of BIN_Token that adds error detection behavior
        to the base class """

    _VERB_ERROR_SUBJECTS = VerbSubjects.VERBS_ERRORS

    def __init__(self, t, original_index):
        """ original_index is the index of this token in
            the original token list, as submitted to the parser,
            including not-understood tokens such as quotation marks """
        super().__init__(t, original_index)

    @staticmethod
    def verb_is_strictly_impersonal(verb):
        """ Return True if the given verb is strictly impersonal,
            i.e. never appears with a nominative subject """
        # Here, we return False because we want to catch errors
        # where impersonal verbs are used with a nominative subject
        return False

    @staticmethod
    def verb_cannot_be_impersonal(verb, form):
        """ Return True if this verb cannot match an so_xxx_op terminal. """
        # Here, we return False because we want to catch
        # errors where verbs such as 'hlakka' are used with a
        # non-nominative subject
        return False

    def verb_subject_matches(self, verb, subj):
        """ Returns True if the given subject type/case is allowed for this verb
            or if it is an erroneous subject which we can flag """
        return subj in self._VERB_SUBJECTS.get(
            verb, set()
        ) or subj in self._VERB_ERROR_SUBJECTS.get(verb, set())


class ErrorDetectingParser(Fast_Parser):

    """ A subclass of Fast_Parser that modifies its behavior to
        include grammar error detection rules in the parsing process """

    @staticmethod
    def _create_wrapped_token(t, ix):
        """ Create an instance of a wrapped token """
        return ErrorDetectionToken(t, ix)


class ReynirCorrect(Reynir):

    """ Parser augmented with the ability to add spelling and grammar
        annotations to the returned sentences """

    # ReynirCorrect has its own class instances of a parser and a reducer,
    # separate from the Reynir class, as they use different settings and
    # parsing enviroments
    _parser = None
    _reducer = None
    _lock = Lock()

    def __init__(self):
        super().__init__()

    def tokenize(self, text):
        """ Use the correcting tokenizer instead of the normal one """
        return tokenize_and_correct(text)

    @property
    def parser(self):
        """ Override the parent class' construction of a parser instance """
        with self._lock:
            if (
                ReynirCorrect._parser is None
                or ReynirCorrect._parser.is_grammar_modified()[0]
            ):
                # Initialize a singleton instance of the parser and the reducer.
                # Both classes are re-entrant and thread safe.
                ReynirCorrect._parser = edp = ErrorDetectingParser()
                ReynirCorrect._reducer = Reducer(edp.grammar)
            return ReynirCorrect._parser

    @property
    def reducer(self):
        """ Return the reducer instance to be used """
        # Should always retrieve the parser attribute first
        assert ReynirCorrect._reducer is not None
        return ReynirCorrect._reducer

    @staticmethod
    def annotate(sent):
        """ Returns a list of annotations for a sentence object, containing
            spelling and grammar annotations of that sentence """
        ann = []
        # First, add token-level annotations
        for ix, t in enumerate(sent.tokens):
            # Note: these tokens and indices are the original tokens from
            # the submitted text, including ones that are not understood
            # by the parser, such as quotation marks and exotic punctuation
            if hasattr(t, "error_code") and t.error_code:
                ann.append(
                    Annotation(
                        start=ix,
                        end=ix + t.error_span - 1,
                        code=t.error_code,
                        text=t.error_description,
                    )
                )
        # Then: if the sentence couldn't be parsed,
        # put an annotation on it as a whole
        if sent.deep_tree is None:
            ann.append(
                # E001: Unable to parse sentence
                Annotation(
                    start=0,
                    end=len(sent.tokens) - 1,
                    code="E001",
                    text="Málsgreinin fellur ekki að reglum",
                )
            )
        else:
            # Successfully parsed:
            # Add error rules from the grammar
            ErrorFinder(ann, sent).go(sent.deep_tree)
        # Sort the annotations by their start token index,
        # and then by decreasing span length
        ann.sort(key=lambda a: (a.start, -a.end))
        return ann

    def create_sentence(self, job, s):
        """ Create a fresh sentence object and annotate it
            before returning it to the client """
        sent = super().create_sentence(job, s)
        # Add spelling and grammar annotations to the sentence
        sent.annotations = self.annotate(sent)
        return sent


def check_single(sentence):
    """ Check and annotate a single sentence, given in plain text """
    rc = ReynirCorrect()
    return rc.parse_single(sentence)


def check(text, *, split_paragraphs=False):
    """ Return a generator of checked paragraphs of text,
        each being a generator of checked sentences with
        annotations """
    rc = ReynirCorrect()
    # This is an asynchronous (on-demand) parse job
    job = rc.submit(text, parse=True, split_paragraphs=split_paragraphs)
    yield from job.paragraphs()


def check_with_custom_parser(text, *,
    split_paragraphs=False,
    parser_class=ReynirCorrect
):
    """ Return a dict containing parsed paragraphs as well as statistics,
        using the given correction/parser class. This is a low-level
        function; normally check_with_stats() should be used. """
    rc = parser_class()
    job = rc.submit(text, parse=True, split_paragraphs=split_paragraphs)
    # Enumerating through the job's paragraphs and sentences causes them
    # to be parsed and their statistics collected
    paragraphs = [[sent for sent in pg] for pg in job.paragraphs()]
    return dict(
        paragraphs=paragraphs,
        num_sentences=job.num_sentences,
        num_parsed=job.num_parsed,
        num_tokens=job.num_tokens,
        ambiguity=job.ambiguity,
        parse_time=job.parse_time,
    )


def check_with_stats(text, *, split_paragraphs=False):
    """ Return a dict containing parsed paragraphs as well as statistics """
    return check_with_custom_parser(text, split_paragraphs=split_paragraphs)
