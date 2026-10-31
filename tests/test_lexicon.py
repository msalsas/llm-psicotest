import collections
import re
import unittest

import _bootstrap
import gen_corpus

from psicotest.checkers import text as checkers_text
from psicotest.checkers.rules import PLURAL_EXCEPTIONS, singular_candidates
from psicotest.checkers.schema import LABEL_RE
from psicotest.generators import contains_animal, lexicon, trigger_animal
from psicotest.rng import Rng, derive_seed
from psicotest.spec import ANIMAL_RE

NAME_SHAPE = re.compile(r"^[A-Z][a-z]{2,7}$")
WORD_SHAPE = re.compile(r"^[a-z]{3,10}$")
ROLE_WORDS = ("knight", "knights", "knave", "knaves", "spy", "spies")
EXCEPTIONS = {
    "bison": "bison",
    "deer": "deer",
    "feet": "foot",
    "fish": "fish",
    "geese": "goose",
    "lice": "louse",
    "mice": "mouse",
    "moose": "moose",
    "octopi": "octopus",
    "oxen": "ox",
    "salmon": "salmon",
    "sheep": "sheep",
    "teeth": "tooth",
}


def lemmatizes_to_animal(word):
    animals = set(lexicon.ANIMAL_WORDS) | set(lexicon.ANIMAL_STOP_WORDS)
    return bool(set(singular_candidates(word)) & animals)


class TestLexicon(unittest.TestCase):
    def test_trigger_animals(self):
        nouns = tuple(n for n, _ in lexicon.TRIGGER_ANIMALS)
        self.assertEqual(nouns, ("sheep", "cat", "mouse", "fish"))
        for noun, article in lexicon.TRIGGER_ANIMALS:
            self.assertEqual(article, "a")
            self.assertIsNotNone(ANIMAL_RE.match(noun))
            self.assertIn(noun, lexicon.ANIMAL_WORDS)

    def test_r3_lexicon_plurals(self):
        pairs = (("sheep", "sheep"), ("cat", "cats"), ("mouse", "mice"), ("fish", "fish"))
        for noun, form in (*pairs, ("fish", "fishes")):
            self.assertIn(noun, singular_candidates(form))
            self.assertEqual(contains_animal(form), (form,))
        self.assertEqual(PLURAL_EXCEPTIONS, EXCEPTIONS)
        self.assertEqual(len(PLURAL_EXCEPTIONS), 13)

    def test_animal_words_shape(self):
        self.assertIs(lexicon.ANIMAL_WORDS, checkers_text.ANIMAL_WORDS)
        self.assertIs(lexicon.ANIMAL_STOP_WORDS, checkers_text.ANIMAL_STOP_WORDS)
        self.assertEqual(len(lexicon.ANIMAL_WORDS), 84)
        self.assertEqual(len(lexicon.ANIMAL_STOP_WORDS), 20)
        for table in (lexicon.ANIMAL_WORDS, lexicon.ANIMAL_STOP_WORDS):
            self.assertEqual(list(table), sorted(set(table)))
        self.assertNotIn("animal", lexicon.ANIMAL_WORDS)
        self.assertFalse(hasattr(lexicon, "ANIMAL_BASE"))

    def test_contains_animal(self):
        self.assertEqual(contains_animal("A cat and two sheep."), ("cat", "sheep"))
        self.assertEqual(contains_animal("Three mice."), ("mice",))
        found = contains_animal("Mr. Fox speaks.")
        self.assertIn("fox", found)
        self.assertIn("phrase:mr fox", found)
        self.assertEqual(contains_animal("Cats"), ("cats",))
        self.assertEqual(contains_animal("A duck."), ("stop:duck",))
        self.assertEqual(contains_animal("animal"), ())
        self.assertEqual(contains_animal("category"), ())

    def test_names_clean(self):
        pool = lexicon.NAME_POOL
        self.assertIs(pool, checkers_text.NAME_POOL)
        self.assertEqual(len(pool), 40)
        self.assertEqual(len({checkers_text.fold(n) for n in pool}), 40)
        folded = [checkers_text.fold(n) for n in pool]
        for name in pool:
            self.assertIsNotNone(NAME_SHAPE.match(name))
            self.assertFalse(lemmatizes_to_animal(name))
            self.assertNotIn(checkers_text.fold(name), checkers_text.NUMBER_WORDS)
            self.assertNotIn(checkers_text.fold(name), (*ROLE_WORDS, "and", "or"))
        initials = collections.Counter(f[0] for f in folded)
        self.assertEqual(len(initials), 20)
        self.assertEqual(set(initials.values()), {2})

    def test_cnt_words_clean(self):
        pool = lexicon.CNT_WORDS
        self.assertIs(pool, checkers_text.CNT_WORDS)
        self.assertEqual(len(pool), 320)
        self.assertEqual(len(set(pool)), 320)
        number_words = set(checkers_text.NUMBER_WORDS)
        names = {checkers_text.fold(n) for n in checkers_text.NAME_POOL}
        other = set(lexicon.ANIMAL_WORDS) | set(lexicon.ANIMAL_STOP_WORDS) | number_words | names
        for word in pool:
            self.assertIsNotNone(WORD_SHAPE.match(word))
            self.assertNotIn(word, other)
            self.assertFalse(lemmatizes_to_animal(word))

    def test_label_pool(self):
        pool = lexicon.LABEL_POOL
        self.assertIs(pool, checkers_text.LABEL_POOL)
        self.assertEqual(len(set(pool)), 16)
        for letter in pool:
            self.assertIsNotNone(LABEL_RE.fullmatch(letter))
            self.assertNotIn(letter, "AEIOUY")

    def test_animal_clause(self):
        for noun, _ in lexicon.TRIGGER_ANIMALS:
            templates = {t.format(art="a", noun=noun) for t in lexicon.ANIMAL_CLAUSES}
            seen = set()
            for s in range(16):
                clause = lexicon.animal_clause(noun, Rng(s))
                self.assertIn(clause, templates)
                self.assertEqual(contains_animal(clause), (noun,))
                seen.add(clause)
            self.assertEqual(seen, templates)
        with self.assertRaises(ValueError):
            lexicon.animal_clause("cow", Rng(1))

    def test_trigger_animal_derivation(self):
        seed = derive_seed("psicotest", "v2", 10001, "A", 17, "animal")
        expected = lexicon.TRIGGER_ANIMALS[seed % 4][0]
        self.assertEqual(trigger_animal("v2", 10001, "A", 17), expected)
        trigger_animal("v2", 10002, "B", 29)
        self.assertEqual(trigger_animal("v2", 10001, "A", 17), expected)

    def test_stop_phrases_never_generated(self):
        for generator in gen_corpus.CAP_GENS:
            for item in gen_corpus.corpus(generator, 0)[:100]:
                for hit in contains_animal(item.prompt_en):
                    self.assertFalse(hit.startswith(("phrase:", "stop:")), msg=item.item_id)


if __name__ == "__main__":
    unittest.main()
