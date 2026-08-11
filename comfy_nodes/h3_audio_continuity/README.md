# MiniMax H3 Audio Continuity

`H3AudioContinuityMaster` joins two native H3 audio decodes at a frame-accurate
video boundary. It keeps the model's native sample rate, removes segment DC,
trims the duplicated anchor interval, applies a short click-safe boundary fade,
uses conservative RMS gain with peak protection, and returns an exact-duration
audio tensor plus diagnostics.

`H3AudioSequenceMaster` applies the same frame-grid contract to one through six
short H3 segments. It is used by H3 Flow so 10/15/30-second outputs can retain
native synchronized audio while keeping every video decode at the verified
124-frame safety size. Gain and peak protection are applied once to the final
sequence rather than repeatedly at every join.

The node does not synthesize missing bandwidth and does not claim that
resampling improves quality.
