# React HIR frontend experiment

This workspace member is an executable path toward parsing JavaScript/JSX
directly into the semantic structures needed by React HIR.

The implemented pipeline is:

1. `dsl.coil` compiles target-neutral S-expression byte classes to generic
   `coil.simd` classifiers.
2. `structural.coil` produces width-independent scalar bitmaps.
3. `lexical.coil` uses SIMD to build a bitmap of state-changing bytes, visits
   only those sparse events, and assigns the ordinary spans between them in one
   operation. It carries quote, escape, line-comment, and block-comment state
   across chunks. A retained scalar implementation is the differential oracle;
   a one-byte overlap resolves comment openers at boundaries.
4. `frontend.coil` shields structural events inside strings and comments.
5. `tape.coil` stably compacts visible events into caller-owned position/kind
   arrays without imposing an allocation strategy.

All bitmap-producing entry points accept an explicit valid byte count. SIMD
tail fill bytes therefore cannot appear as source events. Tape writes report
unconsumed bits when the destination capacity is exhausted.

The lexical state machine currently treats an entire template literal as string
content. Template `${...}` transitions, regular-expression literal recognition,
Unicode identifier semantics, and the grammar/scope/HIR stages remain to be
implemented. Those require parser context and should not be guessed by the byte
classifier.
