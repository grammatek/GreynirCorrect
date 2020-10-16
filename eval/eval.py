#!/usr/bin/env python
"""

    Greynir: Natural language processing for Icelandic

    Evaluation of spelling and grammar correction

    Copyright (C) 2020 Miðeind ehf.

    This software is licensed under the MIT License:

        Permission is hereby granted, free of charge, to any person
        obtaining a copy of this software and associated documentation
        files (the "Software"), to deal in the Software without restriction,
        including without limitation the rights to use, copy, modify, merge,
        publish, distribute, sublicense, and/or sell copies of the Software,
        and to permit persons to whom the Software is furnished to do so,
        subject to the following conditions:

        The above copyright notice and this permission notice shall be
        included in all copies or substantial portions of the Software.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
        EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
        MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
        IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
        CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
        TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
        SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


    This program uses an Icelandic spelling & grammar error corpus
    (https://github.com/antonkarl/iceErrorCorpus) to evaluate the
    performance of the GreynirCorrect package.

    The program reads a development set of hand-annotated texts in
    TEI XML format and automatically annotates errors using GreynirCorrect.
    The machine-generated annotations are then compared with the hand-annotated
    gold reference.

    This program uses Python's multiprocessing.Pool() to perform
    the evaluation using all available CPU cores, simultaneously.

    A normal way to configure this program is to clone the iceErrorCorpus
    repository (from the above path) into a separate directory, and
    then place a symlink to it to the /eval directory. For example:

    $ cd github
    $ git clone https://github.com/antonkarl/iceErrorCorpus
    $ cd GreynirCorrect/eval
    $ ln -s ../../iceErrorCorpus/ .
    $ python eval.py

    An alternate method is to specify a glob path to the error corpus as an
    argument to eval.py:

    $ python eval.py ~/github/iceErrorCorpus/data/**/*.xml

    To measure GreynirCorrect's performance on the test set
    (by default located in ./iceErrorCorpus/testCorpus/):

    $ python eval.py -m

    To run GreynirCorrect on the entire development corpus
    (by default located in ./iceErrorCorpus/data):

    $ python eval.py

    To run GreynirCorrect on 10 files in the development corpus:

    $ python eval.py -n 10

    To run GreynirCorrect on a randomly chosen subset of 10 files
    in the development corpus:

    $ python eval.py -n 10 -r

"""

from typing import Dict, List, Optional, Union, Tuple, Iterable, cast, NamedTuple, Any

import os
from collections import defaultdict
from datetime import datetime
import glob
import random
import heapq
import argparse
import xml.etree.ElementTree as ET
import multiprocessing

# import multiprocessing.dummy as multiprocessing

import reynir_correct as gc
from reynir import _Sentence
from tokenizer import detokenize, Tok, TOK


# The type of a single error descriptor, extracted from a TEI XML file
ErrorDict = Dict[str, Union[str, int, bool]]

# The type of the dict that holds statistical information about sentences
# within a particular content category
SentenceStatsDict = Dict[str, Union[float, int]]

# The type of the dict that holds statistical information about
# content categories
CategoryStatsDict = Dict[str, SentenceStatsDict]

StatsTuple = Tuple[str, int, bool, bool]

# Create a lock to ensure that only one process outputs at a time
OUTPUT_LOCK = multiprocessing.Lock()

# Content categories in iceErrorCorpus, embedded within the file paths
CATEGORIES = (
    "essays",
    "onlineNews",
    "wikipedia",
)

# Error codes in iceErrorCorpus that are considered out of scope
# for GreynirCorrect, at this stage at least
OUT_OF_SCOPE = {
    "agreement-pro",  # samræmi fornafns við undanfara  grammar ...vöðvahólf sem sé um dælinguna. Hann dælir blóðinu > Það dælir blóðinu
    "aux",  # meðferð vera og verða, hjálparsagna   wording mun verða eftirminnilegt > mun vera eftirminnilegt
    "bracket4square",  # svigi fyrir hornklofa  punctuation (Portúgal) > [Portúgal]
    "collocation-idiom",  # fast orðasamband með ógagnsæja merkingu collocation hélt hvorki vindi né vatni > hélt hvorki vatni né vindi
    "collocation",  # fast orðasamband  collocation fram á þennan dag > fram til þessa dags
    "comma4conjunction",  # komma fyrir samtengingu punctuation ...fara með vald Guðs, öll löggjöf byggir... > ...fara með vald Guðs og öll löggjöf byggir...
    "comma4dash",  # komma fyrir bandstrik  punctuation , > -
    "comma4ex",  # komma fyrir upphrópun    punctuation Viti menn, almúginn... > Viti menn! Almúginn...
    "comma4period",  # komma fyrir punkt    punctuation ...kynnast nýju fólki, er á þrítugsaldri > ...kynnast nýju fólki. Hann er á þrítugsaldri
    "comma4qm",  # komma fyrir spurningarmerki  punctuation Höfum við réttinn, eins og að... > Höfum við réttinn? Eins og að...
    "conjunction4comma",  # samtenging fyrir kommu  punctuation ...geta orðið þröngvandi og erfitt getur verið... > ...geta orðið þröngvandi, erfitt getur verið...
    "conjunction4period",  # samtenging fyrir punkt punctuation ...tónlist ár hvert og tónlistarstefnurnar eru orðnar... > ...tónlist ár hvert. Tónlistarstefnurnar eru orðnar...
    "context",  # rangt orð í samhengi  other
    "dash4semicolon",  # bandstrik fyrir semíkommu  punctuation núna - þetta > núna; þetta
    "def4ind",  # ákveðið fyrir óákveðið    grammar skákinni > skák
    "dem-pro",  # hinn í stað fyrir sá; sá ekki til eða ofnotað grammar hinn > sá
    "dem4noun",  # ábendingarfornafn í stað nafnorðs    grammar hinn > maðurinn
    "dem4pers",  # ábendingarfornafn í stað persónufornafns grammar þessi > hún
    "extra-comma",  # auka komma    punctuation stríð, við náttúruna > stríð við náttúruna
    "extra-number",  # tölustöfum ofaukið   other   139,0 > 139
    "extra-period",  # auka punktur punctuation á morgun. Og ... > á morgun og...
    "extra-punctuation",  # auka greinarmerki   punctuation ... að > að
    "extra-space",  # bili ofaukið  spacing 4 . > 4.
    "extra-symbol",  # tákn ofaukið other   Dalvík + gaf... > Dalvík gaf...
    "extra-word",  # orði ofaukið   insertion   augun á mótherja > augu mótherja
    "extra-words",  # orðum ofaukið insertion   ...ég fer að hugsa... > ...ég hugsa...
    "foreign-error",  # villa í útlendu orði    foreign Supurbowl > Super Bowl
    "fw4ice",  # erlent orð þýtt yfir á íslensku    style   Elba > Saxelfur
    "gendered",  # kynjað mál, menn fyrir fólk  exclusion   menn hugsa oft > fólk hugsar oft
    "ice4fw",  # íslenskt orð notað í stað erlends      Demókrata öldungarþings herferðarnefndina > Democratic Senatorial Campaign Committee
    "ind4def",  # óákveðið fyrir ákveðið    grammar gítartakta > gítartaktana
    "ind4sub",  # framsöguháttur fyrir vh.  grammar Þrátt fyrir að konfúsíanismi er upprunninn > Þrátt fyrir að konfúsíanismi sé upprunninn
    "indef-pro",  # óákveðið fornafn    grammar enginn > ekki neinn
    "it4nonit",  # skáletrað fyrir óskáletrað       Studdi Isma'il > Studdi Isma'il
    "loan-syntax",  # lánuð setningagerð    style   ég vaknaði upp > ég vaknaði
    "missing-commas",  # kommur vantar utan um innskot  punctuation Hún er jafn verðmæt ef ekki verðmætari en háskólapróf > Hún er verðmæt, ef ekki verðmætari, en háskólapróf
    "missing-conjunction",  # samtengingu vantar    punctuation í Noregi suður að Gíbraltarsundi > í Noregi og suður að Gíbraltarsundi
    "missing-ex",  # vantar upphrópunarmerki    punctuation Viti menn ég komst af > Viti menn! Ég komst af
    "missing-quot",  # gæsalöpp vantar  punctuation „I'm winning > „I'm winning“
    "missing-quots",  # gæsalappir vantar   punctuation I'm winning > „I'm winning“
    "missing-semicolon",  # vantar semíkommu    punctuation Haukar Björgvin Páll > Haukar; Björgvin Páll
    # "missing-space",        # vantar bil  spacing eðlis-og efnafræði > eðlis- og efnafræði
    "missing-square",  # vantar hornklofi   punctuation þeir > [þeir]
    "missing-symbol",  # tákn vantar    punctuation 0 > 0%
    "missing-word",  # orð vantar   omission    í Donalda > í þorpinu Donalda
    "missing-words",  # fleiri en eitt orð vantar   omission    því betri laun > því betri laun hlýtur maður
    "nonit4it",  # óskáletrað fyrir skáletrað       orðið qibt > orðið qibt
    "noun4dem",  # nafnorð í stað ábendingarfornafns    grammar stærsta klukkan > sú stærsta
    "noun4pro",  # nafnorð í stað fornafns  grammar menntun má nálgast > hana má nálgast
    "past4pres",  # sögn í þátíð í stað nútíðar grammar þegar hún leigði spólur > þegar hún leigir spólur
    "period4comma",  # punktur fyrir kommu  punctuation meira en áður. Hella meira í sig > meira en áður, hella meira í sig
    "period4conjunction",  # punktur fyrir samtengingu  punctuation ...maður vill gera. Vissulega > ...maður vill gera en vissulega
    "period4ex",  # punktur fyrir upphrópun punctuation Viti menn. > Viti menn!
    "pers4dem",  # persónufornafn í staðinn fyrir ábendingarf.  grammar það > þetta
    "pres4past",  # sögn í nútíð í stað þátíðar grammar Þeir fara út > Þeir fóru út
    "pro4noun",  # fornafn í stað nafnorðs  grammar þau voru spurð > parið var spurt
    "pro4reflexive",  # nafnorð í stað afturbeygðs fornafns grammar gefur orku til fólks í kringum það > gefur orku til fólks í kringum sig
    "pro4reflexive",  # persónufornafn í stað afturbeygðs fn.   grammar Fólk heldur að það geri það hamingjusamt > Fólk heldur að það geri sig hamingjusamt
    "punctuation",  # greinarmerki  punctuation hún mætti og hann var ekki tilbúinn > hún mætti en hann var ekki tilbúinn
    "qm4ex",  # spurningarmerki fyrir upphrópun punctuation Algjört hrak sjálf? > Algjört hrak sjálf!
    "reflexive4noun",  # afturbeygt fornafn í stað nafnorðs grammar félagið hélt aðalfund þess > félagið hélt aðalfund sinn
    "reflexive4pro",  # afturbeygt fornafn í stað persónufornafns   grammar gegnum líkama sinn > gegnum líkama hans
    "simple4cont",  # nútíð í stað vera að + nafnh. grammar ók > var að aka
    "square4bracket",  # hornklofi fyrir sviga  punctuation [börnin] > (börnin)
    "style",  # stíll   style   urðu ekkert frægir > urðu ekki frægir
    "sub4ind",  # viðtengingarh. fyrir fh.  grammar Stjórnvöld vildu auka rétt borgara og geri þeim kleift > Stjórnvöld vildu auka rétt borgara og gera þeim kleift
    "unicelandic",  # óíslenskuleg málnotkun    style   ...fer eftir persónunni... > ...fer eftir manneskjunni...
    "upper4lower-proper",  # stór stafur í sérnafni þar sem hann á ekki að vera capitalization  Mál og Menning > Mál og menning
    "wording",  # orðalag   wording ...gerðum allt í raun... > ...gerðum í raun allt...
    "xxx",  # unclassified  unclassified
    "zzz",  # to revisit    unannotated
}

# Default glob path of the development corpus TEI XML files to be processed
_DEV_PATH = "iceErrorCorpus/data/**/*.xml"

# Default glob path of the test corpus TEI XML files to be processed
_TEST_PATH = "iceErrorCorpus/testCorpus/**/*.xml"

# Define the command line arguments

parser = argparse.ArgumentParser(
    description=(
        "This program evaluates the spelling and grammar checking performance "
        "of GreynirCorrect on iceErrorCorpus"
    )
)

parser.add_argument(
    "path",
    nargs="?",
    type=str,
    help=f"glob path of XML files to process (default: {_DEV_PATH})",
)

parser.add_argument(
    "-n",
    "--number",
    type=int,
    default=0,
    help="number of files to process (default=all)",
)

parser.add_argument(
    "-c",
    "--cores",
    type=int,
    help=f"number of CPU cores to use (default=all, i.e. {os.cpu_count() or 1})",
)

parser.add_argument(
    "-m",
    "--measure",
    action="store_true",
    help="run measurements on test corpus and output results only",
)

parser.add_argument(
    "-r", "--randomize", action="store_true", help="process a random subset of files",
)

parser.add_argument(
    "-q",
    "--quiet",
    default=None,
    action="store_true",
    help="output results only, not individual sentences",
)

parser.add_argument(
    "-v",
    "--verbose",
    default=None,
    action="store_true",
    help="output individual sentences as well as results, even for the test corpus",
)

# This boolean global is set to True for quiet output,
# which is the default when processing the test corpus
QUIET = False


def element_text(element: ET.Element) -> str:
    """ Return the text of the given element,
        including all its subelements, if any """
    return "".join(element.itertext())


class Stats:

    """ A container for key statistics on processed files and sentences """

    def __init__(self) -> None:
        """ Initialize empty defaults for the stats collection """
        self._starttime = datetime.utcnow()
        self._files: Dict[str, int] = defaultdict(int)
        self._sentences: CategoryStatsDict = defaultdict(lambda: defaultdict(int))
        self._true_positives: Dict[str, int] = defaultdict(int)
        self._false_negatives: Dict[str, int] = defaultdict(int)

    def add_file(self, category: str) -> None:
        """ Add a processed file in a given content category """
        self._files[category] += 1

    def add_result(
        self,
        *,
        stats: List[StatsTuple],
        true_positives: Dict[str, int],
        false_negatives: Dict[str, int],
    ) -> None:
        """ Add the result of a process() call to the statistics collection """
        for sent_result in stats:
            self.add_sentence(*sent_result)
        for k, v in true_positives.items():
            self._true_positives[k] += v
        for k, v in false_negatives.items():
            self._false_negatives[k] += v

    def add_sentence(
        self, category: str, num_tokens: int, ice_error: bool, gc_error: bool,
        tp: int, tn: int, fp: int, fn: int, right_corr: int, wrong_corr: int,
        right_span: int, wrong_span: int
    ) -> None:
        """ Add a processed sentence in a given content category """
        d = self._sentences[category]
        d["count"] += 1
        d["num_tokens"] += num_tokens
        d["ice_errors"] += 1 if ice_error else 0
        d["gc_errors"] += 1 if gc_error else 0
        # True negative: neither iceErrorCorpus nor GC report an error
        true_negative = not ice_error and not gc_error
        d["true_negatives"] += 1 if true_negative else 0
        # True positive: both iceErrorCorpus and GC report an error
        true_positive = ice_error and gc_error
        d["true_positives"] += 1 if true_positive else 0
        # False negative: iceErrorCorpus reports an error where GC doesn't
        false_negative = ice_error and not gc_error
        d["false_negatives"] += 1 if false_negative else 0
        # False positive: GC reports an error where iceErrorCorpus doesn't
        false_positive = gc_error and not ice_error
        d["false_positives"] += 1 if false_positive else 0

        # Stats for error detection for sentence
        d["tp"] += tp
        d["tn"] += tn
        d["fp"] += fp
        d["fn"] += fn
        # Stats for error correction
        d["right_corr"] += right_corr
        d["wrong_corr"] += wrong_corr
        # Stats for error span
        d["right_span"] += right_span
        d["wrong_span"] += wrong_span

    def output(self, cores: int) -> None:
        """ Write the statistics to stdout """
        # Calculate the duration of the processing
        dur = int((datetime.utcnow() - self._starttime).total_seconds())
        h = dur // 3600
        m = (dur % 3600) // 60
        s = dur % 60
        # Output a summary banner
        print("\n" + "=" * 7)
        print("Summary")
        print("=" * 7 + "\n")
        # Total number of files processed, and timing stats
        print(f"Processing started at {str(self._starttime)[0:19]}")
        print(f"Total processing time {h}h {m:02}m {s:02}s, using {cores} cores")
        print(f"\nFiles processed:            {sum(self._files.values()):6}")
        for c in CATEGORIES:
            print(f"   {c:<13}:           {self._files[c]:6}")
        # Total number of tokens processed
        num_tokens = sum(d["num_tokens"] for d in self._sentences.values())
        print(f"\nTokens processed:           {num_tokens:6}")
        for c in CATEGORIES:
            print(f"   {c:<13}:           {self._sentences[c]['num_tokens']:6}")
        # Total number of sentences processed
        num_sentences = sum(d["count"] for d in self._sentences.values())
        print(f"\nSentences processed:        {num_sentences:6}")
        for c in CATEGORIES:
            print(f"   {c:<13}:           {self._sentences[c]['count']:6}")

        def perc(n):
            """ Return a percentage of total sentences, formatted as 3.2f """
            if num_sentences == 0:
                return "N/A"
            return f"{100.0*n/num_sentences:3.2f}"
            
        ### SENTENCE SCORES
        # TODO Setja útreikning á P, R og F í sérfall, 
        # Fær sent inn TN, TP, FP og FN - er þá búin að summa það upp
        # Get sent inn aukagildi, sem segir t.d. hvort nota á F0,5 eða F1
        # Og hvað er verið að reikna?
        # Get líka sent inn texta sem segir hvað er verið að reikna,
        # s.s. "Results for Error detection" eða "Results for sentence correctness"?

        # Total number of true negatives found
        print("\nResults for error detection in sentences")
        true_negatives = sum(d["true_negatives"] for d in self._sentences.values())
        print(
            f"\nTrue negatives:             {true_negatives:6} {perc(true_negatives):>6}%"
        )
        for c in CATEGORIES:
            print(f"   {c:<13}:           {self._sentences[c]['true_negatives']:6}")

        # Total number of true positives found
        true_positives = sum(d["true_positives"] for d in self._sentences.values())
        print(
            f"\nTrue positives:             {true_positives:6} {perc(true_positives):>6}%"
        )
        for c in CATEGORIES:
            print(f"   {c:<13}:           {self._sentences[c]['true_positives']:6}")

        # Total number of false negatives found
        false_negatives = sum(d["false_negatives"] for d in self._sentences.values())
        print(
            f"\nFalse negatives:            {false_negatives:6} {perc(false_negatives):>6}%"
        )
        for c in CATEGORIES:
            print(f"   {c:<13}:           {self._sentences[c]['false_negatives']:6}")

        # Total number of false positives found
        false_positives = sum(d["false_positives"] for d in self._sentences.values())
        print(
            f"\nFalse positives:            {false_positives:6} {perc(false_positives):>6}%"
        )
        for c in CATEGORIES:
            print(f"   {c:<13}:           {self._sentences[c]['false_positives']:6}")

        # Percentage of true vs. false
        true_results = true_positives + true_negatives
        false_results = false_positives + false_negatives
        if num_sentences == 0:
            result = "N/A"
        else:
            result = f"{100.0*true_results/num_sentences:3.2f}%/{100.0*false_results/num_sentences:3.2f}%"
        print(f"\nTrue/false split: {result:>16}")
        for c in CATEGORIES:
            d = self._sentences[c]
            num_sentences = d["count"]
            true_results = d["true_positives"] + d["true_negatives"]
            false_results = d["false_positives"] + d["false_negatives"]
            if num_sentences == 0:
                result = "N/A"
            else:
                result = f"{100.0*true_results/num_sentences:3.2f}%/{100.0*false_results/num_sentences:3.2f}%"
            print(f"   {c:<13}: {result:>16}")

        # Recall
        if true_positives + false_negatives == 0:
            result = "N/A"
            recall = 0.0
        else:
            recall = true_positives / (true_positives + false_negatives)
            result = f"{recall:1.4f}"
        print(f"\nRecall:                     {result}")
        for c in CATEGORIES:
            d = self._sentences[c]
            denominator = d["true_positives"] + d["false_negatives"]
            if denominator == 0:
                print(f"   {c:<13}:              N/A")
            else:
                rc = d["recall"] = d["true_positives"] / denominator
                print(f"   {c:<13}:           {rc:1.4f}")

        # Precision
        if true_positives + false_positives == 0:
            result = "N/A"
            precision = 0.0
        else:
            precision = true_positives / (true_positives + false_positives)
            result = f"{precision:1.4f}"
        print(f"\nPrecision:                  {result}")
        for c in CATEGORIES:
            d = self._sentences[c]
            denominator = d["true_positives"] + d["false_positives"]
            if denominator == 0:
                print(f"   {c:<13}:              N/A")
            else:
                p = d["precision"] = d["true_positives"] / denominator
                print(f"   {c:<13}:           {p:1.4f}")

        # F1 score
        if precision + recall > 0.0:
            f1 = 2 * precision * recall / (precision + recall)
            result = f"{f1:1.4f}"
        else:
            f1 = 0.0
            result = "N/A"
        print(f"\nF1 score:                   {result}")
        for c in CATEGORIES:
            d = self._sentences[c]
            if "recall" not in d or "precision" not in d:
                print(f"   {c:<13}:              N/A")
                continue
            rc = d["recall"]
            p = d["precision"]
            if p + rc > 0.0:
                f1 = 2 * p * rc / (p + rc)
                print(f"   {c:<13}:           {f1:1.4f}")
            else:
                print(f"   {c:<13}:           N/A")

        total = sum(self._false_negatives.values())
        if total > 0:
            print("\nMost common false negative error types")
            print("--------------------------------------\n")
            for index, (xtype, cnt) in enumerate(
                heapq.nlargest(20, self._false_negatives.items(), key=lambda x: x[1])
            ):
                print(f"{index+1:3}. {xtype} ({cnt}, {100.0*cnt/total:3.2f}%)")

        print("Results for error detection  within sentences")
        num_tokens = sum(d["num_tokens"] for d in self._sentences.values())
        print(f"\nTokens processed:           {num_tokens:6}")
        for c in CATEGORIES:
            print(f"   {c:<13}:           {self._sentences[c]['num_tokens']:6}")

        tp = sum(d["tp"] for d in self._sentences.values())
        print(f"\nTrue positives:           {tp:6}")
        for c in CATEGORIES:
            print(f"   {c:<13}:           {self._sentences[c]['tp']:6}")

        tn = sum(d["tn"] for d in self._sentences.values())
        print(f"\nTrue negatives:           {tn:6}")
        for c in CATEGORIES:
            print(f"   {c:<13}:           {self._sentences[c]['tn']:6}")

        fp = sum(d["fp"] for d in self._sentences.values())
        print(f"\nFalse positives:           {fp:6}")
        for c in CATEGORIES:
            print(f"   {c:<13}:           {self._sentences[c]['fp']:6}")

        fn = sum(d["fn"] for d in self._sentences.values())
        print(f"\nFalse negatives:           {fn:6}")
        for c in CATEGORIES:
            print(f"   {c:<13}:           {self._sentences[c]['fn']:6}")

        print("Results for error correction")
        right_corr = sum(d["right_corr"] for d in self._sentences.values())
        print(f"\nRight correction:           {right_corr:6}")
        for c in CATEGORIES:
            print(f"   {c:<13}:           {self._sentences[c]['right_corr']:6}")
       
        wrong_corr = sum(d["wrong_corr"] for d in self._sentences.values())
        print(f"\nWrong correction:           {wrong_corr:6}")
        for c in CATEGORIES:
            print(f"   {c:<13}:           {self._sentences[c]['wrong_corr']:6}")

        print("Results for error span")
        right_span = sum(d["right_span"] for d in self._sentences.values())
        print(f"\nRight span:           {right_span:6}")
        for c in CATEGORIES:
            print(f"   {c:<13}:           {self._sentences[c]['right_span']:6}")
       
        wrong_span = sum(d["wrong_span"] for d in self._sentences.values())
        print(f"\nWrong span:           {wrong_span:6}")
        for c in CATEGORIES:
            print(f"   {c:<13}:           {self._sentences[c]['wrong_span']:6}")


def correct_spaces(tokens: List[Tuple[str, str]]) -> str:
    """ Returns a string with a reasonably correct concatenation
        of the tokens, where each token is a (tag, text) tuple. """
    return detokenize(
        Tok(TOK.PUNCTUATION if tag == "c" else TOK.WORD, txt, None)
        for tag, txt in tokens
    )


def process(fpath_and_category: Tuple[str, str],) -> Dict[str, Any]:

    """ Process a single error corpus file in TEI XML format.
        This function is called within a multiprocessing pool
        and therefore usually executes in a child process, separate
        from the parent process. It should thus not modify any
        global state, and arguments and return values should be
        picklable. """

    # Unpack arguments
    fpath, category = fpath_and_category

    # Set up XML namespace stuff
    NS = "http://www.tei-c.org/ns/1.0"
    # Length of namespace prefix to cut from tag names, including { }
    nl = len(NS) + 2
    # Namespace dictionary to be passed to ET functions
    ns = dict(ns=NS)

    # Statistics about processed sentences. These data will
    # be returned back to the parent process.
    stats: List[StatsTuple] = []
    # Counter of iceErrorCorpus error types (xtypes) encountered
    true_positives: Dict[str, int] = defaultdict(int)
    false_negatives: Dict[str, int] = defaultdict(int)

    # Accumulate standard output in a buffer, for writing in one fell
    # swoop at the end (after acquiring the output lock)
    buffer: List[str] = []

    def bprint(s: str):
        """ Buffered print: accumulate output for printing at the end """
        buffer.append(s)

    try:

        if not QUIET:
            # Output a file header
            bprint("-" * 64)
            bprint(f"File: {fpath}")
            bprint("-" * 64)
        # Parse the XML file into a tree
        try:
            tree = ET.parse(fpath)
        except ET.ParseError as e:
            if QUIET:
                bprint(f"000: *** Unable to parse XML file {fpath} ***")
            else:
                bprint(f"000: *** Unable to parse XML file ***")
            raise e
        # Obtain the root of the XML tree
        root = tree.getroot()
        # Iterate through the sentences in the file
        for sent in root.findall("ns:text/ns:body/ns:p/ns:s", ns):
            # Sentence identifier (index)
            index = sent.attrib.get("n", "")
            tokens: List[Tuple[str, str]] = []
            errors: List[ErrorDict] = []
            # A dictionary of errors by their index (idx field)
            error_indexes: Dict[str, ErrorDict] = {}
            dependencies: List[Tuple[str, ErrorDict]] = []
            # Enumerate through the tokens in the sentence
            for el in sent:
                tag = el.tag[nl:]
                if tag == "revision":
                    # An error annotation starts here, eventually
                    # spanning multiple tokens
                    original = ""
                    corrected = ""
                    # Note the index of the starting token within the span
                    start = len(tokens)
                    # Revision id
                    rev_id = el.attrib["id"]
                    # Look at the original text
                    el_orig = el.find("ns:original", ns)
                    if el_orig is not None:
                        # We have 0 or more original tokens embedded within the revision tag
                        orig_tokens = [
                            (subel.tag[nl:], element_text(subel)) for subel in el_orig
                        ]
                        tokens.extend(orig_tokens)
                        original = " ".join(t[1] for t in orig_tokens).strip()
                    # Calculate the index of the ending token within the span
                    end = max(start, len(tokens) - 1)
                    # Look at the corrected text
                    el_corr = el.find("ns:corrected", ns)
                    if el_corr is not None:
                        corr_tokens = [element_text(subel) for subel in el_corr]
                        corrected = " ".join(corr_tokens).strip()
                    # Accumulate the annotations (errors)
                    for el_err in el.findall("ns:errors/ns:error", ns):
                        attr = el_err.attrib
                        # Collect relevant information into a dict
                        xtype: str = attr["xtype"].lower()
                        error: ErrorDict = dict(
                            start=start,
                            end=end,
                            rev_id=rev_id,
                            xtype=xtype,
                            in_scope=xtype not in OUT_OF_SCOPE,
                            eid=attr.get("eid", ""),
                            original=original,
                            corrected=corrected,
                        )
                        errors.append(error)
                        # Temporarily index errors by the idx field
                        idx = attr.get("idx")
                        if idx:
                            error_indexes[idx] = error
                        # Accumulate dependencies that need to be "fixed up",
                        # i.e. errors that depend on and refer to other errors
                        # within the sentence
                        if xtype == "dep":
                            dep_id = attr.get("depId")
                            if dep_id:
                                # Note the fact that this error depends on the
                                # error with idx=dep_id
                                dependencies.append((dep_id, error))
                            else:
                                if QUIET:
                                    bprint(f"In file {fpath}:")
                                bprint(
                                    f"\n{index}: *** 'depId' attribute missing for dependency ***"
                                )
                else:
                    tokens.append((tag, element_text(el)))
            # Fix up the dependencies, if any
            for dep_id, error in dependencies:
                if dep_id not in error_indexes:
                    if QUIET:
                        bprint(f"In file {fpath}:")
                    bprint(f"\n{index}: *** No error has idx='{dep_id}' ***")
                else:
                    # Copy the in_scope attribute from the original error
                    error["in_scope"] = error_indexes[dep_id]["in_scope"]
            # Reconstruct the original sentence
            text = correct_spaces(tokens)
            if not text:
                # Nothing to do: drop this and go to the next sentence
                continue
            # Pass it to GreynirCorrect
            pg = [list(p) for p in gc.check(text)]
            s: Optional[_Sentence] = None
            if len(pg) >= 1 and len(pg[0]) >= 1:
                s = pg[0][0]
            if len(pg) > 1 or (len(pg) == 1 and len(pg[0]) > 1):
                if QUIET:
                    bprint(f"In file {fpath}:")
                bprint(f"\n{index}: *** Input contains more than one sentence *** {text}")
            if s is None:
                if QUIET:
                    bprint(f"In file {fpath}:")
                bprint(f"\n{index}: *** No parse for sentence *** {text}")
                continue
            if not QUIET:
                # Output the original sentence
                bprint(f"\n{index}: {text}")
            if not index:
                if QUIET:
                    bprint(f"In file {fpath}:")
                bprint("000: *** Sentence identifier is missing ('n' attribute) ***")
            gc_error = False
            ice_error = False
            # Output GreynirCorrect annotations
            for ann in s.annotations:
                if ann.is_error:
                    gc_error = True
                if not QUIET:
                    bprint(f">>> {ann}")
            # Output iceErrorCorpus annotations
            xtypes: Dict[str, int] = defaultdict(int)
            for err in errors:
                asterisk = "*"
                xtype = cast(str, err["xtype"])
                if err["in_scope"]:
                    # This is an in-scope error
                    asterisk = ""
                    ice_error = True
                    # Count the errors of each xtype
                    if xtype != "dep":
                        xtypes[xtype] += 1
                if not QUIET:
                    bprint(f"<<< {err['start']:03}-{err['end']:03}: {asterisk}{xtype}")
            if not QUIET:
                # Output true/false positive/negative result
                if ice_error and gc_error:
                    bprint("=++ True positive")
                    for xtype in xtypes:
                        true_positives[xtype] += 1
                elif not ice_error and not gc_error:
                    bprint("=-- True negative")
                elif ice_error and not gc_error:
                    bprint("!-- False negative")
                    for xtype in xtypes:
                        false_negatives[xtype] += 1
                else:
                    assert gc_error and not ice_error
                    bprint("!++ False positive")
            # print(" ".join(tokens))
            # for gg in s.annotations:
            #     print(gg)
            # for ii in errors:
            #     print(ii)
            # print("===========Úrvinnsla===========")
            tp, tn, fp, fn = 0, 0, 0, 0
            right_corr, wrong_corr = 0, 0
            right_span, wrong_span = 0, 0
            if ice_error and gc_error:
                gcoutput = iter(x for x in s.annotations)
                iecoutput = iter(y for y in errors if y["in_scope"])
                # Use a kind of a merging algorithm for comparing the errors
                x = next(gcoutput)
                y = next(iecoutput)
                while True:
                    # print("Ber saman:\n\t{}\n\t{}".format(x, y))
                    if x.start == y["start"]:  
                        # Errors start in same place
                        # Can check for same span
                        # and same correction
                        # print("\tByrja á sama stað")
                        tp += 1
                        if x.end == y["end"]:
                            # Found exact same span
                            # Can check for same correction
                            right_span +=1
                            if x.suggest == y["correction"]:
                                # print("\tFann allt eins!")
                                right_corr +=1
                                # TODO Tékka hér hvort er bara viðvörun, x.is_warning()
                                # Ákveða hvernig það spilar inn í niðurstöðurnar
                            else:
                                # print("\tRöng leiðrétting en allt annað rétt")
                                wrong_corr +=1
                            # print("\tFann sömu spönn")
                        else:
                            # Found error with wrong span
                            wrong_span +=1
                        x = next(gcoutput)
                        y = next(iecoutput)
                        continue
                    elif x.start < y["start"]:
                        # Found error not found in gold standard
                        # print("\tFann FP")
                        fp +=1
                        x = next(gcoutput)
                        continue
                    elif x.start > y["start"]:
                        # Didn't find error present in gold standard
                        #print("\tFann FN")
                        fn +=1
                        y = next(iecoutput)
                    else:
                        print("\tHvað gerist hér???")
                # TODO vinna úr rest af listum ef eitthvað er eftir. Get tékkað á lengdinni í upphafi?
            elif ice_error:
                # Only errors in gold standard
                for each in errors:
                    if each["in_scope"]:
                        #print(each)
                        fn +=1
                        #print("\tFann FN")
            elif gc_error:
                # Only errors in output
                for each in s.annotations:
                    #print(each)
                    fp +=1
                    #print("\tFann FP")
            else:
                # Nothing found
                pass
            # TODO Finna fágaðri lausn, sem tekur tillit til villuspana.
            tn = len(tokens)-fp-fn-tp
            # Collect statistics into the stats list, to be returned
            # to the parent process
            # TODO Bæta við stats sem skila
            if stats is not None:
                stats.append((category, len(tokens), ice_error, gc_error, tp, tn, fp, fn, right_corr, wrong_corr, right_span, wrong_span))

    except ET.ParseError:
        # Already handled the exception: exit as gracefully as possible
        pass

    finally:
        # Print the accumulated output before exiting
        with OUTPUT_LOCK:
            for s in buffer:
                print(s)
            if not QUIET:
                print("", flush=True)

    # This return value will be pickled and sent back to the parent process
    #TODO uppfæra þetta
    return dict(
        stats=stats, true_positives=true_positives, false_negatives=false_negatives
    )


def main() -> None:
    """ Main program """
    # Parse the command line arguments
    args = parser.parse_args()

    # For a measurement run on the test corpus, the default is
    # quiet operation. We store the flag in a global variable
    # that is accessible to child processes.
    global QUIET
    QUIET = args.measure

    # Overriding flags
    if args.verbose is not None:
        QUIET = False
    # --quiet has precedence over --verbose
    if args.quiet is not None:
        QUIET = True

    # Maximum number of files to process (0=all files)
    max_count = args.number
    # Initialize the statistics collector
    stats = Stats()
    # The glob path of the XML files to process
    path = args.path
    # When running measurements only, we use _TEST_PATH as the default,
    # otherwise _DEV_PATH
    if path is None:
        path = _TEST_PATH if args.measure else _DEV_PATH

    def gen_files() -> Iterable[Tuple[str, str]]:
        """ Generate tuples with the file paths and categories
            to be processed by the multiprocessing pool """
        count = 0
        it: Iterable[str]
        if args.randomize and max_count > 0:
            # Randomizing only makes sense if there is a max count as well
            it = glob.glob(path, recursive=True)
            it = random.sample(it, max_count)
        else:
            it = glob.iglob(path, recursive=True)
        for fpath in it:
            # Find out which category the file belongs to by
            # inference from the file name
            for category in CATEGORIES:
                if category in fpath:
                    break
            else:
                assert (
                    False
                ), f"File path does not contain a recognized category: {fpath}"
            # Add the file to the statistics under its category
            stats.add_file(category)
            # Yield the file information to the multiprocessing pool
            yield fpath, category
            count += 1
            # If there is a limit on the number of processed files,
            # and we're done, stop the generator
            if max_count > 0 and count >= max_count:
                break

    # Use a multiprocessing pool to process the articles
    with multiprocessing.Pool(processes=args.cores) as pool:
        # Iterate through the TEI XML files in turn and call the process()
        # function on each file, in a child process within the pool
        for result in pool.imap_unordered(process, gen_files()):
            # Results come back as a dict of arguments that
            # we pass to Stats.add_result()
            stats.add_result(**result)
        # Done: close the pool in an orderly manner
        pool.close()
        pool.join()

    # Finally, acquire the output lock and write the final statistics
    with OUTPUT_LOCK:
        stats.output(cores=args.cores or os.cpu_count() or 1)
        print("", flush=True)


if __name__ == "__main__":
    main()
