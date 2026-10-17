"""
Pure parsers that turn text and tables extracted from the Institute's PDFs into reviewable question seeds.

Nothing in this package reads files, the network or the database. The impure part (opening PDFs) lives in
`management/commands/build_question_bank_seed.py`, so every parser here can be tested with a small text excerpt.
"""
