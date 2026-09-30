import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.metrics.features import extract_features
from trio.metrics.tokenize import tokenize

LOCK = SimpleNamespace(language="en")


def doc(text):
    return tokenize(text, LOCK)


def test_empty_document_has_safe_zero_denominators():
    vector = extract_features(doc(""), [])
    assert vector.word_count == 0
    assert vector.mean_word_length == vector.words_per_sentence == 0
    assert vector.punctuation_per_100 == vector.mattr == 0
    assert vector.ngram_repetition == vector.reference_rate == 0
    assert set(vector.lexicon_rates.values()) == {0}


def test_lengths_punctuation_pronouns_negation_and_lexicons():
    vector = extract_features(
        doc("I understand your argument. I disagree because it is not clear!"), []
    )
    assert vector.word_count == 11
    assert vector.words_per_sentence == 5.5
    assert vector.punctuation_per_100 == 200 / 11
    assert vector.first_person_rate == 200 / 11
    assert vector.negation_rate == 100 / 11
    assert vector.reference_rate == 100 / 11
    assert vector.lexicon_rates["affiliation"] == 200 / 11
    assert vector.lexicon_rates["disagreement"] == 100 / 11
    assert vector.lexicon_rates["causal"] == 100 / 11


def test_mattr_and_ngram_repetition_use_previous_two_docs():
    current = doc("one two three four one")
    previous = [doc("ignored one two"), doc("one two nine"), doc("three four ten")]
    vector = extract_features(current, previous)
    assert vector.mattr == 0.8
    assert vector.ngram_repetition == 0.25


def test_identical_inputs_produce_identical_vector():
    current = doc("Imagine this is like your earlier point.")
    prior = [doc("your earlier point was clear")]
    assert extract_features(current, prior) == extract_features(current, prior)
    russian = extract_features(doc("Я не согласен, потому что это неверно."), [])
    assert russian.lexicon_rates["disagreement"] > 0
    assert russian.lexicon_rates["causal"] > 0
