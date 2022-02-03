#!/usr/bin/env python

"""
API and command line interface for the use of GreynirCorrect in a TTS-normalizer pipeline

"""
from reynir_correct.checker import check_single
from islenska import Bin

from reynir_correct.checker import AnnotatedSentence

from typing import (
    Iterator,
    Iterable,
    Tuple
)
import sys
import argparse

# File types for UTF-8 encoded text files
ReadFile = argparse.FileType("r", encoding="utf-8")
WriteFile = argparse.FileType("w", encoding="utf-8")

# Define the command line arguments
parser = argparse.ArgumentParser(description="Corrects Icelandic text")

parser.add_argument(
    "inputfile",
    nargs="?",
    type=ReadFile,
    default=sys.stdin,
    help="UTF-8 text file to correct",
)


def extract_pos_info(variants: list) -> Tuple[str, tuple]:
    """Extract POS-info from variants and return them in the correct format
    for BÍN-lookup"""

    num = variants[0].upper()
    if variants[1] in ['hk', 'kk', 'kvk']:
        genus = variants[1]
        case = variants[2].upper()
    else:
        genus = variants[2]
        case = variants[1].upper()
    if case == 'GR':
        case = 'gr'  # otherwise lookup_variants fails, see bincompress.py in binPackage
    tup = (case, num)
    return genus, tup


def post_process(annot_sent: AnnotatedSentence, bin_db: Bin) -> str:
    """ Use information collected during the spell checking process to determine errors in normalized tokens and
    correct according to pos-tags from the parser.
    The variants list of each terminal holds POS-information from the parser that we can use together with the
    BÍN-tuple list of the corresponding token to determine the correct word form by performing a lookup on BÍN
    as a post-processing step and replace the token in the sentence if necessary.
    Test annot_sent for None and annot_sent.terminals None before calling this method."""

    if annot_sent is None or annot_sent.terminals is None:
        return None

    for annotation in annot_sent.annotations:
        # TODO: use annotations for autocorrect where applicable
        print("{0}".format(annotation))

    checked_sent = []
    for i in range(len(annot_sent.terminals)):
        term = annot_sent.terminals[i]
        token = annot_sent.tokens[i]
        if not token.meanings or len(term.variants) <= 2:
            checked_sent.append(term.text)
            continue
        genus, case_num_tuple = extract_pos_info(term.variants)

        reslist = bin_db.lookup_variants(term.lemma, genus, case_num_tuple)
        word = term.text
        for res in reslist:
            # the lookup might have extracted other lemmas than the one
            # we determined in errtokenizer, check for equal ids
            if res.bin_id == token.meanings[0].utg:
                # don't change letter case of the original
                if term.text.lower() != res.bmynd.lower():
                    word = res.bmynd
                    break
        checked_sent.append(word)

    return ' '.join(checked_sent)


def gen(f: Iterator[str]) -> Iterable[str]:
    """Generate the lines of text in the input file"""
    yield from f


def main():

    args = parser.parse_args()
    inputfile = args.inputfile

    bin_db = Bin()
    checked_text = []

    itering = gen(inputfile)
    for sent in itering:
        if not sent.strip():
            continue
        checked = check_single(sent.strip())
        if not checked or checked.terminals is None:
            # parse and/or spell check failed, we store the original sentence
            checked_text.append(sent.strip())
        else:
            checked_text.append(post_process(checked, bin_db))

    print("CORRECTED: ")
    for sent in checked_text:
        print(sent)


if __name__ == "__main__":
    main()
