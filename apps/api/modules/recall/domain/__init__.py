"""
Pure recall domain (F-15): no Django, no I/O, no clock. Everything here is a function of its arguments, so the same
inputs give the same outputs in Python and in the TypeScript twin (`apps/web/src/modules/recall/lib`). The shared golden
vectors in `tests/vectors/` are the contract between the two.
"""
