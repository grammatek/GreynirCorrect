
.. image:: https://img.shields.io/badge/License-MIT-yellow.svg
    :target: https://opensource.org/licenses/MIT
.. image:: https://img.shields.io/badge/python-3.6-blue.svg
    :target: https://www.python.org/downloads/release/python-360/
.. image:: https://github.com/mideind/GreynirCorrect/workflows/Python%20package/badge.svg?branch=master
    :target: https://github.com/mideind/GreynirCorrect/actions?query=workflow%3A%22Python+package%22

====================================================================================
GreynirCorrect4LT: Spelling and grammar correction for Icelandic Language Technology
====================================================================================
This is a slightly adapted version of `Miðeind's GreynirCorrect <https://github.com/mideind/GreynirCorrect>`__, from which this repository is forked.

This version is implemented for use in a text-to-speech text pre-processing pipeline, but the documentation below shows some access points for a quick adaptation to other use cases in language technology applications.

.. _overview:

********
Overview
********

**GreynirCorrect** is a Python 3 (>= 3.6) package and command line tool for
**checking and correcting spelling and grammar** in Icelandic text.

GreynirCorrect relies on the `Greynir <https://pypi.org/project/reynir/>`__ package,
by the same authors, to tokenize and parse text.

GreynirCorrect is documented in detail `here <https://yfirlestur.is/doc/>`__.

For the instructions on how to use GreynirCorrect as is, please consult the original `repository <https://github.com/mideind/GreynirCorrect>`__

Getting started
----------------------

To try out GreynirCorrect for your use case, a good place to start is to create your own API script in ``src/reynir_correct/tools/``. For examples, see the existing scripts ``diffchecker.py`` and ``tts_frontend.py``. This of course only applies if you plan to change the core code base, otherwise you should use GreynirCorrect or GreynirCorrect4LT as a library.

The correction pipeline
-----------------------

GreynirCorrect relies heavily on the `Greynir <https://pypi.org/project/reynir/>`__ package, and a lot of "magic" happens under the hood, not directly accessible from GreynirCorrect. The tokenizing process also performs corrections along the way, and essentially three tokenizers work together in GreynirCorrect:

`tokenizer.py from Tokenizer <https://github.com/mideind/Tokenizer/blob/master/src/tokenizer/tokenizer.py>`__

`bintokenizer.py from GreynirPackage <https://github.com/mideind/GreynirPackage/blob/master/src/reynir/bintokenizer.py>`__

``errtokenizer.py`` from GreynirCorrect: ``src/reynir_correct/errtokenizer.py``

Since we cannot - and should not - interfere with the tokenizers from Tokenizer and GreynirPackage, we use ``errtokenizer`` to override processes as needed. A spell correction pipeline is defined in ``bintokenizer`` as ``class DefaultPipeline``.  Familiarize yourself with this pipeline to get an overview of how GreynirCorrect works.

The *DefaultPipeline* is overridden as ``class CorrectionPipeline`` in ``errtokenizer.py``. Here, we have the possibility to override PhaseFunctions defined in the ``DefaultPipeline`` to change the default tokenizing/correcting process. In the default implementation of GreynirCorret, the pipeline in ``CorrectionPipeline`` looks like this (remember: ``DefaultPipeline`` is defined in ``bintokenizer.py`` in GreynirPackage, the ``CorrectionPipeline`` in ``errtokenizer.py``):

.. code-block:: python

   DefaultPipeline.tokenize_without_annotation  # core function: tokenizer.tokenize()
   CorrectionPipeline.correct_tokens            # core function: errtokenizer.parse_errors()
   DefaultPipeline.parse_static_phrases         # core function: bintokenizer.StaticPhraseStream.process()
   DefaultPipeline.annotate                     # core function: bintokenizer.annotate()
   DefaultPipeline.recognize_entities           # not implemented
   CorrectionPipeline.check_spelling            # core function: CorrectionPipeline.check_spelling()
   DefaultPipeline.parse_phrases_1              # core function: bintokenizer.parse_phrases_1()
   DefaultPipeline.parse_phrases_2              # core function: bintokenizer.parse_phrases_2()
   DefaultPipeline.parse_phrases_3              # core function: bintokenizer.parse_phrases_3()
   DefaultPipeline.fix_abbreviations            # core function: bintokenizer.fix_abbreviations()
   DefaultPipeline.disambiguate_phrases         # core function: bintokenizer.DisambiguationStream.process()
   CorrectionPipeline.final_correct             # core function: CorrectionPipeline.final_correct()


To change the tokenization itself, i.e. to change the way the input text is split up into tokens, we need to override the first PhaseFunction and change ``DefaultPipeline.tokenize_without_annotation`` to ``CorrectionPipeline.tokenize_without_annotation``. In the current 4LT-implementation, tokens starting with ``<`` are not split up as happens in the original tokenizer. For example, the original tokenizer would split ``<sil>`` into ``< sil >``, making the token ``sil`` an object for correction to ``til``. The text-to-speech (TTS) pipeline relies on all tags being kept as is at this stage, in previous analysis steps for example SSML-tags for the TTS system might have been added.


Adding word lists
-----------------

GreynirCorrect uses different word lists and maps to assist with spell checking and correction. For LT-applications we might want to add our own lists of words that need special treatment during the process. In case of the TTS frontend pipeline, we add a list of lemmas that represent words that are a typical output of a text normalization system for TTS. The normalization system expands abbreviations and replaces digits with their written-out forms, e.g. ``5`` becomes ``five`` in a TTS-normalized text. In Icelandic, many of these words are inflected and while the normalizer has certain means to determine the correct case, gender and number of an expanded word, it does make errors. To increase the possibility of a correct form, we attach all possible forms to these words, should they occur in the input, and let the parser in GreynirPackage choose the most likeliy PoS tags for the token. In a post-processing step we can then correct the token according to the PoS tags.

To add a new word list or word information file, you should add it to ``reynir_correct/config/``. There you can see the files GreynirCorrect already uses. To read a word information file on initialization and to be able to use an object containing this information, you need to edit two files: ``reynir_correct/config/GreynirCorrect.conf`` and ``reynir_correct/settings.py``. 

``GreynirCorrect.conf`` does also contain several word lists, but for additional data it is better to create separate files. To tell GreynirCorrect to read your data on initialization, define the data structure you want to use (set, map, ...) in the ``settings`` file, add a corresponding handling method, and add an entry to ``CONFIG_HANDLERS`` in ``settings.read()``. In ``GreynirCorrect.conf``, add an include statement at the end of the file, see ``tts_normalizer_words`` as an example.


Adding or changing functionality
--------------------------------

To change or add functionality of GreynirCorrect, you most likely will edit, override, or add functions to ``errtokenizer.py``. Study the CorrectionPipeline to find the best fitting access point for your adaptation. Also, make sure to import your data from settings, as described in the previous section, if you have added any extra word information data. To see how functionality may be added, study ``errtokenizer.check_normalized_words()``. 


.. _prerequisites:

*************
Prerequisites
*************

GreynirCorrect runs on CPython 3.6 or newer, and on PyPy 3.6 or newer. It has
been tested on Linux, macOS and Windows. The
`PyPi package <https://pypi.org/project/reynir-correct/>`_
includes binary wheels for common environments, but if the setup on your OS
requires compilation from sources, you may need

.. code-block:: bash

   $ sudo apt-get install python3-dev

...or something to similar effect to enable this.

.. _installation:

************
Installation
************

To install this package (assuming you have Python >= 3.6 with ``pip`` installed):

.. code-block:: bash

   $ pip install reynir-correct

If you want to be able to edit the source, do like so
(assuming you have ``git`` installed):

.. code-block:: bash

   $ git clone https://github.com/mideind/GreynirCorrect
   $ cd GreynirCorrect
   $ # [ Activate your virtualenv here if you have one ]
   $ pip install -e .

The package source code is now in ``GreynirCorrect/src/reynir_correct``.

.. _commandline:

*********************
The command line tool
*********************

After installation, the corrector can be invoked directly from the command line:

.. code-block:: bash

   $ correct input.txt output.txt

...or:

.. code-block:: bash

   $ echo "Þinngið samþikkti tilöguna" | correct
   Þingið samþykkti tillöguna

Input and output files are encoded in UTF-8. If the files are not
given explicitly, ``stdin`` and ``stdout`` are used for input and output,
respectively.

Empty lines in the input are treated as sentence boundaries.

By default, the output consists of one sentence per line, where each
line ends with a single newline character (ASCII LF, ``chr(10)``, ``"\n"``).
Within each line, tokens are separated by spaces.

The following (mutually exclusive) options can be specified
on the command line:

+-------------------+---------------------------------------------------+
| | ``--csv``       | Output token objects in CSV                       |
|                   | format, one per line. Sentences are separated by  |
|                   | lines containing ``0,"",""``                      |
+-------------------+---------------------------------------------------+
| | ``--json``      | Output token objects in JSON format, one per line.|
+-------------------+---------------------------------------------------+
| | ``--normalize`` | Normalize punctuation, causing e.g. quotes to be  |
|                   | output in Icelandic form and hyphens to be        |
|                   | regularized.                                      |
+-------------------+---------------------------------------------------+
| | ``--grammar``   | Output whole-sentence annotations, including      |
|                   | corrections and suggestions for spelling and      |
|                   | grammar. Each sentence in the input is output as  |
|                   | a text line containing a JSON object, terminated  |
|                   | by a newline.                                     |
+-------------------+---------------------------------------------------+

The CSV and JSON formats of token objects are identical to those documented
for the `Tokenizer package <https://github.com/mideind/Tokenizer>`__.

The JSON format of whole-sentence annotations is identical to the one documented for
the `Yfirlestur.is HTTPS REST API <https://github.com/mideind/Yfirlestur#https-api>`__.

Type ``correct -h`` to get a short help message.


Command Line Examples
---------------------

.. code-block:: bash

   $ echo "Atvinuleysi jógst um 3%" | correct
   Atvinnuleysi jókst um 3%

.. code-block:: bash

   $ echo "Barnið vil grænann lit" | correct --csv
   6,"Barnið",""
   6,"vil",""
   6,"grænan",""
   6,"lit",""
   0,"",""

Note how *vil* is not corrected, as it is a valid and common word, and
the ``correct`` command does not perform grammar checking by default.

.. code-block:: bash

   $ echo "Pakkin er fyrir hestin" | correct --json
   {"k":"BEGIN SENT"}
   {"k":"WORD","t":"Pakkinn"}
   {"k":"WORD","t":"er"}
   {"k":"WORD","t":"fyrir"}
   {"k":"WORD","t":"hestinn"}
   {"k":"END SENT"}

To perform whole-sentence grammar checking and annotation as well as spell checking,
use the ``--grammar`` option:

.. code-block:: bash

   $ echo "Ég kláraði verkefnið þrátt fyrir að ég var þreittur." | correct --grammar
      {
         "original":"Ég kláraði verkefnið þrátt fyrir að ég var þreittur.",
         "corrected":"Ég kláraði verkefnið þrátt fyrir að ég var þreyttur.",
         "tokens":[
            {"k":6,"x":"Ég","o":"Ég"},
            {"k":6,"x":"kláraði","o":" kláraði"},
            {"k":6,"x":"verkefnið","o":" verkefnið"},
            {"k":6,"x":"þrátt fyrir","o":" þrátt fyrir"},
            {"k":6,"x":"að","o":" að"},
            {"k":6,"x":"ég","o":" ég"},
            {"k":6,"x":"var","o":" var"},
            {"k":6,"x":"þreyttur","o":" þreittur"},
            {"k":1,"x":".","o":"."}
         ],
         "annotations":[
            {
               "start":6,
               "end":6,
               "start_char":35,
               "end_char":37,
               "code":"P_MOOD_ACK",
               "text":"Hér er réttara að nota viðtengingarhátt
                  sagnarinnar 'vera', þ.e. 'væri'.",
               "detail":"Í viðurkenningarsetningum á borð við 'Z'
                  í dæminu 'X gerði Y þrátt fyrir að Z' á sögnin að vera
                  í viðtengingarhætti fremur en framsöguhætti.",
               "suggest":"væri"
            },
            {
               "start":7,
               "end":7,
               "start_char":38,
               "end_char":41,
               "code":"S004",
               "text":"Orðið 'þreittur' var leiðrétt í 'þreyttur'",
               "detail":"",
               "suggest":"þreyttur"
            }
         ]
      }

The output has been formatted for legibility - each input sentence is actually
represented by a JSON object in a single line of text, terminated by newline.

Note that the ``corrected`` field only includes token-level spelling correction
(in this case *þreittur* ``->`` *þreyttur*), but no grammar corrections.
The grammar corrections are found in the ``annotations`` list.
To apply corrections and suggestions from the annotations,
replace source text or tokens (as identified by the ``start`` and ``end``,
or ``start_char`` and ``end_char`` properties) with the ``suggest`` field, if present.

.. _tests:

*****
Tests
*****

To run the built-in tests, install `pytest <https://docs.pytest.org/en/latest/>`_,
``cd`` to your ``GreynirCorrect`` subdirectory (and optionally activate your
virtualenv), then run:

.. code-block:: bash

   $ python -m pytest

****************
Acknowledgements
****************

Parts of this software are developed under the auspices of the
Icelandic Government's 5-year Language Technology Programme for Icelandic,
which is managed by Almannarómur and described
`here <https://www.stjornarradid.is/lisalib/getfile.aspx?itemid=56f6368e-54f0-11e7-941a-005056bc530c>`__
(English version `here <https://clarin.is/media/uploads/mlt-en.pdf>`__).

.. _license:

*********************
Copyright and License
*********************

.. image:: https://github.com/mideind/GreynirPackage/raw/master/doc/_static/MideindLogoVert100.png?raw=true
   :target: https://mideind.is
   :align: right
   :alt: Miðeind ehf.

**Copyright © 2021 Miðeind ehf.**

GreynirCorrect's original author is *Vilhjálmur Þorsteinsson*.

This software is licensed under the *MIT License*:

   *Permission is hereby granted, free of charge, to any person
   obtaining a copy of this software and associated documentation
   files (the "Software"), to deal in the Software without restriction,
   including without limitation the rights to use, copy, modify, merge,
   publish, distribute, sublicense, and/or sell copies of the Software,
   and to permit persons to whom the Software is furnished to do so,
   subject to the following conditions:*

   *The above copyright notice and this permission notice shall be
   included in all copies or substantial portions of the Software.*

   *THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
   EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
   MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
   IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
   CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
   TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
   SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.*

----

GreynirCorrect indirectly embeds the `Database of Icelandic Morphology <https://bin.arnastofnun.is>`_
(`Beygingarlýsing íslensks nútímamáls <https://bin.arnastofnun.is>`_), abbreviated BÍN,
along with directly using `Ritmyndir <https://bin.arnastofnun.is/DMII/LTdata/comp-format/nonstand-form/>`, a collection of non-standard word forms.
Miðeind does not claim any endorsement by the BÍN authors or copyright holders.

The BÍN source data are publicly available under the
`CC BY-SA 4.0 license <https://creativecommons.org/licenses/by-sa/4.0/>`_, as further
detailed `here in English <https://bin.arnastofnun.is/DMII/LTdata/conditions/>`_
and `here in Icelandic <https://bin.arnastofnun.is/gogn/mimisbrunnur/>`_.

In accordance with the BÍN license terms, credit is hereby given as follows:

*Beygingarlýsing íslensks nútímamáls. Stofnun Árna Magnússonar í íslenskum fræðum.*
*Höfundur og ritstjóri Kristín Bjarnadóttir.*

**GreynirCorrect4LT** is implemented and maintained by Grammatek ehf. as a part of Icelandic Government's 5-year Language Technology Programme for Icelandic. 
